"""Chat functions: Aidentika webhooks (create/list/delete), and free AI
helpers (suggest wishes / video scenario / helpers usage).

Split out of handlers.py to keep files under the 300-line convention.
"""
from __future__ import annotations

from imperal_sdk import ActionResult

import aid_client as aid
from app import ext, chat
from schemas import (
    NoParams,
    CreateAidentikaWebhookParams, AidentikaWebhookCreated,
    ListAidentikaWebhooksParams, AidentikaWebhookList,
    DeleteAidentikaWebhookParams, DeleteResult,
    SuggestWishesParams, SuggestWishesResult,
    SuggestVideoScenarioParams, SuggestVideoScenarioResult,
    HelpersUsage,
)
from handlers_core import _require_key, _image_dict

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
