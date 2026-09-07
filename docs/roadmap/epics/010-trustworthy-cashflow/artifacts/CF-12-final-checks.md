# CF-12 Final Checks (2026-09-07)

## Verification

- Backend: `pytest --cov=app --cov-branch --cov-report=term-missing --cov-report=json:cf12-coverage.json -q` — **234 passed**, 2 warnings.
- Backend coverage scope is `app/`, with no excluded lines: **88.75% statements**, **77.26% branches**, **86.32% combined**. The configured CI gate remains `fail_under = 81.34`.
- Frontend: `npm run typecheck` — passed; `npm test -- --run` — **6 files / 44 tests passed**; `npm run build` — passed.
- Streamlit: `pytest tests/test_cf03_streamlit_walkthrough.py -q` — passed.

## Maintainability review

- CF-14 reuses the existing `expense_amount()` accounting expression and adds no schema, migration, provider, or runtime dependency.
- The API owns all money arithmetic; React and Streamlit consume summarized positive spend, residual refund credits, and balanced totals.
- The legacy signed `negative_categories` response field is retained for compatibility; new clients should use `net_refund_credit_categories`.
- CI uses isolated test databases and mocked providers; no production credentials, financial data, or live-provider calls are required.
- No rollback migration is required for CF-14. Rollback is the normal Git revert of commit `8e14d84`.

## Residual limitation

Independent browser verification remains blocked because the available verification browser rejects local loopback with `net::ERR_BLOCKED_BY_CLIENT`; automated React and Streamlit checks remain available and green.
