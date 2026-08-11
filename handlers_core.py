"""Chat functions: connect/disconnect, info (balance/pricing/categories),
image upload, and free product analysis.

Split out of handlers.py to keep files under the 300-line convention --
see handlers.py for the combined public surface (it re-exports everything
from this module plus handlers_generate/handlers_manage).
"""
from __future__ import annotations

from imperal_sdk import ActionResult

import aid_client as aid
from app import ext, chat
from schemas import (
    NoParams,
    ConnectAidentikaParams, ProviderConnection, DisconnectResult,
    BalanceInfo, PricingInfo, CategoriesList,
    UploadProductImageParams, UploadResult,
    AnalyzeProductParams, AnalyzeResult,
)

async def _get_api_key(ctx) -> str | None:
    return await ctx.secrets.get("aidentika_api_key")


def _image_dict(img) -> dict:
    """ImageInput pydantic model -> API dict, dropping unset fields."""
    d = {"media_type": img.media_type}
    if img.url:
        d["url"] = img.url
    if img.data:
        d["data"] = img.data
    return d


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------

@chat.function(
    "connect_aidentika",
    "Connect Aidentika by saving your API key, after checking it actually "
    "works. Get an API key at app.aidentika.com -> Profile -> API -> "
    "Create key (max 10 keys per account).",
    action_type="write",
    chain_callable=True,
    data_model=ProviderConnection,
    event="aidentika-connector.connect_aidentika",
    effects=["aidentika.provider.connected"],
)
async def connect_aidentika(ctx, params: ConnectAidentikaParams) -> ActionResult:
    """Validate-then-store: a key Aidentika rejects is never written."""
    api_key = params.api_key.strip()
    if not api_key:
        return ActionResult.error(
            "API key is required. Find it at app.aidentika.com -> Profile -> API.",
            code="AID_KEY_MISSING",
        )
    try:
        await aid.get_balance(ctx, api_key)
    except aid.ProviderError as exc:
        return ActionResult.error(str(exc), code=exc.code)

    await ctx.secrets.set("aidentika_api_key", api_key)
    return ActionResult.success(
        data=ProviderConnection(connected=True, message="Aidentika connected and verified."),
        summary="Connected to Aidentika.",
    )


@chat.function(
    "disconnect_aidentika",
    "Disconnect Aidentika: deletes the saved API key. Existing projects, "
    "cards and results in your Aidentika account are not affected.",
    action_type="write",
    chain_callable=True,
    data_model=DisconnectResult,
    event="aidentika-connector.disconnect_aidentika",
    effects=["aidentika.provider.disconnected"],
)
async def disconnect_aidentika(ctx, params: NoParams) -> ActionResult:
    """Remove the saved Aidentika API key. Existing generations/projects on Aidentika are untouched."""
    await ctx.secrets.delete("aidentika_api_key")
    return ActionResult.success(
        data=DisconnectResult(disconnected=True, message="Aidentika API key removed."),
        summary="Disconnected from Aidentika.",
    )


async def _require_key(ctx) -> tuple[str | None, ActionResult | None]:
    api_key = await _get_api_key(ctx)
    if not api_key:
        return None, ActionResult.error(
            "Aidentika is not connected. Connect it first with your API key "
            "from app.aidentika.com -> Profile -> API.",
            code="AID_NOT_CONNECTED",
        )
    return api_key, None


# ---------------------------------------------------------------------------
# Info: balance / pricing / categories
# ---------------------------------------------------------------------------

@chat.function(
    "get_aidentika_balance",
    "Check your current Aidentika sparks balance -- total, available, and "
    "held for in-flight generations.",
    action_type="read",
    chain_callable=True,
    data_model=BalanceInfo,
)
async def get_aidentika_balance(ctx, params: NoParams) -> ActionResult:
    """Fetch current sparks balance from Aidentika."""
    api_key, err = await _require_key(ctx)
    if err:
        return err
    try:
        data = await aid.get_balance(ctx, api_key)
    except aid.ProviderError as exc:
        return ActionResult.error(str(exc), code=exc.code)
    info = BalanceInfo(**data)
    return ActionResult.success(
        data=info,
        summary=f"Balance: {info.balance} sparks ({info.available} available, {info.holds} held).",
    )


@chat.function(
    "get_aidentika_pricing",
    "Read the sparks cost of every Aidentika operation: photo/card "
    "generation, edits, and 5s/10s video.",
    action_type="read",
    chain_callable=True,
    data_model=PricingInfo,
)
async def get_aidentika_pricing(ctx, params: NoParams) -> ActionResult:
    """Fetch the sparks cost of each Aidentika operation."""
    api_key, err = await _require_key(ctx)
    if err:
        return err
    try:
        data = await aid.get_pricing(ctx, api_key)
    except aid.ProviderError as exc:
        return ActionResult.error(str(exc), code=exc.code)
    return ActionResult.success(data=PricingInfo(**data), summary="Fetched Aidentika pricing.")


@chat.function(
    "list_aidentika_categories",
    "List all product categories and their shooting concepts. Use the "
    "category_id/concept_id values in generation calls. Cached 24h by "
    "Aidentika.",
    action_type="read",
    chain_callable=True,
    data_model=CategoriesList,
)
async def list_aidentika_categories(ctx, params: NoParams) -> ActionResult:
    """Fetch all product categories and concepts from Aidentika."""
    api_key, err = await _require_key(ctx)
    if err:
        return err
    try:
        data = await aid.get_categories(ctx, api_key)
    except aid.ProviderError as exc:
        return ActionResult.error(str(exc), code=exc.code)
    cats = data.get("categories", [])
    return ActionResult.success(
        data=CategoriesList(categories=cats),
        summary=f"{len(cats)} categories available.",
    )


# ---------------------------------------------------------------------------
# Upload + free analysis
# ---------------------------------------------------------------------------

@chat.function(
    "upload_product_image",
    "Upload a product image once (base64) to reuse its upload_id across "
    "several generation requests, instead of re-sending the base64 data "
    "each time. Valid for 1 hour; max 20 active uploads per account.",
    action_type="write",
    chain_callable=True,
    data_model=UploadResult,
    event="aidentika-connector.upload_product_image",
    effects=["aidentika.image.uploaded"],
)
async def upload_product_image(ctx, params: UploadProductImageParams) -> ActionResult:
    """Upload one image to Aidentika and return its reusable upload_id."""
    api_key, err = await _require_key(ctx)
    if err:
        return err
    try:
        data = await aid.upload_image(ctx, api_key, _image_dict(params.image))
    except aid.ProviderError as exc:
        return ActionResult.error(str(exc), code=exc.code)
    res = UploadResult(**data)
    return ActionResult.success(
        data=res,
        summary=f"Uploaded. upload_id={res.upload_id}, valid {res.expires_in}s.",
    )


@chat.function(
    "analyze_product",
    "Analyze a product photo for free (no sparks spent): detects category, "
    "product name, and key selling qualities. Use the result to fill in "
    "category_id/product_name/comment on a generation call.",
    action_type="read",
    chain_callable=True,
    data_model=AnalyzeResult,
)
async def analyze_product(ctx, params: AnalyzeProductParams) -> ActionResult:
    """Run Aidentika's free product analysis on one image."""
    api_key, err = await _require_key(ctx)
    if err:
        return err
    try:
        data = await aid.analyze(ctx, api_key, {"image": _image_dict(params.image)})
    except aid.ProviderError as exc:
        return ActionResult.error(str(exc), code=exc.code)
    res = AnalyzeResult(**data)
    return ActionResult.success(
        data=res,
        summary=f"Detected: {res.product_name or 'unknown product'} ({res.category_id or 'uncategorized'}).",
    )


