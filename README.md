# VibeLedger

Single-user personal finance ledger with Plaid ingestion.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
uvicorn app.main:app --reload
pytest
```
