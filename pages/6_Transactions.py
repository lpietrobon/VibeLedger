from __future__ import annotations

import streamlit as st

from dashboard_lib import (
    DEFAULT_DB,
    api_patch,
    apply_filters,
    apply_transaction_filter_tokens,
    compact_page,
    extract_error_message,
    load_transactions,
    parse_transaction_filter_query,
    render_annotation_editor,
    render_app_navigation,
    sidebar_filters,
    tech_sidebar,
)

st.set_page_config(page_title="Transactions – VibeLedger", layout="wide")
compact_page()
render_app_navigation()
st.title("Transactions")

try:
    df = load_transactions(st.session_state.get("db_path") or DEFAULT_DB)
except Exception as exc:
    st.error(f"Could not load transactions: {exc}")
    st.stop()

db_path, start_d, end_d, accounts, exclude_transfers = sidebar_filters(df)
_, api_base = tech_sidebar()
base = apply_filters(df, start_d, end_d, accounts, exclude_transfers)

if "tx_filters" not in st.session_state:
    st.session_state.tx_filters = []
if "tx_search_counter" not in st.session_state:
    st.session_state.tx_search_counter = 0


def on_search_submit() -> None:
    key = f"tx_search_{st.session_state.tx_search_counter}"
    raw = st.session_state.get(key, "").strip()
    if raw:
        st.session_state.tx_filters.extend(parse_transaction_filter_query(raw))
        st.session_state.tx_search_counter += 1


search_col, filter_col = st.columns([5, 1])
with search_col:
    st.text_input(
        "Search transactions",
        label_visibility="collapsed",
        placeholder="Search merchant or use filters: cat:Food  >500  from:2026-05  uncat",
        key=f"tx_search_{st.session_state.tx_search_counter}",
        on_change=on_search_submit,
    )

with filter_col:
    with st.popover("Filters", use_container_width=True):
        review_filter = st.selectbox(
            "Review status",
            ["All", "Needs review", "Reviewed"],
            key="tx_review_filter",
        )
        category_values = (
            base["effective_category"]
            .fillna("Uncategorized")
            .astype(str)
            .str.split("/")
            .str[0]
            .str.strip()
            .replace("", "Uncategorized")
        )
        category_filter = st.selectbox(
            "Category",
            ["All"] + sorted(category_values.unique().tolist()),
            key="tx_category_filter",
        )
        minimum_amount = st.number_input(
            "Minimum amount",
            min_value=0.0,
            value=0.0,
            step=25.0,
            key="tx_min_amount",
        )
        compact_columns = st.checkbox("Compact columns", value=True, key="tx_compact_columns")

active_filters = st.session_state.tx_filters
if active_filters:
    labels = [item["label"] for item in active_filters]
    pill_col, clear_col = st.columns([5, 1])
    with pill_col:
        remaining = st.pills(
            "Active filters",
            options=labels,
            selection_mode="multi",
            default=labels,
            label_visibility="collapsed",
            key="tx_filter_pills",
        )
    with clear_col:
        if st.button("Clear", key="tx_clear_filters", use_container_width=True):
            st.session_state.tx_filters.clear()
            st.rerun()

    remaining_set = set(remaining or [])
    if remaining_set != set(labels):
        st.session_state.tx_filters = [
            item for item in active_filters if item["label"] in remaining_set
        ]
        st.rerun()

filtered = apply_transaction_filter_tokens(base, st.session_state.tx_filters)
if review_filter == "Needs review":
    filtered = filtered[~filtered["reviewed"].fillna(False).astype(bool)]
elif review_filter == "Reviewed":
    filtered = filtered[filtered["reviewed"].fillna(False).astype(bool)]
if category_filter != "All":
    categories = (
        filtered["effective_category"]
        .fillna("Uncategorized")
        .astype(str)
        .str.split("/")
        .str[0]
        .str.strip()
        .replace("", "Uncategorized")
    )
    filtered = filtered[categories == category_filter]
if minimum_amount > 0:
    filtered = filtered[filtered["amount"].abs() >= minimum_amount]

filtered = filtered.sort_values(["date", "id"], ascending=[False, False]).reset_index(drop=True)

# Detail is the first DOM column so it stacks above the list on phones after a
# selection, while the wider transaction list remains the dominant desktop pane.
detail_col, list_col = st.columns([2, 3], gap="medium")
with list_col:
    st.caption(f"{len(filtered):,} transactions · select one to edit or several for bulk actions")
    compact_display = ["date", "effective_merchant", "effective_category", "amount"]
    detailed_display = [
        "date",
        "amount",
        "effective_merchant",
        "name",
        "effective_account_name",
        "effective_category",
        "category_source",
    ]
    display_columns = compact_display if compact_columns else detailed_display
    available = [column for column in display_columns if column in filtered.columns]

    event = st.dataframe(
        filtered[available],
        width="stretch",
        height=460,
        hide_index=True,
        key="tx_table",
        on_select="rerun",
        selection_mode="multi-row",
        column_config={
            "date": st.column_config.DateColumn("Date", width="small"),
            "amount": st.column_config.NumberColumn("Amount", width="small", format="$%.2f"),
            "effective_merchant": st.column_config.TextColumn("Merchant", width="medium"),
            "name": st.column_config.TextColumn("Description"),
            "effective_account_name": st.column_config.TextColumn("Account", width="medium"),
            "effective_category": st.column_config.TextColumn("Category", width="medium"),
            "category_source": st.column_config.TextColumn("Source", width="small"),
        },
    )

selected_indexes = (event.selection or {}).get("rows", [])
selected_rows = filtered.iloc[selected_indexes] if selected_indexes else filtered.iloc[0:0]
if len(selected_rows) == 1:
    st.session_state.tx_selected_id = int(selected_rows.iloc[0]["id"])

with detail_col:
    if len(selected_rows) > 1:
        st.subheader(f"Bulk edit · {len(selected_rows)} selected")
        st.caption("Apply one focused change across the selected transactions.")
        bulk_category = st.selectbox(
            "Category override",
            ["(no category change)"]
            + sorted(
                {
                    str(value)
                    for value in df["effective_category"].fillna("Uncategorized").tolist()
                    if value
                }
            ),
            key="tx_bulk_category",
        )
        bulk_review = st.selectbox(
            "Review status",
            ["Mark reviewed", "Mark not reviewed"],
            key="tx_bulk_review",
        )
        if st.button("Apply to selected", type="primary", use_container_width=True):
            failures = []
            for transaction_id in selected_rows["id"].astype(int).tolist():
                payload = {"reviewed": bulk_review == "Mark reviewed"}
                if bulk_category != "(no category change)":
                    payload["user_category"] = bulk_category
                response = api_patch(
                    f"/transactions/{transaction_id}/annotation",
                    json=payload,
                    base=api_base,
                )
                if not response.ok:
                    failures.append(
                        f"#{transaction_id}: {response.status_code} {extract_error_message(response)}"
                    )
            if failures:
                st.error("Some updates failed: " + "; ".join(failures[:5]))
            else:
                st.success(f"Updated {len(selected_rows)} transactions.")
                st.cache_data.clear()
                st.rerun()
    else:
        selected_id = st.session_state.get("tx_selected_id")
        selected_match = filtered[filtered["id"] == selected_id] if selected_id else filtered.iloc[0:0]
        if selected_match.empty:
            st.subheader("Transaction detail")
            st.info("Select a transaction to review or edit it.")
        else:
            row = selected_match.iloc[0]
            merchant = row.get("effective_merchant") or row.get("name") or "Transaction"
            st.subheader(str(merchant))
            st.caption(
                f"{row['date']} · ${float(row['amount']):,.2f} · "
                f"{row.get('effective_account_name') or row.get('account_name') or 'Unknown account'}"
            )
            st.markdown(f"**Category:** {row.get('effective_category') or 'Uncategorized'}")
            if row.get("name") and row.get("name") != merchant:
                st.caption(str(row.get("name")))

            current = {
                "user_category": row.get("user_category"),
                "merchant_name_override": row.get("merchant_name_override"),
                "notes": row.get("notes"),
                "reviewed": row.get("reviewed", False),
                "refund_status": row.get("refund_status"),
            }
            all_categories = sorted(
                {
                    str(value)
                    for value in df["effective_category"].fillna("Uncategorized").tolist()
                    if value
                }
            )
            render_annotation_editor(
                int(row["id"]),
                current,
                api_base,
                key_prefix="tx_",
                categories=all_categories,
            )
            if st.button("Clear selection", use_container_width=True):
                st.session_state.pop("tx_selected_id", None)
                st.rerun()
