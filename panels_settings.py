"""The single 'App settings' screen (center slot) -- every configurable
thing this app has: connection (connect/rotate/disconnect) and webhooks
(add/delete). Split out of panels.py to keep files under the 300-line
convention; shared helpers (_connection_status, _connect_form) live there.

Per ~/UI_INTERFACE_STANDARD.md: rendered into the CENTER slot only via the
sidebar's "App settings" button, every setting here really persists
(chat.function write calls in handlers_core.py / handlers_webhooks.py),
each returns ActionResult.summary as the platform's green success/error
notice, and refresh_panels names exactly what needs to update
(aid_results for the sidebar status/badge/balance/results list,
aid_settings for this screen itself).
"""
from __future__ import annotations

from imperal_sdk import ui

import aid_client as aid
from app import ext
import handlers as h
from panels import _connection_status, _connect_form

_WEBHOOK_EVENT_OPTIONS = [
    {"value": "generation.completed", "label": "Generation completed"},
    {"value": "generation.failed", "label": "Generation failed"},
    {"value": "edit.completed", "label": "Edit completed"},
    {"value": "edit.failed", "label": "Edit failed"},
    {"value": "video.completed", "label": "Video completed"},
    {"value": "video.failed", "label": "Video failed"},
]


def _connection_section(connected: bool, confirm_disconnect: bool = False) -> ui.UINode:
    if not connected:
        return ui.Card(
            title="Connection",
            subtitle="Not connected",
            content=_connect_form("Verify and connect"),
        )
    if confirm_disconnect:
        # Real 2-step confirm, done by re-rendering this same center panel
        # with a flag -- ui.Call has no generic "confirm" prop (verified:
        # Button/Call signatures carry no such field); the only verified
        # confirm affordance in this SDK is ListItem.actions[].confirm,
        # which doesn't fit a standalone button, so the panel does its own
        # step instead of guessing at an unverified kwarg.
        return ui.Card(
            title="Connection",
            subtitle="Confirm disconnect",
            content=ui.Stack(direction="v", gap=2, children=[
                ui.Alert(
                    title="Disconnect Aidentika?",
                    message=(
                        "Your projects, cards and results stay on Aidentika "
                        "-- nothing is deleted there. You'll need to "
                        "reconnect to generate again."
                    ),
                    type="warning",
                ),
                ui.Stack(direction="h", gap=2, children=[
                    ui.Button("Yes, disconnect", variant="danger", size="sm",
                              on_click=ui.Call("disconnect_aidentika")),
                    ui.Button("Cancel", variant="secondary", size="sm",
                              on_click=ui.Call("__panel__aid_settings")),
                ]),
            ]),
        )
    return ui.Card(
        title="Connection",
        subtitle="Connected",
        content=ui.Stack(direction="v", gap=3, children=[
            ui.Text("Your API key is saved and verified.", variant="caption"),
            ui.Accordion(sections=[{
                "id": "rotate",
                "title": "Rotate key",
                "children": [
                    ui.Text(
                        "Replacing your saved key -- the old one keeps "
                        "working at Aidentika until you revoke it there "
                        "yourself.",
                        variant="caption",
                    ),
                    _connect_form("Save new key", api_key_placeholder="New API key (ak_...)"),
                ],
            }]),
            ui.Divider(),
            ui.Button(
                "Disconnect", variant="danger", size="sm",
                on_click=ui.Call("__panel__aid_settings", confirm_disconnect=True),
            ),
        ]),
    )


def _webhook_row(item: dict) -> ui.UINode:
    events = ", ".join(item.get("events", [])) or "all events"
    return ui.ListItem(
        id=str(item.get("id")),
        title=item.get("url", "?"),
        subtitle=events,
        meta="active" if item.get("is_active", True) else "inactive",
        actions=[{
            "icon": "Trash2",
            "on_click": ui.Call("delete_aidentika_webhook", webhook_id=item.get("id")),
            "confirm": "Delete this webhook? Notifications to this URL will stop immediately.",
        }],
    )


async def _webhooks_section(ctx, connected: bool) -> ui.UINode:
    if not connected:
        return ui.Card(
            title="Notifications (webhooks)",
            content=ui.Text("Connect Aidentika above to manage webhooks.", variant="caption"),
        )
    api_key = await h._get_api_key(ctx)
    try:
        data = await aid.list_webhooks(ctx, api_key)
    except aid.ProviderError as exc:
        return ui.Card(
            title="Notifications (webhooks)",
            content=ui.Alert(title="Could not load webhooks", message=str(exc), type="error"),
        )
    webhooks = data.get("webhooks", [])
    rows: list[ui.UINode] = []
    if webhooks:
        rows.append(ui.List(items=[_webhook_row(w) for w in webhooks]))
    else:
        rows.append(ui.Text("No webhooks registered yet.", variant="caption"))
    rows.append(ui.Divider())
    rows.append(ui.Text(
        "Add a webhook to get notified when a generation completes or "
        "fails, instead of polling. Max 5 per account. The signing secret "
        "is shown once, right after creation -- copy it immediately.",
        variant="caption",
    ))
    rows.append(ui.Form(
        action="create_aidentika_webhook",
        submit_label="Add webhook",
        children=[
            ui.Input(param_name="url", placeholder="https://your-endpoint.example.com/hook"),
            ui.MultiSelect(
                options=_WEBHOOK_EVENT_OPTIONS,
                param_name="events",
                placeholder="All events (leave empty) or pick specific ones",
            ),
        ],
    ))
    return ui.Card(title=f"Notifications (webhooks) -- {len(webhooks)}/5", content=ui.Stack(direction="v", gap=2, children=rows))


@ext.panel("aid_settings", slot="center", title="App settings", icon="⚙️", center_overlay=True)
async def aid_settings_panel(ctx, confirm_disconnect: bool = False, **kwargs) -> object:
    connected, _ = await _connection_status(ctx)
    sections: list[ui.UINode] = [
        ui.Text("Aidentika -- App settings", variant="title"),
        _connection_section(connected, confirm_disconnect=confirm_disconnect and connected),
        await _webhooks_section(ctx, connected),
    ]
    return ui.Stack(direction="v", gap=3, children=sections)
