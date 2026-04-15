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


def _has_index(engine: Engine, table: str, index_name: str) -> bool:
    insp = inspect(engine)
    if table not in insp.get_table_names():
        return False
    return index_name in {idx["name"] for idx in insp.get_indexes(table)}


def apply_patches(engine: Engine) -> None:
    if not _has_column(engine, "transaction_annotations", "is_transfer_override"):
        with engine.begin() as conn:
            conn.execute(text(
                "ALTER TABLE transaction_annotations "
                "ADD COLUMN is_transfer_override BOOLEAN DEFAULT 0 NOT NULL"
            ))

    if not _has_column(engine, "transaction_annotations", "rule_category"):
        with engine.begin() as conn:
            conn.execute(text(
                "ALTER TABLE transaction_annotations "
                "ADD COLUMN rule_category VARCHAR(128)"
            ))

    if not _has_column(engine, "transaction_annotations", "rule_id"):
        with engine.begin() as conn:
            conn.execute(text(
                "ALTER TABLE transaction_annotations "
                "ADD COLUMN rule_id INTEGER REFERENCES category_rules(id)"
            ))

    if not _has_column(engine, "transaction_annotations", "rule_evaluated_at"):
        with engine.begin() as conn:
            conn.execute(text(
                "ALTER TABLE transaction_annotations "
                "ADD COLUMN rule_evaluated_at DATETIME"
            ))

    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE IF NOT EXISTS category_rules ("
            "id INTEGER PRIMARY KEY, "
            "rank INTEGER DEFAULT 0 NOT NULL, "
            "enabled BOOLEAN DEFAULT 1 NOT NULL, "
            "description_regex VARCHAR(255), "
            "account_name_regex VARCHAR(255), "
            "min_amount NUMERIC(12, 2), "
            "max_amount NUMERIC(12, 2), "
            "assigned_category VARCHAR(128) NOT NULL, "
            "name VARCHAR(255), "
            "created_at DATETIME, "
            "updated_at DATETIME"
            ")"
        ))
        conn.execute(text(
            "CREATE TABLE IF NOT EXISTS category_decision_events ("
            "id INTEGER PRIMARY KEY, "
            "transaction_id INTEGER NOT NULL REFERENCES transactions(id), "
            "old_effective_category VARCHAR(128), "
            "new_effective_category VARCHAR(128) NOT NULL, "
            "source VARCHAR(32) NOT NULL, "
            "rule_id INTEGER REFERENCES category_rules(id), "
            "changed_at DATETIME, "
            "metadata_json TEXT"
            ")"
        ))

    if not _has_index(engine, "category_rules", "ix_category_rules_enabled_rank"):
        with engine.begin() as conn:
            conn.execute(text(
                "CREATE INDEX ix_category_rules_enabled_rank "
                "ON category_rules(enabled, rank)"
            ))

    if not _has_index(engine, "transaction_annotations", "ix_transaction_annotations_rule_id"):
        with engine.begin() as conn:
            conn.execute(text(
                "CREATE INDEX ix_transaction_annotations_rule_id "
                "ON transaction_annotations(rule_id)"
            ))

    if not _has_index(engine, "category_decision_events", "ix_category_decision_events_transaction_changed_at"):
        with engine.begin() as conn:
            conn.execute(text(
                "CREATE INDEX ix_category_decision_events_transaction_changed_at "
                "ON category_decision_events(transaction_id, changed_at)"
            ))
