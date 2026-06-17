import os
from contextlib import suppress
from datetime import date

from supabase import Client, create_client

_client: Client | None = None


def get_client() -> Client:
    global _client
    if _client is None:
        # Service role key bypasses RLS — backend is a trusted server
        _client = create_client(
            os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"]
        )
    return _client


def upsert_auth_user(discord_user_id: str, username: str) -> str:
    """Create or find the Supabase auth user for a Discord user. Returns hashed_token for session creation."""
    email = f"{discord_user_id}@discord.invalid"
    admin = get_client().auth.admin
    with suppress(Exception):
        admin.create_user(
            {
                "email": email,
                "email_confirm": True,
                "user_metadata": {"discord_user_id": discord_user_id},
            }
        )
    result = admin.generate_link(
        {
            "type": "magiclink",
            "email": email,
        }
    )
    return result.properties.hashed_token


def validate_token(jwt: str) -> tuple[str, str]:
    """Validate a Supabase JWT. Returns (supabase_user_id, discord_user_id) or raises ValueError."""
    response = get_client().auth.get_user(jwt)
    if response is None or response.user is None:
        raise ValueError("Invalid token")
    user = response.user
    discord_user_id = (user.user_metadata or {}).get("discord_user_id", "")
    return str(user.id), discord_user_id


def upsert_roster(
    discord_user_id: str,
    guild_id: str,
    game_date: date,
    player_ids: list[int],
    supabase_user_id: str,
) -> dict:
    result = (
        get_client()
        .table("rosters")
        .upsert(
            {
                "discord_user_id": discord_user_id,
                "guild_id": guild_id,
                "game_date": game_date.isoformat(),
                "player_ids": player_ids,
                "supabase_user_id": supabase_user_id,
            },
            on_conflict="discord_user_id,guild_id,game_date",
        )
        .execute()
    )
    return result.data[0]


def get_rosters_for_date(game_date: date) -> list[dict]:
    result = (
        get_client()
        .table("rosters")
        .select("*")
        .eq("game_date", game_date.isoformat())
        .execute()
    )
    return result.data


def update_roster_fp(roster_id: str, total_fp: float) -> None:
    (
        get_client()
        .table("rosters")
        .update({"total_fp": total_fp})
        .eq("id", roster_id)
        .execute()
    )


def upsert_guild(guild_id: str, webhook_url: str) -> None:
    get_client().table("guilds").upsert(
        {"guild_id": guild_id, "webhook_url": webhook_url}
    ).execute()


def get_guilds_for_date(game_date: date) -> dict[str, str]:
    """Return {guild_id: webhook_url} for guilds with at least one roster on game_date."""
    rosters = (
        get_client()
        .table("rosters")
        .select("guild_id")
        .eq("game_date", game_date.isoformat())
        .execute()
    )
    guild_ids = list({r["guild_id"] for r in rosters.data})
    if not guild_ids:
        return {}
    guilds = (
        get_client()
        .table("guilds")
        .select("guild_id,webhook_url")
        .in_("guild_id", guild_ids)
        .execute()
    )
    return {g["guild_id"]: g["webhook_url"] for g in guilds.data}


def get_leaderboard_weekly() -> list[dict]:
    result = get_client().table("weekly_leaderboard").select("*").execute()
    return result.data


def get_leaderboard_lifetime() -> list[dict]:
    result = get_client().table("lifetime_leaderboard").select("*").execute()
    return result.data
