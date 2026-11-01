# PI-01 Streamlit retirement evidence

The React/Vite application is now the only supported VibeLedger product UI.

## Inventory result

- Removed `Spend.py`, `dashboard_lib.py`, all legacy `pages/*.py`, `.streamlit/`,
  and Streamlit-specific tests.
- Removed the `dashboard` dependency extra and the unused Plotly runtime
  dependency from `pyproject.toml`.
- Updated README, agent instructions, frontend README, testing guidance, and
  transaction-search documentation to describe React/API operation only.
- Updated CI to install the `dev` extra without dashboard packages.
- Preserved historical roadmap records under epic 010 unchanged.

## Verification

- Repository search for live Streamlit imports/configuration/commands returned no
  matches outside historical roadmap records.
- Backend: `/root/.local/bin/pytest -q` → **230 passed**.
- Frontend `npm test`, `npm run typecheck`, and `npm run build` were not runnable
  locally because `node_modules` is absent and npm registry access was unavailable;
  the existing CI workflow continues to run all three checks.
