import secrets
from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.time import utcnow
from app.models.models import ConnectSession


class ConnectService:
    ttl_minutes = 20

    def create_session(
        self,
        db: Session,
        user_id: str = "default-user",
        link_token: str | None = None,
    ) -> ConnectSession:
        session = ConnectSession(
            session_token=secrets.token_urlsafe(32),
            user_id=user_id,
            status="created",
            link_token=link_token,
            expires_at=utcnow() + timedelta(minutes=self.ttl_minutes),
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        return session

    def get_active_session(self, db: Session, token: str) -> ConnectSession | None:
        session = (
            db.query(ConnectSession)
            .filter(ConnectSession.session_token == token)
            .first()
        )
        if not session:
            return None
        if session.expires_at < utcnow() or session.status == "completed":
            return None
        return session
