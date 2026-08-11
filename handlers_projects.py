"""Chat functions: Aidentika projects and cards (create/list/get/update
projects; get/move cards).

Split out of handlers.py to keep files under the 300-line convention.
"""
from __future__ import annotations

from imperal_sdk import ActionResult

import aid_client as aid
from app import ext, chat
from schemas import (
    CreateAidentikaProjectParams, ListAidentikaProjectsParams,
    GetAidentikaProjectParams, UpdateAidentikaProjectParams,
    AidentikaProject, AidentikaProjectList,
    GetAidentikaCardParams, MoveAidentikaCardParams, AidentikaCard,
)
from handlers_core import _require_key

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


