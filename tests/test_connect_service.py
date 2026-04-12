from datetime import datetime, timedelta

from app.db.session import SessionLocal
from app.models.models import ConnectSession
from app.services.connect_service import ConnectService


def test_connect_session_signing_and_ttl():
    svc = ConnectService()
    with SessionLocal() as db:
        session = svc.create_session(db, user_id="user-123")

        assert svc.validate_session_token(session.session_token)
        assert svc.get_active_session(db, session.session_token) is not None
        ttl_remaining = session.expires_at - datetime.utcnow()
        assert timedelta(seconds=0) < ttl_remaining <= timedelta(minutes=svc.ttl_minutes, seconds=5)


def test_connect_session_rejects_tampered_expired_and_completed_tokens():
    svc = ConnectService()
    with SessionLocal() as db:
        created = svc.create_session(db, user_id="user-123")
        raw, _ = created.session_token.split(".", 1)
        tampered = f"{raw}.not-a-real-signature"

        assert svc.validate_session_token(tampered) is False
        assert svc.get_active_session(db, tampered) is None

        created.status = "completed"
        db.commit()
        assert svc.get_active_session(db, created.session_token) is None

        expired_raw = "expired-session"
        expired = ConnectSession(
            session_token=f"{expired_raw}.{svc._sign(expired_raw)}",
            user_id="u2",
            status="created",
            expires_at=datetime.utcnow() - timedelta(seconds=1),
        )
        db.add(expired)
        db.commit()
        assert svc.get_active_session(db, expired.session_token) is None
