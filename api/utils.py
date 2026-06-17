from datetime import date, datetime, timedelta
from functools import cache
from typing import cast
from zoneinfo import ZoneInfo

import pandas as pd
from nba_api.stats.endpoints import (
    BoxScoreTraditionalV3,
    LeagueDashPlayerStats,
    PlayerCareerStats,
    PlayerGameLog,
    ScoreboardV3,
    TeamEstimatedMetrics,
)


def get_player_last_game_stats(
    player_id: int | str, season_type: str = "Regular Season"
):
    """Return a Series with the player's stats from their most recent game.

    season_type: "Regular Season", "Playoffs", "Pre Season", or "PlayIn"
    """
    log = PlayerGameLog(player_id=player_id, season_type_all_star=season_type)
    df = log.player_game_log.get_data_frame()
    return df.iloc[0]


def _current_nba_season() -> str:
    now = datetime.now()
    year = now.year if now.month >= 10 else now.year - 1
    return f"{year}-{str(year + 1)[2:]}"


@cache
def fetch_league_stats(season: str | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Fetch all player stats and team metrics for a season.

    Returns (merged_players, team_metrics) DataFrames.
    """
    if season is None:
        season = _current_nba_season()

    base_all = (
        LeagueDashPlayerStats(
            measure_type_detailed_defense="Base",
            per_mode_detailed="PerGame",
            season=season,
        ).league_dash_player_stats.get_data_frame()
    )[["PLAYER_ID", "PLAYER_NAME", "TEAM_ID", "PTS", "REB", "AST", "BLK", "TOV", "STL"]]
    base_all = base_all.rename(
        columns={"PTS": "PPG", "REB": "RPG", "AST": "APG", "BLK": "BPG"}
    )

    adv_all = (
        LeagueDashPlayerStats(
            measure_type_detailed_defense="Advanced",
            per_mode_detailed="PerGame",
            season=season,
        ).league_dash_player_stats.get_data_frame()
    )[["PLAYER_ID", "USG_PCT", "OFF_RATING"]]
    adv_all = adv_all.rename(columns={"OFF_RATING": "ORTG"})

    metrics = TeamEstimatedMetrics(
        season=season
    ).team_estimated_metrics.get_data_frame()
    merged = pd.merge(base_all, adv_all, on="PLAYER_ID", how="inner")

    return merged, metrics


def get_team_df(
    team_id: int, merged: pd.DataFrame, metrics: pd.DataFrame
) -> pd.DataFrame:
    """Filter pre-fetched league stats for a single team."""
    drtg = metrics.loc[metrics["TEAM_ID"] == team_id, "E_DEF_RATING"].iloc[0]
    df = merged[merged["TEAM_ID"] == team_id].copy()
    df["TEAM_DRTG"] = drtg
    return cast(
        pd.DataFrame,
        df[
            [
                "PLAYER_ID",
                "PLAYER_NAME",
                "PPG",
                "RPG",
                "APG",
                "BPG",
                "STL",
                "TOV",
                "USG_PCT",
                "ORTG",
                "TEAM_DRTG",
            ]
        ],
    ).reset_index(drop=True)


def calculate_players(team: pd.DataFrame, opponent_drtg: float) -> pd.DataFrame:
    import math

    fp = (
        team["PPG"]
        + 1.2 * team["RPG"]
        + 1.5 * team["APG"]
        + 2 * team["STL"]
        + 2 * team["BPG"]
        - team["TOV"]
    ).round(1)

    u = 0.85 + (team["USG_PCT"] * 0.9)
    m = 1 + ((team["ORTG"] - opponent_drtg) / 250)
    cost = (fp * u * m * 1.5).apply(math.ceil).clip(lower=25)

    return pd.DataFrame(
        {
            "PLAYER_ID": team["PLAYER_ID"].values,
            "PLAYER_NAME": team["PLAYER_NAME"].values,
            "FP": fp.values,
            "COST": cost.values,
        }
    )


def calculate_costs_for_games(
    merged: pd.DataFrame,
    metrics: pd.DataFrame,
    games: list[dict],
) -> pd.DataFrame:
    all_results = []
    for game in games:
        away = game["away_team"]
        home = game["home_team"]

        away_drtg = metrics.loc[
            metrics["TEAM_ID"] == away["teamId"], "E_DEF_RATING"
        ].iloc[0]
        home_drtg = metrics.loc[
            metrics["TEAM_ID"] == home["teamId"], "E_DEF_RATING"
        ].iloc[0]

        away_df = get_team_df(away["teamId"], merged, metrics)
        away_calc = calculate_players(away_df, home_drtg)
        away_calc["TEAM"] = away["teamTricode"]
        away_calc["OPP"] = home["teamTricode"]

        home_df = get_team_df(home["teamId"], merged, metrics)
        home_calc = calculate_players(home_df, away_drtg)
        home_calc["TEAM"] = home["teamTricode"]
        home_calc["OPP"] = away["teamTricode"]

        all_results.extend([away_calc, home_calc])

    if not all_results:
        return pd.DataFrame(
            columns=["PLAYER_ID", "PLAYER_NAME", "FP", "COST", "TEAM", "OPP"]
        )
    return pd.concat(all_results, ignore_index=True)


def get_team_comparison(
    team_id_1: int, team_id_2: int
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return per-player season averages + team DRTG for two teams."""
    merged, metrics = fetch_league_stats()
    return get_team_df(team_id_1, merged, metrics), get_team_df(
        team_id_2, merged, metrics
    )


def get_player_stats(player_id: int | str):
    """Return a dict with per-season and career regular-season stats for a player."""
    stats = PlayerCareerStats(player_id=player_id)
    return {
        "season_totals": stats.season_totals_regular_season.get_data_frame(),
        "career_totals": stats.career_totals_regular_season.get_data_frame(),
    }


def get_games(of_date: date | None = None) -> list[dict]:
    """Get a list of games on a particular date. Defaults to tomorrow if no date provided."""
    game_date = of_date or datetime.now(
        ZoneInfo("America/New_York")
    ).date() + timedelta(days=1)
    date_str = game_date.strftime("%Y-%m-%d")
    scoreboard = ScoreboardV3(game_date=date_str)
    assert scoreboard.line_score is not None
    line_score_df = scoreboard.line_score.get_data_frame()
    assert scoreboard.game_header is not None
    game_header_df = scoreboard.game_header.get_data_frame().set_index("gameId")

    games = []
    for game_id, group in line_score_df.groupby("gameId", sort=False):
        rows = group[["teamId", "teamCity", "teamName", "teamTricode"]].to_dict(
            orient="records"
        )
        if len(rows) == 2:
            utc_str = game_header_df.loc[game_id, "gameTimeUTC"]
            unix_ts = int(
                datetime.fromisoformat(utc_str.replace("Z", "+00:00")).timestamp()
            )
            games.append(
                {
                    "game_id": game_id,
                    "game_date": game_date.isoformat(),
                    "away_team": rows[0],
                    "home_team": rows[1],
                    "tipoff": f"<t:{unix_ts}:f>",
                    "tipoff_ts": unix_ts,
                }
            )

    return games


def fetch_actual_fp_for_games(games: list[dict]) -> dict[int, float]:
    """Fetch actual fantasy points for all players across the given completed games."""
    player_fp: dict[int, float] = {}
    for game in games:
        try:
            df = BoxScoreTraditionalV3(game["game_id"]).player_stats.get_data_frame()
            for _, row in df.iterrows():
                fp = (
                    row["points"]
                    + 1.2 * row["reboundsTotal"]
                    + 1.5 * row["assists"]
                    + 2 * row["steals"]
                    + 2 * row["blocks"]
                    - row["turnovers"]
                )
                player_fp[int(row["personId"])] = round(fp, 1)
        except Exception:
            continue
    return player_fp
