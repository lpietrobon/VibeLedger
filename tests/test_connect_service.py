from datetime import timedelta

from app.core.time import utcnow
from app.db.session import SessionLocal
from app.models.models import ConnectSession
from app.services.connect_service import ConnectService


def test_connect_session_ttl_and_lookup():
    svc = ConnectService()
    with SessionLocal() as db:
        session = svc.create_session(db, user_id="user-123", link_token="lt-abc")
        assert svc.get_active_session(db, session.session_token) is not None
        assert session.link_token == "lt-abc"
        ttl_remaining = session.expires_at - utcnow()
        assert timedelta(seconds=0) < ttl_remaining <= timedelta(minutes=svc.ttl_minutes, seconds=5)


def test_connect_session_rejects_unknown_expired_and_completed_tokens():
    svc = ConnectService()
    with SessionLocal() as db:
        assert svc.get_active_session(db, "not-a-real-token") is None

        created = svc.create_session(db, user_id="user-123")
        created.status = "completed"
        db.commit()
        assert svc.get_active_session(db, created.session_token) is None

        expired = ConnectSession(
            session_token="exp-tok",
            user_id="u2",
            status="created",
            expires_at=utcnow() - timedelta(seconds=1),
        )
        db.add(expired)
        db.commit()
        assert svc.get_active_session(db, expired.session_token) is None
