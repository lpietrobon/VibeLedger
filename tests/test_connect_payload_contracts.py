from app.schemas.connect import ConnectSessionCreateRequest, TransactionAnnotationPatchRequest


def test_connect_session_payload_defaults_user_id():
    payload = ConnectSessionCreateRequest()
    assert payload.user_id == "default-user"


def test_annotation_patch_tracks_explicit_null_fields():
    payload = TransactionAnnotationPatchRequest(notes=None)
    assert "notes" in payload.model_fields_set
