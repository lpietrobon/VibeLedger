from pydantic import BaseModel


class LinkTokenRequest(BaseModel):
    user_id: str = "default-user"


class LinkTokenResponse(BaseModel):
    link_token: str


class PublicTokenExchangeRequest(BaseModel):
    public_token: str


class PublicTokenExchangeResponse(BaseModel):
    item_id: str
    status: str


class ConnectSessionCreateRequest(BaseModel):
    user_id: str = "default-user"


class ConnectCompleteRequest(BaseModel):
    session_token: str
    public_token: str


class TransactionAnnotationPatchRequest(BaseModel):
    user_category: str | None = None
    notes: str | None = None
    reviewed: bool | None = None
