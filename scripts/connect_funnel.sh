#!/usr/bin/env bash
set -euo pipefail

# connect_funnel.sh
# -----------------
# Why this exists:
# - We want Plaid connect traffic to terminate on the VPS (server-side token exchange/storage).
# - We only need public exposure for a short window while the user completes Link.
# - We already run other Funnel routes (e.g. /gmail-pubsub) that must stay up.
#
# Safety guarantee:
# - This script ONLY adds/removes one path-scoped Funnel handler (default: /connect).
# - It does NOT call `tailscale funnel reset` or `tailscale serve reset`.
# - Therefore existing handlers like /gmail-pubsub remain untouched.
#
# Usage:
#   ./scripts/connect_funnel.sh open
#   ./scripts/connect_funnel.sh close
#   ./scripts/connect_funnel.sh status
#
# Optional env vars:
#   CONNECT_PATH=/connect               # path to expose publicly
#   CONNECT_TARGET=http://127.0.0.1:8000
#   TS_FUNNEL_HOST=contabo.tail....     # only used for status URL output

ACTION="${1:-}"
if [[ -z "$ACTION" ]]; then
  echo "Usage: $0 {open|close|status}" >&2
  exit 2
fi

CONNECT_PATH="${CONNECT_PATH:-/connect}"
CONNECT_TARGET="${CONNECT_TARGET:-http://127.0.0.1:8000}"

if [[ -z "${TS_FUNNEL_HOST:-}" ]]; then
  # Prefer cert domain from tailscale status for a stable public URL.
  TS_FUNNEL_HOST="$(tailscale status --json 2>/dev/null | python3 -c 'import json,sys; d=json.load(sys.stdin); print((d.get("CertDomains") or [""])[0])' || true)"
fi

if [[ -z "$TS_FUNNEL_HOST" ]]; then
  # Fallback: still perform open/close, but status URL might be unknown.
  TS_FUNNEL_HOST="<set-TS_FUNNEL_HOST>"
fi

case "$ACTION" in
  open)
    tailscale funnel --bg --https=443 --set-path "$CONNECT_PATH" "$CONNECT_TARGET" >/dev/null
    echo "OPENED_PATH=$CONNECT_PATH"
    echo "PUBLIC_BASE_URL=https://$TS_FUNNEL_HOST$CONNECT_PATH"
    ;;

  close)
    # Path-scoped shutdown. Leaves other routes (e.g. /gmail-pubsub) intact.
    tailscale funnel --https=443 --set-path "$CONNECT_PATH" off >/dev/null
    echo "CLOSED_PATH=$CONNECT_PATH"
    ;;

  status)
    tailscale funnel status
    echo "PUBLIC_BASE_URL=https://$TS_FUNNEL_HOST$CONNECT_PATH"
    ;;

  *)
    echo "Unknown action: $ACTION" >&2
    echo "Usage: $0 {open|close|status}" >&2
    exit 2
    ;;
esac
