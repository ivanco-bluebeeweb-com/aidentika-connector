"""Pydantic schemas for Aidentika Connector -- params and typed data models.

Field shapes (types, maxLength, defaults, enums) are copied directly from
Aidentika's own OpenAPI 3.1 spec (`GET /api/v1/public/openapi.json`), not
guessed from doc prose -- so a param name/limit here matches the real API
exactly.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class NoParams(BaseModel):
    """Empty params for parameterless read tools."""
    pass


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------

class ConnectAidentikaParams(BaseModel):
    api_key: str = Field(description="Your Aidentika API key (starts with ak_) from app.aidentika.com -> Profile -> API")


class ProviderConnection(BaseModel):
    connected: bool
    message: str


class DisconnectResult(BaseModel):
    disconnected: bool
    message: str


# ---------------------------------------------------------------------------
# Shared: image input
# ---------------------------------------------------------------------------

class ImageInput(BaseModel):
    """One product/reference image -- provide ONE of url or data.

    `data` accepts base64-encoded image bytes OR an `upload_id` (upl_...)
    returned by `upload_product_image`, per Aidentika's ImageInput schema.
    """
    url: str | None = Field(default=None, max_length=2048, description="Public HTTPS URL of the image")
    data: str | None = Field(default=None, max_length=21000000, description="Base64-encoded image bytes, or an upload_id (upl_...)")
    media_type: str = Field(default="image/jpeg", description="MIME type hint, used with data")


# ---------------------------------------------------------------------------
# Info: balance / pricing / categories
# ---------------------------------------------------------------------------

class BalanceInfo(BaseModel):
    balance: int
    available: int
    holds: int


class PricingInfo(BaseModel):
    generation: int
    improvement: int
    video_5sec: int
    video_10sec: int


class ConceptItem(BaseModel):
    id: str
    name: str


class CategoryItem(BaseModel):
    id: str
    name: str
    concepts: list[ConceptItem] = Field(default_factory=list)


class CategoriesList(BaseModel):
    categories: list[CategoryItem] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Upload / analyze
# ---------------------------------------------------------------------------

class UploadProductImageParams(BaseModel):
    image: ImageInput = Field(description="Image to upload (base64 data or a public HTTPS url)")


class UploadResult(BaseModel):
    upload_id: str
    expires_in: int = 3600


class AnalyzeProductParams(BaseModel):
    image: ImageInput = Field(description="Product image to analyze")


class AnalyzeResult(BaseModel):
    category_id: str | None = None
    product_name: str | None = None
    qualities: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

class GeneratePhotoParams(BaseModel):
    images: list[ImageInput] = Field(min_length=1, max_length=5, description="1-5 product reference images")
    project_id: int | None = Field(default=None, description="Append the generated Card to an existing Project; omit for the key's default 'API Inbox'")
    client_group_id: str | None = Field(default=None, max_length=100, description="Arbitrary correlation tag echoed back in results/webhooks")
    category_id: str | None = Field(default=None, max_length=50, description="Omit for auto-detection from images")
    concept_id: str | None = Field(default=None, max_length=50, description="Omit to use the default concept for the category")
    product_name: str | None = Field(default=None, max_length=200)
    comment: str | None = Field(default=None, max_length=5000, description="User wishes / additional description")
    photo_style: str = Field(default="classic", description="'classic' or 'home'")
    aspect_ratio: str = Field(default="3:4", description="9:16, 4:3, 1:1, 16:9, or 3:4")
    resolution: str = Field(default="2K", description="Output resolution: 1K, 2K (default), 4K -- affects sparks cost")
    webhook_url: str | None = Field(default=None, max_length=500)


class GenerateCardParams(BaseModel):
    images: list[ImageInput] = Field(min_length=1, max_length=5, description="1-5 product reference images")
    project_id: int | None = Field(default=None, description="Append the generated Card to an existing Project; omit for the key's default 'API Inbox'")
    client_group_id: str | None = Field(default=None, max_length=100)
    category_id: str | None = Field(default=None, max_length=50)
    concept_id: str = Field(default="infographic", max_length=50)
    product_name: str | None = Field(default=None, max_length=200)
    user_text: str | None = Field(default=None, max_length=5000, description="What to highlight on the card")
    design_key: str | None = Field(default=None, max_length=100, description="Reuse a design style by key")
    creativity: float = Field(default=0.5, ge=0.0, le=1.0, description="0=exact copy, 1=free interpretation")
    design_reference_image: ImageInput | None = Field(default=None, description="Style reference image")
    aspect_ratio: str = Field(default="3:4")
    webhook_url: str | None = Field(default=None, max_length=500)


class GenerateVideoParams(BaseModel):
    image: ImageInput = Field(description="Source image to animate")
    project_id: int | None = Field(default=None, description="Append the generated Card to an existing Project; omit for the key's default 'API Inbox'")
    client_group_id: str | None = Field(default=None, max_length=100)
    scenario: str = Field(default="", max_length=1500, description="Video motion description")
    duration_sec: int = Field(default=5, description="5 or 10 seconds")
    loop_mode: bool = Field(default=False, description="Seamless loop video")
    card_mode: bool = Field(default=False, description="Static camera, preserve text/infographics")
    final_frame: ImageInput | None = Field(default=None, description="Custom final frame, ignored if loop_mode")
    aspect_ratio: str = Field(default="3:4")
    webhook_url: str | None = Field(default=None, max_length=500)


class EditActionParams(BaseModel):
    action_id: int = Field(description="Existing completed action (photo/card) to edit")
    instruction: str = Field(max_length=1000, description="Edit instruction text")
    client_group_id: str | None = Field(default=None, max_length=100)
    webhook_url: str | None = Field(default=None, max_length=500)


class GenerateResult(BaseModel):
    action_id: int
    status: str = "pending"
    poll_url: str | None = None
    project_id: int | None = None
    card_id: int | None = None


# ---------------------------------------------------------------------------
# Status / results
# ---------------------------------------------------------------------------

class GetActionStatusParams(BaseModel):
    action_id: int = Field(description="Action id returned by a generate/edit call")


class ActionStatus(BaseModel):
    action_id: int
    status: str
    type: str
    result_url: str | None = None
    result_url_expires_at: str | None = None
    error_message: str | None = None
    created_at: str | None = None
    completed_at: str | None = None


class CancelActionParams(BaseModel):
    action_id: int = Field(description="Pending/processing action to cancel")


class CancelResult(BaseModel):
    action_id: int
    cancelled: bool
    message: str


class DownloadResultParams(BaseModel):
    action_id: int = Field(description="Completed action whose result to download")


class DownloadResult(BaseModel):
    result_url: str | None = None
    status: str | None = None
    message: str | None = None


class ListResultsParams(BaseModel):
    type: Literal["generate", "edit", "video"] | None = Field(default=None, description="Filter by action type")
    status: Literal["pending", "processing", "completed", "failed"] | None = Field(default=None)
    created_after: str | None = Field(default=None, max_length=10, description="YYYY-MM-DD")
    created_before: str | None = Field(default=None, max_length=10, description="YYYY-MM-DD")
    project_id: int | None = Field(default=None, description="Show only results in this project")
    client_group_id: str | None = Field(default=None, max_length=100, description="Filter by correlation tag sent on generate")
    page: int = Field(default=1, ge=1, le=1000)
    page_size: int = Field(default=20, ge=1, le=100)


class ResultItem(BaseModel):
    action_id: int
    project_id: int | None = None
    card_id: int | None = None
    client_group_id: str | None = None
    type: str
    status: str
    result_url: str | None = None
    result_url_expires_at: str | None = None
    storage_status: str = "available"
    error_message: str | None = None
    created_at: str | None = None
    completed_at: str | None = None


class ResultsList(BaseModel):
    items: list[ResultItem] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20
    total_pages: int = 0


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
