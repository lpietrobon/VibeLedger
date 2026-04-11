import sqlite3
import pandas as pd
import streamlit as st
import plotly.express as px
from datetime import date, timedelta

st.set_page_config(page_title='VibeLedger Dashboard', layout='wide')
st.title('VibeLedger — Category Explorer')

DB_PATH = st.sidebar.text_input('DB path', 'vibeledger.db')

def load_df(db_path: str):
    conn = sqlite3.connect(db_path)
    q = '''
    SELECT t.id, t.date, t.amount, t.name, t.merchant_name,
           t.plaid_category_primary,
           COALESCE(ta.user_category, t.plaid_category_primary, 'uncategorized') AS effective_category,
           a.name AS account_name, a.mask, a.type, a.subtype
    FROM transactions t
    LEFT JOIN transaction_annotations ta ON ta.transaction_id=t.id
    LEFT JOIN accounts a ON a.id=t.account_id
    '''
    df = pd.read_sql_query(q, conn)
    conn.close()
    if not df.empty:
        df['date'] = pd.to_datetime(df['date']).dt.date
    return df

try:
    df = load_df(DB_PATH)
except Exception as e:
    st.error(f'Failed to load DB: {e}')
    st.stop()

if df.empty:
    st.warning('No transactions found.')
    st.stop()

min_d, max_d = df['date'].min(), df['date'].max()
def_start = max(min_d, date.today() - timedelta(days=30))
start_d, end_d = st.sidebar.date_input('Date range', (def_start, max_d), min_value=min_d, max_value=max_d)

accounts = sorted(df['account_name'].fillna('Unknown').unique().tolist())
selected_accounts = st.sidebar.multiselect('Accounts', accounts, default=accounts)

cats = sorted(df['effective_category'].fillna('uncategorized').unique().tolist())
selected_cats = st.sidebar.multiselect('Categories', cats, default=cats)

f = df[(df['date'] >= start_d) & (df['date'] <= end_d)]
f = f[f['account_name'].fillna('Unknown').isin(selected_accounts)]
f = f[f['effective_category'].fillna('uncategorized').isin(selected_cats)]

spend = f[f['amount'] > 0].copy()

col1, col2 = st.columns(2)
with col1:
    st.metric('Transactions', len(f))
with col2:
    st.metric('Spend (positive amounts)', f"${spend['amount'].sum():,.2f}")

st.subheader('Top Categories')
cat = spend.groupby('effective_category', as_index=False)['amount'].sum().sort_values('amount', ascending=False).head(20)
fig = px.bar(cat, x='amount', y='effective_category', orientation='h', title='Spend by Category')
fig.update_layout(yaxis_title='Category', xaxis_title='Spend')
st.plotly_chart(fig, use_container_width=True)

st.subheader('This Month vs Last Month')
if not spend.empty:
    today = date.today()
    first_this = today.replace(day=1)
    first_prev = (first_this - timedelta(days=1)).replace(day=1)
    last_prev = first_this - timedelta(days=1)
    m = spend.copy()
    m['bucket'] = m['date'].apply(lambda d: 'This month' if d >= first_this else ('Last month' if first_prev <= d <= last_prev else 'Other'))
    m = m[m['bucket'].isin(['This month','Last month'])]
    cmp = m.groupby(['effective_category','bucket'], as_index=False)['amount'].sum()
    top = cmp.groupby('effective_category', as_index=False)['amount'].sum().sort_values('amount', ascending=False).head(15)['effective_category']
    cmp = cmp[cmp['effective_category'].isin(top)]
    fig2 = px.bar(cmp, x='effective_category', y='amount', color='bucket', barmode='group', title='Category comparison')
    fig2.update_xaxes(tickangle=35)
    st.plotly_chart(fig2, use_container_width=True)

st.subheader('Transaction Samples by Category')
cat_pick = st.selectbox('Pick a category', sorted(f['effective_category'].fillna('uncategorized').unique().tolist()))
samples = f[f['effective_category'].fillna('uncategorized') == cat_pick].sort_values('date', ascending=False)
st.dataframe(samples[['date','amount','account_name','merchant_name','name','plaid_category_primary','effective_category']].head(200), use_container_width=True)
