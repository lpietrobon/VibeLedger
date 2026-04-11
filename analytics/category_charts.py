#!/usr/bin/env python3
from __future__ import annotations
import datetime as dt
import sqlite3
from pathlib import Path
import plotly.graph_objects as go

DB='vibeledger.db'
OUT=Path('analytics/out')
OUT.mkdir(parents=True, exist_ok=True)

conn=sqlite3.connect(DB)
conn.row_factory=sqlite3.Row

# last 30d top categories (spend only)
end=dt.date.today()
start=end-dt.timedelta(days=29)
rows=conn.execute('''
SELECT COALESCE(ta.user_category, t.plaid_category_primary, 'uncategorized') AS category,
       SUM(t.amount) as spend
FROM transactions t
LEFT JOIN transaction_annotations ta ON ta.transaction_id=t.id
WHERE t.date>=? AND t.date<=? AND t.amount>0
GROUP BY 1
ORDER BY spend DESC
LIMIT 15
''',(start.isoformat(),end.isoformat())).fetchall()

cats=[r['category'] for r in rows][::-1]
vals=[float(r['spend']) for r in rows][::-1]
fig=go.Figure(go.Bar(x=vals,y=cats,orientation='h',marker_color='#636EFA'))
fig.update_layout(title='Top Spend Categories — Last 30 Days',xaxis_title='Spend',yaxis_title='Category',template='plotly_white')
p1=OUT/'categories_top_30d.png'
fig.write_image(str(p1),width=1400,height=700,scale=2)

# this month vs last month by category
first_this=end.replace(day=1)
first_prev=(first_this-dt.timedelta(days=1)).replace(day=1)
last_prev=first_this-dt.timedelta(days=1)
rows=conn.execute('''
SELECT COALESCE(ta.user_category, t.plaid_category_primary, 'uncategorized') AS category,
       SUM(CASE WHEN t.date>=? AND t.date<=? AND t.amount>0 THEN t.amount ELSE 0 END) as this_month,
       SUM(CASE WHEN t.date>=? AND t.date<=? AND t.amount>0 THEN t.amount ELSE 0 END) as last_month
FROM transactions t
LEFT JOIN transaction_annotations ta ON ta.transaction_id=t.id
WHERE t.date>=? AND t.date<=?
GROUP BY 1
HAVING this_month>0 OR last_month>0
ORDER BY (this_month+last_month) DESC
LIMIT 15
''',(first_this.isoformat(),end.isoformat(),first_prev.isoformat(),last_prev.isoformat(),first_prev.isoformat(),end.isoformat())).fetchall()

cats=[r['category'] for r in rows]
thisv=[float(r['this_month']) for r in rows]
lastv=[float(r['last_month']) for r in rows]
fig2=go.Figure()
fig2.add_trace(go.Bar(name='This month',x=cats,y=thisv,marker_color='#EF553B'))
fig2.add_trace(go.Bar(name='Last month',x=cats,y=lastv,marker_color='#00CC96'))
fig2.update_layout(title='Spend by Category — This Month vs Last Month',xaxis_title='Category',yaxis_title='Spend',barmode='group',template='plotly_white')
fig2.update_xaxes(tickangle=35)
p2=OUT/'categories_month_compare.png'
fig2.write_image(str(p2),width=1600,height=800,scale=2)

print(p1)
print(p2)
