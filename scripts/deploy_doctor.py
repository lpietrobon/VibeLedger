#!/usr/bin/env python3
"""Validate one VibeLedger deployment without printing secrets."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import urlopen


REPO_ROOT = Path(__file__).resolve().parents[1]
SERVICES = (
    "vibeledger.service",
    "vibeledger-dash.service",
    "vibeledger-frontend.service",
)
LOCAL_ENDPOINTS = (
    ("API health", "http://127.0.0.1:8000/health"),
    ("dashboard health", "http://127.0.0.1:8501/vibeledger/dash/_stcore/health"),
    ("frontend", "http://127.0.0.1:5173/vibeledger/frontend/"),
    ("frontend API proxy", "http://127.0.0.1:5173/vibeledger/api/health"),
)


def load_env_value(path: Path, name: str) -> str | None:
    """Read a dotenv value as data; never source the file as shell code."""
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() != name:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        return value
    return None


def validate_app_base_url(value: str | None) -> tuple[list[str], object | None]:
    errors: list[str] = []
    if not value:
        return ["APP_BASE_URL is missing or empty"], None
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"}:
        errors.append("APP_BASE_URL must use http or https")
    if not parsed.hostname:
        errors.append("APP_BASE_URL must include a hostname")
    if parsed.username or parsed.password:
        errors.append("APP_BASE_URL must not contain credentials")
    if parsed.query or parsed.fragment:
        errors.append("APP_BASE_URL must not contain a query string or fragment")
    if value.endswith("/"):
        errors.append("APP_BASE_URL must not end with a slash")
    if parsed.hostname not in {"localhost", "127.0.0.1", "::1"} and parsed.scheme != "https":
        errors.append("non-local APP_BASE_URL must use https")
    return errors, parsed


def tailscale_route_errors(status: dict, app_base_url: str) -> list[str]:
    parsed = urlsplit(app_base_url)
    authority = parsed.netloc
    path = parsed.path or "/"
    web = status.get("Web") or {}
    if authority not in web:
        available = ", ".join(sorted(web)) or "none"
        return [
            f"APP_BASE_URL authority {authority!r} is not served by Tailscale; "
            f"configured authorities: {available}"
        ]
    handlers = web[authority].get("Handlers") or {}
    handler = handlers.get(path)
    if not handler:
        available = ", ".join(sorted(handlers)) or "none"
        return [
            f"APP_BASE_URL path {path!r} is not a Tailscale Serve handler; "
            f"configured paths: {available}"
        ]
    proxy = handler.get("Proxy", "")
    if "127.0.0.1:5173" not in proxy:
        return [f"Tailscale handler {authority}{path} does not target the frontend on 127.0.0.1:5173"]
    return []


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(command, check=False, capture_output=True, text=True)
    except FileNotFoundError:
        return subprocess.CompletedProcess(command, 127, "", f"command not found: {command[0]}")


def check_url(label: str, url: str) -> str | None:
    try:
        with urlopen(url, timeout=8) as response:
            if not 200 <= response.status < 400:
                return f"{label} returned HTTP {response.status}: {url}"
    except HTTPError as exc:
        return f"{label} returned HTTP {exc.code}: {url}"
    except (URLError, OSError) as exc:
        reason = getattr(exc, "reason", str(exc))
        return f"{label} is unreachable: {url} ({reason})"
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", type=Path, default=REPO_ROOT / ".env")
    parser.add_argument("--config-only", action="store_true")
    parser.add_argument("--skip-tailscale", action="store_true")
    parser.add_argument("--skip-external", action="store_true")
    args = parser.parse_args()

    errors: list[str] = []
    if not args.env_file.is_file():
        errors.append(f"environment file not found: {args.env_file}")
        app_base_url = None
    else:
        app_base_url = load_env_value(args.env_file, "APP_BASE_URL")
        url_errors, _ = validate_app_base_url(app_base_url)
        errors.extend(url_errors)

    if app_base_url and not args.skip_tailscale:
        result = run(["tailscale", "serve", "status", "--json"])
        if result.returncode:
            errors.append("could not read Tailscale Serve status (use --skip-tailscale for non-Tailscale installs)")
        else:
            try:
                errors.extend(tailscale_route_errors(json.loads(result.stdout), app_base_url))
            except json.JSONDecodeError:
                errors.append("Tailscale Serve returned invalid JSON")

    if not args.config_only:
        for service in SERVICES:
            result = run(["systemctl", "--user", "is-active", service])
            if result.returncode or result.stdout.strip() != "active":
                errors.append(f"service is not active: {service}")
        for label, url in LOCAL_ENDPOINTS:
            if error := check_url(label, url):
                errors.append(error)
        if app_base_url and not args.skip_external:
            for label, suffix in (("external frontend", "/frontend/"), ("external health", "/health")):
                if error := check_url(label, app_base_url + suffix):
                    errors.append(error)

    if errors:
        for error in errors:
            print(f"FAIL: {error}", file=sys.stderr)
        return 1
    print(f"OK: deployment configuration and health checks passed for {app_base_url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
