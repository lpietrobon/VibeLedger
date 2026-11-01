"""Read-only-to-repository audit; creates a disposable synthetic database.

Run from the repository root with the project's Python environment. Prints
observations rather than using current implementation output as an oracle.
"""
import json
import os
from pathlib import Path
import sys
import tempfile
from datetime import date

sys.path.insert(0, str(Path.cwd()))

with tempfile.TemporaryDirectory() as tmp:
    os.environ.update(
        DATABASE_URL=f"sqlite:///{tmp}/audit.db",
        TOKEN_ENCRYPTION_KEY="MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=",
        VIBELEDGER_API_TOKEN="audit-synthetic-token",
        PLAID_USE_MOCK="true",
        SYNC_INTERVAL_HOURS="0",
    )
    from fastapi.testclient import TestClient
    from sqlalchemy import text
    from app.api import routes
    from app.db.session import SessionLocal
    from app.main import app
    from app.models.models import Account, Item, Transaction, TransactionAnnotation, TransferPair
    from app.services.security import encrypt_token

    class Clock(date):
        @classmethod
        def today(cls):
            return date(2024, 3, 15)

    routes.date = Clock
    with TestClient(app) as client:
        with SessionLocal() as db:
            item = Item(plaid_item_id="audit", access_token_encrypted=encrypt_token("synthetic"))
            db.add(item)
            db.flush()
            accounts = {}
            for name, kind in [("checking", "depository"), ("card", "credit"), ("payment", "depository")]:
                account = Account(plaid_account_id=name, item_id=item.id, name=name, type=kind, currency="USD")
                db.add(account)
                db.flush()
                accounts[name] = account.id
            rows = [
                ("salary", "checking", -2000, "INCOME", False),
                ("dinner", "card", 120, "FOOD_AND_DRINK", False),
                ("repayment out", "checking", 200, "TRANSFER_OUT", False),
                ("repayment in", "card", -200, "TRANSFER_IN", False),
                ("fund out", "checking", 75, "TRANSFER_OUT", False),
                ("fund in", "payment", -75, "TRANSFER_IN", False),
                ("purchase", "payment", 25, "FOOD_AND_DRINK", False),
                ("refund", "card", -40, "FOOD_AND_DRINK", False),
                ("pending purchase", "card", 999, "FOOD_AND_DRINK", True),
                ("pending income", "checking", -500, "INCOME", True),
            ]
            ids = {}
            for name, account, amount, category, pending in rows:
                txn = Transaction(plaid_transaction_id=name, item_id=item.id, account_id=accounts[account],
                                  name=name, amount=amount, date=date(2024, 3, 5),
                                  plaid_category_primary=category, pending=pending)
                db.add(txn)
                db.flush()
                ids[name] = txn.id
            db.add(TransferPair(txn_out_id=ids["repayment out"], txn_in_id=ids["repayment in"], confirmed=False))
            db.add(TransferPair(txn_out_id=ids["fund out"], txn_in_id=ids["fund in"], confirmed=True))
            db.add(TransactionAnnotation(transaction_id=ids["refund"], refund_status="confirmed"))
            db.commit()
        output = {"expected_posted": {"income": 2200, "expenses": 305, "net": 1895}}
        for endpoint in ["monthly-spend", "category-spend", "cashflow-trend", "overview"]:
            response = client.get("/analytics/" + endpoint, headers={"Authorization": "Bearer audit-synthetic-token"})
            response.raise_for_status()
            output[endpoint] = response.json()
        with SessionLocal() as db:
            output["sql_scope"] = [dict(r) for r in db.execute(text(
                "SELECT et.name, et.amount, et.pending, tp.confirmed AS pair_confirmed "
                "FROM effective_transactions et LEFT JOIN transfer_pairs tp "
                "ON et.id = tp.txn_out_id OR et.id = tp.txn_in_id ORDER BY et.id"
            )).mappings()]
        response = client.get("/transactions", params={"q": "is:spend", "limit": 100},
                              headers={"Authorization": "Bearer audit-synthetic-token"})
        response.raise_for_status()
        output["spend_drilldown_count"] = response.json()["total"]
        print(json.dumps(output, indent=2, default=str))
