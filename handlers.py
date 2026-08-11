"""Chat functions for Aidentika Connector -- combined public surface.

The actual @chat.function definitions live in focused modules (each kept
under ~300 lines): handlers_core (connect/disconnect, info, upload,
analyze), handlers_generate (photo/card/video/edit generation,
status/cancel/download, results listing), handlers_projects (projects +
cards), handlers_webhooks (webhooks + free AI helpers). This module just
imports all of them so a single `import handlers` (main.py, tests, panels)
registers every @chat.function on the same Extension, and re-exports the
private helpers other modules import by name.
"""
from __future__ import annotations

# Import order matters: handlers_core defines the shared helpers the other
# modules import from it, so it must load first.
from handlers_core import (  # noqa: F401
    _get_api_key, _image_dict, _require_key,
    connect_aidentika, disconnect_aidentika,
    get_aidentika_balance, get_aidentika_pricing, list_aidentika_categories,
    upload_product_image, analyze_product,
)
from handlers_generate import (  # noqa: F401
    _generate_result,
    generate_product_photo, generate_product_card, generate_product_video,
    edit_generated_action,
    get_action_status, cancel_action, download_result,
    list_generation_results,
)
from handlers_projects import (  # noqa: F401
    create_aidentika_project, list_aidentika_projects,
    get_aidentika_project, update_aidentika_project,
    get_aidentika_card, move_aidentika_card,
)
from handlers_webhooks import (  # noqa: F401
    create_aidentika_webhook, list_aidentika_webhooks,
    delete_aidentika_webhook,
    suggest_product_wishes, suggest_video_scenario, get_helpers_usage,
)
