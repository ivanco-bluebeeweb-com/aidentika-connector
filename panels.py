"""Panel UI: LEFT sidebar = connection status/form + (once connected) the
one "App settings" entry point + recent generation results. CENTER = either
one action's detail OR (when opened via "App settings") the settings
screen. There is no right-slot panel in this app -- confirmed from a user
screenshot that only left+center render on their surface, so everything
that needs to be reachable lives in the left sidebar instead.

Before connecting: the left sidebar shows ONLY the connect form (no point
rendering an empty results list yet). Once connected: the connect form is
gone for good (per the standing rule -- stop rendering what there's no
more need for) and the sidebar shows a compact "Connected" card + the
"App settings" button + the results list, all in one slot.

There is no local store cache here -- projects/cards/results all live on
Aidentika's own servers, so panels call aid_client directly (read-only GET
calls) instead of querying ctx.store.

Follows ~/UI_INTERFACE_STANDARD.md: exactly one secondary "App settings"
button in the sidebar, it renders the settings screen into the CENTER slot
(aid_settings_panel, not a modal), every setting there actually persists
via a write chat.function, each of those returns ActionResult.summary
(shown as the platform's green success/error notice) and refresh_panels
naming exactly the slots that need to change.
"""
from __future__ import annotations

from imperal_sdk import ui

import aid_client as aid
from app import ext
import handlers as h

_WEBHOOK_EVENT_OPTIONS = [
    {"value": "generation.completed", "label": "Generation completed"},
    {"value": "generation.failed", "label": "Generation failed"},
    {"value": "edit.completed", "label": "Edit completed"},
    {"value": "edit.failed", "label": "Edit failed"},
    {"value": "video.completed", "label": "Video completed"},
    {"value": "video.failed", "label": "Video failed"},
]


async def _connection_status(ctx) -> tuple[bool, str]:
    key = await h._get_api_key(ctx)
    return bool(key), ("Connected" if key else "Not connected")


def _settings_button() -> ui.UINode:
    """The one required secondary entry point into the settings screen."""
    return ui.Button(
        "App settings", variant="secondary", size="sm", full_width=True,
        icon="settings", on_click=ui.Call("__panel__aid_settings"),
    )


def _connect_form(submit_label: str, api_key_placeholder: str = "API key (ak_...)") -> ui.UINode:
    return ui.Stack(direction="v", gap=2, children=[
        ui.Text(
            "Get an API key at app.aidentika.com -> Profile -> API -> "
            "Create key (max 10 per account). Verified before saving.",
            variant="caption",
        ),
        ui.Link(label="Open app.aidentika.com", href="https://app.aidentika.com/"),
        ui.Form(
            action="connect_aidentika",
            submit_label=submit_label,
            children=[ui.Password(param_name="api_key", placeholder=api_key_placeholder)],
        ),
    ])


async def _balance_card(ctx) -> ui.UINode | None:
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


@ext.panel("aid_results", slot="left", title="Aidentika", icon="🪄")
async def aid_results_panel(ctx, **kwargs) -> object:
    connected, _ = await _connection_status(ctx)

    if not connected:
        # Nothing else to render until there's a key -- no empty results
        # list, no balance card, just the one thing the user can act on.
        return ui.Stack(direction="v", gap=3, children=[
            ui.Card(
                title="Connect Aidentika",
                subtitle="Bring your own Aidentika account",
                content=_connect_form("Verify and connect"),
            ),
            ui.Alert(
                title="Not connected yet",
                message="Connect your Aidentika account to generate product photos, cards, and videos.",
                type="info",
            ),
        ])

    # Connected: the connect form is retired for good -- replaced by a
    # compact status card, the App settings entry point, balance, and the
    # actual results list.
    children: list[ui.UINode] = [
        ui.Card(
            title="Aidentika",
            subtitle="Connected",
            content=ui.Stack(direction="v", gap=2, children=[
                ui.Text("Your API key is saved and verified.", variant="caption"),
                _settings_button(),
            ]),
        ),
    ]
    balance = await _balance_card(ctx)
    if balance is not None:
        children.append(balance)

    api_key = await h._get_api_key(ctx)
    try:
        data = await aid.list_results(ctx, api_key, {"page": 1, "page_size": 30})
    except aid.ProviderError as exc:
        children.append(ui.Alert(title="Could not load results", message=str(exc), type="error"))
        return ui.Stack(direction="v", gap=3, children=children)

    items = data.get("items", [])
    if not items:
        children.append(ui.Empty(message="No generations yet -- start one from chat.", icon="🖼️"))
    else:
        list_items = [
            ui.ListItem(
                id=str(item["action_id"]),
                title=f"#{item['action_id']} -- {item.get('type', '?')}",
                subtitle=f"{item.get('status', '?')}" + (f" -- {item['error_message']}" if item.get("error_message") else ""),
                on_click=ui.Call("__panel__aid_detail", action_id=item["action_id"]),
            )
            for item in items
        ]
        children.append(ui.Card(
            title=f"Recent results ({data.get('total', len(items))})",
            content=ui.List(items=list_items, searchable=True),
        ))

    return ui.Stack(direction="v", gap=3, children=children)


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
