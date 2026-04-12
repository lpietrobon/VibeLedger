from pydantic import BaseModel


class ConnectSessionCreateRequest(BaseModel):
    user_id: str = "default-user"


class ConnectCompleteRequest(BaseModel):
    session_token: str
    public_token: str


class TransactionAnnotationPatchRequest(BaseModel):
    user_category: str | None = None
    notes: str | None = None
    reviewed: bool | None = None
