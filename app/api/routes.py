from datetime import date, datetime
import logging
import os
import subprocess
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.services.plaid_client import PlaidClient
from app.schemas.plaid import (
    ConnectCompleteRequest,
    ConnectSessionCreateRequest,
    LinkTokenRequest,
    LinkTokenResponse,
    PublicTokenExchangeRequest,
    PublicTokenExchangeResponse,
    TransactionAnnotationPatchRequest,
)
from app.models.models import ConnectSession, Item, Transaction, TransactionAnnotation
from app.services.security import encrypt_token
from app.services.sync_service import SyncService
from app.services.connect_service import ConnectService

router = APIRouter()
logger = logging.getLogger(__name__)


def _run_connect_tunnel(action: str) -> None:
    """
    Path-scoped Funnel helper.

    If CONNECT_TUNNEL_STRICT=1 (default when automation is enabled), failures
    raise and block the request. If strict is off, failures are logged only.
    """
    if os.getenv("CONNECT_TUNNEL_AUTOMATION", "0") != "1":
        return

    strict = os.getenv("CONNECT_TUNNEL_STRICT", "1") == "1"
    script = os.getenv("CONNECT_TUNNEL_SCRIPT", "./scripts/connect_funnel.sh")
    try:
        proc = subprocess.run(
            [script, action],
            cwd=os.getenv("CONNECT_TUNNEL_CWD", os.getcwd()),
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
def health():
    return {"status": "ok", "service": "vibeledger"}


@router.post("/plaid/link-token/create", response_model=LinkTokenResponse)
def create_link_token(payload: LinkTokenRequest):
    client = PlaidClient()
    resp = client.create_link_token(payload.user_id)
    return LinkTokenResponse(link_token=resp["link_token"])


@router.post("/plaid/public-token/exchange", response_model=PublicTokenExchangeResponse)
def exchange_public_token(payload: PublicTokenExchangeRequest, db: Session = Depends(get_db)):
    client = PlaidClient()
    resp = client.exchange_public_token(payload.public_token)

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

    db.commit()
    return PublicTokenExchangeResponse(item_id=resp["item_id"], status="linked")


@router.post("/connect/sessions")
def create_connect_session(payload: ConnectSessionCreateRequest, db: Session = Depends(get_db)):
    user_id = payload.user_id
    session = ConnectService().create_session(db, user_id=user_id)

    # Open short-lived public path for the connect flow.
    try:
        _run_connect_tunnel("open")
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

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

    client = PlaidClient()
    link_token = client.create_link_token(active.user_id)["link_token"]

    html = f"""
<!doctype html>
<html>
  <head><title>VibeLedger Connect</title></head>
  <body>
    <h3>Connect your account to VibeLedger</h3>
    <button id='link-button'>Connect with Plaid</button>
    <script src='https://cdn.plaid.com/link/v2/stable/link-initialize.js'></script>
    <script>
      const sessionToken = {session!r};
      const handler = Plaid.create({{
        token: {link_token!r},
        onSuccess: async (public_token, metadata) => {{
          const completePath = window.location.pathname.endsWith('/start')
            ? window.location.pathname.slice(0, -6) + '/complete'
            : '/connect/complete';
          const resp = await fetch(completePath, {{
            method: 'POST',
            headers: {{ 'Content-Type': 'application/json' }},
            body: JSON.stringify({{ session_token: sessionToken, public_token }})
          }});
          if (resp.ok) {{
            document.body.innerHTML = '<h3>✅ Account connected. You can return to Discord.</h3>';
          }} else {{
            document.body.innerHTML = '<h3>❌ Failed to connect. Please retry.</h3>';
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
    svc = ConnectService()
    active = svc.get_active_session(db, payload.session_token)
    if not active:
        raise HTTPException(status_code=400, detail="invalid or expired session")

    client = PlaidClient()
    resp = client.exchange_public_token(payload.public_token)

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
    active.completed_at = datetime.utcnow()
    db.commit()

    # Close short-lived public path right after successful token exchange.
    # This is path-scoped, so other Funnel handlers stay up.
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


@router.get("/transactions")
def list_transactions(
    db: Session = Depends(get_db),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    category: str | None = Query(default=None),
):
    q = db.query(Transaction, TransactionAnnotation).outerjoin(
        TransactionAnnotation,
        Transaction.id == TransactionAnnotation.transaction_id,
    )

    if start_date:
        q = q.filter(Transaction.date >= start_date)
    if end_date:
        q = q.filter(Transaction.date <= end_date)
    if category:
        q = q.filter(TransactionAnnotation.user_category == category)

    rows = q.order_by(Transaction.date.desc()).limit(500).all()
    return [
        {
            "id": t.id,
            "plaid_transaction_id": t.plaid_transaction_id,
            "date": str(t.date),
            "amount": float(t.amount),
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
    ]


@router.patch("/transactions/{transaction_id}/annotation")
def patch_annotation(
    transaction_id: int,
    payload: TransactionAnnotationPatchRequest,
    db: Session = Depends(get_db),
):
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
def monthly_spend(db: Session = Depends(get_db)):
    rows = (
        db.query(func.strftime("%Y-%m", Transaction.date), func.sum(Transaction.amount))
        .group_by(func.strftime("%Y-%m", Transaction.date))
        .all()
    )
    return [{"month": month, "spend": float(total)} for month, total in rows]


@router.get("/analytics/category-spend")
def category_spend(db: Session = Depends(get_db)):
    rows = (
        db.query(TransactionAnnotation.user_category, func.sum(Transaction.amount))
        .join(Transaction, Transaction.id == TransactionAnnotation.transaction_id)
        .group_by(TransactionAnnotation.user_category)
        .all()
    )
    return [{"category": c or "uncategorized", "spend": float(total)} for c, total in rows]


@router.get("/analytics/cashflow-trend")
def cashflow_trend(db: Session = Depends(get_db)):
    rows = (
        db.query(func.strftime("%Y-%m", Transaction.date), func.sum(Transaction.amount))
        .group_by(func.strftime("%Y-%m", Transaction.date))
        .all()
    )
    out = []
    for month, total in rows:
        total = float(total)
        out.append(
            {
                "month": month,
                "expenses": abs(total) if total > 0 else 0.0,
                "income": abs(total) if total < 0 else 0.0,
                "net": -total,
            }
        )
    return out
