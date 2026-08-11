"""Pydantic schemas: Aidentika projects, cards, webhooks, and free AI
helpers (suggest wishes / video scenario / helpers usage).

Split out of schemas.py to keep files under the 300-line convention.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from schemas_generation import ImageInput

# ---------------------------------------------------------------------------
# Projects / cards
# ---------------------------------------------------------------------------

class CreateAidentikaProjectParams(BaseModel):
    name: str | None = Field(default=None, max_length=200, description="Display name")
    product_name: str | None = Field(default=None, max_length=200)
    category_id: str | None = Field(default=None, max_length=50)
    concept_id: str | None = Field(default=None, max_length=50)
    comment: str | None = Field(default=None, max_length=5000)


class ListAidentikaProjectsParams(BaseModel):
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
    source: str | None = Field(default=None, description="'api', 'api_inbox', or 'all'; default -- both API sources")


class GetAidentikaProjectParams(BaseModel):
    project_id: int


class UpdateAidentikaProjectParams(BaseModel):
    project_id: int
    name: str | None = Field(default=None, max_length=200)
    product_name: str | None = Field(default=None, max_length=200)
    category_id: str | None = Field(default=None, max_length=50)
    concept_id: str | None = Field(default=None, max_length=50)
    comment: str | None = Field(default=None, max_length=5000)


class AidentikaProject(BaseModel):
    id: int
    name: str | None = None
    product_name: str | None = None
    category_id: str | None = None
    concept_id: str | None = None
    comment: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class AidentikaProjectList(BaseModel):
    projects: list[AidentikaProject] = Field(default_factory=list)
    total: int = 0


class GetAidentikaCardParams(BaseModel):
    card_id: int


class MoveAidentikaCardParams(BaseModel):
    card_id: int
    project_id: int = Field(description="Destination project id (must belong to the same owner)")


class CardActionSummary(BaseModel):
    id: int | None = None
    type: str | None = None
    status: str | None = None
    depth: int = 0
    parent_action_id: int | None = None
    asset_path: str | None = None
    created_at: str | None = None
    completed_at: str | None = None


class AidentikaCard(BaseModel):
    id: int
    project_id: int
    status: str
    content_type: str
    aspect_ratio: str | None = None
    category_id: str | None = None
    concept_id: str | None = None
    comment: str | None = None
    card_user_text: str | None = None
    design_key: str | None = None
    active_action_id: int | None = None
    created_at: str | None = None
    updated_at: str | None = None
    actions: list[CardActionSummary] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Webhooks
# ---------------------------------------------------------------------------

class CreateAidentikaWebhookParams(BaseModel):
    url: str = Field(description="HTTPS URL to receive notifications, up to 2000 chars")
    events: list[str] | None = Field(default=None, description="Subscribe to specific events; omit for all: generation.completed/failed, edit.completed/failed, video.completed/failed")


class AidentikaWebhookCreated(BaseModel):
    id: int
    url: str
    secret: str = Field(description="Shown only once at creation -- save it for signature verification")
    events: list[str] = Field(default_factory=list)
    is_active: bool = True
    created_at: str | None = None


class ListAidentikaWebhooksParams(BaseModel):
    pass


class AidentikaWebhookItem(BaseModel):
    id: int
    url: str
    events: list[str] = Field(default_factory=list)
    is_active: bool
    created_at: str | None = None
    updated_at: str | None = None


class AidentikaWebhookList(BaseModel):
    webhooks: list[AidentikaWebhookItem] = Field(default_factory=list)


class DeleteAidentikaWebhookParams(BaseModel):
    webhook_id: int


class DeleteResult(BaseModel):
    deleted: bool
    message: str


# ---------------------------------------------------------------------------
# AI helpers (synchronous)
# ---------------------------------------------------------------------------

class SuggestWishesParams(BaseModel):
    images: list[ImageInput] = Field(min_length=1, max_length=5, description="1-5 product photos")
    category_id: str = Field(max_length=50)
    concept_id: str = Field(max_length=50)
    product_name: str | None = Field(default=None, max_length=200)


class SuggestWishesResult(BaseModel):
    text: str


class SuggestVideoScenarioParams(BaseModel):
    image: ImageInput = Field(description="Product photo")
    product_name: str | None = Field(default=None, max_length=200)
    category_id: str | None = Field(default=None, max_length=50)


class SuggestVideoScenarioResult(BaseModel):
    scenario: str


class HelpersUsage(BaseModel):
    used_today: int
    free_limit: int
    free_remaining: int
    paid_rate: str
