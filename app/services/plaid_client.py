from datetime import date
from typing import Any

from app.core.config import settings


class PlaidClient:
    def __init__(self) -> None:
        self._client = None
        self._mock = settings.plaid_use_mock

        if self._mock:
            return

        if not settings.plaid_client_id or not settings.plaid_secret:
            raise ValueError("PLAID_CLIENT_ID and PLAID_SECRET are required when PLAID_USE_MOCK=false")

        try:
            import plaid
            from plaid.api import plaid_api

            host_map = {
                "sandbox": plaid.Environment.Sandbox,
                "production": plaid.Environment.Production,
            }
            env = settings.plaid_env.lower()
            if env == "development":
                # plaid-python v16 exposes Sandbox/Production only; map development to sandbox-compatible host.
                env = "sandbox"
            host = host_map.get(env)
            if not host:
                raise ValueError("PLAID_ENV must be sandbox|development|production")

            configuration = plaid.Configuration(
                host=host,
                api_key={
                    "clientId": settings.plaid_client_id,
                    "secret": settings.plaid_secret,
                },
            )
            api_client = plaid.ApiClient(configuration)
            self._client = plaid_api.PlaidApi(api_client)
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Plaid SDK client: {e}") from e

    def create_link_token(self, user_id: str) -> dict:
        if self._mock:
            return {"link_token": f"mock-link-token-{user_id}"}

        from plaid.model.country_code import CountryCode
        from plaid.model.link_token_create_request import LinkTokenCreateRequest
        from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
        from plaid.model.products import Products

        products = [Products(p.strip()) for p in settings.plaid_products.split(",") if p.strip()]
        country_codes = [CountryCode(c.strip()) for c in settings.plaid_country_codes.split(",") if c.strip()]

        req_kwargs: dict[str, Any] = {
            "user": LinkTokenCreateRequestUser(client_user_id=user_id),
            "client_name": "VibeLedger",
            "products": products,
            "country_codes": country_codes,
            "language": "en",
        }
        if settings.plaid_redirect_uri:
            req_kwargs["redirect_uri"] = settings.plaid_redirect_uri

        request = LinkTokenCreateRequest(**req_kwargs)
        response = self._client.link_token_create(request)
        return {"link_token": response["link_token"]}

    def exchange_public_token(self, public_token: str) -> dict:
        if self._mock:
            return {
                "access_token": f"access-{public_token}",
                "item_id": "item-mock-123",
            }

        from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest

        request = ItemPublicTokenExchangeRequest(public_token=public_token)
        response = self._client.item_public_token_exchange(request)
        return {
            "access_token": response["access_token"],
            "item_id": response["item_id"],
        }

    def get_accounts(self, access_token: str) -> list[dict[str, Any]]:
        if self._mock:
            return [
                {
                    "account_id": "acct-001",
                    "name": "Mock Checking",
                    "official_name": "Mock Checking Account",
                    "mask": "0000",
                    "type": "depository",
                    "subtype": "checking",
                    "current_balance": 1000.00,
                    "available_balance": 1000.00,
                    "iso_currency_code": "USD",
                    "limit": None,
                }
            ]

        from plaid.model.accounts_get_request import AccountsGetRequest

        request = AccountsGetRequest(access_token=access_token)
        response = self._client.accounts_get(request)
        out: list[dict[str, Any]] = []
        for a in response.get("accounts", []):
            b = a.get("balances", {})
            out.append(
                {
                    "account_id": a.get("account_id"),
                    "name": a.get("name"),
                    "official_name": a.get("official_name"),
                    "mask": a.get("mask"),
                    "type": str(a.get("type")) if a.get("type") is not None else None,
                    "subtype": str(a.get("subtype")) if a.get("subtype") is not None else None,
                    "current_balance": b.get("current"),
                    "available_balance": b.get("available"),
                    "iso_currency_code": b.get("iso_currency_code"),
                    "limit": b.get("limit"),
                }
            )
        return out

    def sync_transactions(self, access_token: str, cursor: str | None = None) -> dict:
        if self._mock:
            return {
                "added": [
                    {
                        "transaction_id": "txn-001",
                        "account_id": "acct-001",
                        "date": str(date.today()),
                        "amount": 12.34,
                        "name": "Coffee Shop",
                        "merchant_name": "Coffee Shop",
                        "plaid_category_primary": "FOOD_AND_DRINK",
                        "pending": False,
                    }
                ],
                "modified": [],
                "removed": [],
                "next_cursor": "cursor-1" if cursor is None else f"{cursor}-next",
                "has_more": False,
            }

        from plaid.model.transactions_sync_request import TransactionsSyncRequest

        all_added: list[dict[str, Any]] = []
        all_modified: list[dict[str, Any]] = []
        all_removed: list[dict[str, Any]] = []
        next_cursor = cursor

        while True:
            if next_cursor is None:
                request = TransactionsSyncRequest(access_token=access_token)
            else:
                request = TransactionsSyncRequest(access_token=access_token, cursor=next_cursor)
            response = self._client.transactions_sync(request)

            all_added.extend([self._normalize_txn(t) for t in response.get("added", [])])
            all_modified.extend([self._normalize_txn(t) for t in response.get("modified", [])])
            all_removed.extend([{"transaction_id": t["transaction_id"]} for t in response.get("removed", [])])

            next_cursor = response.get("next_cursor")
            if not response.get("has_more"):
                break

        return {
            "added": all_added,
            "modified": all_modified,
            "removed": all_removed,
            "next_cursor": next_cursor,
            "has_more": False,
        }

    @staticmethod
    def _normalize_txn(t: dict[str, Any]) -> dict[str, Any]:
        d = t.get("date")
        pfc = t.get("personal_finance_category") or {}
        normalized: dict[str, Any] = {
            "transaction_id": t["transaction_id"],
            "account_id": t["account_id"],
            "date": d.isoformat() if hasattr(d, "isoformat") else d,
            "amount": t["amount"],
            "name": t.get("name") or "",
            "merchant_name": t.get("merchant_name"),
            "plaid_category_primary": pfc.get("primary"),
            "pending": t.get("pending", False),
        }
        try:
            if hasattr(t, "to_dict"):
                normalized["_source"] = t.to_dict()
            else:
                normalized["_source"] = dict(t)
        except Exception:
            pass
        return normalized
