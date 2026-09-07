# Deployment

VibeLedger has two configuration layers. Keep their ownership explicit.

## Repository-owned contract

The repository owns application requirements, service templates, the deployment
procedure, and verification. It must not contain a host's credentials or exact
private topology.

- `.env.example` documents required values.
- `deploy/systemd/*.service.in` defines the API, dashboard, and frontend processes.
- `scripts/deploy.sh` updates, builds, restarts all three processes, and verifies them.
- `scripts/deploy_doctor.py` checks local health and the configured Tailscale route.

## Host-owned state

The deployment host owns:

- the real environment file and secrets;
- its Tailscale DNS name, HTTPS port, and Serve/Funnel map;
- rendered systemd user units;
- its SQLite database and backups.

Prefer a restricted environment file outside the checkout, for example
`~/.config/vibeledger/vibeledger.env`, and set `VIBELEDGER_ENV_FILE` when deploying.
The existing repository-local `.env` remains supported and is ignored by Git.

## External URL contract

`APP_BASE_URL` is the complete URL a browser uses to enter VibeLedger. It must
include the scheme, hostname, non-default port (if any), and application prefix,
with no trailing slash:

```text
https://machine.example.ts.net:8444/vibeledger
```

The port is not optional when Tailscale Serve listens on a non-default HTTPS
port. A missing `:8444` sends the browser to port 443 and causes newly generated
Plaid Connect URLs to point at the wrong listener.

For the React application, Tailscale Serve should route the `APP_BASE_URL` path
to the loopback frontend edge. That edge serves React and proxies API and Connect
requests to FastAPI:

```text
https://machine.example.ts.net:8444/vibeledger
    -> http://127.0.0.1:5173/vibeledger
        -> React files
        -> /vibeledger/api/* and /vibeledger/connect/* -> 127.0.0.1:8000
```

Streamlit may have a sibling Serve route:

```text
/vibeledger/dash -> http://127.0.0.1:8501/vibeledger/dash
```

Tailscale Serve is tailnet-only. Funnel is not required for ordinary phone use
when the phone is connected to Tailscale. OAuth callbacks or webhooks that Plaid
must initiate may require a narrowly scoped public route; never expose the whole
application merely to solve a path or port mismatch.

## Installing user services

Render each `deploy/systemd/*.service.in` file into
`~/.config/systemd/user/`, replacing:

- `@REPO_ROOT@` with the absolute checkout path;
- `@ENV_FILE@` with the absolute private environment-file path.

Then inspect the rendered units before enabling them:

```bash
systemctl --user daemon-reload
systemctl --user enable --now \
  vibeledger.service vibeledger-dash.service vibeledger-frontend.service
```

The services deliberately bind only to `127.0.0.1`. Tailscale Serve or an SSH
local forward is the network boundary.

## Deploying

From a clean deployment checkout:

```bash
VIBELEDGER_ENV_FILE="$HOME/.config/vibeledger/vibeledger.env" \
  ./scripts/deploy.sh main
```

The script refuses a dirty checkout, fast-forwards the selected remote branch,
installs Python and Node dependencies, builds React, restarts the API, dashboard,
and frontend together, then runs the deployment doctor. Pass a commit SHA for a
detached exact-revision deployment.

Run verification without changing code:

```bash
python3 scripts/deploy_doctor.py \
  --env-file "$HOME/.config/vibeledger/vibeledger.env"
```

For a non-Tailscale installation, add `--skip-tailscale`. Use `--skip-external`
only when intentionally testing local services without the external route.
The deployment wrapper accepts the equivalent
`VIBELEDGER_SKIP_TAILSCALE=1` and `VIBELEDGER_SKIP_EXTERNAL=1` environment
switches.

Deployment is complete only when all three services are active and the doctor
passes. Restarting only the frontend can leave React and FastAPI on incompatible
revisions; changing `APP_BASE_URL` without checking Tailscale Serve can generate
unreachable Plaid links.
