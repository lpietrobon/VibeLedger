from datetime import date


class PlaidClient:
    def create_link_token(self, user_id: str) -> dict:
        return {"link_token": f"mock-link-token-{user_id}"}

    def exchange_public_token(self, public_token: str) -> dict:
        return {
            "access_token": f"access-{public_token}",
            "item_id": "item-mock-123",
        }

    def sync_transactions(self, access_token: str, cursor: str | None = None) -> dict:
        # placeholder deterministic payload
        return {
            "added": [
                {
                    "transaction_id": "txn-001",
                    "account_id": "acct-001",
                    "date": str(date.today()),
                    "amount": 12.34,
                    "name": "Coffee Shop",
                    "merchant_name": "Coffee Shop",
                    "pending": False,
                }
            ],
            "modified": [],
            "removed": [],
            "next_cursor": "cursor-1" if cursor is None else f"{cursor}-next",
            "has_more": False,
        }
