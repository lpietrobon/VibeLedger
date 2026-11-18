# INV-08 implementation evidence

Author: GPT-5.6-Luna, 2026-11-18. Synthetic fixtures only; no deployment.

Implemented backend scoped summary fields (account/tax filters, holdings, observed history, as-of, effective range, qualifications and null gain), `/investments` React route, `/overview` compatibility mapping, and Investments navigation slot. Existing overview API and spending routes remain unchanged.

GREEN command: `/home/skywalker/VibeLedger/.venv/bin/python -m pytest -q tests/test_investment_visibility_tdd.py tests/test_investment_ingestion.py tests/test_investment_isolation.py` → **34 passed**.

`npm exec tsc -- --noEmit` was attempted in the frontend worktree but exceeded the 497 MiB tool memory limit; independent verification must rerun it with constrained workers or a smaller scoped command.
