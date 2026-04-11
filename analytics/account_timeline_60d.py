#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import sqlite3
from pathlib import Path


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--db", default="vibeledger.db")
    p.add_argument("--account-id", type=int)
    p.add_argument("--item-id", type=int, default=None, help="Generate plots for all accounts in an item")
    p.add_argument("--days", type=int, default=60)
    p.add_argument("--anchor-balance", type=float, default=None)
    p.add_argument("--anchor-date", default=None)
    p.add_argument("--outdir", default="analytics/out")
    p.add_argument("--list-accounts", action="store_true")
    return p.parse_args()


def list_accounts(conn: sqlite3.Connection) -> None:
    rows = conn.execute(
        """
        SELECT a.id, a.item_id, a.name, a.mask, a.type, a.subtype, i.institution_name
        FROM accounts a
        LEFT JOIN items i ON i.id = a.item_id
        ORDER BY a.item_id, a.id
        """
    ).fetchall()
    print("id | item_id | institution | name | mask | type/subtype")
    for r in rows:
        print(f"{r[0]} | {r[1]} | {r[6] or '-'} | {r[2]} | {r[3] or '-'} | {r[4] or '-'} / {r[5] or '-'}")


def get_account_meta(conn: sqlite3.Connection, account_id: int) -> tuple[str, float | None, str | None, str | None]:
    r = conn.execute(
        """
        SELECT a.name, a.mask, i.institution_name, a.current_balance, a.type, a.subtype
        FROM accounts a
        LEFT JOIN items i ON i.id = a.item_id
        WHERE a.id = ?
        """,
        (account_id,),
    ).fetchone()
    if not r:
        return f"Account {account_id}", None, None, None
    name = r[0] or f"Account {account_id}"
    mask = r[1]
    inst = r[2]
    cur = float(r[3]) if r[3] is not None else None
    acc_type = r[4]
    acc_subtype = r[5]
    suffix = f" • {inst}" if inst else ""
    mask_part = f" ({mask})" if mask else ""
    return f"{name}{mask_part}{suffix}", cur, acc_type, acc_subtype


def daterange(start: dt.date, end: dt.date):
    cur = start
    while cur <= end:
        yield cur
        cur += dt.timedelta(days=1)


def build_account_timeline(conn: sqlite3.Connection, account_id: int, days: int, anchor_balance: float | None, anchor_date: str | None, account_type: str | None = None):
    today = dt.date.today()
    start = today - dt.timedelta(days=days - 1)

    rows = conn.execute(
        """
        SELECT date, amount
        FROM transactions
        WHERE account_id = ?
          AND date >= ?
          AND date <= ?
        ORDER BY date ASC
        """,
        (account_id, start.isoformat(), today.isoformat()),
    ).fetchall()

    daily_net = {d: 0.0 for d in daterange(start, today)}
    daily_spend = {d: 0.0 for d in daterange(start, today)}
    daily_credits = {d: 0.0 for d in daterange(start, today)}

    for r in rows:
        d = dt.date.fromisoformat(r["date"])
        amt = float(r["amount"])
        daily_net[d] += amt
        if amt > 0:
            daily_spend[d] += amt
        elif amt < 0:
            daily_credits[d] += amt

    balance = {}
    if anchor_balance is not None:
        a_date = dt.date.fromisoformat(anchor_date) if anchor_date else today
        days_list = list(daterange(start, today))

        # Balance delta direction depends on account type.
        # - Depository-like accounts: spend(+) lowers balance, credit(-) raises => delta = -daily_net
        # - Credit-like accounts: spend(+) raises owed balance, payment(-) lowers => delta = +daily_net
        is_credit_like = (account_type or '').lower() in {'credit', 'loan'}
        sign = 1.0 if is_credit_like else -1.0

        balance[a_date] = anchor_balance

        # Walk backward from anchor to start.
        d = a_date
        while d > start:
            prev = d - dt.timedelta(days=1)
            balance[prev] = balance[d] - sign * daily_net[d]
            d = prev

        # Walk forward from anchor to today.
        d = a_date
        while d < today:
            nxt = d + dt.timedelta(days=1)
            balance[nxt] = balance[d] + sign * daily_net[nxt]
            d = nxt

        # Fill any gaps if anchor outside range.
        if a_date < start or a_date > today:
            run = 0.0
            is_credit_like = (account_type or '').lower() in {'credit', 'loan'}
            sign = 1.0 if is_credit_like else -1.0
            for d in days_list:
                run += sign * daily_net[d]
                balance[d] = run
    else:
        run = 0.0
        is_credit_like = (account_type or '').lower() in {'credit', 'loan'}
        sign = 1.0 if is_credit_like else -1.0
        for d in daterange(start, today):
            run += sign * daily_net[d]
            balance[d] = run

    return start, today, daily_spend, daily_credits, daily_net, balance


def save_csv(outdir: Path, account_id: int, days: int, start: dt.date, end: dt.date, daily_spend, daily_credits, daily_net, balance):
    path = outdir / f"account_{account_id}_timeline_{days}d.csv"
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "spend_positive", "credits_negative", "net_flow", "balance_line"])
        for d in daterange(start, end):
            w.writerow([d.isoformat(), round(daily_spend[d], 2), round(daily_credits[d], 2), round(daily_net[d], 2), round(balance[d], 2)])
    return path


def save_plotly(outdir: Path, account_id: int, account_label: str, days: int, start: dt.date, end: dt.date, daily_spend, daily_credits, balance):
    import plotly.graph_objects as go

    ds = [d.isoformat() for d in daterange(start, end)]
    spend_vals = [daily_spend[d] for d in daterange(start, end)]
    credit_vals = [daily_credits[d] for d in daterange(start, end)]
    bal_vals = [balance[d] for d in daterange(start, end)]

    fig = go.Figure()
    # Balance on primary y-axis (left)
    fig.add_trace(go.Scatter(x=ds, y=bal_vals, name="Balance", yaxis="y", mode="lines", line=dict(color="#111111", width=2)))
    # Transaction flows on secondary y-axis (right)
    fig.add_trace(go.Bar(x=ds, y=spend_vals, name="Spend (+)", yaxis="y2", marker_color="#EF553B", opacity=0.55))
    fig.add_trace(go.Bar(x=ds, y=credit_vals, name="Credits (-)", yaxis="y2", marker_color="#00CC96", opacity=0.55))

    fig.update_layout(
        title=f"{account_label} — Last {days} Days",
        barmode="relative",
        xaxis_title="Date",
        yaxis=dict(title="Balance", side="left"),
        yaxis2=dict(title="Daily flow", overlaying="y", side="right"),
        legend=dict(orientation="h"),
        template="plotly_white",
    )

    html_path = outdir / f"account_{account_id}_timeline_{days}d.html"
    png_path = outdir / f"account_{account_id}_timeline_{days}d.png"
    fig.write_html(str(html_path), include_plotlyjs="cdn")
    fig.write_image(str(png_path), width=1400, height=600, scale=2)
    return html_path, png_path


def main() -> None:
    args = parse_args()
    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row

    if args.list_accounts:
        list_accounts(conn)
        return

    account_ids = []
    if args.item_id is not None:
        account_ids = [r[0] for r in conn.execute("SELECT id FROM accounts WHERE item_id=? ORDER BY id", (args.item_id,)).fetchall()]
    elif args.account_id is not None:
        account_ids = [args.account_id]

    if not account_ids:
        raise SystemExit("Pass --account-id <id> or --item-id <item_id> (or use --list-accounts)")

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    for account_id in account_ids:
        account_label, current_balance, account_type, account_subtype = get_account_meta(conn, account_id)
        anchor_balance = args.anchor_balance if args.anchor_balance is not None else current_balance
        anchor_date = args.anchor_date if args.anchor_date else dt.date.today().isoformat()
        start, end, daily_spend, daily_credits, daily_net, balance = build_account_timeline(
            conn, account_id, args.days, anchor_balance, anchor_date, account_type=account_type
        )
        csv_path = save_csv(outdir, account_id, args.days, start, end, daily_spend, daily_credits, daily_net, balance)
        html_path, png_path = save_plotly(outdir, account_id, account_label, args.days, start, end, daily_spend, daily_credits, balance)
        print(f"account {account_id}: {csv_path}")
        print(f"account {account_id}: {html_path}")
        print(f"account {account_id}: {png_path}")


if __name__ == "__main__":
    main()
