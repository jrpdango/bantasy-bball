import type { Game, LeaderboardEntry, PlayerCost, Roster } from "./types";

const BASE =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "/api";

let _authToken: string | null = null;

export function setAuthToken(token: string): void {
  _authToken = token;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    ...(init?.headers as Record<string, string>),
  };
  if (_authToken) {
    headers["Authorization"] = `Bearer ${_authToken}`;
  }
  const res = await fetch(`${BASE}${path}`, { ...init, headers });
  if (!res.ok) {
    const detail = await res
      .json()
      .then((d) => d.detail)
      .catch(() => res.statusText);
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

export function getGames(): Promise<Game[]> {
  return request<Game[]>("/games");
}

export function getPlayerCosts(): Promise<PlayerCost[]> {
  return request<PlayerCost[]>("/players/costs");
}

export function submitRoster(body: {
  discord_user_id: string;
  guild_id: string;
  player_ids: number[];
}): Promise<unknown> {
  return request("/roster", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function getRoster(userId: string, guildId: string): Promise<Roster> {
  return request<Roster>(
    `/roster?discord_user_id=${userId}&guild_id=${guildId}`,
  );
}

export function getWeeklyLeaderboard(): Promise<LeaderboardEntry[]> {
  return request<LeaderboardEntry[]>("/leaderboard/weekly");
}

export function getLifetimeLeaderboard(): Promise<LeaderboardEntry[]> {
  return request<LeaderboardEntry[]>("/leaderboard/lifetime");
}
