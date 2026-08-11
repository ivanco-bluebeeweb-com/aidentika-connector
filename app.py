"""Extension declaration, secret, lifecycle hooks.

WHY BYOK. Aidentika (aidentika.com) is a paid third-party AI product-photo
and product-video generation service -- the user has their own
app.aidentika.com account and their own sparks balance. Not something
Imperal can broker centrally, so the user pastes their own API key once.

WHY ONE SECRET (unlike DataForSEO's login+password pair). Aidentika issues
a single opaque Bearer key `ak_...` per docs.aidentika.com/api/authentication
-- there is nothing else to store.

WHY write_mode="both", same reasoning as DataForSEO Connector / Media
Studio's Magnific integration. Declaring write_mode="user" would mean only
the platform's generic Secrets screen could write it -- leaving a
first-time user with no in-app explanation of what an Aidentika API key is
or whether what they pasted actually works. write_mode="both" keeps the
platform Secrets screen working AND lets this extension's own
`connect_aidentika` validate the key against Aidentika's API (a free
GET /balance call) before writing it, so a bad paste is rejected immediately.
"""
from imperal_sdk import Extension, ChatExtension

ext = Extension(
    "aidentika-connector",
    version="0.1.0",
    display_name="Aidentika Connector",
    description=(
        "Generate AI product photos, infographic cards, and short videos "
        "from your own product photos via your Aidentika account -- styled "
        "photo/card/video generation, free product analysis, image "
        "uploads for reuse, balance/pricing/category lookups, projects and "
        "cards to organize results, webhooks for completion notifications, "
        "and free AI helpers that draft marketing text and video scenarios. "
        "Bring your own Aidentika API key; every call runs on your own "
        "sparks balance."
    ),
    icon="icon.svg",
    actions_explicit=True,
    capabilities=["aidentika:read", "aidentika:write"],
)

chat = ChatExtension(
    ext,
    tool_name="aidentika-connector",
    description="AI product photo/card/video generation via your own Aidentika account",
)

ext.secret(
    name="aidentika_api_key",
    description=(
        "Aidentika API key (starts with ak_) -- create one at "
        "app.aidentika.com -> Profile -> API. Max 10 keys per account."
    ),
    write_mode="both",
)


@ext.health_check
async def health_check(ctx) -> bool:
    """Basic liveness check -- confirms the store surface is reachable."""
    await ctx.store.query("aidentika_settings", limit=1)
    return True
