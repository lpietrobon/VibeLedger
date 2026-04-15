from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field


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


class ConnectCompleteRequest(BaseModel):
    session_token: str
    public_token: str


class PatchAnnotationRequest(BaseModel):
    user_category: str | None = None
    notes: str | None = None
    reviewed: bool | None = None


class CategoryRuleDraft(BaseModel):
    rank: int = 0
    enabled: bool = True
    description_regex: str | None = None
    account_name_regex: str | None = None
    min_amount: Decimal | None = None
    max_amount: Decimal | None = None
    assigned_category: str
    name: str | None = None


class CategoryRuleCreateRequest(CategoryRuleDraft):
    pass


class CategoryRulePatchRequest(BaseModel):
    rank: int | None = None
    enabled: bool | None = None
    description_regex: str | None = None
    account_name_regex: str | None = None
    min_amount: Decimal | None = None
    max_amount: Decimal | None = None
    assigned_category: str | None = None
    name: str | None = None


class CategoryRuleScopeFilters(BaseModel):
    start_date: date | None = None
    end_date: date | None = None
    account_ids: list[int] = Field(default_factory=list)
    item_ids: list[int] = Field(default_factory=list)
    include_pending: bool = True


class CategoryRulePreviewRequest(BaseModel):
    rule_id: int | None = None
    draft_rule: CategoryRuleDraft | None = None
    scope: CategoryRuleScopeFilters = Field(default_factory=CategoryRuleScopeFilters)
    sample_limit: int = Field(default=25, ge=1, le=200)


class CategoryRuleApplyRequest(BaseModel):
    dry_run: bool = False
    scope: CategoryRuleScopeFilters = Field(default_factory=CategoryRuleScopeFilters)
    batch_size: int = Field(default=500, ge=1, le=2000)


class CategoryRuleRecomputeRequest(BaseModel):
    batch_size: int = Field(default=500, ge=1, le=2000)
    include_pending: bool = True


class CategoryRuleResponse(BaseModel):
    id: int
    rank: int
    enabled: bool
    description_regex: str | None
    account_name_regex: str | None
    min_amount: Decimal | None
    max_amount: Decimal | None
    assigned_category: str
    name: str | None
    created_at: datetime
    updated_at: datetime
