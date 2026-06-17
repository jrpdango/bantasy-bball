import os
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone

import httpx
import pandas as pd
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException
from nba_api.stats.endpoints import CommonAllPlayers
from pydantic import BaseModel

from . import db
from .utils import (
    calculate_costs_for_games,
    fetch_actual_fp_for_games,
    fetch_league_stats,
    get_games,
)

load_dotenv()

_player_costs: pd.DataFrame | None = None
_current_games: list[dict] | None = None
_current_game_date: date | None = None
_refresh_error: str | None = None


class RosterSubmission(BaseModel):
    discord_user_id: str
    guild_id: str
    player_ids: list[int]


class GuildRegistration(BaseModel):
    guild_id: str
    webhook_url: str


class TokenExchange(BaseModel):
    code: str


def _format_results_message(game_date: date, rosters: list[dict]) -> str:
    lines = [f"**Fantasy Basketball Results — {game_date.strftime('%B %d, %Y')}**\n"]
    if not rosters:
        lines.append("No rosters submitted for today.")
        return "\n".join(lines)
    for i, roster in enumerate(rosters, 1):
        fp = roster.get("total_fp")
        fp_str = f"{fp:.1f}" if fp is not None else "N/A"
        lines.append(f"{i}. <@{roster['discord_user_id']}> — {fp_str} FP")
    return "\n".join(lines)


async def _post_results(
    game_date: date, rosters: list[dict], player_fp: dict[int, float]
) -> None:
    guild_webhooks = db.get_guilds_for_date(game_date)
    async with httpx.AsyncClient() as client:
        for guild_id, webhook_url in guild_webhooks.items():
            guild_rosters = sorted(
                [r for r in rosters if r["guild_id"] == guild_id],
                key=lambda r: r.get("total_fp") or 0,
                reverse=True,
            )
            message = _format_results_message(game_date, guild_rosters)
            try:
                await client.post(webhook_url, json={"content": message})
            except Exception as e:
                print(f"Failed to post results to guild {guild_id}: {e}")


async def _refresh_data():
    global _player_costs, _current_games, _current_game_date, _refresh_error

    if _current_games and _current_game_date:
        try:
            player_fp = fetch_actual_fp_for_games(_current_games)
            rosters = db.get_rosters_for_date(_current_game_date)
            for roster in rosters:
                fp = sum(player_fp.get(pid, 0.0) for pid in roster["player_ids"])
                db.update_roster_fp(roster["id"], round(fp, 1))
            await _post_results(_current_game_date, rosters, player_fp)
        except Exception as e:
            print(f"Error during daily scoring: {e}")

    try:
        fetch_league_stats.cache_clear()
        merged, metrics = fetch_league_stats()
        games = get_games(of_date=date(2024, 1, 12))
        _player_costs = calculate_costs_for_games(merged, metrics, games)
        _current_games = games
        _current_game_date = (
            date.fromisoformat(games[0]["game_date"]) if games else None
        )
        _refresh_error = None
    except Exception as e:
        _player_costs = None
        _current_games = None
        _current_game_date = None
        _refresh_error = str(e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await _refresh_data()

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        _refresh_data,
        CronTrigger(hour=10, minute=0, timezone="UTC"),  # 6pm UTC+8
    )
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(lifespan=lifespan)


@app.get("/players/search")
async def search_players(search_string: str):
    players = CommonAllPlayers(is_only_current_season=1)
    player_data = players.common_all_players.get_data_frame()

    search_lower = search_string.lower()
    results = player_data[
        player_data["DISPLAY_FIRST_LAST"]
        .str.lower()
        .str.contains(search_lower, na=False)
    ]
    return results.to_dict(orient="records")


@app.get("/players/costs")
async def get_player_costs():
    if _refresh_error is not None or _player_costs is None:
        raise HTTPException(
            status_code=503, detail=_refresh_error or "Data unavailable"
        )
    return _player_costs.to_dict(orient="records")


@app.get("/games")
async def get_games_today():
    if _current_games is None:
        raise HTTPException(
            status_code=503, detail=_refresh_error or "Data unavailable"
        )
    return _current_games


@app.post("/roster")
async def submit_roster(
    body: RosterSubmission, authorization: str | None = Header(None)
):
    if _player_costs is None or _current_games is None or _current_game_date is None:
        raise HTTPException(
            status_code=503, detail=_refresh_error or "Data unavailable"
        )

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing authorization")

    jwt = authorization.removeprefix("Bearer ")
    try:
        supabase_user_id, token_discord_id = db.validate_token(jwt)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    if token_discord_id and token_discord_id != body.discord_user_id:
        raise HTTPException(status_code=403, detail="User ID mismatch")

    if len(body.player_ids) != 5:
        raise HTTPException(
            status_code=422, detail="Roster must have exactly 5 players"
        )

    costs_by_id = _player_costs.set_index("PLAYER_ID")["COST"].to_dict()

    for pid in body.player_ids:
        if pid not in costs_by_id:
            raise HTTPException(
                status_code=422, detail=f"Player {pid} is not available today"
            )

    total_cost = sum(costs_by_id[pid] for pid in body.player_ids)
    if total_cost > 300:
        raise HTTPException(
            status_code=422,
            detail=f"Total cost {total_cost} exceeds budget of 300",
        )

    earliest_tipoff = min(g["tipoff_ts"] for g in _current_games)
    if int(datetime.now(timezone.utc).timestamp()) >= earliest_tipoff:
        raise HTTPException(status_code=422, detail="Draft window has closed")

    roster = db.upsert_roster(
        body.discord_user_id,
        body.guild_id,
        _current_game_date,
        body.player_ids,
        supabase_user_id,
    )
    return roster


@app.get("/roster")
async def get_roster(discord_user_id: str, guild_id: str):
    if _player_costs is None or _current_game_date is None:
        raise HTTPException(
            status_code=503, detail=_refresh_error or "Data unavailable"
        )

    rosters = db.get_rosters_for_date(_current_game_date)
    roster = next(
        (
            r
            for r in rosters
            if r["discord_user_id"] == discord_user_id and r["guild_id"] == guild_id
        ),
        None,
    )
    if roster is None:
        raise HTTPException(status_code=404, detail="Roster not found")

    costs_by_id = _player_costs.set_index("PLAYER_ID").to_dict(orient="index")
    players = []
    for pid in roster["player_ids"]:
        info = costs_by_id.get(pid, {})
        players.append(
            {
                "player_id": pid,
                "player_name": info.get("PLAYER_NAME"),
                "cost": info.get("COST"),
                "fp": info.get("FP"),
                "team": info.get("TEAM"),
                "opp": info.get("OPP"),
            }
        )

    return {
        "discord_user_id": roster["discord_user_id"],
        "guild_id": roster["guild_id"],
        "game_date": roster["game_date"],
        "players": players,
        "total_cost": sum(p["cost"] or 0 for p in players),
        "total_fp": roster.get("total_fp"),
    }


@app.post("/auth/token")
async def exchange_token(body: TokenExchange):
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://discord.com/api/oauth2/token",
            data={
                "client_id": os.environ["DISCORD_CLIENT_ID"],
                "client_secret": os.environ["DISCORD_CLIENT_SECRET"],
                "grant_type": "authorization_code",
                "code": body.code,
            },
        )
        if not resp.is_success:
            raise HTTPException(status_code=502, detail="Discord token exchange failed")

        discord_access_token = resp.json()["access_token"]

        user_resp = await client.get(
            "https://discord.com/api/users/@me",
            headers={"Authorization": f"Bearer {discord_access_token}"},
        )
        if not user_resp.is_success:
            raise HTTPException(
                status_code=502, detail="Failed to fetch Discord user info"
            )

        discord_user = user_resp.json()

    hashed_token = db.upsert_auth_user(
        discord_user["id"], discord_user.get("username", "")
    )

    async with httpx.AsyncClient() as client:
        verify_resp = await client.post(
            f"{os.environ['SUPABASE_URL']}/auth/v1/verify",
            json={"token_hash": hashed_token, "type": "magiclink"},
            headers={"apikey": os.environ["SUPABASE_SECRET_KEY"]},
        )
    if not verify_resp.is_success:
        raise HTTPException(status_code=502, detail="Failed to create Supabase session")

    session = verify_resp.json()
    return {
        "access_token": discord_access_token,
        "supabase_access_token": session["access_token"],
        "supabase_refresh_token": session["refresh_token"],
    }


@app.get("/leaderboard/weekly")
async def get_weekly_leaderboard():
    return db.get_leaderboard_weekly()


@app.get("/leaderboard/lifetime")
async def get_lifetime_leaderboard():
    return db.get_leaderboard_lifetime()


@app.post("/guilds/register")
async def register_guild(body: GuildRegistration):
    db.upsert_guild(body.guild_id, body.webhook_url)
    return {"guild_id": body.guild_id}
