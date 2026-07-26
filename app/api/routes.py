from datetime import date
import calendar
import re
from pathlib import Path
from types import SimpleNamespace
import logging
import json
import os
import subprocess
import time

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy import case, func, or_, select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.time import utcnow
from app.db.session import SessionLocal
from app.services.plaid_client import PlaidClient
from app.models.models import (
    Account,
    AccountBalanceSnapshot,
    AnnotationFingerprint,
    CategoryDecisionEvent,
    CategoryRule,
    ConnectSession,
    Item,
    RecurringOverride,
    SyncRun,
    SyncState,
    Transaction,
    TransactionAnnotation,
    TransferPair,
)
from app.schemas.plaid import (
    BatchPatchAnnotationRequest,
    CategoryRuleApplyRequest,
    CategoryRuleCreateRequest,
    CategoryRulePatchRequest,
    CategoryRulePreviewRequest,
    CategoryRuleRecomputeRequest,
    ConnectCompleteRequest,
    CreateConnectSessionRequest,
    PatchAccountRequest,
    PatchAnnotationRequest,
    RecurringStatusRequest,
    TransferCreateRequest,
)
from app.services.security import decrypt_token, encrypt_token
from app.services.sync_service import SyncInProgressError, SyncService
from app.services.connect_service import ConnectService
from app.services import transfer_detector
from app.services.refund_detector import classify_refunds
from app.services.category_catalog import merge_catalog
from app.services.recurring_detector import detect_recurring
from app.services.search_query import (
    IS_VALUES,
    SEARCH_FIELDS,
    parse_query,
    suggestion_context,
)
from app.services.category_resolver import (
    PLAID_DETAILED_FRIENDLY_MAP,
    PLAID_FRIENDLY_MAP,
    compile_rules,
    find_first_matching_rule,
    resolve_effective_category,
)

router = APIRouter()
logger = logging.getLogger(__name__)

_CONNECT_TUNNEL_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "connect_funnel.sh"


def _friendly_plaid_case():
    """SQL CASE mapping raw Plaid primary -> friendly category, built from the
    shared PLAID_FRIENDLY_MAP so the API matches the effective_transactions view."""
    whens = [
        (Transaction.plaid_category_primary == plaid, friendly)
        for plaid, friendly in PLAID_FRIENDLY_MAP.items()
    ]
    detailed_whens = [
        (
            func.json_extract(
                Transaction.raw_json,
                "$.personal_finance_category.detailed",
            ) == plaid,
            friendly,
        )
        for plaid, friendly in PLAID_DETAILED_FRIENDLY_MAP.items()
    ]
    detailed_case = case(*detailed_whens, else_=None)
    return func.coalesce(
        detailed_case,
        case(*whens, else_=Transaction.plaid_category_primary),
    )


def _plaid_detailed_category_expr():
    return func.json_extract(
        Transaction.raw_json,
        "$.personal_finance_category.detailed",
    )


def _effective_category_expr():
    return func.coalesce(
        TransactionAnnotation.user_category,
        TransactionAnnotation.rule_category,
        _friendly_plaid_case(),
        "uncategorized",
    )


def _category_source_expr():
    return case(
        (TransactionAnnotation.user_category.is_not(None), "manual"),
        (TransactionAnnotation.rule_category.is_not(None), "rule"),
        (Transaction.plaid_category_primary.is_not(None), "plaid"),
        else_="default",
    )


def _effective_merchant_expr():
    return func.coalesce(
        TransactionAnnotation.merchant_name_override,
        Transaction.merchant_name,
    )


def _effective_account_name_expr():
    return func.coalesce(
        Account.nickname,
        Account.name + " ··" + Account.mask,
    )


def _run_connect_tunnel(action: str) -> None:
    if os.getenv("CONNECT_TUNNEL_AUTOMATION", "0") != "1":
        return

    strict = os.getenv("CONNECT_TUNNEL_STRICT", "1") == "1"
    try:
        proc = subprocess.run(
            [str(_CONNECT_TUNNEL_SCRIPT), action],
            cwd=str(_CONNECT_TUNNEL_SCRIPT.parent.parent),
            check=True,
            capture_output=True,
            text=True,
        )
        if proc.stdout.strip():
            logger.info("connect tunnel %s: %s", action, proc.stdout.strip())
    except Exception as e:
        if strict:
            raise RuntimeError(f"connect tunnel {action} failed: {e}") from e
        logger.warning("connect tunnel %s failed: %s", action, e)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/health")
def health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    status = "ok" if db_ok else "degraded"
    return {"status": status, "service": "vibeledger", "db": "ok" if db_ok else "unreachable"}


@router.post("/connect/sessions")
def create_connect_session(payload: CreateConnectSessionRequest, db: Session = Depends(get_db)):
    user_id = payload.user_id

    try:
        _run_connect_tunnel("open")
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    client = PlaidClient()
    link_token = client.create_link_token(user_id)["link_token"]

    session = ConnectService().create_session(db, user_id=user_id, link_token=link_token)
    connect_url = f"{settings.app_base_url}/connect/start?session={session.session_token}"
    return {
        "session_token": session.session_token,
        "expires_at": session.expires_at.isoformat(),
        "connect_url": connect_url,
    }


@router.get("/connect/start", response_class=HTMLResponse)
def connect_start(session: str, db: Session = Depends(get_db)):
    svc = ConnectService()
    active = svc.get_active_session(db, session)
    if not active:
        raise HTTPException(status_code=400, detail="invalid or expired session")

    if not active.link_token:
        client = PlaidClient()
        active.link_token = client.create_link_token(active.user_id)["link_token"]
        db.commit()

    link_token = active.link_token

    html = f"""
<!doctype html>
<html>
  <head><title>VibeLedger Connect</title></head>
  <body>
    <h3>Connect your account to VibeLedger</h3>
    <button id='link-button'>Connect with Plaid</button>
    <script src='https://cdn.plaid.com/link/v2/stable/link-initialize.js'></script>
    <script>
      const sessionToken = {json.dumps(session)};
      const handler = Plaid.create({{
        token: {json.dumps(link_token)},
        onSuccess: async (public_token, metadata) => {{
          const completePath = window.location.pathname.replace(/\\/start$/, '/complete');
          const resp = await fetch(completePath, {{
            method: 'POST',
            headers: {{ 'Content-Type': 'application/json' }},
            body: JSON.stringify({{ session_token: sessionToken, public_token }})
          }});
          if (resp.ok) {{
            document.body.innerHTML = '<h3>Account connected. You can return to Discord.</h3>';
          }} else {{
            document.body.innerHTML = '<h3>Failed to connect. Please retry.</h3>';
          }}
        }}
      }});
      document.getElementById('link-button').onclick = () => handler.open();
    </script>
  </body>
</html>
"""
    return HTMLResponse(content=html)


@router.post("/connect/complete")
def connect_complete(payload: ConnectCompleteRequest, db: Session = Depends(get_db)):
    session_token = payload.session_token
    public_token = payload.public_token

    svc = ConnectService()
    active = svc.get_active_session(db, session_token)
    if not active:
        raise HTTPException(status_code=400, detail="invalid or expired session")

    client = PlaidClient()
    resp = client.exchange_public_token(public_token)

    existing = db.query(Item).filter(Item.plaid_item_id == resp["item_id"]).first()
    if not existing:
        existing = Item(
            plaid_item_id=resp["item_id"],
            access_token_encrypted=encrypt_token(resp["access_token"]),
            status="active",
        )
        db.add(existing)
    else:
        existing.access_token_encrypted = encrypt_token(resp["access_token"])
        existing.status = "active"

    active.status = "completed"
    active.plaid_item_id = resp["item_id"]
    active.completed_at = utcnow()
    db.commit()

    try:
        _run_connect_tunnel("close")
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    return {"status": "linked", "item_id": resp["item_id"]}


@router.get("/connect/sessions/{session_token}")
def connect_session_status(session_token: str, db: Session = Depends(get_db)):
    session = db.query(ConnectSession).filter(ConnectSession.session_token == session_token).first()
    if not session:
        raise HTTPException(status_code=404, detail="session not found")
    return {
        "status": session.status,
        "created_at": session.created_at.isoformat(),
        "expires_at": session.expires_at.isoformat(),
        "completed_at": session.completed_at.isoformat() if session.completed_at else None,
        "item_id": session.plaid_item_id,
    }


@router.post("/items/{item_id}/remove")
def remove_item(item_id: int, db: Session = Depends(get_db)):
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="item not found")

    try:
        access_token = decrypt_token(item.access_token_encrypted)
        PlaidClient().remove_item(access_token)
    except Exception:
        logger.exception("Plaid item_remove failed for item %d; continuing with local cleanup", item_id)

    account_ids = [a.id for a in db.query(Account.id).filter(Account.item_id == item_id)]
    txn_ids = [t.id for t in db.query(Transaction.id).filter(Transaction.item_id == item_id)]

    if txn_ids:
        db.query(TransactionAnnotation).filter(
            TransactionAnnotation.refund_match_transaction_id.in_(txn_ids)
        ).update(
            {
                TransactionAnnotation.refund_status: None,
                TransactionAnnotation.refund_match_transaction_id: None,
                TransactionAnnotation.refund_reason: None,
            },
            synchronize_session=False,
        )
        # A fingerprint still claiming one of these transactions would look
        # applied forever; see list_annotation_fingerprints.
        db.query(AnnotationFingerprint).filter(
            AnnotationFingerprint.applied_transaction_id.in_(txn_ids)
        ).update(
            {AnnotationFingerprint.applied_transaction_id: None},
            synchronize_session=False,
        )
        db.query(TransferPair).filter(
            or_(TransferPair.txn_out_id.in_(txn_ids), TransferPair.txn_in_id.in_(txn_ids))
        ).delete(synchronize_session=False)
        db.query(CategoryDecisionEvent).filter(CategoryDecisionEvent.transaction_id.in_(txn_ids)).delete(
            synchronize_session=False
        )
        db.query(TransactionAnnotation).filter(TransactionAnnotation.transaction_id.in_(txn_ids)).delete(
            synchronize_session=False
        )
        db.query(Transaction).filter(Transaction.item_id == item_id).delete(synchronize_session=False)

    if account_ids:
        db.query(AccountBalanceSnapshot).filter(AccountBalanceSnapshot.account_id.in_(account_ids)).delete(
            synchronize_session=False
        )
        db.query(Account).filter(Account.item_id == item_id).delete(synchronize_session=False)

    db.query(SyncRun).filter(SyncRun.item_id == item_id).delete(synchronize_session=False)
    db.query(SyncState).filter(SyncState.item_id == item_id).delete(synchronize_session=False)
    db.delete(item)
    db.commit()

    return {"status": "removed", "item_id": item_id}


@router.post("/sync/item/{item_id}/historical")
def sync_item_historical(
    item_id: int,
    start_date: date = Query(..., description="Start date for historical sync (YYYY-MM-DD)"),
    end_date: date = Query(..., description="End date for historical sync (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
):
    try:
        return SyncService().sync_item_historical(db, item_id, start_date, end_date)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except SyncInProgressError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except HTTPException:
        raise
    except Exception:
        logger.exception("historical sync failed for item %d", item_id)
        raise HTTPException(status_code=502, detail="historical sync failed")


@router.post("/sync/item/{item_id}")
def sync_item(item_id: int, db: Session = Depends(get_db)):
    try:
        return SyncService().sync_item(db, item_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except SyncInProgressError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except HTTPException:
        raise
    except Exception:
        logger.exception("sync failed for item %d", item_id)
        raise HTTPException(status_code=502, detail="sync failed")


@router.post("/sync/all")
def sync_all(db: Session = Depends(get_db)):
    items = db.query(Item).filter(Item.status == "active").all()
    if not items:
        return {"results": [], "summary": "no active items"}

    service = SyncService()
    results = []
    for item in items:
        try:
            result = service.sync_item(db, item.id)
            results.append({"item_id": item.id, "plaid_item_id": item.plaid_item_id, **result})
        except SyncInProgressError:
            results.append({"item_id": item.id, "plaid_item_id": item.plaid_item_id, "status": "skipped", "reason": "sync already in progress"})
        except Exception:
            logger.exception("sync failed for item %d", item.id)
            results.append({"item_id": item.id, "plaid_item_id": item.plaid_item_id, "status": "error", "reason": "sync failed"})

    succeeded = sum(1 for r in results if r.get("status") == "success")
    return {"results": results, "summary": f"{succeeded}/{len(results)} items synced"}


def _contains(expr, value: str):
    return func.lower(expr).like(f"%{value.strip().lower()}%")


def _apply_search_query(query, parsed):
    """Turn a ParsedQuery (app/services/search_query.py) into SQL filters.

    Multiple values for the same field OR together; different fields AND."""
    if parsed.merchant:
        query = query.filter(
            or_(*[_contains(_effective_merchant_expr(), v) for v in parsed.merchant])
        )
    if parsed.account:
        query = query.filter(
            or_(*[_contains(_effective_account_name_expr(), v) for v in parsed.account])
        )
    if parsed.category:
        # A parent matches its children: FOOD also matches FOOD/DINING.
        clauses = []
        for value in parsed.category:
            needle = value.strip().lower()
            clauses.append(
                or_(
                    func.lower(_effective_category_expr()) == needle,
                    func.lower(_effective_category_expr()).like(f"{needle}/%"),
                )
            )
        query = query.filter(or_(*clauses))
    if parsed.amount_min is not None:
        query = query.filter(func.abs(Transaction.amount) > parsed.amount_min)
    if parsed.amount_max is not None:
        query = query.filter(func.abs(Transaction.amount) < parsed.amount_max)
    if parsed.date_from:
        query = query.filter(Transaction.date >= parsed.date_from)
    if parsed.date_to:
        query = query.filter(Transaction.date <= parsed.date_to)

    if "unreviewed" in parsed.flags:
        query = query.filter(
            or_(
                TransactionAnnotation.reviewed.is_(None),
                TransactionAnnotation.reviewed == False,  # noqa: E712
            )
        )
    if "reviewed" in parsed.flags:
        query = query.filter(TransactionAnnotation.reviewed == True)  # noqa: E712
    if "uncategorized" in parsed.flags:
        query = query.filter(func.lower(_effective_category_expr()) == "uncategorized")
    if "refund" in parsed.flags:
        query = query.filter(_is_refund_expr())
    if "likely-refund" in parsed.flags:
        query = query.filter(TransactionAnnotation.refund_status == "likely")
    if "not-transfer" in parsed.flags:
        # Same exclusion the analytics counts use, so a count and the search
        # that drills into it can describe the same set.
        query = _apply_transfer_exclusion(query, include_transfers=False)
    if "pending" in parsed.flags:
        query = query.filter(Transaction.pending == True)  # noqa: E712

    for word in parsed.text:
        query = query.filter(
            or_(
                _contains(Transaction.name, word),
                _contains(_effective_merchant_expr(), word),
                _contains(_effective_category_expr(), word),
            )
        )
    return query


@router.get("/transactions/search-suggestions")
def transaction_search_suggestions(
    db: Session = Depends(get_db),
    q: str | None = Query(default=None, description="Partial query being typed"),
    limit: int = Query(default=20, ge=1, le=50),
):
    """Context-aware suggestions powering the search bar dropdown.

    With no input (or between tokens) this returns the field menu — that list is
    what removes the need to remember the syntax. Inside a `field:` token it
    returns real values from the ledger."""
    context, field_key, active = suggestion_context(q)

    if context == "field":
        prefix = active.strip().lower()
        fields = [
            {"value": f.token, "label": f.label, "hint": f.hint, "has_values": f.has_values}
            for f in SEARCH_FIELDS
            if not prefix or prefix in f.label.lower() or f.token.startswith(prefix)
        ]
        return {
            "context": "field",
            "field": None,
            "replace_token": active,
            "suggestions": fields[:limit],
        }

    value_prefix = active.partition(":")[2].strip().lower()
    token_prefix = active.partition(":")[0] + ":"

    if field_key == "is":
        return {
            "context": "value",
            "field": "is",
            "replace_token": active,
            "suggestions": [
                {"value": f"is:{value}", "label": value, "hint": hint, "has_values": False}
                for value, hint in IS_VALUES
                if not value_prefix or value.startswith(value_prefix)
            ][:limit],
        }

    expr = {
        "merchant": _effective_merchant_expr(),
        "category": _effective_category_expr(),
        "account": _effective_account_name_expr(),
    }[field_key]

    rows = (
        db.query(expr.label("value"), func.count(Transaction.id).label("n"))
        .join(Account, Account.id == Transaction.account_id)
        .outerjoin(TransactionAnnotation, Transaction.id == TransactionAnnotation.transaction_id)
        .filter(expr.is_not(None))
        .group_by(expr)
        .order_by(func.count(Transaction.id).desc())
        .all()
    )
    suggestions = [
        {
            "value": f"{token_prefix}{_quote_value(str(value))}",
            "label": str(value),
            "hint": f"{count} transaction{'s' if count != 1 else ''}",
            "has_values": False,
        }
        for value, count in rows
        if value and (not value_prefix or value_prefix in str(value).lower())
    ]
    return {
        "context": "value",
        "field": field_key,
        "replace_token": active,
        "suggestions": suggestions[:limit],
    }


def _quote_value(value: str) -> str:
    return f'"{value}"' if " " in value else value


@router.get("/categories")
def list_categories(
    db: Session = Depends(get_db),
    limit: int = Query(default=500, ge=1, le=2000),
):
    """The category vocabulary for pickers: every category in use, plus rule
    targets and a curated starter set.

    `count` is the number of transactions currently resolving to that category
    (0 for rule/default entries that nothing matches yet); `source` is
    ledger|rule|default. Case variants are merged — notably the SQL fallback
    literal 'uncategorized' and a manual "UNCATEGORIZED" annotation."""
    expr = _effective_category_expr()
    ledger_rows = (
        db.query(expr.label("value"), func.count(Transaction.id).label("n"))
        .join(Account, Account.id == Transaction.account_id)
        .outerjoin(TransactionAnnotation, Transaction.id == TransactionAnnotation.transaction_id)
        .filter(expr.is_not(None))
        .group_by(expr)
        .all()
    )
    # A rule's target is a category the user coined, even with nothing matching
    # it yet — and disabled rules still carry intent.
    rule_categories = [
        row[0] for row in db.query(CategoryRule.assigned_category).distinct().all() if row[0]
    ]

    items = merge_catalog([(value, count) for value, count in ledger_rows], rule_categories)
    return {"items": items[:limit]}


@router.get("/transactions")
def list_transactions(
    db: Session = Depends(get_db),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    category: str | None = Query(default=None),
    q: str | None = Query(default=None, description="Search name, merchant, or category"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    effective_category = _effective_category_expr().label("effective_category")
    category_source = _category_source_expr().label("category_source")
    effective_merchant = _effective_merchant_expr().label("effective_merchant")
    effective_account_name = _effective_account_name_expr().label("effective_account_name")
    plaid_category_detailed = _plaid_detailed_category_expr().label("plaid_category_detailed")
    plaid_category_friendly = _friendly_plaid_case().label("plaid_category_friendly")

    base = db.query(
        Transaction,
        TransactionAnnotation,
        effective_category,
        category_source,
        effective_merchant,
        effective_account_name,
        plaid_category_detailed,
        plaid_category_friendly,
    ).join(
        Account,
        Account.id == Transaction.account_id,
    ).outerjoin(
        TransactionAnnotation,
        Transaction.id == TransactionAnnotation.transaction_id,
    )

    if start_date:
        base = base.filter(Transaction.date >= start_date)
    if end_date:
        base = base.filter(Transaction.date <= end_date)
    if category:
        # Case-insensitive: the value a picker offers comes from /categories,
        # which merges case variants ('uncategorized' and a manual
        # 'UNCATEGORIZED' collapse into one row), and the SQL fallback literal
        # is lowercase. An exact match would answer that merged value with an
        # empty list.
        base = base.filter(func.lower(_effective_category_expr()) == category.lower())
    if q:
        base = _apply_search_query(base, parse_query(q))

    total = base.with_entities(func.count(Transaction.id)).scalar()
    rows = (
        base.order_by(Transaction.date.desc(), Transaction.id.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )

    # This list deliberately shows everything, transfers included — but a row
    # excluded from spend/income analytics should say so, otherwise money
    # silently goes missing from the totals with no visible cause.
    page_ids = [row[0].id for row in rows]
    pair_by_txn: dict[int, int] = {}
    if page_ids:
        pair_rows = db.query(
            TransferPair.id, TransferPair.txn_out_id, TransferPair.txn_in_id
        ).filter(
            or_(
                TransferPair.txn_out_id.in_(page_ids),
                TransferPair.txn_in_id.in_(page_ids),
            )
        ).all()
        for pair_id, out_id, in_id in pair_rows:
            pair_by_txn[out_id] = pair_id
            pair_by_txn[in_id] = pair_id

    return {
        "total": total,
        "items": [
            {
                "id": t.id,
                "plaid_transaction_id": t.plaid_transaction_id,
                "date": str(t.date),
                "amount": round(float(t.amount), 2),
                "name": t.name,
                "merchant_name": t.merchant_name,
                "effective_merchant": resolved_merchant,
                "effective_account_name": resolved_account_name,
                "pending": t.pending,
                "plaid_category_primary": t.plaid_category_primary,
                "plaid_category_detailed": plaid_detailed,
                "plaid_category_friendly": plaid_friendly,
                "effective_category": resolved_category,
                "category_source": resolved_source,
                "rule_id": a.rule_id if (a and resolved_source == "rule") else None,
                "transfer_pair_id": pair_by_txn.get(t.id),
                "is_transfer": t.id in pair_by_txn,
                "refund_status": a.refund_status if a else None,
                "refund_match_transaction_id": a.refund_match_transaction_id if a else None,
                "refund_reason": a.refund_reason if a else None,
                "annotation": {
                    "user_category": a.user_category if a else None,
                    "merchant_name_override": a.merchant_name_override if a else None,
                    "notes": a.notes if a else None,
                    "reviewed": a.reviewed if a else False,
                },
            }
            for (
                t,
                a,
                resolved_category,
                resolved_source,
                resolved_merchant,
                resolved_account_name,
                plaid_detailed,
                plaid_friendly,
            ) in rows
        ],
    }


@router.patch("/transactions/{transaction_id}/annotation")
def patch_annotation(transaction_id: int, payload: PatchAnnotationRequest, db: Session = Depends(get_db)):
    tx = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not tx:
        raise HTTPException(status_code=404, detail="transaction not found")

    _apply_annotation_payload(db, tx, payload)

    db.commit()
    if payload.refund_status == "auto":
        classify_refunds(db)
    return {"status": "ok", "transaction_id": transaction_id}


@router.patch("/transactions/annotations/batch")
def patch_annotations_batch(payload: BatchPatchAnnotationRequest, db: Session = Depends(get_db)):
    transaction_ids = list(dict.fromkeys(payload.transaction_ids))
    rows = db.query(Transaction).filter(Transaction.id.in_(transaction_ids)).all()
    found_ids = {tx.id for tx in rows}
    missing_ids = [tx_id for tx_id in transaction_ids if tx_id not in found_ids]
    if missing_ids:
        raise HTTPException(status_code=404, detail={"missing_transaction_ids": missing_ids})

    for tx in rows:
        _apply_annotation_payload(db, tx, payload)

    db.commit()
    if payload.refund_status == "auto":
        classify_refunds(db)
    return {"status": "ok", "transaction_ids": transaction_ids, "updated": len(rows)}


def _apply_annotation_payload(db: Session, tx: Transaction, payload: PatchAnnotationRequest) -> TransactionAnnotation:
    annotation = (
        db.query(TransactionAnnotation)
        .filter(TransactionAnnotation.transaction_id == tx.id)
        .first()
    )
    if not annotation:
        annotation = TransactionAnnotation(transaction_id=tx.id)
        db.add(annotation)

    fields_set = payload.model_fields_set

    if "user_category" in fields_set:
        annotation.user_category = payload.user_category or None
    if "merchant_name_override" in fields_set:
        annotation.merchant_name_override = payload.merchant_name_override or None
    if "notes" in fields_set:
        annotation.notes = payload.notes or None
    if payload.reviewed is not None:
        annotation.reviewed = payload.reviewed
    if payload.refund_status is not None:
        if payload.refund_status == "auto":
            annotation.refund_status = None
            annotation.refund_match_transaction_id = None
            annotation.refund_reason = None
        else:
            annotation.refund_status = payload.refund_status
            annotation.refund_match_transaction_id = None
            annotation.refund_reason = "Manual classification"

    if tx.txn_hash is not None:
        account = db.query(Account).filter(Account.id == tx.account_id).first()
        fingerprint = (
            db.query(AnnotationFingerprint)
            .filter(
                AnnotationFingerprint.txn_hash == tx.txn_hash,
                AnnotationFingerprint.txn_occurrence == tx.txn_occurrence,
            )
            .first()
        )
        if not fingerprint:
            fingerprint = AnnotationFingerprint(
                txn_hash=tx.txn_hash,
                txn_occurrence=tx.txn_occurrence,
                account_mask=account.mask if account else None,
                txn_date=tx.date,
                amount=tx.amount,
                name=tx.name,
                source_transaction_id=tx.id,
            )
            db.add(fingerprint)

        fingerprint.user_category = annotation.user_category
        fingerprint.merchant_name_override = annotation.merchant_name_override
        fingerprint.notes = annotation.notes
        fingerprint.reviewed = annotation.reviewed
        fingerprint.is_transfer_override = annotation.is_transfer_override
        fingerprint.refund_status = annotation.refund_status
        fingerprint.source_transaction_id = tx.id
        fingerprint.applied_transaction_id = tx.id
        fingerprint.applied_at = utcnow()

    return annotation


@router.get("/annotations/fingerprints")
def list_annotation_fingerprints(
    unapplied_only: bool = Query(False),
    db: Session = Depends(get_db),
):
    q = db.query(AnnotationFingerprint)
    if unapplied_only:
        # "Unapplied" means no *live* transaction carries it. A fingerprint whose
        # transaction was deleted still holds that id, so a bare IS NULL check
        # would keep hiding annotations that no longer apply to anything —
        # exactly the ones this endpoint exists to surface after a re-link.
        q = q.filter(
            or_(
                AnnotationFingerprint.applied_transaction_id.is_(None),
                ~AnnotationFingerprint.applied_transaction_id.in_(select(Transaction.id)),
            )
        )
    rows = q.order_by(AnnotationFingerprint.updated_at.desc()).all()
    return [
        {
            "id": f.id,
            "txn_hash": f.txn_hash,
            "txn_occurrence": f.txn_occurrence,
            "account_mask": f.account_mask,
            "txn_date": f.txn_date,
            "amount": f.amount,
            "name": f.name,
            "user_category": f.user_category,
            "merchant_name_override": f.merchant_name_override,
            "notes": f.notes,
            "reviewed": f.reviewed,
            "is_transfer_override": f.is_transfer_override,
            "refund_status": f.refund_status,
            "source_transaction_id": f.source_transaction_id,
            "applied_transaction_id": f.applied_transaction_id,
            "updated_at": f.updated_at,
            "applied_at": f.applied_at,
        }
        for f in rows
    ]


@router.patch("/accounts/{account_id}")
def patch_account(account_id: int, payload: PatchAccountRequest, db: Session = Depends(get_db)):
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="account not found")
    if payload.nickname is not None:
        account.nickname = payload.nickname or None
    db.commit()
    return {"status": "ok", "account_id": account_id}


def _serialize_rule(rule: CategoryRule) -> dict:
    return {
        "id": rule.id,
        "rank": rule.rank,
        "enabled": rule.enabled,
        "description_regex": rule.description_regex,
        "account_name_regex": rule.account_name_regex,
        "min_amount": float(rule.min_amount) if rule.min_amount is not None else None,
        "max_amount": float(rule.max_amount) if rule.max_amount is not None else None,
        "assigned_category": rule.assigned_category,
        "name": rule.name,
        "created_at": rule.created_at.isoformat(),
        "updated_at": rule.updated_at.isoformat(),
    }


def _compiled_regex(pattern: str | None):
    if not pattern:
        return None
    try:
        return re.compile(pattern, re.IGNORECASE)
    except re.error as e:
        raise HTTPException(status_code=400, detail=f"invalid regex '{pattern}': {e}")


def _rule_like(rule):
    """Adapt a rule dict (preview drafts) to the attribute-based RuleLike the
    category_resolver expects. ORM CategoryRule instances pass through unchanged."""
    if isinstance(rule, dict):
        return SimpleNamespace(
            id=rule.get("id"),
            rank=rule.get("rank") or 0,
            enabled=bool(rule.get("enabled", True)),
            description_regex=rule.get("description_regex"),
            account_name_regex=rule.get("account_name_regex"),
            min_amount=rule.get("min_amount"),
            max_amount=rule.get("max_amount"),
            assigned_category=rule.get("assigned_category"),
        )
    return rule


def _scoped_transactions_query(db: Session, scope):
    q = db.query(Transaction, Account, TransactionAnnotation).join(Account, Account.id == Transaction.account_id).outerjoin(
        TransactionAnnotation,
        TransactionAnnotation.transaction_id == Transaction.id,
    )

    if scope.start_date:
        q = q.filter(Transaction.date >= scope.start_date)
    if scope.end_date:
        q = q.filter(Transaction.date <= scope.end_date)
    if scope.account_ids:
        q = q.filter(Transaction.account_id.in_(scope.account_ids))
    if scope.item_ids:
        q = q.filter(Transaction.item_id.in_(scope.item_ids))
    if not scope.include_pending:
        q = q.filter(Transaction.pending == False)  # noqa: E712

    return q.order_by(Transaction.id.asc())


def _scoped_transactions(db: Session, scope):
    return _scoped_transactions_query(db, scope).all()


def _iter_scoped_transaction_batches(db: Session, scope, batch_size: int):
    base_query = _scoped_transactions_query(db, scope)
    last_tx_id: int | None = None
    while True:
        query = base_query
        if last_tx_id is not None:
            query = query.filter(Transaction.id > last_tx_id)
        batch = query.limit(batch_size).all()
        if not batch:
            break
        last_tx_id = batch[-1][0].id
        yield batch


def _current_effective(tx, annotation) -> str:
    """Effective category from the *stored* state (existing annotation), no re-evaluation."""
    return resolve_effective_category(tx, annotation, rule_match=None).category


def _simulated_effective(tx, annotation, rule_match) -> str:
    """Effective category if the rule stack were applied now. A manual user_category
    still wins; otherwise the freshly matched rule (or Plaid fallback) decides."""
    sim_annotation = annotation if (annotation and annotation.user_category) else None
    return resolve_effective_category(tx, sim_annotation, rule_match=rule_match).category


@router.get("/category-rules")
def list_category_rules(db: Session = Depends(get_db)):
    rules = db.query(CategoryRule).order_by(CategoryRule.rank.asc(), CategoryRule.id.asc()).all()
    return {"items": [_serialize_rule(rule) for rule in rules]}


@router.post("/category-rules")
def create_category_rule(payload: CategoryRuleCreateRequest, db: Session = Depends(get_db)):
    rule = CategoryRule(
        rank=payload.rank,
        enabled=payload.enabled,
        description_regex=payload.description_regex,
        account_name_regex=payload.account_name_regex,
        min_amount=payload.min_amount,
        max_amount=payload.max_amount,
        assigned_category=payload.assigned_category,
        name=payload.name,
    )
    _compiled_regex(rule.description_regex)
    _compiled_regex(rule.account_name_regex)
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return _serialize_rule(rule)


@router.patch("/category-rules/{rule_id}")
def patch_category_rule(rule_id: int, payload: CategoryRulePatchRequest, db: Session = Depends(get_db)):
    rule = db.get(CategoryRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="rule not found")

    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(rule, key, value)

    _compiled_regex(rule.description_regex)
    _compiled_regex(rule.account_name_regex)
    db.commit()
    db.refresh(rule)
    return _serialize_rule(rule)


@router.delete("/category-rules/{rule_id}")
def delete_category_rule(rule_id: int, db: Session = Depends(get_db)):
    rule = db.get(CategoryRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="rule not found")
    db.delete(rule)
    db.commit()
    return {"status": "deleted", "id": rule_id}


@router.post("/category-rules/preview")
def preview_category_rules(payload: CategoryRulePreviewRequest, db: Session = Depends(get_db)):
    base_rules = db.query(CategoryRule).order_by(CategoryRule.rank.asc(), CategoryRule.id.asc()).all()

    draft_rule_payload = payload.draft_rule.model_dump() if payload.draft_rule else None
    if payload.rule_id and not draft_rule_payload:
        existing = db.get(CategoryRule, payload.rule_id)
        if not existing:
            raise HTTPException(status_code=404, detail="rule not found")
        draft_rule_payload = {
            "id": existing.id,
            "rank": existing.rank,
            "enabled": existing.enabled,
            "description_regex": existing.description_regex,
            "account_name_regex": existing.account_name_regex,
            "min_amount": existing.min_amount,
            "max_amount": existing.max_amount,
            "assigned_category": existing.assigned_category,
        }

    merged_rules: list[CategoryRule | dict] = []
    replaced = False
    for rule in base_rules:
        if draft_rule_payload and payload.rule_id and rule.id == payload.rule_id:
            merged_rules.append({**draft_rule_payload, "id": rule.id})
            replaced = True
        else:
            merged_rules.append(rule)

    if draft_rule_payload and (not payload.rule_id or not replaced):
        merged_rules.append({**draft_rule_payload, "id": payload.rule_id})

    try:
        compiled_rules = compile_rules([_rule_like(r) for r in merged_rules])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    rows = _scoped_transactions(db, payload.scope)

    changed = []
    for tx, account, annotation in rows:
        match = find_first_matching_rule(compiled_rules, tx=tx, account=account)
        current = _current_effective(tx, annotation)
        simulated = _simulated_effective(tx, annotation, match)
        if current != simulated:
            changed.append((tx, current, simulated, match.rule_id if match else None))

    sample = [
        {
            "transaction_id": tx.id,
            "date": str(tx.date),
            "amount": round(float(tx.amount), 2),
            "name": tx.name,
            "current_effective_category": current,
            "simulated_effective_category": simulated,
            "rule_id": rule_id,
        }
        for tx, current, simulated, rule_id in changed[: payload.sample_limit]
    ]

    return {
        "total_scanned": len(rows),
        "would_change_count": len(changed),
        "samples": sample,
    }


@router.post("/category-rules/apply")
def apply_category_rules(payload: CategoryRuleApplyRequest, db: Session = Depends(get_db)):
    run_started = time.perf_counter()
    now = utcnow()
    rules = (
        db.query(CategoryRule)
        .filter(CategoryRule.enabled == True)  # noqa: E712
        .order_by(CategoryRule.rank.asc(), CategoryRule.id.asc())
        .all()
    )
    try:
        compiled_rules = compile_rules([_rule_like(rule) for rule in rules])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    scanned = 0
    matched = 0
    changed = 0
    skipped_manual = 0
    updated_count = 0
    event_count = 0

    for batch in _iter_scoped_transaction_batches(db, payload.scope, payload.batch_size):
        annotation_inserts = []
        annotation_updates = []
        event_inserts = []

        for tx, account, annotation in batch:
            scanned += 1

            if annotation and annotation.user_category:
                skipped_manual += 1
                continue

            matched_rule = find_first_matching_rule(compiled_rules, tx=tx, account=account)
            if matched_rule:
                matched += 1

            current_effective = _current_effective(tx, annotation)
            simulated_effective = _simulated_effective(tx, annotation, matched_rule)
            effective_changed = current_effective != simulated_effective
            if effective_changed:
                changed += 1

            if payload.dry_run:
                continue

            matched_category = matched_rule.category if matched_rule else None
            matched_rule_id = matched_rule.rule_id if matched_rule else None

            if annotation:
                annotation_updates.append(
                    {
                        "id": annotation.id,
                        "rule_category": matched_category,
                        "rule_id": matched_rule_id,
                        "rule_evaluated_at": now,
                    }
                )
            else:
                annotation_inserts.append(
                    {
                        "transaction_id": tx.id,
                        "rule_category": matched_category,
                        "rule_id": matched_rule_id,
                        "rule_evaluated_at": now,
                    }
                )

            if effective_changed:
                event_inserts.append(
                    {
                        "transaction_id": tx.id,
                        "old_effective_category": current_effective,
                        "new_effective_category": simulated_effective,
                        "source": "rule_apply",
                        "rule_id": matched_rule_id,
                        "changed_at": now,
                        "metadata_json": json.dumps({"dry_run": False}),
                    }
                )

        if not payload.dry_run:
            if annotation_inserts:
                db.bulk_insert_mappings(TransactionAnnotation, annotation_inserts)
            if annotation_updates:
                db.bulk_update_mappings(TransactionAnnotation, annotation_updates)
            if event_inserts:
                db.bulk_insert_mappings(CategoryDecisionEvent, event_inserts)
            db.flush()
            updated_count += len(annotation_inserts) + len(annotation_updates)
            event_count += len(event_inserts)

    if not payload.dry_run:
        db.commit()

    duration_ms = int((time.perf_counter() - run_started) * 1000)
    run_summary = {
        "scanned": scanned,
        "matched": matched,
        "changed": changed,
        "skipped_manual": skipped_manual,
        "duration_ms": duration_ms,
    }
    return {
        "dry_run": payload.dry_run,
        "total_scanned": scanned,
        "would_change_count": changed,
        "updated_count": updated_count,
        "event_count": event_count,
        "run_summary": run_summary,
    }


@router.post("/category-rules/recompute-all")
def recompute_all_category_rules(payload: CategoryRuleRecomputeRequest, db: Session = Depends(get_db)):
    apply_payload = CategoryRuleApplyRequest(
        dry_run=False,
        batch_size=payload.batch_size,
        scope={"include_pending": payload.include_pending},
    )
    return apply_category_rules(apply_payload, db)


def _apply_transfer_exclusion(q, include_transfers: bool):
    """Filter out transactions participating in a TransferPair.

    A transfer is a *matched pair* across two covered accounts — that is the only
    thing that can double-count money as both income and expense. The legacy
    one-sided `is_transfer_override` flag is deliberately no longer honored: it
    removed single transactions from every analytic with no counterparty, could
    not be set or cleared through any API, and survived re-sync via annotation
    fingerprints, so anything carrying it was silently and permanently missing
    from spend and income.
    """
    if include_transfers:
        return q
    return q.filter(
        ~Transaction.id.in_(select(TransferPair.txn_out_id)),
        ~Transaction.id.in_(select(TransferPair.txn_in_id)),
    )


def _is_refund_expr():
    return TransactionAnnotation.refund_status.in_(["confirmed", "likely"])


@router.post("/refunds/detect")
def refunds_detect(db: Session = Depends(get_db)):
    return classify_refunds(db)


@router.get("/analytics/monthly-spend")
def monthly_spend(
    db: Session = Depends(get_db),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    include_transfers: bool = Query(default=False),
):
    month_col = func.strftime("%Y-%m", Transaction.date).label("month")
    q = (
        db.query(
            month_col,
            func.sum(case(
                (_is_refund_expr(), Transaction.amount),
                (Transaction.amount > 0, Transaction.amount),
                else_=0,
            )),
        )
        .outerjoin(TransactionAnnotation, Transaction.id == TransactionAnnotation.transaction_id)
    )
    q = _apply_transfer_exclusion(q, include_transfers)
    if start_date:
        q = q.filter(Transaction.date >= start_date)
    if end_date:
        q = q.filter(Transaction.date <= end_date)
    rows = q.group_by(month_col).order_by(month_col).all()
    return [{"month": month, "spend": round(float(total or 0), 2)} for month, total in rows]


@router.get("/analytics/category-spend")
def category_spend(
    db: Session = Depends(get_db),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    include_transfers: bool = Query(default=False),
):
    effective_category = _effective_category_expr().label("category")
    q = (
        db.query(
            effective_category,
            func.sum(case(
                (_is_refund_expr(), Transaction.amount),
                (Transaction.amount > 0, Transaction.amount),
                else_=0,
            )),
        )
        .outerjoin(TransactionAnnotation, Transaction.id == TransactionAnnotation.transaction_id)
    )
    q = _apply_transfer_exclusion(q, include_transfers)
    if start_date:
        q = q.filter(Transaction.date >= start_date)
    if end_date:
        q = q.filter(Transaction.date <= end_date)
    rows = q.group_by(effective_category).order_by(effective_category).all()
    return [{"category": c, "spend": round(float(total or 0), 2)} for c, total in rows]


@router.get("/analytics/cashflow-trend")
def cashflow_trend(
    db: Session = Depends(get_db),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    include_transfers: bool = Query(default=False),
):
    month_col = func.strftime("%Y-%m", Transaction.date).label("month")
    q = (
        db.query(
            month_col,
            func.sum(case(
                (_is_refund_expr(), Transaction.amount),
                (Transaction.amount > 0, Transaction.amount),
                else_=0,
            )).label("expenses"),
            func.sum(case(
                (
                    (Transaction.amount < 0)
                    & or_(
                        TransactionAnnotation.refund_status.is_(None),
                        ~TransactionAnnotation.refund_status.in_(["confirmed", "likely"]),
                    ),
                    -Transaction.amount,
                ),
                else_=0,
            )).label("income"),
        )
        .outerjoin(TransactionAnnotation, Transaction.id == TransactionAnnotation.transaction_id)
    )
    q = _apply_transfer_exclusion(q, include_transfers)
    if start_date:
        q = q.filter(Transaction.date >= start_date)
    if end_date:
        q = q.filter(Transaction.date <= end_date)
    rows = q.group_by(month_col).order_by(month_col).all()
    return [
        {
            "month": month,
            "expenses": round(float(expenses or 0), 2),
            "income": round(float(income or 0), 2),
            "net": round(float((income or 0) - (expenses or 0)), 2),
        }
        for month, expenses, income in rows
    ]


@router.get("/analytics/accounts-summary")
def accounts_summary(db: Session = Depends(get_db)):
    accounts = db.query(Account).all()
    by_type: dict[str, list[dict]] = {}
    for a in accounts:
        bal = float(a.current_balance) if a.current_balance is not None else 0.0
        by_type.setdefault(a.type or "other", []).append({
            "id": a.id,
            "name": a.name,
            "display_name": a.nickname or a.name,
            "nickname": a.nickname,
            "mask": a.mask,
            "subtype": a.subtype,
            "current_balance": round(bal, 2),
            "available_balance": round(float(a.available_balance), 2) if a.available_balance is not None else None,
            "currency": a.currency,
            "credit_limit": round(float(a.credit_limit), 2) if a.credit_limit is not None else None,
        })
    assets = sum(x["current_balance"] for x in by_type.get("depository", []))
    liabilities = sum(x["current_balance"] for x in by_type.get("credit", []))
    liabilities += sum(x["current_balance"] for x in by_type.get("loan", []))
    return {
        "assets": round(assets, 2),
        "liabilities": round(liabilities, 2),
        "net_worth": round(assets - liabilities, 2),
        "groups": by_type,
    }


def _month_key(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def _prev_month_key(month: str) -> str:
    y, m = (int(x) for x in month.split("-"))
    m -= 1
    if m == 0:
        m, y = 12, y - 1
    return f"{y:04d}-{m:02d}"


def _month_bounds(month: str) -> tuple[date, date]:
    y, m = (int(x) for x in month.split("-"))
    return date(y, m, 1), date(y, m, calendar.monthrange(y, m)[1])


def _month_label(month: str) -> str:
    y, m = (int(x) for x in month.split("-"))
    return f"{calendar.month_name[m]} {y}"


def _expense_value_case():
    """Signed per-transaction expense: positive charges add, refunds subtract."""
    return case(
        (_is_refund_expr(), Transaction.amount),
        (Transaction.amount > 0, Transaction.amount),
        else_=0,
    )


def _project_month(month: str, total: float) -> float:
    """Straight-line projection for the in-progress current month; else unchanged."""
    today = date.today()
    y, m = (int(x) for x in month.split("-"))
    days_in_month = calendar.monthrange(y, m)[1]
    if y == today.year and m == today.month and today.day:
        return round(total / today.day * days_in_month, 2)
    return round(total, 2)


def _merge_comparison(current: dict[str, float], previous: dict[str, float]) -> list[dict]:
    rows = [
        {
            "category": cat,
            "current": round(current.get(cat, 0.0), 2),
            "previous": round(previous.get(cat, 0.0), 2),
        }
        for cat in (set(current) | set(previous))
    ]
    rows.sort(key=lambda r: r["current"], reverse=True)
    return rows


@router.get("/analytics/overview")
def analytics_overview(db: Session = Depends(get_db)):
    """One-shot summary for the mobile Overview screen (KPIs + needs-attention)."""
    accounts = accounts_summary(db)
    cash = cashflow_trend(db, start_date=None, end_date=None, include_transfers=False)
    by_month = {row["month"]: row for row in cash}
    latest = cash[-1]["month"] if cash else _month_key(date.today())
    previous = _prev_month_key(latest)
    cur = by_month.get(latest, {})
    pre = by_month.get(previous, {})

    as_of = db.query(func.max(Transaction.date)).scalar() or date.today()

    # Counted over transactions, not annotations: an annotation whose transaction
    # is gone is invisible everywhere else, so counting it here would advertise
    # rows the Transactions screen can never show.
    likely_refunds = (
        db.query(func.count(Transaction.id))
        .join(TransactionAnnotation, Transaction.id == TransactionAnnotation.transaction_id)
        .filter(TransactionAnnotation.refund_status == "likely")
        .scalar()
    ) or 0
    transfer_pending = (
        db.query(func.count(TransferPair.id))
        .filter(TransferPair.confirmed == False)  # noqa: E712
        .scalar()
    ) or 0

    unreviewed_q = db.query(func.count(Transaction.id)).outerjoin(
        TransactionAnnotation, Transaction.id == TransactionAnnotation.transaction_id
    )
    unreviewed_q = _apply_transfer_exclusion(unreviewed_q, include_transfers=False)
    unreviewed = unreviewed_q.filter(
        or_(
            TransactionAnnotation.reviewed.is_(None),
            TransactionAnnotation.reviewed == False,  # noqa: E712
        )
    ).scalar() or 0

    uncategorized = (
        db.query(func.count(Transaction.id))
        .outerjoin(TransactionAnnotation, Transaction.id == TransactionAnnotation.transaction_id)
        .filter(func.lower(_effective_category_expr()) == "uncategorized")
        .scalar()
    ) or 0

    return {
        "as_of_date": str(as_of),
        "net_worth": accounts["net_worth"],
        "assets": accounts["assets"],
        "liabilities": accounts["liabilities"],
        "month_spend": cur.get("expenses", 0.0),
        "previous_month_spend": pre.get("expenses", 0.0),
        "month_income": cur.get("income", 0.0),
        "previous_month_income": pre.get("income", 0.0),
        "net_cashflow": cur.get("net", 0.0),
        "previous_net_cashflow": pre.get("net", 0.0),
        "needs_attention": {
            "unreviewed_transactions": int(unreviewed),
            "uncategorized_transactions": int(uncategorized),
            "likely_refunds": int(likely_refunds),
            "transfer_pairs_pending": int(transfer_pending),
        },
    }


@router.get("/analytics/spending-summary")
def analytics_spending_summary(
    db: Session = Depends(get_db),
    granularity: str = Query(default="monthly"),
):
    """Period spend total, comparison, projection, top driver, and per-category diff."""
    monthly = monthly_spend(db, start_date=None, end_date=None, include_transfers=False)
    spend_by_month = {r["month"]: r["spend"] for r in monthly}
    latest = monthly[-1]["month"] if monthly else _month_key(date.today())

    if granularity == "yearly":
        year = int(latest.split("-")[0])
        prev_year = year - 1
        total = round(sum(v for m, v in spend_by_month.items() if m.startswith(f"{year}-")), 2)
        previous_total = round(
            sum(v for m, v in spend_by_month.items() if m.startswith(f"{prev_year}-")), 2
        )
        months_with_data = sum(1 for m in spend_by_month if m.startswith(f"{year}-"))
        projection = round(total / months_with_data * 12, 2) if months_with_data else 0.0
        cur_cats = {r["category"]: r["spend"] for r in category_spend(db, date(year, 1, 1), date(year, 12, 31), include_transfers=False)}
        prev_cats = {r["category"]: r["spend"] for r in category_spend(db, date(prev_year, 1, 1), date(prev_year, 12, 31), include_transfers=False)}
        period_label = f"{year} YTD"
    else:
        previous = _prev_month_key(latest)
        total = round(spend_by_month.get(latest, 0.0), 2)
        previous_total = round(spend_by_month.get(previous, 0.0), 2)
        projection = _project_month(latest, total)
        cur_start, cur_end = _month_bounds(latest)
        prev_start, prev_end = _month_bounds(previous)
        cur_cats = {r["category"]: r["spend"] for r in category_spend(db, cur_start, cur_end, include_transfers=False)}
        prev_cats = {r["category"]: r["spend"] for r in category_spend(db, prev_start, prev_end, include_transfers=False)}
        period_label = _month_label(latest)

    comparison = _merge_comparison(cur_cats, prev_cats)
    top_driver = None
    if comparison:
        top = comparison[0]
        top_driver = {"category": top["category"], "amount": round(top["current"] - top["previous"], 2)}
    change_pct = round((total - previous_total) / previous_total * 100, 2) if previous_total else None

    return {
        "period_label": period_label,
        "total": total,
        "previous_total": previous_total,
        "change": round(total - previous_total, 2),
        "change_pct": change_pct,
        "projection": projection,
        "top_driver": top_driver,
        "category_comparison": comparison,
    }


def _daily_expense(db: Session, start: date, end: date, bucket: str) -> dict[int, float]:
    """Sum expense per day-of-month ('%d') or per month-of-year ('%m') in [start, end]."""
    bucket_col = func.strftime(bucket, Transaction.date)
    q = db.query(bucket_col, func.sum(_expense_value_case())).outerjoin(
        TransactionAnnotation, Transaction.id == TransactionAnnotation.transaction_id
    )
    q = _apply_transfer_exclusion(q, include_transfers=False)
    q = q.filter(Transaction.date >= start, Transaction.date <= end)
    rows = q.group_by(bucket_col).all()
    return {int(b): float(total or 0) for b, total in rows if b is not None}


def _cumulative(daily: dict[int, float], length: int) -> list[float | None]:
    """Running total over 1..length; None once past the last bucket that had data."""
    if not daily:
        return [None] * length
    last = max(daily)
    out: list[float | None] = []
    running = 0.0
    for i in range(1, length + 1):
        running += daily.get(i, 0.0)
        out.append(round(running, 2) if i <= last else None)
    return out


@router.get("/analytics/cumulative-spend")
def analytics_cumulative_spend(
    db: Session = Depends(get_db),
    granularity: str = Query(default="monthly"),
):
    """Cumulative spend pace for the current period vs the prior three."""
    anchor = db.query(func.max(Transaction.date)).scalar() or date.today()
    keys = ("current", "previous1", "previous2", "previous3")

    if granularity == "yearly":
        years = [anchor.year - i for i in range(4)]
        series = [
            _cumulative(_daily_expense(db, date(y, 1, 1), date(y, 12, 31), "%m"), 12)
            for y in years
        ]
        length = 12
    else:
        months = [_month_key(anchor)]
        for _ in range(3):
            months.append(_prev_month_key(months[-1]))
        anchor_month = _month_key(anchor)
        length = calendar.monthrange(int(anchor_month[:4]), int(anchor_month[5:7]))[1]
        series = []
        for mkey in months:
            start, end = _month_bounds(mkey)
            series.append(_cumulative(_daily_expense(db, start, end, "%d"), length))

    return [
        {"x": i + 1, **{key: series[j][i] for j, key in enumerate(keys)}}
        for i in range(length)
    ]


@router.get("/analytics/recurring")
def analytics_recurring(
    db: Session = Depends(get_db),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    status: str | None = Query(default=None, description="Filter to 'active' or 'inactive'"),
    min_monthly: float = Query(default=0.0, ge=0.0),
):
    """Detect subscriptions / recurring payments from expense history.

    Transfers and refunds are excluded (only positive expense-side transactions
    are considered). Detection is deterministic — see
    app/services/recurring_detector.py."""
    effective_merchant = _effective_merchant_expr()
    effective_category = _effective_category_expr()
    q = (
        db.query(Transaction, effective_merchant, effective_category)
        .join(Account, Account.id == Transaction.account_id)
        .outerjoin(TransactionAnnotation, Transaction.id == TransactionAnnotation.transaction_id)
        .filter(Transaction.pending == False)  # noqa: E712
        .filter(Transaction.amount > 0)
    )
    q = _apply_transfer_exclusion(q, include_transfers=False)
    if start_date:
        q = q.filter(Transaction.date >= start_date)
    if end_date:
        q = q.filter(Transaction.date <= end_date)

    txns = [
        SimpleNamespace(
            id=t.id,
            date=t.date,
            amount=float(t.amount),
            name=t.name,
            merchant_name=merchant,
            account_id=t.account_id,
            category=category,
        )
        for (t, merchant, category) in q.all()
    ]

    series = detect_recurring(txns)
    overrides = {o.merchant_key: o.status for o in db.query(RecurringOverride).all()}

    def _effective_status(s) -> str:
        manual = overrides.get(s.merchant_key)
        if manual == "canceled":
            return "inactive"
        if manual == "kept":
            return "active"
        return s.status

    # Enrich every series (effective status + manual override) before filtering,
    # so the summary reflects the whole portfolio regardless of the status filter.
    enriched = [(s, _effective_status(s), overrides.get(s.merchant_key)) for s in series]

    active_monthly = round(sum(s.monthly_estimate for s, eff, _ in enriched if eff == "active"), 2)
    active_annual = round(sum(s.annual_estimate for s, eff, _ in enriched if eff == "active"), 2)
    active_count = sum(1 for _, eff, _ in enriched if eff == "active")

    filtered = enriched
    if status in {"active", "inactive"}:
        filtered = [e for e in filtered if e[1] == status]
    if min_monthly > 0:
        filtered = [e for e in filtered if e[0].monthly_estimate >= min_monthly]

    items = [
        {
            "merchant_key": s.merchant_key,
            "merchant_label": s.merchant_label,
            "cadence": s.cadence,
            "occurrences": s.occurrences,
            "average_amount": s.average_amount,
            "min_amount": s.min_amount,
            "max_amount": s.max_amount,
            "amount_consistent": s.amount_consistent,
            "first_date": str(s.first_date),
            "last_date": str(s.last_date),
            "next_expected_date": str(s.next_expected_date),
            "median_interval_days": s.median_interval_days,
            "monthly_estimate": s.monthly_estimate,
            "annual_estimate": s.annual_estimate,
            "status": eff,
            "auto_status": s.status,
            "manual_status": manual,
            "category": s.category,
            "account_ids": s.account_ids,
            "sample_transaction_ids": s.sample_transaction_ids,
        }
        for s, eff, manual in filtered
    ]
    return {
        "items": items,
        "summary": {
            "count": len(items),
            "active_count": active_count,
            "active_monthly_estimate": active_monthly,
            "active_annual_estimate": active_annual,
        },
    }


@router.post("/analytics/recurring/{merchant_key}/status")
def set_recurring_status(
    merchant_key: str,
    payload: RecurringStatusRequest,
    db: Session = Depends(get_db),
):
    """Manually override a recurring series' status (persisted, keyed by merchant).

    'auto' clears the override; 'kept' forces active; 'canceled' forces inactive."""
    row = (
        db.query(RecurringOverride)
        .filter(RecurringOverride.merchant_key == merchant_key)
        .first()
    )
    if payload.status == "auto":
        if row:
            db.delete(row)
            db.commit()
        return {"merchant_key": merchant_key, "manual_status": None}

    if row:
        row.status = payload.status
    else:
        db.add(RecurringOverride(merchant_key=merchant_key, status=payload.status))
    db.commit()
    return {"merchant_key": merchant_key, "manual_status": payload.status}


@router.post("/transfers/detect")
def transfers_detect(
    db: Session = Depends(get_db),
    window_days: int = Query(default=3, ge=0, le=14),
    reset_auto: bool = Query(
        default=False,
        description="Discard unconfirmed auto pairs first (keeps confirmed/manual)",
    ),
):
    cleared = transfer_detector.clear_auto_pairs(db) if reset_auto else 0
    created = transfer_detector.detect_candidates(db, window_days=window_days)
    return {"cleared": cleared, "created": len(created), "pair_ids": [p.id for p in created]}


def _transfer_side(db: Session, txn_id: int) -> dict:
    """One leg of a pair, with enough account context to be interpretable.

    The account is the whole point of a transfer — showing only the transaction
    description ("PAYMENT THANK YOU") tells you nothing about what moved where.
    """
    txn = db.get(Transaction, txn_id)
    if not txn:
        return {"transaction_id": txn_id, "account_id": None, "account_name": None,
                "account_type": None, "date": None, "name": None, "amount": None}
    account = db.get(Account, txn.account_id)
    account_name = None
    if account:
        account_name = account.nickname or (
            f"{account.name} ··{account.mask}" if account.mask else account.name
        )
    return {
        "transaction_id": txn.id,
        "account_id": txn.account_id,
        "account_name": account_name,
        "account_type": account.type if account else None,
        "date": str(txn.date),
        "name": txn.name,
        "amount": round(float(txn.amount), 2) if txn.amount is not None else None,
    }


@router.get("/transfers")
def transfers_list(
    db: Session = Depends(get_db),
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    confirmed: bool | None = Query(default=None),
):
    """Pairs, newest first. `pending` is a whole-table count, not a page count:
    the client must not derive it by filtering `items`, which is truncated."""
    base = db.query(TransferPair)
    if confirmed is not None:
        base = base.filter(TransferPair.confirmed == confirmed)

    total = base.with_entities(func.count(TransferPair.id)).scalar() or 0
    pending = (
        db.query(func.count(TransferPair.id))
        .filter(TransferPair.confirmed == False)  # noqa: E712
        .scalar()
    ) or 0
    rows = base.order_by(TransferPair.id.desc()).limit(limit).offset(offset).all()
    items = []
    for p in rows:
        out = _transfer_side(db, p.txn_out_id)
        inn = _transfer_side(db, p.txn_in_id)
        gap = None
        if out["date"] and inn["date"]:
            gap = (date.fromisoformat(inn["date"]) - date.fromisoformat(out["date"])).days
        items.append({
            "id": p.id,
            "detected_by": p.detected_by,
            "confirmed": p.confirmed,
            "amount": out["amount"],
            "gap_days": gap,
            "out": out,
            "in": inn,
        })
    return {"total": total, "pending": pending, "items": items}


@router.post("/transfers")
def transfers_create(
    payload: TransferCreateRequest,
    db: Session = Depends(get_db),
):
    try:
        pair = transfer_detector.manual_pair(db, payload.txn_a_id, payload.txn_b_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"id": pair.id, "status": "paired"}


@router.post("/transfers/{pair_id}/confirm")
def transfers_confirm(pair_id: int, db: Session = Depends(get_db)):
    pair = db.get(TransferPair, pair_id)
    if not pair:
        raise HTTPException(status_code=404, detail="pair not found")
    pair.confirmed = True
    db.commit()
    return {"id": pair.id, "confirmed": True}


@router.delete("/transfers/{pair_id}")
def transfers_delete(pair_id: int, db: Session = Depends(get_db)):
    """Unpair, and remember the rejection.

    Detection re-runs after every sync, so deleting alone would let the same
    false pair reappear immediately — the review queue would be a treadmill.
    """
    pair = db.get(TransferPair, pair_id)
    if not pair:
        raise HTTPException(status_code=404, detail="pair not found")
    transfer_detector.reject_pair(db, pair.txn_out_id, pair.txn_in_id)
    db.delete(pair)
    db.commit()
    return {"status": "unpaired", "remembered": True}
