#!/usr/bin/env python3
from __future__ import annotations
import argparse
import datetime as dt
import sqlite3
from pathlib import Path
import plotly.graph_objects as go


def daterange(start: dt.date, end: dt.date):
    d = start
    while d <= end:
        yield d
        d += dt.timedelta(days=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--db', default='vibeledger.db')
    ap.add_argument('--days', type=int, default=60)
    ap.add_argument('--outdir', default='analytics/out')
    ap.add_argument('--item-id', type=int, default=None)
    args = ap.parse_args()

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    q = """
    SELECT a.id, a.name, a.mask, a.type, a.subtype, a.current_balance
    FROM accounts a
    """
    params = []
    if args.item_id is not None:
        q += " WHERE a.item_id = ?"
        params.append(args.item_id)
    q += " ORDER BY a.type, a.subtype, a.id"
    accounts = conn.execute(q, params).fetchall()

    today = dt.date.today()
    start = today - dt.timedelta(days=args.days - 1)

    # group by subtype first, fallback to type
    groups = {}
    for a in accounts:
        g = (a['subtype'] or a['type'] or 'other').lower()
        groups.setdefault(g, []).append(a)

    produced = []
    for g, accs in groups.items():
        fig = go.Figure()
        max_y = 0.0
        for a in accs:
            acct_id = a['id']
            label = a['name'] or f"Account {acct_id}"
            if a['mask']:
                label += f" ({a['mask']})"
            anchor = float(a['current_balance'] or 0.0)

            # daily net: spend +, credit -
            rows = conn.execute(
                """
                SELECT date, amount FROM transactions
                WHERE account_id = ? AND date >= ? AND date <= ?
                ORDER BY date ASC
                """,
                (acct_id, start.isoformat(), today.isoformat()),
            ).fetchall()
            net = {d: 0.0 for d in daterange(start, today)}
            for r in rows:
                net[dt.date.fromisoformat(r['date'])] += float(r['amount'])

            # account type sign
            acc_type = (a['type'] or '').lower()
            sign = 1.0 if acc_type in {'credit', 'loan'} else -1.0

            bal = {today: anchor}
            d = today
            while d > start:
                prev = d - dt.timedelta(days=1)
                bal[prev] = bal[d] - sign * net[d]
                d = prev

            xs = [d.isoformat() for d in daterange(start, today)]
            ys = [bal[d] for d in daterange(start, today)]
            max_y = max(max_y, max(ys) if ys else 0.0)
            fig.add_trace(go.Scatter(x=xs, y=ys, mode='lines', name=label))

        title = f"Balances — {g.replace('_',' ').title()} Accounts (last {args.days}d)"
        fig.update_layout(
            title=title,
            xaxis_title='Date',
            yaxis=dict(title='Balance', range=[0, max_y * 1.1 if max_y > 0 else 1]),
            template='plotly_white',
            legend=dict(orientation='h')
        )
        png = outdir / f"balances_{g}_{args.days}d.png"
        fig.write_image(str(png), width=1400, height=650, scale=2)
        print(png)
        produced.append(str(png))


if __name__ == '__main__':
    main()
