from datetime import date
from pathlib import Path
import logging
import json
import os
import subprocess

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy import case, func, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.time import utcnow
from app.db.session import SessionLocal
from app.services.plaid_client import PlaidClient
from app.models.models import ConnectSession, Item, Transaction, TransactionAnnotation
from app.schemas.plaid import ConnectCompleteRequest, CreateConnectSessionRequest, PatchAnnotationRequest
from app.services.security import encrypt_token
from app.services.sync_service import SyncInProgressError, SyncService
from app.services.connect_service import ConnectService

router = APIRouter()
logger = logging.getLogger(__name__)

_CONNECT_TUNNEL_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "connect_funnel.sh"


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


@router.get("/transactions")
def list_transactions(
    db: Session = Depends(get_db),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    category: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    effective_category = func.coalesce(
        TransactionAnnotation.user_category,
        Transaction.plaid_category_primary,
    )

    base = db.query(Transaction, TransactionAnnotation).outerjoin(
        TransactionAnnotation,
        Transaction.id == TransactionAnnotation.transaction_id,
    )

    if start_date:
        base = base.filter(Transaction.date >= start_date)
    if end_date:
        base = base.filter(Transaction.date <= end_date)
    if category:
        base = base.filter(effective_category == category)

    total = base.with_entities(func.count(Transaction.id)).scalar()
    rows = (
        base.order_by(Transaction.date.desc(), Transaction.id.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )
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
                "pending": t.pending,
                "annotation": {
                    "user_category": a.user_category if a else None,
                    "notes": a.notes if a else None,
                    "reviewed": a.reviewed if a else False,
                },
            }
            for t, a in rows
        ],
    }


@router.patch("/transactions/{transaction_id}/annotation")
def patch_annotation(transaction_id: int, payload: PatchAnnotationRequest, db: Session = Depends(get_db)):
    tx = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not tx:
        raise HTTPException(status_code=404, detail="transaction not found")

    annotation = (
        db.query(TransactionAnnotation)
        .filter(TransactionAnnotation.transaction_id == transaction_id)
        .first()
    )
    if not annotation:
        annotation = TransactionAnnotation(transaction_id=transaction_id)
        db.add(annotation)

    if payload.user_category is not None:
        annotation.user_category = payload.user_category
    if payload.notes is not None:
        annotation.notes = payload.notes
    if payload.reviewed is not None:
        annotation.reviewed = payload.reviewed

    db.commit()
    return {"status": "ok", "transaction_id": transaction_id}


@router.get("/analytics/monthly-spend")
def monthly_spend(
    db: Session = Depends(get_db),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
):
    month_col = func.strftime("%Y-%m", Transaction.date).label("month")
    q = db.query(
        month_col,
        func.sum(case((Transaction.amount > 0, Transaction.amount), else_=0)),
    )
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
):
    effective_category = func.coalesce(
        TransactionAnnotation.user_category,
        Transaction.plaid_category_primary,
        "uncategorized",
    ).label("category")
    q = (
        db.query(
            effective_category,
            func.sum(case((Transaction.amount > 0, Transaction.amount), else_=0)),
        )
        .outerjoin(TransactionAnnotation, Transaction.id == TransactionAnnotation.transaction_id)
    )
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
):
    month_col = func.strftime("%Y-%m", Transaction.date).label("month")
    q = db.query(
        month_col,
        func.sum(case((Transaction.amount > 0, Transaction.amount), else_=0)).label("expenses"),
        func.sum(case((Transaction.amount < 0, -Transaction.amount), else_=0)).label("income"),
    )
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
