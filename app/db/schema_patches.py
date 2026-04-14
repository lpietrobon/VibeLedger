"""Idempotent, lightweight schema patches for an existing SQLite DB.

The project has no migration framework; Base.metadata.create_all handles new
tables but cannot add columns to existing tables. Run on startup after
create_all to keep long-lived single-user DBs in sync without a full drop.
"""
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def _has_column(engine: Engine, table: str, column: str) -> bool:
    insp = inspect(engine)
    if table not in insp.get_table_names():
        return False
    return column in {c["name"] for c in insp.get_columns(table)}


def apply_patches(engine: Engine) -> None:
    if not _has_column(engine, "transaction_annotations", "is_transfer_override"):
        with engine.begin() as conn:
            conn.execute(text(
                "ALTER TABLE transaction_annotations "
                "ADD COLUMN is_transfer_override BOOLEAN DEFAULT 0 NOT NULL"
            ))
