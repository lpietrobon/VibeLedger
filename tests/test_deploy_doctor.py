from pathlib import Path

from scripts.deploy_doctor import load_env_value, tailscale_route_errors, validate_app_base_url


def test_load_env_value_treats_file_as_data(tmp_path: Path):
    env_file = tmp_path / "app.env"
    env_file.write_text(
        "IGNORED=$(echo unsafe)\nAPP_BASE_URL='https://homepi.example.ts.net:8444/vibeledger'\n",
        encoding="utf-8",
    )
    assert load_env_value(env_file, "APP_BASE_URL") == (
        "https://homepi.example.ts.net:8444/vibeledger"
    )


def test_app_base_url_requires_complete_secure_origin():
    errors, _ = validate_app_base_url("https://homepi.example.ts.net:8444/vibeledger")
    assert errors == []
    errors, _ = validate_app_base_url("http://homepi.example.ts.net/vibeledger/")
    assert "non-local APP_BASE_URL must use https" in errors
    assert "APP_BASE_URL must not end with a slash" in errors


def test_tailscale_route_comparison_catches_omitted_port():
    status = {
        "Web": {
            "homepi.example.ts.net:8444": {
                "Handlers": {
                    "/vibeledger": {"Proxy": "http://127.0.0.1:5173/vibeledger"}
                }
            }
        }
    }
    errors = tailscale_route_errors(status, "https://homepi.example.ts.net/vibeledger")
    assert errors
    assert "homepi.example.ts.net:8444" in errors[0]


def test_tailscale_route_comparison_accepts_exact_authority_path_and_target():
    status = {
        "Web": {
            "homepi.example.ts.net:8444": {
                "Handlers": {
                    "/vibeledger": {"Proxy": "http://127.0.0.1:5173/vibeledger"}
                }
            }
        }
    }
    assert tailscale_route_errors(
        status, "https://homepi.example.ts.net:8444/vibeledger"
    ) == []
