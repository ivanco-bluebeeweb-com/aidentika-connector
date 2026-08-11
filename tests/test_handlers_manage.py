"""Tests for handlers -- Aidentika projects, cards, webhooks, and free AI
helpers.

Split out of test_handlers.py to keep files under the 300-line convention.
"""
from __future__ import annotations

import pytest

import handlers as h
from schemas import (
    NoParams, ImageInput,
    CreateAidentikaProjectParams, ListAidentikaProjectsParams,
    GetAidentikaProjectParams, UpdateAidentikaProjectParams,
    GetAidentikaCardParams, MoveAidentikaCardParams,
    CreateAidentikaWebhookParams, ListAidentikaWebhooksParams,
    DeleteAidentikaWebhookParams,
    SuggestWishesParams, SuggestVideoScenarioParams,
)


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
