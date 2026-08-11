"""Panel UI: right = connect + balance/pricing, left = recent generation
results, center = one action's detail. Same three-slot shape as DataForSEO
Connector, adapted for Aidentika: there is no local store cache here --
projects/cards/results all live on Aidentika's own servers, so panels call
aid_client directly (read-only GET calls) instead of querying ctx.store.
"""
from __future__ import annotations

from imperal_sdk import ui

import aid_client as aid
from app import ext
import handlers as h


async def _connection_status(ctx) -> tuple[bool, str]:
    key = await h._get_api_key(ctx)
    return bool(key), ("Connected" if key else "Not connected")


def _connect_card(connected: bool) -> ui.UINode:
    if connected:
        return ui.Card(
            title="Aidentika",
            subtitle="Connected",
            content=ui.Stack(direction="v", gap=2, children=[
                ui.Text("Your API key is saved and verified.", variant="caption"),
                ui.Button("Disconnect", variant="danger", size="sm",
                          on_click=ui.Call("disconnect_aidentika")),
            ]),
        )
    return ui.Card(
        title="Connect Aidentika",
        subtitle="Bring your own Aidentika account",
        content=ui.Stack(direction="v", gap=2, children=[
            ui.Text(
                "Get an API key at app.aidentika.com -> Profile -> API -> "
                "Create key (max 10 per account). Verified before saving.",
                variant="caption",
            ),
            ui.Link(label="Open app.aidentika.com", href="https://app.aidentika.com/"),
            ui.Form(
                action="connect_aidentika",
                submit_label="Verify and connect",
                children=[ui.Password(param_name="api_key", placeholder="API key (ak_...)")],
            ),
        ]),
    )


async def _balance_card(ctx, connected: bool) -> ui.UINode | None:
    if not connected:
        return None
    api_key = await h._get_api_key(ctx)
    try:
        data = await aid.get_balance(ctx, api_key)
    except aid.ProviderError:
        return None
    return ui.Card(
        title="Sparks balance",
        content=ui.Stack(direction="v", gap=1, children=[
            ui.Text(f"Available: {data.get('available', '?')}", variant="body"),
            ui.Text(f"Total: {data.get('balance', '?')} -- Holds: {data.get('holds', '?')}", variant="caption"),
        ]),
    )


@ext.panel("aid_connect", slot="right", title="Aidentika", icon="🪄",
           default_width=300, min_width=240, max_width=420)
async def aid_connect_panel(ctx, **kwargs) -> object:
    connected, _ = await _connection_status(ctx)
    children: list[ui.UINode] = [_connect_card(connected)]
    balance = await _balance_card(ctx, connected)
    if balance is not None:
        children.append(balance)
    if not connected:
        children.append(ui.Alert(
            title="Not connected yet",
            message="Connect your Aidentika account to generate product photos, cards, and videos.",
            type="info",
        ))
    return ui.Stack(direction="v", gap=3, children=children)


@ext.panel("aid_results", slot="left", title="Results", icon="🖼️")
async def aid_results_panel(ctx, **kwargs) -> object:
    connected, _ = await _connection_status(ctx)
    if not connected:
        return ui.Empty(message="Connect Aidentika on the right to see your generations.", icon="🖼️")

    api_key = await h._get_api_key(ctx)
    try:
        data = await aid.list_results(ctx, api_key, {"page": 1, "page_size": 30})
    except aid.ProviderError as exc:
        return ui.Alert(title="Could not load results", message=str(exc), type="error")

    items = data.get("items", [])
    if not items:
        return ui.Empty(message="No generations yet -- start one from chat.", icon="🖼️")

    list_items = [
        ui.ListItem(
            id=str(item["action_id"]),
            title=f"#{item['action_id']} -- {item.get('type', '?')}",
            subtitle=f"{item.get('status', '?')}" + (f" -- {item['error_message']}" if item.get("error_message") else ""),
            on_click=ui.Call("__panel__aid_detail", action_id=item["action_id"]),
        )
        for item in items
    ]
    return ui.Stack(direction="v", gap=2, children=[
        ui.Card(title=f"Recent results ({data.get('total', len(items))})",
                content=ui.List(items=list_items, searchable=True)),
    ])


@ext.panel("aid_detail", slot="center", title="Result detail", icon="🔎", center_overlay=True)
async def aid_detail_panel(ctx, action_id: int | str = "", **kwargs) -> object:
    if not action_id:
        return ui.Empty(message="Select a result on the left to see its detail.", icon="🔎")

    connected, _ = await _connection_status(ctx)
    if not connected:
        return ui.Empty(message="Connect Aidentika first.", icon="🔎")

    api_key = await h._get_api_key(ctx)
    try:
        data = await aid.get_status(ctx, api_key, int(action_id))
    except aid.ProviderError as exc:
        return ui.Alert(title="Could not load detail", message=str(exc), type="error")

    rows: list[ui.UINode] = [
        ui.Text(f"Action #{data.get('action_id')} -- {data.get('type', '?')}", variant="title"),
        ui.Badge(label=data.get("status", "?"), color=(
            "success" if data.get("status") == "completed"
            else "danger" if data.get("status") == "failed"
            else "warning"
        )),
    ]
    if data.get("result_url"):
        rows.append(ui.Link(label="Open result", href=data["result_url"]))
    if data.get("error_message"):
        rows.append(ui.Text(data["error_message"], variant="caption"))
    rows.append(ui.Text(f"Created: {data.get('created_at', '?')}", variant="caption"))
    if data.get("completed_at"):
        rows.append(ui.Text(f"Completed: {data['completed_at']}", variant="caption"))

    return ui.Stack(direction="v", gap=2, children=rows)
