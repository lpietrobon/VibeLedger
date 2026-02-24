from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.services.plaid_client import PlaidClient
from app.schemas.plaid import (
    LinkTokenRequest,
    LinkTokenResponse,
    PublicTokenExchangeRequest,
    PublicTokenExchangeResponse,
)
from app.models.models import Item, Transaction, TransactionAnnotation
from app.services.security import encrypt_token
from app.services.sync_service import SyncService

router = APIRouter()


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
def patch_annotation(transaction_id: int, payload: dict, db: Session = Depends(get_db)):
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

    if "user_category" in payload:
        annotation.user_category = payload["user_category"]
    if "notes" in payload:
        annotation.notes = payload["notes"]
    if "reviewed" in payload:
        annotation.reviewed = bool(payload["reviewed"])

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
