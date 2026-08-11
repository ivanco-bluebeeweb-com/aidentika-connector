"""Chat functions for Aidentika Connector.

Connect/disconnect, info (balance/pricing/categories), image upload +
free analysis, photo/card/video generation, edit, status/cancel/download,
results listing, projects + cards, webhooks, and free AI helpers.
"""
from __future__ import annotations

from imperal_sdk import ActionResult

import aid_client as aid
from app import ext, chat
from schemas import (
    NoParams,
    ConnectAidentikaParams, ProviderConnection, DisconnectResult,
    BalanceInfo, PricingInfo, CategoriesList,
    UploadProductImageParams, UploadResult,
    AnalyzeProductParams, AnalyzeResult,
    GeneratePhotoParams, GenerateCardParams, GenerateVideoParams,
    EditActionParams, GenerateResult,
    GetActionStatusParams, ActionStatus,
    CancelActionParams, CancelResult,
    DownloadResultParams, DownloadResult,
    ListResultsParams, ResultsList,
    CreateAidentikaProjectParams, ListAidentikaProjectsParams,
    GetAidentikaProjectParams, UpdateAidentikaProjectParams,
    AidentikaProject, AidentikaProjectList,
    GetAidentikaCardParams, MoveAidentikaCardParams, AidentikaCard,
    CreateAidentikaWebhookParams, AidentikaWebhookCreated,
    ListAidentikaWebhooksParams, AidentikaWebhookList,
    DeleteAidentikaWebhookParams, DeleteResult,
    SuggestWishesParams, SuggestWishesResult,
    SuggestVideoScenarioParams, SuggestVideoScenarioResult,
    HelpersUsage,
)


async def _get_api_key(ctx) -> str | None:
    return await ctx.secrets.get("aidentika_api_key")


def _image_dict(img) -> dict:
    """ImageInput pydantic model -> API dict, dropping unset fields."""
    d = {"media_type": img.media_type}
    if img.url:
        d["url"] = img.url
    if img.data:
        d["data"] = img.data
    return d


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------

@chat.function(
    "connect_aidentika",
    "Connect Aidentika by saving your API key, after checking it actually "
    "works. Get an API key at app.aidentika.com -> Profile -> API -> "
    "Create key (max 10 keys per account).",
    action_type="write",
    chain_callable=True,
    data_model=ProviderConnection,
    event="aidentika-connector.connect_aidentika",
    effects=["aidentika.provider.connected"],
)
async def connect_aidentika(ctx, params: ConnectAidentikaParams) -> ActionResult:
    """Validate-then-store: a key Aidentika rejects is never written."""
    api_key = params.api_key.strip()
    if not api_key:
        return ActionResult.error(
            "API key is required. Find it at app.aidentika.com -> Profile -> API.",
            code="AID_KEY_MISSING",
        )
    try:
        await aid.get_balance(ctx, api_key)
    except aid.ProviderError as exc:
        return ActionResult.error(str(exc), code=exc.code)

    await ctx.secrets.set("aidentika_api_key", api_key)
    return ActionResult.success(
        data=ProviderConnection(connected=True, message="Aidentika connected and verified."),
        summary="Connected to Aidentika.",
    )


@chat.function(
    "disconnect_aidentika",
    "Disconnect Aidentika: deletes the saved API key. Existing projects, "
    "cards and results in your Aidentika account are not affected.",
    action_type="write",
    chain_callable=True,
    data_model=DisconnectResult,
    event="aidentika-connector.disconnect_aidentika",
    effects=["aidentika.provider.disconnected"],
)
async def disconnect_aidentika(ctx, params: NoParams) -> ActionResult:
    """Remove the saved Aidentika API key. Existing generations/projects on Aidentika are untouched."""
    await ctx.secrets.delete("aidentika_api_key")
    return ActionResult.success(
        data=DisconnectResult(disconnected=True, message="Aidentika API key removed."),
        summary="Disconnected from Aidentika.",
    )


async def _require_key(ctx) -> tuple[str | None, ActionResult | None]:
    api_key = await _get_api_key(ctx)
    if not api_key:
        return None, ActionResult.error(
            "Aidentika is not connected. Connect it first with your API key "
            "from app.aidentika.com -> Profile -> API.",
            code="AID_NOT_CONNECTED",
        )
    return api_key, None


# ---------------------------------------------------------------------------
# Info: balance / pricing / categories
# ---------------------------------------------------------------------------

@chat.function(
    "get_aidentika_balance",
    "Check your current Aidentika sparks balance -- total, available, and "
    "held for in-flight generations.",
    action_type="read",
    chain_callable=True,
    data_model=BalanceInfo,
)
async def get_aidentika_balance(ctx, params: NoParams) -> ActionResult:
    """Fetch current sparks balance from Aidentika."""
    api_key, err = await _require_key(ctx)
    if err:
        return err
    try:
        data = await aid.get_balance(ctx, api_key)
    except aid.ProviderError as exc:
        return ActionResult.error(str(exc), code=exc.code)
    info = BalanceInfo(**data)
    return ActionResult.success(
        data=info,
        summary=f"Balance: {info.balance} sparks ({info.available} available, {info.holds} held).",
    )


@chat.function(
    "get_aidentika_pricing",
    "Read the sparks cost of every Aidentika operation: photo/card "
    "generation, edits, and 5s/10s video.",
    action_type="read",
    chain_callable=True,
    data_model=PricingInfo,
)
async def get_aidentika_pricing(ctx, params: NoParams) -> ActionResult:
    """Fetch the sparks cost of each Aidentika operation."""
    api_key, err = await _require_key(ctx)
    if err:
        return err
    try:
        data = await aid.get_pricing(ctx, api_key)
    except aid.ProviderError as exc:
        return ActionResult.error(str(exc), code=exc.code)
    return ActionResult.success(data=PricingInfo(**data), summary="Fetched Aidentika pricing.")


@chat.function(
    "list_aidentika_categories",
    "List all product categories and their shooting concepts. Use the "
    "category_id/concept_id values in generation calls. Cached 24h by "
    "Aidentika.",
    action_type="read",
    chain_callable=True,
    data_model=CategoriesList,
)
async def list_aidentika_categories(ctx, params: NoParams) -> ActionResult:
    """Fetch all product categories and concepts from Aidentika."""
    api_key, err = await _require_key(ctx)
    if err:
        return err
    try:
        data = await aid.get_categories(ctx, api_key)
    except aid.ProviderError as exc:
        return ActionResult.error(str(exc), code=exc.code)
    cats = data.get("categories", [])
    return ActionResult.success(
        data=CategoriesList(categories=cats),
        summary=f"{len(cats)} categories available.",
    )


# ---------------------------------------------------------------------------
# Upload + free analysis
# ---------------------------------------------------------------------------

@chat.function(
    "upload_product_image",
    "Upload a product image once (base64) to reuse its upload_id across "
    "several generation requests, instead of re-sending the base64 data "
    "each time. Valid for 1 hour; max 20 active uploads per account.",
    action_type="write",
    chain_callable=True,
    data_model=UploadResult,
    event="aidentika-connector.upload_product_image",
    effects=["aidentika.image.uploaded"],
)
async def upload_product_image(ctx, params: UploadProductImageParams) -> ActionResult:
    """Upload one image to Aidentika and return its reusable upload_id."""
    api_key, err = await _require_key(ctx)
    if err:
        return err
    try:
        data = await aid.upload_image(ctx, api_key, _image_dict(params.image))
    except aid.ProviderError as exc:
        return ActionResult.error(str(exc), code=exc.code)
    res = UploadResult(**data)
    return ActionResult.success(
        data=res,
        summary=f"Uploaded. upload_id={res.upload_id}, valid {res.expires_in}s.",
    )


@chat.function(
    "analyze_product",
    "Analyze a product photo for free (no sparks spent): detects category, "
    "product name, and key selling qualities. Use the result to fill in "
    "category_id/product_name/comment on a generation call.",
    action_type="read",
    chain_callable=True,
    data_model=AnalyzeResult,
)
async def analyze_product(ctx, params: AnalyzeProductParams) -> ActionResult:
    """Run Aidentika's free product analysis on one image."""
    api_key, err = await _require_key(ctx)
    if err:
        return err
    try:
        data = await aid.analyze(ctx, api_key, {"image": _image_dict(params.image)})
    except aid.ProviderError as exc:
        return ActionResult.error(str(exc), code=exc.code)
    res = AnalyzeResult(**data)
    return ActionResult.success(
        data=res,
        summary=f"Detected: {res.product_name or 'unknown product'} ({res.category_id or 'uncategorized'}).",
    )


# ---------------------------------------------------------------------------
# Generation: photo / card / video / edit
# ---------------------------------------------------------------------------

def _generate_result(data: dict) -> GenerateResult:
    return GenerateResult(
        action_id=data["action_id"],
        status=data.get("status", "pending"),
        poll_url=data.get("poll_url"),
        project_id=data.get("project_id"),
        card_id=data.get("card_id"),
    )


@chat.function(
    "generate_product_photo",
    "Generate styled product photo(s) from 1-5 reference images. All "
    "fields except images are optional -- category/concept/product name "
    "are auto-detected from the photos if omitted. Runs asynchronously: "
    "returns an action_id, poll get_action_status until completed, then "
    "download_result to get the image.",
    action_type="write",
    chain_callable=True,
    data_model=GenerateResult,
    event="aidentika-connector.generate_product_photo",
    effects=["aidentika.generation.started"],
)
async def generate_product_photo(ctx, params: GeneratePhotoParams) -> ActionResult:
    """Start an async styled product photo generation."""
    api_key, err = await _require_key(ctx)
    if err:
        return err
    body: dict = {"images": [_image_dict(i) for i in params.images]}
    for f in ("project_id", "client_group_id", "category_id", "concept_id",
              "product_name", "comment", "photo_style", "aspect_ratio",
              "resolution", "webhook_url"):
        v = getattr(params, f)
        if v is not None:
            body[f] = v
    try:
        data = await aid.generate_photo(ctx, api_key, body)
    except aid.ProviderError as exc:
        return ActionResult.error(str(exc), code=exc.code)
    res = _generate_result(data)
    return ActionResult.success(
        data=res,
        summary=f"Photo generation started. action_id={res.action_id}.",
    )


@chat.function(
    "generate_product_card",
    "Generate an infographic/marketing card from 1-5 reference images -- "
    "highlights text (user_text) over a designed layout. Runs "
    "asynchronously: returns an action_id, poll get_action_status until "
    "completed, then download_result.",
    action_type="write",
    chain_callable=True,
    data_model=GenerateResult,
    event="aidentika-connector.generate_product_card",
    effects=["aidentika.generation.started"],
)
async def generate_product_card(ctx, params: GenerateCardParams) -> ActionResult:
    """Start an async infographic/marketing card generation."""
    api_key, err = await _require_key(ctx)
    if err:
        return err
    body: dict = {"images": [_image_dict(i) for i in params.images]}
    for f in ("project_id", "client_group_id", "category_id", "concept_id",
              "product_name", "user_text", "design_key", "creativity",
              "aspect_ratio", "webhook_url"):
        v = getattr(params, f)
        if v is not None:
            body[f] = v
    if params.design_reference_image is not None:
        body["design_reference_image"] = _image_dict(params.design_reference_image)
    try:
        data = await aid.generate_card(ctx, api_key, body)
    except aid.ProviderError as exc:
        return ActionResult.error(str(exc), code=exc.code)
    res = _generate_result(data)
    return ActionResult.success(
        data=res,
        summary=f"Card generation started. action_id={res.action_id}.",
    )


@chat.function(
    "generate_product_video",
    "Animate a product image into a short video (5 or 10 seconds), "
    "optionally with a motion scenario description. Runs asynchronously: "
    "returns an action_id, poll get_action_status until completed, then "
    "download_result.",
    action_type="write",
    chain_callable=True,
    data_model=GenerateResult,
    event="aidentika-connector.generate_product_video",
    effects=["aidentika.generation.started"],
)
async def generate_product_video(ctx, params: GenerateVideoParams) -> ActionResult:
    """Start an async product video generation."""
    api_key, err = await _require_key(ctx)
    if err:
        return err
    body: dict = {"image": _image_dict(params.image)}
    for f in ("project_id", "client_group_id", "scenario", "duration_sec",
              "loop_mode", "card_mode", "aspect_ratio", "webhook_url"):
        v = getattr(params, f)
        if v is not None:
            body[f] = v
    if params.final_frame is not None:
        body["final_frame"] = _image_dict(params.final_frame)
    try:
        data = await aid.generate_video(ctx, api_key, body)
    except aid.ProviderError as exc:
        return ActionResult.error(str(exc), code=exc.code)
    res = _generate_result(data)
    return ActionResult.success(
        data=res,
        summary=f"Video generation started. action_id={res.action_id}.",
    )


@chat.function(
    "edit_generated_action",
    "Request a further edit/improvement of a completed generation "
    "(photo/card), by natural-language instruction. Creates a new version "
    "under the same Card. Runs asynchronously like any other generation.",
    action_type="write",
    chain_callable=True,
    data_model=GenerateResult,
    event="aidentika-connector.edit_generated_action",
    effects=["aidentika.generation.started"],
)
async def edit_generated_action(ctx, params: EditActionParams) -> ActionResult:
    """Start an async edit of a previous action's result."""
    api_key, err = await _require_key(ctx)
    if err:
        return err
    body: dict = {"instruction": params.instruction}
    if params.webhook_url is not None:
        body["webhook_url"] = params.webhook_url
    if params.client_group_id is not None:
        body["client_group_id"] = params.client_group_id
    try:
        data = await aid.edit_action(ctx, api_key, params.action_id, body)
    except aid.ProviderError as exc:
        return ActionResult.error(str(exc), code=exc.code)
    res = _generate_result(data)
    return ActionResult.success(
        data=res,
        summary=f"Edit started. new action_id={res.action_id}.",
    )


# ---------------------------------------------------------------------------
# Status / cancel / download / results
# ---------------------------------------------------------------------------

@chat.function(
    "get_action_status",
    "Check the status of a generation/edit/video action: pending, "
    "processing, completed (with result_url, signed for 30 days), or "
    "failed (with error_message).",
    action_type="read",
    chain_callable=True,
    data_model=ActionStatus,
)
async def get_action_status(ctx, params: GetActionStatusParams) -> ActionResult:
    """Fetch the current status of one Aidentika action."""
    api_key, err = await _require_key(ctx)
    if err:
        return err
    try:
        data = await aid.get_status(ctx, api_key, params.action_id)
    except aid.ProviderError as exc:
        return ActionResult.error(str(exc), code=exc.code)
    res = ActionStatus(**data)
    return ActionResult.success(data=res, summary=f"Action {res.action_id}: {res.status}.")


@chat.function(
    "cancel_action",
    "Cancel a pending or in-progress generation/edit/video action. Any "
    "held sparks are released back to your balance.",
    action_type="write",
    chain_callable=True,
    data_model=CancelResult,
    event="aidentika-connector.cancel_action",
    effects=["aidentika.generation.cancelled"],
)
async def cancel_action(ctx, params: CancelActionParams) -> ActionResult:
    """Cancel a pending/processing Aidentika action."""
    api_key, err = await _require_key(ctx)
    if err:
        return err
    try:
        data = await aid.cancel_action(ctx, api_key, params.action_id)
    except aid.ProviderError as exc:
        return ActionResult.error(str(exc), code=exc.code)
    res = CancelResult(**data)
    return ActionResult.success(data=res, summary=res.message)


@chat.function(
    "download_result",
    "Get the signed download URL for a completed action's result "
    "(image or video). Returns a status message instead if the action "
    "is not completed yet.",
    action_type="read",
    chain_callable=True,
    data_model=DownloadResult,
)
async def download_result(ctx, params: DownloadResultParams) -> ActionResult:
    """Resolve the signed result URL for a completed action via its status."""
    api_key, err = await _require_key(ctx)
    if err:
        return err
    try:
        data = await aid.download_result(ctx, api_key, params.action_id)
    except aid.ProviderError as exc:
        return ActionResult.error(str(exc), code=exc.code)
    status = data.get("status")
    if status == "completed" and data.get("result_url"):
        res = DownloadResult(result_url=data["result_url"], status=status, message=None)
        return ActionResult.success(data=res, summary="Result ready.")
    msg = data.get("error_message") if status == "failed" else f"Action is {status} -- not ready yet."
    res = DownloadResult(result_url=None, status=status, message=msg)
    return ActionResult.success(data=res, summary=msg or "Not ready yet.")


@chat.function(
    "list_generation_results",
    "List your past generation/edit/video actions with filters by type, "
    "status, date range, project, or correlation tag. Paginated.",
    action_type="read",
    chain_callable=True,
    data_model=ResultsList,
)
async def list_generation_results(ctx, params: ListResultsParams) -> ActionResult:
    """List past Aidentika actions with optional filters."""
    api_key, err = await _require_key(ctx)
    if err:
        return err
    query: dict = {"page": params.page, "page_size": params.page_size}
    for f in ("type", "status", "created_after", "created_before", "project_id", "client_group_id"):
        v = getattr(params, f)
        if v is not None:
            query[f] = v
    try:
        data = await aid.list_results(ctx, api_key, query)
    except aid.ProviderError as exc:
        return ActionResult.error(str(exc), code=exc.code)
    res = ResultsList(**data)
    return ActionResult.success(
        data=res,
        summary=f"{res.total} results (page {res.page}/{res.total_pages}).",
    )


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------

@chat.function(
    "create_aidentika_project",
    "Create a new Aidentika project (a named container for a batch of "
    "Cards) so generations can be grouped under a shared name instead of "
    "falling into the default 'API Inbox' project.",
    action_type="write",
    chain_callable=True,
    data_model=AidentikaProject,
    event="aidentika-connector.create_aidentika_project",
    effects=["aidentika.project.created"],
)
async def create_aidentika_project(ctx, params: CreateAidentikaProjectParams) -> ActionResult:
    """Create a new Aidentika project."""
    api_key, err = await _require_key(ctx)
    if err:
        return err
    body = {k: v for k, v in params.model_dump().items() if v is not None}
    try:
        data = await aid.create_project(ctx, api_key, body)
    except aid.ProviderError as exc:
        return ActionResult.error(str(exc), code=exc.code)
    res = AidentikaProject(**data)
    return ActionResult.success(data=res, summary=f"Project created: #{res.id} {res.name or ''}".strip())


@chat.function(
    "list_aidentika_projects",
    "List your Aidentika projects, optionally filtered to only api-created "
    "ones, only the default API Inbox, or all.",
    action_type="read",
    chain_callable=True,
    data_model=AidentikaProjectList,
)
async def list_aidentika_projects(ctx, params: ListAidentikaProjectsParams) -> ActionResult:
    """List Aidentika projects."""
    api_key, err = await _require_key(ctx)
    if err:
        return err
    query = {"limit": params.limit, "offset": params.offset}
    if params.source is not None:
        query["source"] = params.source
    try:
        data = await aid.list_projects(ctx, api_key, query)
    except aid.ProviderError as exc:
        return ActionResult.error(str(exc), code=exc.code)
    items = [AidentikaProject(**p) for p in data.get("items", data.get("projects", []))]
    return ActionResult.success(
        data=AidentikaProjectList(projects=items, total=data.get("total", len(items))),
        summary=f"{len(items)} project(s).",
    )


@chat.function(
    "get_aidentika_project",
    "Read one Aidentika project in full, including its Cards.",
    action_type="read",
    chain_callable=True,
    data_model=AidentikaProject,
)
async def get_aidentika_project(ctx, params: GetAidentikaProjectParams) -> ActionResult:
    """Fetch one Aidentika project with its cards and actions."""
    api_key, err = await _require_key(ctx)
    if err:
        return err
    try:
        data = await aid.get_project(ctx, api_key, params.project_id)
    except aid.ProviderError as exc:
        return ActionResult.error(str(exc), code=exc.code)
    res = AidentikaProject(**{k: v for k, v in data.items() if k in AidentikaProject.model_fields})
    return ActionResult.success(data=res, summary=f"Project #{res.id}: {res.name or '(unnamed)'}")


@chat.function(
    "update_aidentika_project",
    "Update an Aidentika project's name, product name, category/concept, "
    "or comment. Only given fields change.",
    action_type="write",
    chain_callable=True,
    data_model=AidentikaProject,
    event="aidentika-connector.update_aidentika_project",
    effects=["aidentika.project.updated"],
)
async def update_aidentika_project(ctx, params: UpdateAidentikaProjectParams) -> ActionResult:
    """Update fields of an existing Aidentika project."""
    api_key, err = await _require_key(ctx)
    if err:
        return err
    body = {k: v for k, v in params.model_dump().items() if k != "project_id" and v is not None}
    try:
        data = await aid.update_project(ctx, api_key, params.project_id, body)
    except aid.ProviderError as exc:
        return ActionResult.error(str(exc), code=exc.code)
    res = AidentikaProject(**{k: v for k, v in data.items() if k in AidentikaProject.model_fields})
    return ActionResult.success(data=res, summary=f"Project #{res.id} updated.")


# ---------------------------------------------------------------------------
# Cards
# ---------------------------------------------------------------------------

@chat.function(
    "get_aidentika_card",
    "Read one Aidentika Card in full: its status, category/concept, "
    "comment, active version, and every generate/edit action (version) "
    "recorded under it.",
    action_type="read",
    chain_callable=True,
    data_model=AidentikaCard,
)
async def get_aidentika_card(ctx, params: GetAidentikaCardParams) -> ActionResult:
    """Fetch one Aidentika card with its action history."""
    api_key, err = await _require_key(ctx)
    if err:
        return err
    try:
        data = await aid.get_card(ctx, api_key, params.card_id)
    except aid.ProviderError as exc:
        return ActionResult.error(str(exc), code=exc.code)
    res = AidentikaCard(**data)
    return ActionResult.success(data=res, summary=f"Card #{res.id}: {res.status}, {len(res.actions)} version(s).")


@chat.function(
    "move_aidentika_card",
    "Move an Aidentika Card to a different project (must belong to the "
    "same account).",
    action_type="write",
    chain_callable=True,
    data_model=AidentikaCard,
    event="aidentika-connector.move_aidentika_card",
    effects=["aidentika.card.moved"],
)
async def move_aidentika_card(ctx, params: MoveAidentikaCardParams) -> ActionResult:
    """Move an Aidentika card to a different project."""
    api_key, err = await _require_key(ctx)
    if err:
        return err
    try:
        data = await aid.move_card(ctx, api_key, params.card_id, {"project_id": params.project_id})
    except aid.ProviderError as exc:
        return ActionResult.error(str(exc), code=exc.code)
    res = AidentikaCard(**data)
    return ActionResult.success(data=res, summary=f"Card #{res.id} moved to project #{res.project_id}.")


# ---------------------------------------------------------------------------
# Webhooks
# ---------------------------------------------------------------------------

@chat.function(
    "create_aidentika_webhook",
    "Register a webhook URL to get notified when generations complete or "
    "fail, instead of polling get_action_status. Max 5 webhooks per "
    "account. The signing secret is shown ONLY in this response -- save it.",
    action_type="write",
    chain_callable=True,
    data_model=AidentikaWebhookCreated,
    event="aidentika-connector.create_aidentika_webhook",
    effects=["aidentika.webhook.created"],
)
async def create_aidentika_webhook(ctx, params: CreateAidentikaWebhookParams) -> ActionResult:
    """Register a new Aidentika webhook."""
    api_key, err = await _require_key(ctx)
    if err:
        return err
    body: dict = {"url": params.url}
    if params.events is not None:
        body["events"] = params.events
    try:
        data = await aid.create_webhook(ctx, api_key, body)
    except aid.ProviderError as exc:
        return ActionResult.error(str(exc), code=exc.code)
    res = AidentikaWebhookCreated(**data)
    return ActionResult.success(
        data=res,
        summary=f"Webhook #{res.id} created for {', '.join(res.events)}. Secret shown once -- save it now.",
    )


@chat.function(
    "list_aidentika_webhooks",
    "List your registered Aidentika webhooks (URLs and subscribed "
    "events). Secrets are never shown again after creation.",
    action_type="read",
    chain_callable=True,
    data_model=AidentikaWebhookList,
)
async def list_aidentika_webhooks(ctx, params: NoParams) -> ActionResult:
    """List registered Aidentika webhooks."""
    api_key, err = await _require_key(ctx)
    if err:
        return err
    try:
        data = await aid.list_webhooks(ctx, api_key)
    except aid.ProviderError as exc:
        return ActionResult.error(str(exc), code=exc.code)
    items = data.get("webhooks", [])
    return ActionResult.success(
        data=AidentikaWebhookList(webhooks=items),
        summary=f"{len(items)} webhook(s) registered.",
    )


@chat.function(
    "delete_aidentika_webhook",
    "Permanently delete an Aidentika webhook. Cannot be undone.",
    action_type="destructive",
    chain_callable=True,
    data_model=DeleteResult,
    event="aidentika-connector.delete_aidentika_webhook",
    effects=["aidentika.webhook.deleted"],
)
async def delete_aidentika_webhook(ctx, params: DeleteAidentikaWebhookParams) -> ActionResult:
    """Permanently delete an Aidentika webhook."""
    api_key, err = await _require_key(ctx)
    if err:
        return err
    try:
        await aid.delete_webhook(ctx, api_key, params.webhook_id)
    except aid.ProviderError as exc:
        return ActionResult.error(str(exc), code=exc.code)
    return ActionResult.success(
        data=DeleteResult(deleted=True, message=f"Webhook {params.webhook_id} deleted."),
        summary=f"Webhook {params.webhook_id} deleted.",
    )


# ---------------------------------------------------------------------------
# AI helpers -- synchronous, free (1-100/day), then 1 spark per 20 calls
# ---------------------------------------------------------------------------

@chat.function(
    "suggest_product_wishes",
    "AI-generate marketing description text from 1-5 product photos. "
    "Synchronous -- result comes back immediately. Free for the first "
    "1-100 calls/day, then 1 spark per 20 calls.",
    action_type="read",
    chain_callable=True,
    data_model=SuggestWishesResult,
)
async def suggest_product_wishes(ctx, params: SuggestWishesParams) -> ActionResult:
    """Ask Aidentika's free AI helper to draft marketing text from product photos."""
    api_key, err = await _require_key(ctx)
    if err:
        return err
    body: dict = {
        "images": [_image_dict(i) for i in params.images],
        "category_id": params.category_id,
        "concept_id": params.concept_id,
    }
    if params.product_name is not None:
        body["product_name"] = params.product_name
    try:
        data = await aid.suggest_wishes(ctx, api_key, body)
    except aid.ProviderError as exc:
        return ActionResult.error(str(exc), code=exc.code)
    return ActionResult.success(data=SuggestWishesResult(**data), summary="Marketing text drafted.")


@chat.function(
    "suggest_video_scenario",
    "AI-generate a motion scenario description for a product video from "
    "one photo. Use the result in generate_product_video's scenario "
    "field. Synchronous, same free-tier/spark rule as suggest_product_wishes.",
    action_type="read",
    chain_callable=True,
    data_model=SuggestVideoScenarioResult,
)
async def suggest_video_scenario(ctx, params: SuggestVideoScenarioParams) -> ActionResult:
    """Ask Aidentika's free AI helper to draft a video motion scenario."""
    api_key, err = await _require_key(ctx)
    if err:
        return err
    body: dict = {"image": _image_dict(params.image)}
    if params.product_name is not None:
        body["product_name"] = params.product_name
    if params.category_id is not None:
        body["category_id"] = params.category_id
    try:
        data = await aid.suggest_video_scenario(ctx, api_key, body)
    except aid.ProviderError as exc:
        return ActionResult.error(str(exc), code=exc.code)
    return ActionResult.success(data=SuggestVideoScenarioResult(**data), summary="Video scenario drafted.")


@chat.function(
    "get_helpers_usage",
    "Check how many AI-helper calls (suggest_product_wishes + "
    "suggest_video_scenario combined) you've used today against the "
    "free daily allowance.",
    action_type="read",
    chain_callable=True,
    data_model=HelpersUsage,
)
async def get_helpers_usage(ctx, params: NoParams) -> ActionResult:
    """Fetch today's free-tier usage for Aidentika's AI helpers."""
    api_key, err = await _require_key(ctx)
    if err:
        return err
    try:
        data = await aid.get_helpers_usage(ctx, api_key)
    except aid.ProviderError as exc:
        return ActionResult.error(str(exc), code=exc.code)
    res = HelpersUsage(**data)
    return ActionResult.success(data=res, summary=f"{res.used_today} helper call(s) used today.")
