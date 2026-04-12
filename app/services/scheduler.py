import asyncio
import logging

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.models import Item
from app.services.sync_service import SyncInProgressError, SyncService

logger = logging.getLogger(__name__)


async def scheduled_sync_loop():
    interval = settings.sync_interval_hours * 3600
    if interval <= 0:
        logger.info("Scheduled sync disabled (SYNC_INTERVAL_HOURS=0)")
        return

    logger.info("Scheduled sync enabled: every %d hours", settings.sync_interval_hours)

    while True:
        await asyncio.sleep(interval)
        logger.info("Starting scheduled sync of all active items")
        await _sync_all_items()


async def _sync_all_items():
    service = SyncService()
    with SessionLocal() as db:
        items = db.query(Item).filter(Item.status == "active").all()
        item_ids = [item.id for item in items]

    for item_id in item_ids:
        try:
            with SessionLocal() as db:
                result = service.sync_item(db, item_id)
                logger.info("Scheduled sync item %d: %s", item_id, result)
        except SyncInProgressError:
            logger.warning("Skipping item %d: sync already in progress", item_id)
        except Exception:
            logger.exception("Scheduled sync failed for item %d", item_id)
