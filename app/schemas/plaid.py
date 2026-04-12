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


class CreateConnectSessionRequest(BaseModel):
    user_id: str = "default-user"


class PatchAnnotationRequest(BaseModel):
    user_category: str | None = None
    notes: str | None = None
    reviewed: bool | None = None
