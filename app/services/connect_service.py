import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.models import ConnectSession


class ConnectService:
    ttl_minutes = 20

    def create_session(self, db: Session, user_id: str = "default-user") -> ConnectSession:
        raw = secrets.token_urlsafe(24)
        sig = self._sign(raw)
        session_token = f"{raw}.{sig}"
        session = ConnectSession(
            session_token=session_token,
            user_id=user_id,
            status="created",
            expires_at=datetime.utcnow() + timedelta(minutes=self.ttl_minutes),
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        return session

    def validate_session_token(self, token: str) -> bool:
        try:
            raw, sig = token.split(".", 1)
        except ValueError:
            return False
        expected = self._sign(raw)
        return hmac.compare_digest(sig, expected)

    def get_active_session(self, db: Session, token: str) -> ConnectSession | None:
        if not self.validate_session_token(token):
            return None
        session = db.query(ConnectSession).filter(ConnectSession.session_token == token).first()
        if not session:
            return None
        if session.expires_at < datetime.utcnow() or session.status == "completed":
            return None
        return session

    def _sign(self, raw: str) -> str:
        digest = hmac.new(
            settings.connect_signing_key.encode("utf-8"),
            raw.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        return base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")
