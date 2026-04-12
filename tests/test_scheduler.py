import asyncio

from app.db.session import SessionLocal
from app.models.models import Item, SyncRun
from app.services.security import encrypt_token
from app.services.scheduler import _sync_all_items


def test_sync_all_items_syncs_active_items():
    with SessionLocal() as db:
        item1 = Item(plaid_item_id="sched-1", access_token_encrypted=encrypt_token("tok"), status="active")
        item2 = Item(plaid_item_id="sched-2", access_token_encrypted=encrypt_token("tok"), status="active")
        inactive = Item(plaid_item_id="sched-3", access_token_encrypted=encrypt_token("tok"), status="inactive")
        db.add_all([item1, item2, inactive])
        db.commit()

    asyncio.run(_sync_all_items())

    with SessionLocal() as db:
        runs = db.query(SyncRun).all()
        synced_item_ids = {r.item_id for r in runs}
        # Both active items should have been synced
        active_ids = {
            db.query(Item).filter(Item.plaid_item_id == "sched-1").first().id,
            db.query(Item).filter(Item.plaid_item_id == "sched-2").first().id,
        }
        assert synced_item_ids == active_ids
        assert all(r.status == "success" for r in runs)


def test_sync_all_items_continues_after_failure():
    """If one item fails, the rest should still sync."""
    with SessionLocal() as db:
        # Item with bad encrypted token will fail during sync
        bad = Item(plaid_item_id="sched-bad", access_token_encrypted="not-a-valid-fernet-token", status="active")
        good = Item(plaid_item_id="sched-good", access_token_encrypted=encrypt_token("tok"), status="active")
        db.add_all([bad, good])
        db.commit()
        bad_id = bad.id
        good_id = good.id

    asyncio.run(_sync_all_items())

    with SessionLocal() as db:
        bad_run = db.query(SyncRun).filter(SyncRun.item_id == bad_id).first()
        good_run = db.query(SyncRun).filter(SyncRun.item_id == good_id).first()
        assert bad_run.status == "error"
        assert good_run.status == "success"
