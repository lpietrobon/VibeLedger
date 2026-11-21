# INV-07 frozen RED evidence

Author: GPT-5.6-Luna (test author), 2026-11-18. Synthetic fixtures only.

Source before test commit: `648a1e5`.

Command:

`/home/skywalker/VibeLedger/.venv/bin/python -m pytest -q tests/test_investment_visibility_tdd.py`

Result: **3 failed**, as expected. Two failures demonstrate the summary lacks scoped arguments; one demonstrates the endpoint lacks effective-range disclosure. Tests are frozen in `tests/test_investment_visibility_tdd.py`; implementation must not weaken literal expectations.
