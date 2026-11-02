#!/usr/bin/env bash
set -euo pipefail

# Update a clean deployment checkout to a remote branch, rebuild every runtime,
# restart all VibeLedger services, and verify both local and Tailscale paths.

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
deploy_ref="${1:-main}"
env_file="${VIBELEDGER_ENV_FILE:-${repo_root}/.env}"
doctor_flags=(--env-file "$env_file")
if [[ "${VIBELEDGER_SKIP_TAILSCALE:-0}" == "1" ]]; then
  doctor_flags+=(--skip-tailscale)
fi
if [[ "${VIBELEDGER_SKIP_EXTERNAL:-0}" == "1" ]]; then
  doctor_flags+=(--skip-external)
fi

cd "$repo_root"

if [[ -n "$(git status --porcelain)" ]]; then
  echo "FAIL: deployment checkout is not clean" >&2
  exit 1
fi

python3 scripts/deploy_doctor.py "${doctor_flags[@]}" --config-only

git fetch origin --prune
if git show-ref --verify --quiet "refs/remotes/origin/${deploy_ref}"; then
  if git show-ref --verify --quiet "refs/heads/${deploy_ref}"; then
    git switch "$deploy_ref"
  else
    git switch --track -c "$deploy_ref" "origin/${deploy_ref}"
  fi
  git merge --ff-only "origin/${deploy_ref}"
else
  target="$(git rev-parse --verify "${deploy_ref}^{commit}")"
  git switch --detach "$target"
fi

revision="$(git rev-parse HEAD)"

"${repo_root}/.venv/bin/python" -m pip install -e '.[dashboard]'
npm ci --prefix frontend
npm run build --prefix frontend

systemctl --user restart \
  vibeledger.service \
  vibeledger-dash.service \
  vibeledger-frontend.service

python3 scripts/deploy_doctor.py "${doctor_flags[@]}"
echo "DEPLOYED_REVISION=${revision}"
