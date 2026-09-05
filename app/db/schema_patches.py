"""Idempotent, lightweight schema patches for an existing SQLite DB.

The project has no migration framework; Base.metadata.create_all handles new
tables but cannot add columns to existing tables. Run on startup after
create_all to keep long-lived single-user DBs in sync without a full drop.
"""
from datetime import date

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


def _backfill_txn_hashes(engine: Engine) -> None:
    from app.services.txn_fingerprint import compute_txn_hash

    with engine.begin() as conn:
        rows = conn.execute(text(
            "SELECT t.id, t.date, t.amount, t.name, a.mask "
            "FROM transactions t "
            "LEFT JOIN accounts a ON a.id = t.account_id "
            "ORDER BY t.id"
        )).fetchall()

        seen: dict[str, int] = {}
        for row in rows:
            txn_date = row.date if isinstance(row.date, date) else date.fromisoformat(row.date)
            h = compute_txn_hash(row.mask, txn_date, row.amount, row.name)
            occurrence = seen.get(h, 0)
            seen[h] = occurrence + 1
            conn.execute(
                text("UPDATE transactions SET txn_hash = :h, txn_occurrence = :occ WHERE id = :id"),
                {"h": h, "occ": occurrence, "id": row.id},
            )


def _purge_orphan_transaction_rows(engine: Engine) -> None:
    """Delete rows left pointing at transactions that no longer exist.

    Historic syncs deleted removed transactions without cleaning up their
    dependents (nothing cascades here), leaving annotations that no join can
    reach but a bare COUNT still finds — e.g. Overview's "likely refunds"
    reporting rows the Transactions screen could never show. Orphans are also a
    correctness hazard: SQLite reuses rowids, so a stale annotation can latch
    onto an unrelated future transaction. Manual edits survive in
    annotation_fingerprints, so nothing the user typed is lost here.
    """
    insp = inspect(engine)
    tables = set(insp.get_table_names())
    if "transactions" not in tables:
        return

    with engine.begin() as conn:
        if "transaction_annotations" in tables:
            conn.execute(text(
                "DELETE FROM transaction_annotations WHERE transaction_id NOT IN "
                "(SELECT id FROM transactions)"
            ))
            conn.execute(text(
                "UPDATE transaction_annotations "
                "SET refund_status = NULL, refund_match_transaction_id = NULL, "
                "    refund_reason = NULL "
                "WHERE refund_match_transaction_id IS NOT NULL "
                "  AND refund_match_transaction_id NOT IN (SELECT id FROM transactions)"
            ))
        if "transfer_pairs" in tables:
            conn.execute(text(
                "DELETE FROM transfer_pairs WHERE txn_out_id NOT IN (SELECT id FROM transactions) "
                "   OR txn_in_id NOT IN (SELECT id FROM transactions)"
            ))
        if "category_decision_events" in tables:
            conn.execute(text(
                "DELETE FROM category_decision_events WHERE transaction_id NOT IN "
                "(SELECT id FROM transactions)"
            ))


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

    if not _has_column(engine, "transaction_annotations", "merchant_name_override"):
        with engine.begin() as conn:
            conn.execute(text(
                "ALTER TABLE transaction_annotations "
                "ADD COLUMN merchant_name_override VARCHAR(255)"
            ))

    if not _has_column(engine, "transaction_annotations", "refund_status"):
        with engine.begin() as conn:
            conn.execute(text(
                "ALTER TABLE transaction_annotations ADD COLUMN refund_status VARCHAR(32)"
            ))

    if not _has_column(engine, "transaction_annotations", "refund_match_transaction_id"):
        with engine.begin() as conn:
            conn.execute(text(
                "ALTER TABLE transaction_annotations "
                "ADD COLUMN refund_match_transaction_id INTEGER REFERENCES transactions(id)"
            ))

    if not _has_column(engine, "transaction_annotations", "refund_reason"):
        with engine.begin() as conn:
            conn.execute(text(
                "ALTER TABLE transaction_annotations ADD COLUMN refund_reason VARCHAR(255)"
            ))

    if not _has_column(engine, "annotation_fingerprints", "refund_status"):
        with engine.begin() as conn:
            conn.execute(text(
                "ALTER TABLE annotation_fingerprints ADD COLUMN refund_status VARCHAR(32)"
            ))

    if not _has_column(engine, "accounts", "nickname"):
        with engine.begin() as conn:
            conn.execute(text(
                "ALTER TABLE accounts ADD COLUMN nickname VARCHAR(255)"
            ))

    if not _has_column(engine, "transactions", "txn_hash"):
        with engine.begin() as conn:
            conn.execute(text(
                "ALTER TABLE transactions ADD COLUMN txn_hash VARCHAR(16)"
            ))

    if not _has_column(engine, "transactions", "txn_occurrence"):
        with engine.begin() as conn:
            conn.execute(text(
                "ALTER TABLE transactions ADD COLUMN txn_occurrence INTEGER"
            ))

    if not _has_index(engine, "transactions", "ix_transactions_txn_hash"):
        with engine.begin() as conn:
            conn.execute(text(
                "CREATE INDEX ix_transactions_txn_hash ON transactions(txn_hash)"
            ))

    with engine.connect() as conn:
        unhashed = conn.execute(text(
            "SELECT COUNT(*) FROM transactions WHERE txn_hash IS NULL"
        )).scalar()
    if unhashed:
        _backfill_txn_hashes(engine)

    # effective_transactions view — single canonical source for all COALESCE
    # definitions. Recreated on every startup (safe: views hold no data). The
    # Plaid->friendly category CASE is generated from the shared PLAID_FRIENDLY_MAP
    # (app/services/category_resolver.py) so the view and the API agree.
    from app.services.category_resolver import PLAID_DETAILED_FRIENDLY_MAP, PLAID_FRIENDLY_MAP

    friendly_when = "".join(
        f"WHEN '{plaid}' THEN '{friendly}' " for plaid, friendly in PLAID_FRIENDLY_MAP.items()
    )
    detailed_friendly_when = "".join(
        f"WHEN '{plaid}' THEN '{friendly}' "
        for plaid, friendly in PLAID_DETAILED_FRIENDLY_MAP.items()
    )
    with engine.begin() as conn:
        conn.execute(text("DROP VIEW IF EXISTS effective_transactions"))
        conn.execute(text(f"""
            CREATE VIEW effective_transactions AS
            WITH categorized AS (
            SELECT
                t.id,
                t.plaid_transaction_id,
                t.account_id,
                t.item_id,
                t.date,
                t.amount,
                t.name,
                t.merchant_name,
                t.pending,
                t.plaid_category_primary,
                json_extract(t.raw_json, '$.personal_finance_category.detailed')
                    AS plaid_category_detailed,
                COALESCE(ta.user_category, ta.rule_category,
                    CASE json_extract(t.raw_json, '$.personal_finance_category.detailed')
                        {detailed_friendly_when}
                        ELSE NULL
                    END,
                    CASE t.plaid_category_primary
                    {friendly_when}
                    ELSE t.plaid_category_primary
                    END,
                    'uncategorized'
                ) AS base_category,
                COALESCE(ta.merchant_name_override, t.merchant_name)
                    AS effective_merchant,
                COALESCE(a.nickname, a.name || ' \xb7\xb7' || a.mask)
                    AS effective_account_name,
                COALESCE(ta.is_transfer_override, 0) AS is_transfer_override,
                ta.refund_status,
                ta.refund_match_transaction_id,
                ta.refund_reason,
                CASE WHEN t.amount < 0 AND ta.refund_status IN ('confirmed', 'likely') THEN 1 ELSE 0 END
                    AS is_refund,
                EXISTS (SELECT 1 FROM transfer_pairs p WHERE p.confirmed = 1
                    AND (p.txn_out_id = t.id OR p.txn_in_id = t.id)) AS is_transfer,
                EXISTS (SELECT 1 FROM transfer_pairs p WHERE p.confirmed = 0
                    AND (p.txn_out_id = t.id OR p.txn_in_id = t.id)) AS is_transfer_candidate,
                ta.merchant_name_override,
                ta.user_category,
                ta.rule_category,
                ta.rule_id,
                ta.notes,
                COALESCE(ta.reviewed, 0) AS reviewed,
                a.name      AS account_name,
                a.nickname  AS account_nickname,
                a.mask,
                a.type      AS account_type,
                a.subtype   AS account_subtype
            FROM transactions t
            LEFT JOIN transaction_annotations ta ON ta.transaction_id = t.id
            LEFT JOIN accounts a ON a.id = t.account_id
            ), effective AS (
                SELECT c.*,
                    COALESCE(c.user_category,
                        CASE WHEN c.is_refund = 1 AND original.amount > 0
                            THEN original.base_category END,
                        c.base_category) AS effective_category
                FROM categorized c
                LEFT JOIN categorized original ON original.id = c.refund_match_transaction_id
            )
            SELECT effective.*,
                CASE WHEN pending = 0 AND is_transfer = 0 AND (amount > 0 OR is_refund = 1)
                    THEN amount ELSE 0 END AS expense_amount,
                CASE WHEN pending = 0 AND is_transfer = 0 AND amount < 0 AND is_refund = 0
                    THEN -amount ELSE 0 END AS income_amount
            FROM effective
        """))

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

    if not _has_index(engine, "transaction_annotations", "ix_transaction_annotations_refund_match_transaction_id"):
        with engine.begin() as conn:
            conn.execute(text(
                "CREATE INDEX ix_transaction_annotations_refund_match_transaction_id "
                "ON transaction_annotations(refund_match_transaction_id)"
            ))

    if not _has_index(engine, "category_decision_events", "ix_category_decision_events_transaction_changed_at"):
        with engine.begin() as conn:
            conn.execute(text(
                "CREATE INDEX ix_category_decision_events_transaction_changed_at "
                "ON category_decision_events(transaction_id, changed_at)"
            ))

    _purge_orphan_transaction_rows(engine)
