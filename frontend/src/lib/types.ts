export interface PlayerCost {
  PLAYER_ID: number;
  PLAYER_NAME: string;
  COST: number;
  FP: number;
  TEAM: string;
  OPP: string;
}

export interface TeamInfo {
  teamId: number;
  teamCity: string;
  teamName: string;
  teamTricode: string;
}

export interface Game {
  game_id: string;
  game_date: string;
  away_team: TeamInfo;
  home_team: TeamInfo;
  tipoff: string;
  tipoff_ts: number;
}

export interface RosterPlayer {
  player_id: number;
  player_name: string | null;
  cost: number | null;
  fp: number | null;
  team: string | null;
  opp: string | null;
}

export interface Roster {
  discord_user_id: string;
  guild_id: string;
  game_date: string;
  players: RosterPlayer[];
  total_cost: number;
  total_fp: number | null;
}

export interface LeaderboardEntry {
  discord_user_id: string;
  total_fp: number;
  games_played: number;
  week_start?: string;
}
