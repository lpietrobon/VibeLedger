from datetime import date, timedelta

from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.main import app
from app.models.models import (
    Account,
    Item,
    Transaction,
    TransactionAnnotation,
    TransferPair,
)
from app.services.security import encrypt_token
from tests.conftest import AUTH_HEADERS


def _seed():
    """A monthly subscription, a one-off purchase, and a transfer pair."""
    with SessionLocal() as db:
        item = Item(plaid_item_id="i-rec", access_token_encrypted=encrypt_token("t"), status="active")
        db.add(item)
        db.flush()
        checking = Account(plaid_account_id="a-rec-chk", item_id=item.id, name="Checking")
        credit = Account(plaid_account_id="a-rec-cc", item_id=item.id, name="Card")
        db.add_all([checking, credit])
        db.flush()

        tx_id = 0

        def add(account, d, amt, name, merchant=None, cat=None):
            nonlocal tx_id
            tx_id += 1
            t = Transaction(
                plaid_transaction_id=f"rec-{tx_id}",
                account_id=account.id,
                item_id=item.id,
                date=d,
                amount=amt,
                name=name,
                merchant_name=merchant,
                plaid_category_primary=cat,
                pending=False,
            )
            db.add(t)
            db.flush()
            return t

        # Monthly subscription across 6 months.
        for k in range(6):
            add(credit, date(2026, 1 + k, 12), 15.99, "SPOTIFY", "Spotify", "ENTERTAINMENT")

        # A single non-recurring purchase.
        add(credit, date(2026, 3, 3), 240.0, "Furniture Store", "Furniture Store", "GENERAL_MERCHANDISE")

        # A credit-card payment transfer pair — must be excluded from recurring.
        out = add(checking, date(2026, 2, 1), 500.0, "CC Payment")
        inn = add(credit, date(2026, 2, 1), -500.0, "CC Payment")
        db.add(TransferPair(txn_out_id=out.id, txn_in_id=inn.id, detected_by="manual", confirmed=True))
        db.commit()


def test_recurring_endpoint_finds_subscription():
    _seed()
    with TestClient(app) as client:
        r = client.get("/analytics/recurring", headers=AUTH_HEADERS, params={"end_date": "2026-06-30"})
    assert r.status_code == 200
    body = r.json()
    labels = {item["merchant_label"]: item for item in body["items"]}

    assert "Spotify" in labels
    spotify = labels["Spotify"]
    assert spotify["cadence"] == "monthly"
    assert spotify["occurrences"] == 6
    assert spotify["average_amount"] == 15.99

    # One-off purchase and the transfer pair must not appear.
    assert "Furniture Store" not in labels
    assert "CC Payment" not in labels

    assert body["summary"]["count"] == 1
    assert body["summary"]["active_monthly_estimate"] == spotify["monthly_estimate"]


def _seed_noisy_descriptors():
    """9 monthly Zelle payments whose raw name carries a per-charge confirmation
    code — the shape that made the drilldown link return a single row."""
    with SessionLocal() as db:
        item = Item(plaid_item_id="i-zelle", access_token_encrypted=encrypt_token("t"), status="active")
        db.add(item)
        db.flush()
        checking = Account(plaid_account_id="a-zelle-chk", item_id=item.id, name="Checking")
        db.add(checking)
        db.flush()

        for k in range(9):
            month = 9 + k  # 2025-10 .. 2026-06
            db.add(
                Transaction(
                    plaid_transaction_id=f"zelle-{k}",
                    account_id=checking.id,
                    item_id=item.id,
                    date=date(2025 + month // 12, month % 12 + 1, 20),
                    # The $1.00 charge is the one whose label used to win.
                    amount=1.0 if k == 0 else 814.25,
                    name=f"Zelle payment to Clara -SF26 JPM{k}9ck4gexd",
                    pending=False,
                )
            )
        db.commit()


def test_recurring_drilldown_query_returns_the_whole_series():
    _seed_noisy_descriptors()
    with TestClient(app) as client:
        body = client.get(
            "/analytics/recurring", headers=AUTH_HEADERS, params={"end_date": "2026-06-30"}
        ).json()
        series = next(i for i in body["items"] if i["merchant_key"] == "zellepaymenttoclara")
        assert series["occurrences"] == 9

        # The drilldown link's query has to reproduce the detector's group.
        assert series["search_query"] == "zelle payment to clara"
        drilldown = client.get(
            "/transactions", headers=AUTH_HEADERS, params={"q": series["search_query"], "limit": 500}
        ).json()
        assert len(drilldown["items"]) == series["occurrences"]

        # The raw sample label carries a suffix unique to one charge; searching
        # it ANDs that suffix in and collapses the series to a single row.
        one_sample = next(t["name"] for t in drilldown["items"] if t["amount"] == 1.0)
        narrowed = client.get(
            "/transactions", headers=AUTH_HEADERS, params={"q": one_sample, "limit": 500}
        ).json()
        assert len(narrowed["items"]) == 1

        # …which is exactly why the label is cleaned up before it is shown.
        assert series["merchant_label"] == "Zelle payment to Clara"


def test_manual_status_override_canceled_and_cleared():
    _seed()
    with TestClient(app) as client:
        before = client.get("/analytics/recurring", headers=AUTH_HEADERS).json()
        spotify = next(i for i in before["items"] if i["merchant_label"] == "Spotify")
        assert spotify["status"] == "active"
        assert spotify["manual_status"] is None
        key = spotify["merchant_key"]  # deterministic: "spotify"

        # Manually mark it canceled → effective status flips, summary drops it.
        set_resp = client.post(
            f"/analytics/recurring/{key}/status",
            json={"status": "canceled"},
            headers=AUTH_HEADERS,
        )
        assert set_resp.status_code == 200

        after = client.get("/analytics/recurring", headers=AUTH_HEADERS).json()
        s2 = next(i for i in after["items"] if i["merchant_key"] == key)
        assert s2["status"] == "inactive"
        assert s2["manual_status"] == "canceled"
        assert s2["auto_status"] == "active"  # the detector still says active
        assert after["summary"]["active_count"] == 0
        assert after["summary"]["active_monthly_estimate"] == 0

        # Only appears under the inactive filter now.
        active_only = client.get("/analytics/recurring", params={"status": "active"}, headers=AUTH_HEADERS).json()
        assert all(i["merchant_key"] != key for i in active_only["items"])

        # Clearing the override restores auto behavior.
        client.post(f"/analytics/recurring/{key}/status", json={"status": "auto"}, headers=AUTH_HEADERS)
        restored = client.get("/analytics/recurring", headers=AUTH_HEADERS).json()
        s3 = next(i for i in restored["items"] if i["merchant_key"] == key)
        assert s3["status"] == "active"
        assert s3["manual_status"] is None


def test_one_sided_transfer_override_no_longer_hides_recurring():
    """The legacy one-sided override is not a transfer and must not suppress
    detection — only a real pair across two covered accounts does that."""
    _seed()
    with SessionLocal() as db:
        spotify_ids = [
            t.id for t in db.query(Transaction).filter(Transaction.merchant_name == "Spotify").all()
        ]
        for tid in spotify_ids:
            db.add(TransactionAnnotation(transaction_id=tid, is_transfer_override=True))
        db.commit()

    with TestClient(app) as client:
        r = client.get("/analytics/recurring", headers=AUTH_HEADERS)
    assert r.status_code == 200
    assert [i["merchant_label"] for i in r.json()["items"]] == ["Spotify"]
