"""Chat functions: photo/card/video generation, edit, status/cancel/
download, and results listing.

Split out of handlers.py to keep files under the 300-line convention.
"""
from __future__ import annotations

from imperal_sdk import ActionResult

import aid_client as aid
from app import ext, chat
from schemas import (
    GeneratePhotoParams, GenerateCardParams, GenerateVideoParams,
    EditActionParams, GenerateResult,
    GetActionStatusParams, ActionStatus,
    CancelActionParams, CancelResult,
    DownloadResultParams, DownloadResult,
    ListResultsParams, ResultsList,
)
from handlers_core import _require_key, _image_dict

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


