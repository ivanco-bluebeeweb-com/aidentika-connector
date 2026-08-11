"""Aidentika Public API client -- auth, error mapping, thin endpoint wrappers.

WHY BYOK (bring-your-own-key), same reasoning as DataForSEO Connector and
Media Studio's Magnific integration. Aidentika is a paid third-party AI
product-photo/video generation service -- the user has their own
app.aidentika.com account and their own sparks balance/billing, not
something Imperal can broker centrally. The user pastes their own API key
once, Vault-encrypted via `ctx.secrets`, and every call runs against their
own quota.

WHY BEARER TOKEN, NOT BASIC AUTH (unlike DataForSEO).
Aidentika issues a single opaque key `ak_...` (created in
app.aidentika.com -> Profile -> API, max 10 keys/account) sent as
`Authorization: Bearer ak_...` -- one secret, not a login+password pair.

BASE URL is fixed (`https://api.aidentika.com/api/v1/public`) -- Aidentika
has no sandbox/live split the way DataForSEO does, so there is no mode
toggle here.

ASYNC GENERATION MODEL. `/generate/photo`, `/generate/card`, `/generate/video`
and `/edit/{action_id}` all return `{action_id, status: "pending", poll_url}`
immediately (per docs.aidentika.com/api/generation and /api/status) -- the
actual image/video work happens server-side over 20s-5min. This client does
NOT poll internally; handlers.py exposes `get_action_status` as its own
chat function so the user (or an automation) decides when to check, exactly
like Media Studio's status/poll split for Magnific/Mystic jobs.

ERROR TAXONOMY. Every Aidentika error is `{"error": code, "message": ..,
"details": {...}}` (docs.aidentika.com/api/errors) -- `ProviderError` below
carries that `code` through unchanged so handlers can return the SAME
machine-readable code the API gave us, not a re-invented one.
"""
from __future__ import annotations

from typing import Any

BASE_URL = "https://api.aidentika.com/api/v1/public"


class ProviderError(Exception):
    """Raised for any non-2xx response from the Aidentika API.

    `code` is Aidentika's own machine error code (e.g. `invalid_api_key`,
    `insufficient_tokens`, `rate_limit_exceeded`) when the API returned one,
    else a client-side fallback code (`AID_HTTP_ERROR`).
    """

    def __init__(self, message: str, code: str = "AID_HTTP_ERROR", details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.details = details or {}


def _headers(api_key: str) -> dict:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def _raise_for_body(status_code: int, body: Any) -> None:
    if status_code < 400:
        return
    if isinstance(body, dict):
        code = body.get("error") or f"AID_HTTP_{status_code}"
        message = body.get("message") or f"Aidentika API returned HTTP {status_code}"
        details = body.get("details") or {}
    else:
        code = f"AID_HTTP_{status_code}"
        message = f"Aidentika API returned HTTP {status_code}"
        details = {}
    raise ProviderError(message, code=code, details=details)


async def _get(ctx, api_key: str, path: str, params: dict | None = None) -> dict:
    resp = await ctx.http.get(f"{BASE_URL}{path}", headers=_headers(api_key), params=params or {})
    _raise_for_body(resp.status_code, resp.body)
    return resp.body


async def _post(ctx, api_key: str, path: str, json: dict | None = None) -> dict:
    resp = await ctx.http.post(f"{BASE_URL}{path}", headers=_headers(api_key), json=json or {})
    _raise_for_body(resp.status_code, resp.body)
    return resp.body


async def _patch(ctx, api_key: str, path: str, json: dict | None = None) -> dict:
    resp = await ctx.http.patch(f"{BASE_URL}{path}", headers=_headers(api_key), json=json or {})
    _raise_for_body(resp.status_code, resp.body)
    return resp.body


async def _delete(ctx, api_key: str, path: str) -> dict:
    resp = await ctx.http.delete(f"{BASE_URL}{path}", headers=_headers(api_key))
    _raise_for_body(resp.status_code, resp.body)
    return resp.body if isinstance(resp.body, dict) else {}


async def validate_key(ctx, api_key: str) -> dict:
    """Cheapest real call to confirm a key works: GET /balance costs no
    sparks and every account has one -- same "validate before saving"
    pattern as DataForSEO's validate_credentials."""
    return await _get(ctx, api_key, "/balance")


# ---------------------------------------------------------------------------
# Info
# ---------------------------------------------------------------------------

async def get_balance(ctx, api_key: str) -> dict:
    return await _get(ctx, api_key, "/balance")


async def get_pricing(ctx, api_key: str) -> dict:
    return await _get(ctx, api_key, "/pricing")


async def get_categories(ctx, api_key: str) -> dict:
    return await _get(ctx, api_key, "/categories")


# ---------------------------------------------------------------------------
# Images
# ---------------------------------------------------------------------------

async def upload_image(ctx, api_key: str, image: dict) -> dict:
    return await _post(ctx, api_key, "/upload", {"image": image})


async def analyze(ctx, api_key: str, payload: dict) -> dict:
    return await _post(ctx, api_key, "/analyze", payload)


# ---------------------------------------------------------------------------
# Generation (async: returns action_id/status/poll_url)
# ---------------------------------------------------------------------------

async def generate_photo(ctx, api_key: str, payload: dict) -> dict:
    return await _post(ctx, api_key, "/generate/photo", payload)


async def generate_card(ctx, api_key: str, payload: dict) -> dict:
    return await _post(ctx, api_key, "/generate/card", payload)


async def generate_video(ctx, api_key: str, payload: dict) -> dict:
    return await _post(ctx, api_key, "/generate/video", payload)


async def edit_action(ctx, api_key: str, action_id: int, payload: dict) -> dict:
    return await _post(ctx, api_key, f"/edit/{action_id}", payload)


# ---------------------------------------------------------------------------
# Status / results
# ---------------------------------------------------------------------------

async def get_status(ctx, api_key: str, action_id: int) -> dict:
    return await _get(ctx, api_key, f"/status/{action_id}")


async def cancel_action(ctx, api_key: str, action_id: int) -> dict:
    return await _post(ctx, api_key, f"/cancel/{action_id}", {})


async def download_result(ctx, api_key: str, action_id: int) -> dict:
    """Return the completed action's signed result URL.

    Deliberately calls GET /status, NOT GET /results/{id}/download.
    Per docs.aidentika.com/api/status, /download issues a 302 redirect
    straight to the binary asset when the action is completed -- and
    Imperal's ctx.http follows redirects automatically, which would pull
    raw image/video bytes into this JSON-shaped client instead of a URL.
    /status returns the exact same result_url as a small JSON object with
    no redirect, which is what every caller here actually wants.
    """
    return await _get(ctx, api_key, f"/status/{action_id}")


async def list_results(ctx, api_key: str, params: dict) -> dict:
    return await _get(ctx, api_key, "/results", params=params)


# ---------------------------------------------------------------------------
# Projects / cards
# ---------------------------------------------------------------------------

async def create_project(ctx, api_key: str, payload: dict) -> dict:
    return await _post(ctx, api_key, "/projects", payload)


async def list_projects(ctx, api_key: str, params: dict) -> dict:
    return await _get(ctx, api_key, "/projects", params=params)


async def get_project(ctx, api_key: str, project_id: int) -> dict:
    return await _get(ctx, api_key, f"/projects/{project_id}")


async def update_project(ctx, api_key: str, project_id: int, payload: dict) -> dict:
    return await _patch(ctx, api_key, f"/projects/{project_id}", payload)


async def get_card(ctx, api_key: str, card_id: int) -> dict:
    return await _get(ctx, api_key, f"/cards/{card_id}")


async def move_card(ctx, api_key: str, card_id: int, payload: dict) -> dict:
    return await _patch(ctx, api_key, f"/cards/{card_id}", payload)


# ---------------------------------------------------------------------------
# Webhooks
# ---------------------------------------------------------------------------

async def create_webhook(ctx, api_key: str, payload: dict) -> dict:
    return await _post(ctx, api_key, "/webhooks", payload)


async def list_webhooks(ctx, api_key: str) -> dict:
    return await _get(ctx, api_key, "/webhooks")


async def delete_webhook(ctx, api_key: str, webhook_id: int) -> dict:
    return await _delete(ctx, api_key, f"/webhooks/{webhook_id}")


# ---------------------------------------------------------------------------
# AI helpers (synchronous)
# ---------------------------------------------------------------------------

async def suggest_wishes(ctx, api_key: str, payload: dict) -> dict:
    return await _post(ctx, api_key, "/wishes/suggest", payload)


async def suggest_video_scenario(ctx, api_key: str, payload: dict) -> dict:
    return await _post(ctx, api_key, "/video/suggest-scenario", payload)


async def get_helpers_usage(ctx, api_key: str) -> dict:
    return await _get(ctx, api_key, "/helpers/usage")
