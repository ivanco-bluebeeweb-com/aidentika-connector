"""Tests for handlers.py -- connection, generation, status, projects,
cards, webhooks, and AI helpers."""
from __future__ import annotations

import pytest

import handlers as h
from schemas import (
    NoParams, ConnectAidentikaParams, ImageInput,
    UploadProductImageParams, AnalyzeProductParams,
    GeneratePhotoParams, GenerateVideoParams, EditActionParams,
    GetActionStatusParams, CancelActionParams, DownloadResultParams,
    ListResultsParams, CreateAidentikaProjectParams,
    ListAidentikaProjectsParams, GetAidentikaProjectParams,
    UpdateAidentikaProjectParams, GetAidentikaCardParams,
    MoveAidentikaCardParams, CreateAidentikaWebhookParams,
    ListAidentikaWebhooksParams, DeleteAidentikaWebhookParams,
    SuggestWishesParams, SuggestVideoScenarioParams,
)


# ── connection ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_connect_rejects_empty_key(ctx):
    result = await h.connect_aidentika(ctx, ConnectAidentikaParams(api_key="  "))
    assert result.error is not None
    assert result.error_code == "AID_KEY_MISSING"


@pytest.mark.asyncio
async def test_connect_validates_before_saving(ctx):
    ctx.http.mock_get("/balance", {"error": "invalid_api_key", "message": "bad"}, status=401)
    result = await h.connect_aidentika(ctx, ConnectAidentikaParams(api_key="ak_bad"))
    assert result.error is not None
    key = await ctx.secrets.get("aidentika_api_key")
    assert key is None


@pytest.mark.asyncio
async def test_connect_saves_on_success(ctx):
    ctx.http.mock_get("/balance", {"balance": 100, "available": 96, "holds": 4})
    result = await h.connect_aidentika(ctx, ConnectAidentikaParams(api_key="ak_good"))
    assert result.error is None
    key = await ctx.secrets.get("aidentika_api_key")
    assert key == "ak_good"


@pytest.mark.asyncio
async def test_disconnect_clears_key(ctx_connected):
    result = await h.disconnect_aidentika(ctx_connected, NoParams())
    assert result.error is None
    key = await ctx_connected.secrets.get("aidentika_api_key")
    assert key is None


@pytest.mark.asyncio
async def test_functions_require_connection(ctx):
    result = await h.get_aidentika_balance(ctx, NoParams())
    assert result.error is not None
    assert result.error_code == "AID_NOT_CONNECTED"


# ── info ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_balance(ctx_connected):
    ctx_connected.http.mock_get("/balance", {"balance": 50, "available": 40, "holds": 10})
    result = await h.get_aidentika_balance(ctx_connected, NoParams())
    assert result.error is None
    assert result.data.balance == 50


@pytest.mark.asyncio
async def test_get_pricing(ctx_connected):
    ctx_connected.http.mock_get("/pricing", {
        "generation": 4, "improvement": 2, "video_5sec": 10, "video_10sec": 18,
    })
    result = await h.get_aidentika_pricing(ctx_connected, NoParams())
    assert result.error is None
    assert result.data.video_5sec == 10


@pytest.mark.asyncio
async def test_list_categories(ctx_connected):
    ctx_connected.http.mock_get("/categories", {
        "categories": [{"id": "apparel", "name": "Apparel", "concepts": [{"id": "studio", "name": "Studio"}]}],
    })
    result = await h.list_aidentika_categories(ctx_connected, NoParams())
    assert result.error is None
    assert len(result.data.categories) == 1


# ── upload + analyze ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_upload_product_image(ctx_connected):
    ctx_connected.http.mock_post("/upload", {"upload_id": "upl_abc", "expires_in": 3600})
    params = UploadProductImageParams(image=ImageInput(url="https://example.com/p.jpg"))
    result = await h.upload_product_image(ctx_connected, params)
    assert result.error is None
    assert result.data.upload_id == "upl_abc"


@pytest.mark.asyncio
async def test_analyze_product(ctx_connected):
    ctx_connected.http.mock_post("/analyze", {
        "category_id": "cosmetics", "product_name": "Face Cream", "qualities": ["hydrating"],
    })
    params = AnalyzeProductParams(image=ImageInput(url="https://example.com/p.jpg"))
    result = await h.analyze_product(ctx_connected, params)
    assert result.error is None
    assert result.data.product_name == "Face Cream"


# ── generation ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_generate_product_photo(ctx_connected):
    ctx_connected.http.mock_post("/generate/photo", {
        "action_id": 123, "status": "pending", "poll_url": "/status/123",
    })
    params = GeneratePhotoParams(images=[ImageInput(url="https://example.com/p.jpg")])
    result = await h.generate_product_photo(ctx_connected, params)
    assert result.error is None
    assert result.data.action_id == 123


@pytest.mark.asyncio
async def test_generate_product_video(ctx_connected):
    ctx_connected.http.mock_post("/generate/video", {
        "action_id": 456, "status": "pending", "poll_url": "/status/456",
    })
    params = GenerateVideoParams(image=ImageInput(url="https://example.com/p.jpg"))
    result = await h.generate_product_video(ctx_connected, params)
    assert result.error is None
    assert result.data.action_id == 456


@pytest.mark.asyncio
async def test_edit_generated_action(ctx_connected):
    ctx_connected.http.mock_post("/edit/123", {
        "action_id": 789, "status": "pending", "poll_url": "/status/789",
    })
    params = EditActionParams(action_id=123, instruction="make background white")
    result = await h.edit_generated_action(ctx_connected, params)
    assert result.error is None
    assert result.data.action_id == 789


# ── status / cancel / download / results ──────────────────────────────────

@pytest.mark.asyncio
async def test_get_action_status(ctx_connected):
    ctx_connected.http.mock_get("/status/123", {
        "action_id": 123, "status": "completed", "type": "generate",
        "result_url": "https://cdn.aidentika.com/x.jpg",
    })
    result = await h.get_action_status(ctx_connected, GetActionStatusParams(action_id=123))
    assert result.error is None
    assert result.data.status == "completed"


@pytest.mark.asyncio
async def test_cancel_action(ctx_connected):
    ctx_connected.http.mock_post("/cancel/123", {
        "action_id": 123, "cancelled": True, "message": "Cancelled.",
    })
    result = await h.cancel_action(ctx_connected, CancelActionParams(action_id=123))
    assert result.error is None
    assert result.data.cancelled is True


@pytest.mark.asyncio
async def test_download_result_not_ready(ctx_connected):
    ctx_connected.http.mock_get("/status/123", {
        "action_id": 123, "status": "processing", "type": "generate", "result_url": None,
    })
    result = await h.download_result(ctx_connected, DownloadResultParams(action_id=123))
    assert result.error is None
    assert result.data.result_url is None


@pytest.mark.asyncio
async def test_download_result_ready(ctx_connected):
    ctx_connected.http.mock_get("/status/123", {
        "action_id": 123, "status": "completed", "type": "generate",
        "result_url": "https://cdn.aidentika.com/x.jpg",
    })
    result = await h.download_result(ctx_connected, DownloadResultParams(action_id=123))
    assert result.error is None
    assert result.data.result_url == "https://cdn.aidentika.com/x.jpg"


@pytest.mark.asyncio
async def test_list_generation_results(ctx_connected):
    ctx_connected.http.mock_get("/results", {
        "items": [], "total": 0, "page": 1, "page_size": 20, "total_pages": 0,
    })
    result = await h.list_generation_results(ctx_connected, ListResultsParams())
    assert result.error is None
    assert result.data.total == 0


# ── projects / cards ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_aidentika_project(ctx_connected):
    ctx_connected.http.mock_post("/projects", {"id": 1, "name": "My Project"})
    result = await h.create_aidentika_project(ctx_connected, CreateAidentikaProjectParams(name="My Project"))
    assert result.error is None
    assert result.data.id == 1


@pytest.mark.asyncio
async def test_list_aidentika_projects(ctx_connected):
    ctx_connected.http.mock_get("/projects", {
        "items": [{"id": 1, "name": "P1"}], "total": 1, "limit": 20, "offset": 0,
    })
    result = await h.list_aidentika_projects(ctx_connected, ListAidentikaProjectsParams())
    assert result.error is None
    assert result.data.total == 1


@pytest.mark.asyncio
async def test_get_aidentika_project(ctx_connected):
    ctx_connected.http.mock_get("/projects/1", {
        "id": 1, "name": "P1", "cards": [], "actions": [],
    })
    result = await h.get_aidentika_project(ctx_connected, GetAidentikaProjectParams(project_id=1))
    assert result.error is None
    assert result.data.id == 1


@pytest.mark.asyncio
async def test_update_aidentika_project(ctx_connected):
    ctx_connected.http.mock_post("/projects/1", {"id": 1, "name": "New"})
    ctx_connected.http._mocks.append(("PATCH", "/projects/1", {"id": 1, "name": "New"}, 200, {}))
    result = await h.update_aidentika_project(ctx_connected, UpdateAidentikaProjectParams(project_id=1, name="New"))
    assert result.error is None
    assert result.data.name == "New"


@pytest.mark.asyncio
async def test_get_aidentika_card(ctx_connected):
    ctx_connected.http.mock_get("/cards/1", {
        "id": 1, "project_id": 1, "status": "completed", "content_type": "photo", "actions": [],
    })
    result = await h.get_aidentika_card(ctx_connected, GetAidentikaCardParams(card_id=1))
    assert result.error is None
    assert result.data.id == 1


@pytest.mark.asyncio
async def test_move_aidentika_card(ctx_connected):
    ctx_connected.http._mocks.append(("PATCH", "/cards/1", {
        "id": 1, "project_id": 2, "status": "completed", "content_type": "photo", "actions": [],
    }, 200, {}))
    result = await h.move_aidentika_card(ctx_connected, MoveAidentikaCardParams(card_id=1, project_id=2))
    assert result.error is None
    assert result.data.project_id == 2


# ── webhooks ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_aidentika_webhook(ctx_connected):
    ctx_connected.http.mock_post("/webhooks", {
        "id": 1, "url": "https://example.com/hook", "secret": "whsec_abc",
        "events": ["generation.completed"], "is_active": True, "created_at": None,
    })
    result = await h.create_aidentika_webhook(ctx_connected, CreateAidentikaWebhookParams(url="https://example.com/hook"))
    assert result.error is None
    assert result.data.secret == "whsec_abc"


@pytest.mark.asyncio
async def test_list_aidentika_webhooks(ctx_connected):
    ctx_connected.http.mock_get("/webhooks", {"webhooks": []})
    result = await h.list_aidentika_webhooks(ctx_connected, ListAidentikaWebhooksParams())
    assert result.error is None
    assert result.data.webhooks == []


@pytest.mark.asyncio
async def test_delete_aidentika_webhook(ctx_connected):
    ctx_connected.http._mocks.append(("DELETE", "/webhooks/1", {"deleted": True}, 200, {}))
    result = await h.delete_aidentika_webhook(ctx_connected, DeleteAidentikaWebhookParams(webhook_id=1))
    assert result.error is None
    assert result.data.deleted is True


# ── AI helpers ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_suggest_product_wishes(ctx_connected):
    ctx_connected.http.mock_post("/wishes/suggest", {"text": "Great cream for hydration."})
    params = SuggestWishesParams(
        images=[ImageInput(url="https://example.com/p.jpg")],
        category_id="cosmetics", concept_id="studio",
    )
    result = await h.suggest_product_wishes(ctx_connected, params)
    assert result.error is None
    assert "cream" in result.data.text.lower()


@pytest.mark.asyncio
async def test_suggest_video_scenario(ctx_connected):
    ctx_connected.http.mock_post("/video/suggest-scenario", {"scenario": "Slow rotate on white background."})
    params = SuggestVideoScenarioParams(image=ImageInput(url="https://example.com/p.jpg"))
    result = await h.suggest_video_scenario(ctx_connected, params)
    assert result.error is None
    assert "rotate" in result.data.scenario.lower()


@pytest.mark.asyncio
async def test_get_helpers_usage(ctx_connected):
    ctx_connected.http.mock_get("/helpers/usage", {
        "used_today": 3, "free_limit": 100, "free_remaining": 97, "paid_rate": "1 spark per 20 calls",
    })
    result = await h.get_helpers_usage(ctx_connected, NoParams())
    assert result.error is None
    assert result.data.used_today == 3
