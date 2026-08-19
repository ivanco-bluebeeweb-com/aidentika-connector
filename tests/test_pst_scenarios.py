"""Plausible Scenario Tests (PST) -- Aidentika Connector.

Method: Docs/session-notes/SCENARIO_TESTING_STANDARD.md. Persona: single
role, the Aidentika account owner (BYOK -- their own app.aidentika.com
account, their own sparks balance). Complements the existing happy-path
unit tests in test_handlers_manage.py / test_handlers_generate.py, which
this file does NOT duplicate -- it adds the missing branches: error,
blocked, recovery, adversarial, across the full generation lifecycle.
"""
from __future__ import annotations

import pytest

import handlers as h
from schemas import (
    NoParams, ImageInput, ConnectAidentikaParams,
    GeneratePhotoParams, GenerateVideoParams, EditActionParams,
    GetActionStatusParams, CancelActionParams, DownloadResultParams,
    UploadProductImageParams, AnalyzeProductParams,
    CreateAidentikaWebhookParams, DeleteAidentikaWebhookParams,
    ListResultsParams,
)


# ── happy: full generation lifecycle chained together ──────────────────────

@pytest.mark.asyncio
async def test_happy_full_photo_lifecycle_start_to_download(ctx_connected):
    ctx_connected.http.mock_post("/generate/photo", {
        "action_id": 500, "status": "pending", "poll_url": "/status/500",
    })
    start = await h.generate_product_photo(
        ctx_connected, GeneratePhotoParams(images=[ImageInput(url="https://example.com/p.jpg")]))
    assert start.error is None
    action_id = start.data.action_id

    ctx_connected.http.mock_get("/status/500", {
        "action_id": 500, "status": "completed", "type": "generate",
        "result_url": "https://cdn.aidentika.com/500.jpg",
    })
    dl = await h.download_result(ctx_connected, DownloadResultParams(action_id=action_id))
    assert dl.error is None
    assert dl.data.result_url == "https://cdn.aidentika.com/500.jpg"


# ── error: provider rejects the request (insufficient sparks) ──────────────

@pytest.mark.asyncio
async def test_error_generate_insufficient_sparks_surfaces_provider_code(ctx_connected):
    ctx_connected.http.mock_post("/generate/photo", {
        "error": "insufficient_tokens", "message": "Not enough sparks for this operation.",
    }, status=402)
    result = await h.generate_product_photo(
        ctx_connected, GeneratePhotoParams(images=[ImageInput(url="https://example.com/p.jpg")]))
    assert result.error is not None
    assert result.error_code == "insufficient_tokens"


@pytest.mark.asyncio
async def test_error_rate_limit_exceeded_surfaces_provider_code(ctx_connected):
    ctx_connected.http.mock_get("/balance", {
        "error": "rate_limit_exceeded", "message": "Too many requests.",
    }, status=429)
    result = await h.get_aidentika_balance(ctx_connected, NoParams())
    assert result.error is not None
    assert result.error_code == "rate_limit_exceeded"


@pytest.mark.asyncio
async def test_error_malformed_error_body_falls_back_to_http_code(ctx_connected):
    """Provider returns a non-JSON-dict error body -- client must not crash,
    must fall back to a synthetic AID_HTTP_<code>."""
    ctx_connected.http.mock_get("/balance", "Internal Server Error", status=500)
    result = await h.get_aidentika_balance(ctx_connected, NoParams())
    assert result.error is not None
    assert result.error_code == "AID_HTTP_500"


# ── blocked: not connected / action doesn't exist yet ───────────────────────

@pytest.mark.asyncio
async def test_blocked_generate_without_connection(ctx):
    result = await h.generate_product_photo(
        ctx, GeneratePhotoParams(images=[ImageInput(url="https://example.com/p.jpg")]))
    assert result.error is not None
    assert result.error_code == "AID_NOT_CONNECTED"


@pytest.mark.asyncio
async def test_blocked_cancel_unknown_action_id(ctx_connected):
    ctx_connected.http.mock_post("/cancel/999999", {
        "error": "action_not_found", "message": "No such action.",
    }, status=404)
    result = await h.cancel_action(ctx_connected, CancelActionParams(action_id=999999))
    assert result.error is not None
    assert result.error_code == "action_not_found"


@pytest.mark.asyncio
async def test_blocked_download_on_failed_action_returns_error_message_not_url(ctx_connected):
    ctx_connected.http.mock_get("/status/321", {
        "action_id": 321, "status": "failed", "type": "generate",
        "result_url": None, "error_message": "Reference image was rejected by moderation.",
    })
    result = await h.download_result(ctx_connected, DownloadResultParams(action_id=321))
    assert result.error is None  # surfaced as a status message, not an ActionResult error
    assert result.data.result_url is None
    assert "moderation" in (result.data.message or "").lower()


# ── recovery: connect fails once, then succeeds after fixing the key ───────

@pytest.mark.asyncio
async def test_recovery_reconnect_after_bad_key_then_good_key(ctx):
    ctx.http.mock_get("/balance", {"error": "invalid_api_key", "message": "bad"}, status=401)
    first = await h.connect_aidentika(ctx, ConnectAidentikaParams(api_key="ak_bad"))
    assert first.error is not None
    assert await ctx.secrets.get("aidentika_api_key") is None

    # MockHTTP._find returns the FIRST matching entry in registration order,
    # not the most-recently registered one -- clear before re-mocking the
    # same path for the second call in this sequence.
    ctx.http._mocks.clear()
    ctx.http.mock_get("/balance", {"balance": 10, "available": 10, "holds": 0})
    second = await h.connect_aidentika(ctx, ConnectAidentikaParams(api_key="ak_good"))
    assert second.error is None
    assert await ctx.secrets.get("aidentika_api_key") == "ak_good"


@pytest.mark.asyncio
async def test_recovery_cancel_then_retry_generation(ctx_connected):
    ctx_connected.http.mock_post("/cancel/700", {
        "action_id": 700, "cancelled": True, "message": "Cancelled, sparks released.",
    })
    cancel = await h.cancel_action(ctx_connected, CancelActionParams(action_id=700))
    assert cancel.error is None
    assert cancel.data.cancelled is True

    ctx_connected.http.mock_post("/generate/photo", {
        "action_id": 701, "status": "pending", "poll_url": "/status/701",
    })
    retry = await h.generate_product_photo(
        ctx_connected, GeneratePhotoParams(images=[ImageInput(url="https://example.com/p2.jpg")]))
    assert retry.error is None
    assert retry.data.action_id == 701


# ── adversarial: edge/weird inputs the provider or client must not choke on ─

@pytest.mark.asyncio
async def test_adversarial_disconnect_is_idempotent_when_never_connected(ctx):
    """Disconnecting when nothing was ever connected must not raise."""
    result = await h.disconnect_aidentika(ctx, NoParams())
    assert result.error is None
    assert result.data.disconnected is True


@pytest.mark.asyncio
async def test_adversarial_delete_webhook_twice_second_call_not_found(ctx_connected):
    ctx_connected.http._mocks.append(("DELETE", "/webhooks/9", {"deleted": True}, 200, {}))
    first = await h.delete_aidentika_webhook(ctx_connected, DeleteAidentikaWebhookParams(webhook_id=9))
    assert first.error is None
    assert first.data.deleted is True

    # Same MockHTTP FIFO-match note as the recovery test above: clear before
    # re-mocking the same path for the second call.
    ctx_connected.http._mocks.clear()
    ctx_connected.http._mocks.append(("DELETE", "/webhooks/9", {
        "error": "webhook_not_found", "message": "Already deleted.",
    }, 404, {}))
    second = await h.delete_aidentika_webhook(ctx_connected, DeleteAidentikaWebhookParams(webhook_id=9))
    assert second.error is not None
    assert second.error_code == "webhook_not_found"


@pytest.mark.asyncio
async def test_adversarial_edit_action_on_already_completed_action_id(ctx_connected):
    """Editing an action_id that belongs to an already-terminal action --
    provider is the source of truth here, client must pass its rejection
    straight through, not silently succeed."""
    ctx_connected.http.mock_post("/edit/42", {
        "error": "action_not_editable", "message": "Action is not in a completed state that supports edits.",
    }, status=409)
    result = await h.edit_generated_action(
        ctx_connected, EditActionParams(action_id=42, instruction="make it brighter"))
    assert result.error is not None
    assert result.error_code == "action_not_editable"


@pytest.mark.asyncio
async def test_adversarial_list_results_empty_page_beyond_range(ctx_connected):
    """Requesting a page number past the end must return an empty, valid
    list -- not an error and not a crash on missing keys."""
    ctx_connected.http.mock_get("/results", {
        "items": [], "total": 3, "page": 99, "page_size": 20, "total_pages": 1,
    })
    result = await h.list_generation_results(ctx_connected, ListResultsParams(page=99))
    assert result.error is None
    assert result.data.items == []


@pytest.mark.asyncio
async def test_adversarial_upload_then_analyze_with_reused_upload_id_shape(ctx_connected):
    """upload_product_image returns an upload_id; ImageInput accepts either
    url/data/upload_id-shaped payloads -- exercise the base64 'data' path
    (not just 'url') through analyze_product to catch any field that only
    the url-path was ever tested against."""
    ctx_connected.http.mock_post("/analyze", {
        "category_id": "electronics", "product_name": "Wireless Mouse", "qualities": ["ergonomic"],
    })
    params = AnalyzeProductParams(image=ImageInput(media_type="image/png", data="aGVsbG8="))
    result = await h.analyze_product(ctx_connected, params)
    assert result.error is None
    assert result.data.product_name == "Wireless Mouse"
