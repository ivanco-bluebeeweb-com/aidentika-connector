"""Pydantic schemas for Aidentika Connector -- combined public surface.

Field shapes (types, maxLength, defaults, enums) are copied directly from
Aidentika's own OpenAPI 3.1 spec (`GET /api/v1/public/openapi.json`), not
guessed from doc prose -- so a param name/limit here matches the real API
exactly.

The actual class definitions live in schemas_generation (connection, image
input, info, upload/analyze, generation, status/cancel/download, results)
and schemas_manage (projects, cards, webhooks, AI helpers), each kept
under ~300 lines. This module just re-exports both so `from schemas import
X` keeps working everywhere (handlers_*.py, tests, panels).
"""
from __future__ import annotations

from schemas_generation import (  # noqa: F401
    NoParams,
    ConnectAidentikaParams, ProviderConnection, DisconnectResult,
    ImageInput,
    BalanceInfo, PricingInfo, ConceptItem, CategoryItem, CategoriesList,
    UploadProductImageParams, UploadResult,
    AnalyzeProductParams, AnalyzeResult,
    GeneratePhotoParams, GenerateCardParams, GenerateVideoParams,
    EditActionParams, GenerateResult,
    GetActionStatusParams, ActionStatus,
    CancelActionParams, CancelResult,
    DownloadResultParams, DownloadResult,
    ListResultsParams, ResultItem, ResultsList,
)
from schemas_manage import (  # noqa: F401
    CreateAidentikaProjectParams, ListAidentikaProjectsParams,
    GetAidentikaProjectParams, UpdateAidentikaProjectParams,
    AidentikaProject, AidentikaProjectList,
    GetAidentikaCardParams, MoveAidentikaCardParams,
    CardActionSummary, AidentikaCard,
    CreateAidentikaWebhookParams, AidentikaWebhookCreated,
    ListAidentikaWebhooksParams, AidentikaWebhookItem, AidentikaWebhookList,
    DeleteAidentikaWebhookParams, DeleteResult,
    SuggestWishesParams, SuggestWishesResult,
    SuggestVideoScenarioParams, SuggestVideoScenarioResult,
    HelpersUsage,
)
