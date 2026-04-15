from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

import pandas as pd
import streamlit as st

from dashboard_lib import (
    DEFAULT_API,
    DEFAULT_DB,
    api_delete,
    api_get,
    api_patch,
    api_post,
    extract_error_message,
    load_accounts,
    load_transactions,
)

st.set_page_config(page_title="Rules", layout="wide")
st.title("Category rules")
st.caption("Manage rule stack order, simulate impacts, and apply rule decisions.")


def _list_rules(api_base: str) -> list[dict]:
    resp = api_get("/category-rules", base=api_base)
    if not resp.ok:
        st.error(f"Failed to load rules: {resp.status_code} {extract_error_message(resp)}")
        return []
    items = resp.json().get("items", [])
    return sorted(items, key=lambda r: (r.get("rank", 0), r.get("id", 0)))


def _patch_rule(rule_id: int, payload: dict, api_base: str) -> bool:
    resp = api_patch(f"/category-rules/{rule_id}", json=payload, base=api_base)
    if not resp.ok:
        st.error(f"Update failed ({resp.status_code}): {extract_error_message(resp)}")
        return False
    st.success(f"Rule #{rule_id} updated.")
    st.cache_data.clear()
    return True


def _renumber_rules(order: list[int], api_base: str) -> bool:
    for idx, rule_id in enumerate(order, start=1):
        resp = api_patch(f"/category-rules/{rule_id}", json={"rank": idx}, base=api_base)
        if not resp.ok:
            st.error(f"Reorder failed for rule #{rule_id}: {resp.status_code} {extract_error_message(resp)}")
            return False
    st.success("Rule order updated.")
    st.cache_data.clear()
    return True


def _to_decimal_or_none(raw: str):
    raw = raw.strip()
    if not raw:
        return None
    try:
        return Decimal(raw)
    except InvalidOperation:
        return "invalid"


def _draft_from_state() -> dict:
    return {
        "rank": int(st.session_state.get("rule_rank", 0)),
        "enabled": bool(st.session_state.get("rule_enabled", True)),
        "description_regex": (st.session_state.get("rule_description_regex", "") or "").strip() or None,
        "account_name_regex": (st.session_state.get("rule_account_regex", "") or "").strip() or None,
        "min_amount": _to_decimal_or_none(st.session_state.get("rule_min_amount", "")),
        "max_amount": _to_decimal_or_none(st.session_state.get("rule_max_amount", "")),
        "assigned_category": (st.session_state.get("rule_assigned_category", "") or "").strip(),
        "name": (st.session_state.get("rule_name", "") or "").strip() or None,
    }


def _default_scope_from_transactions(txns: pd.DataFrame):
    if txns.empty:
        today = date.today()
        return today - timedelta(days=90), today
    return txns["date"].min(), txns["date"].max()


def _scope_payload(start_d, end_d, selected_account_ids: list[int], include_pending: bool) -> dict:
    return {
        "start_date": str(start_d) if start_d else None,
        "end_date": str(end_d) if end_d else None,
        "account_ids": selected_account_ids,
        "include_pending": include_pending,
    }


def _pick_preview_payload(editing_rule_id: int | None, scope: dict) -> dict | None:
    draft = _draft_from_state()
    if draft["min_amount"] == "invalid" or draft["max_amount"] == "invalid":
        st.error("Amount bounds must be valid decimal numbers.")
        return None

    preview_payload: dict = {"scope": scope, "sample_limit": 200}
    if editing_rule_id:
        preview_payload["rule_id"] = editing_rule_id
    preview_payload["draft_rule"] = draft
    return preview_payload


def _render_conditions(rule: dict) -> str:
    conds = []
    if rule.get("description_regex"):
        conds.append(f"desc~/{rule['description_regex']}/")
    if rule.get("account_name_regex"):
        conds.append(f"acct~/{rule['account_name_regex']}/")
    if rule.get("min_amount") is not None:
        conds.append(f"min≥{rule['min_amount']}")
    if rule.get("max_amount") is not None:
        conds.append(f"max≤{rule['max_amount']}")
    return ", ".join(conds) if conds else "(no conditions)"


def _hydrate_editor(rule: dict):
    st.session_state["editing_rule_id"] = int(rule["id"])
    st.session_state["rule_rank"] = int(rule.get("rank", 0))
    st.session_state["rule_enabled"] = bool(rule.get("enabled", True))
    st.session_state["rule_description_regex"] = rule.get("description_regex") or ""
    st.session_state["rule_account_regex"] = rule.get("account_name_regex") or ""
    st.session_state["rule_min_amount"] = "" if rule.get("min_amount") is None else str(rule["min_amount"])
    st.session_state["rule_max_amount"] = "" if rule.get("max_amount") is None else str(rule["max_amount"])
    st.session_state["rule_assigned_category"] = rule.get("assigned_category") or ""
    st.session_state["rule_name"] = rule.get("name") or ""


def _reset_editor():
    st.session_state["editing_rule_id"] = None
    st.session_state["rule_rank"] = 0
    st.session_state["rule_enabled"] = True
    st.session_state["rule_description_regex"] = ""
    st.session_state["rule_account_regex"] = ""
    st.session_state["rule_min_amount"] = ""
    st.session_state["rule_max_amount"] = ""
    st.session_state["rule_assigned_category"] = ""
    st.session_state["rule_name"] = ""


db_path = st.sidebar.text_input("DB path", DEFAULT_DB, key="db_path")
api_base = st.sidebar.text_input("API base", DEFAULT_API, key="api_base")

try:
    txns = load_transactions(db_path)
except Exception as e:
    st.error(f"Failed to load transactions from DB: {e}")
    st.stop()

accounts_df = load_accounts(db_path)
rules = _list_rules(api_base)

if "editing_rule_id" not in st.session_state:
    _reset_editor()

st.subheader("Rule stack")
if not rules:
    st.info("No rules yet. Create one in the editor below.")
else:
    stack_rows = [
        {
            "ID": int(r["id"]),
            "rank": int(r.get("rank", 0)),
            "enabled": bool(r.get("enabled", False)),
            "conditions": _render_conditions(r),
            "assigned category": r.get("assigned_category", ""),
        }
        for r in rules
    ]
    st.dataframe(pd.DataFrame(stack_rows), hide_index=True, use_container_width=True)

    ordered_ids = [int(r["id"]) for r in rules]
    for idx, rule in enumerate(rules):
        c1, c2, c3, c4, c5, c6 = st.columns([2.2, 1, 1, 1, 1, 1])
        with c1:
            st.caption(
                f"#{rule['id']} · rank={rule['rank']} · {'enabled' if rule['enabled'] else 'disabled'} · {rule.get('name') or 'unnamed'}"
            )
        with c2:
            if st.button("↑", key=f"up_{rule['id']}", disabled=idx == 0):
                reordered = ordered_ids.copy()
                reordered[idx - 1], reordered[idx] = reordered[idx], reordered[idx - 1]
                if _renumber_rules(reordered, api_base):
                    st.rerun()
        with c3:
            if st.button("↓", key=f"down_{rule['id']}", disabled=idx == len(rules) - 1):
                reordered = ordered_ids.copy()
                reordered[idx], reordered[idx + 1] = reordered[idx + 1], reordered[idx]
                if _renumber_rules(reordered, api_base):
                    st.rerun()
        with c4:
            if st.button("Edit", key=f"edit_{rule['id']}"):
                _hydrate_editor(rule)
                st.rerun()
        with c5:
            if st.button("Toggle", key=f"toggle_{rule['id']}"):
                if _patch_rule(int(rule["id"]), {"enabled": not bool(rule.get("enabled", True))}, api_base):
                    st.rerun()
        with c6:
            if st.button("Delete", key=f"delete_{rule['id']}"):
                resp = api_delete(f"/category-rules/{int(rule['id'])}", base=api_base)
                if resp.ok:
                    st.success(f"Deleted rule #{rule['id']}.")
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error(f"Delete failed ({resp.status_code}): {extract_error_message(resp)}")

st.divider()
st.subheader("Rule editor")

edit_id = st.session_state.get("editing_rule_id")
if edit_id:
    st.info(f"Editing rule #{edit_id}")

with st.form("rule_editor"):
    st.number_input("Rank", key="rule_rank", step=1)
    st.checkbox("Enabled", key="rule_enabled")
    st.text_input("Rule name", key="rule_name", placeholder="Optional label")
    st.text_input("Description regex", key="rule_description_regex", placeholder="e.g. starbucks|coffee")
    st.text_input("Account regex", key="rule_account_regex", placeholder="e.g. checking|visa")
    st.text_input("Min amount", key="rule_min_amount", placeholder="Optional decimal")
    st.text_input("Max amount", key="rule_max_amount", placeholder="Optional decimal")
    st.text_input("Assigned category *", key="rule_assigned_category", placeholder="coffee")

    col_save, col_new = st.columns(2)
    submit = col_save.form_submit_button("Save rule")
    new_rule = col_new.form_submit_button("Start new")

if new_rule:
    _reset_editor()
    st.rerun()

if submit:
    draft = _draft_from_state()
    hints = []
    if not draft["assigned_category"]:
        hints.append("Assigned category is required.")
    if draft["min_amount"] == "invalid" or draft["max_amount"] == "invalid":
        hints.append("Min/max amount must be valid decimals.")
    if draft["min_amount"] not in (None, "invalid") and draft["max_amount"] not in (None, "invalid"):
        if draft["min_amount"] > draft["max_amount"]:
            hints.append("Min amount cannot be greater than max amount.")
    if not any([draft["description_regex"], draft["account_name_regex"], draft["min_amount"], draft["max_amount"]]):
        st.warning("Hint: this rule has no conditions and could match all transactions.")

    if hints:
        for h in hints:
            st.warning(h)
    else:
        payload = {
            "rank": draft["rank"],
            "enabled": draft["enabled"],
            "description_regex": draft["description_regex"],
            "account_name_regex": draft["account_name_regex"],
            "min_amount": str(draft["min_amount"]) if draft["min_amount"] is not None else None,
            "max_amount": str(draft["max_amount"]) if draft["max_amount"] is not None else None,
            "assigned_category": draft["assigned_category"],
            "name": draft["name"],
        }
        if edit_id:
            resp = api_patch(f"/category-rules/{int(edit_id)}", json=payload, base=api_base)
        else:
            resp = api_post("/category-rules", json=payload, base=api_base)

        if resp.ok:
            st.success("Rule saved.")
            st.cache_data.clear()
            if not edit_id:
                _reset_editor()
            st.rerun()
        else:
            st.error(f"Server validation failed ({resp.status_code}): {extract_error_message(resp)}")

st.divider()
st.subheader("Test panel")

scope_min, scope_max = _default_scope_from_transactions(txns)
scope_start, scope_end = st.date_input(
    "Scope date range",
    value=(scope_min, scope_max),
    min_value=scope_min,
    max_value=scope_max,
    key="rule_scope_date",
)

account_options = []
if not accounts_df.empty:
    account_options = [
        {
            "id": int(row["id"]),
            "label": f"#{int(row['id'])} {row.get('name') or 'Unknown'}",
        }
        for _, row in accounts_df.sort_values("name").iterrows()
    ]
selected_account_labels = st.multiselect(
    "Scope accounts",
    options=[a["label"] for a in account_options],
    default=[a["label"] for a in account_options],
)
selected_account_ids = [a["id"] for a in account_options if a["label"] in selected_account_labels]

include_pending = st.checkbox("Include pending", value=True, key="rule_include_pending")
text_filter = st.text_input("Result text filter (name contains)", key="rule_result_text")
result_min_amount = st.number_input("Result min amount", value=0.0, step=1.0)
result_max_amount = st.number_input("Result max amount", value=999999.0, step=1.0)

if st.button("Run preview endpoint"):
    scope = _scope_payload(scope_start, scope_end, selected_account_ids, include_pending)
    preview_payload = _pick_preview_payload(edit_id, scope)
    if preview_payload:
        resp = api_post("/category-rules/preview", json=preview_payload, base=api_base)
        if not resp.ok:
            st.error(f"Preview failed ({resp.status_code}): {extract_error_message(resp)}")
        else:
            st.session_state["preview_result"] = resp.json()
            st.success("Preview complete.")

preview_result = st.session_state.get("preview_result")
if preview_result:
    st.write(
        f"Scanned: {preview_result.get('total_scanned', 0)} · "
        f"Would change: {preview_result.get('would_change_count', 0)}"
    )

    samples = preview_result.get("samples", [])
    samples_df = pd.DataFrame(samples)
    if samples_df.empty:
        st.info("No changed transactions found in preview scope.")
    else:
        tx_lookup = txns[["id", "account_name"]].drop_duplicates(subset=["id"]).rename(columns={"id": "transaction_id"})
        samples_df = samples_df.merge(tx_lookup, on="transaction_id", how="left")
        if text_filter.strip():
            samples_df = samples_df[samples_df["name"].fillna("").str.contains(text_filter.strip(), case=False)]
        samples_df = samples_df[(samples_df["amount"] >= result_min_amount) & (samples_df["amount"] <= result_max_amount)]
        samples_df["changed"] = samples_df["current_effective_category"] != samples_df["simulated_effective_category"]
        diff_cols = {
            "transaction_id": "transaction id",
            "date": "date",
            "name": "name",
            "account_name": "account",
            "current_effective_category": "current effective category",
            "simulated_effective_category": "simulated category",
            "changed": "changed flag",
        }
        st.dataframe(samples_df[list(diff_cols.keys())].rename(columns=diff_cols), hide_index=True, use_container_width=True)

st.divider()
st.subheader("Apply panel")

if st.button("Dry-run apply"):
    scope = _scope_payload(scope_start, scope_end, selected_account_ids, include_pending)
    resp = api_post("/category-rules/apply", json={"dry_run": True, "scope": scope}, base=api_base)
    if resp.ok:
        st.session_state["apply_dry_run"] = resp.json()
        st.success("Dry-run complete.")
    else:
        st.error(f"Dry-run failed ({resp.status_code}): {extract_error_message(resp)}")

last_dry_run = st.session_state.get("apply_dry_run")
if last_dry_run:
    st.write(
        f"Dry-run summary → scanned: {last_dry_run.get('total_scanned', 0)}, "
        f"would change: {last_dry_run.get('would_change_count', 0)}"
    )

if st.button("Confirm apply"):
    if not st.session_state.get("apply_dry_run"):
        st.warning("Run dry-run apply before confirm apply.")
    else:
        scope = _scope_payload(scope_start, scope_end, selected_account_ids, include_pending)
        resp = api_post("/category-rules/apply", json={"dry_run": False, "scope": scope}, base=api_base)
        if resp.ok:
            body = resp.json()
            st.success(
                "Apply completed. "
                f"Scanned={body.get('total_scanned', 0)}, "
                f"Changed={body.get('would_change_count', 0)}, "
                f"Updated={body.get('updated_count', 0)}, "
                f"Events={body.get('event_count', 0)}"
            )
            st.session_state["apply_result"] = body
            st.cache_data.clear()
        else:
            st.error(f"Apply failed ({resp.status_code}): {extract_error_message(resp)}")

if st.session_state.get("apply_result"):
    run = st.session_state["apply_result"]
    st.json(
        {
            "total_scanned": run.get("total_scanned"),
            "would_change_count": run.get("would_change_count"),
            "updated_count": run.get("updated_count"),
            "event_count": run.get("event_count"),
        }
    )
