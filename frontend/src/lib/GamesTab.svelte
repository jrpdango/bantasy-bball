<script lang="ts">
    import { onMount } from "svelte";
    import { getGames } from "./api";
    import type { Game } from "./types";

    let games = $state<Game[]>([]);
    let loading = $state(true);
    let error = $state<string | null>(null);

    onMount(async () => {
        try {
            games = await getGames();
        } catch (e) {
            error = e instanceof Error ? e.message : "Failed to load games";
        } finally {
            loading = false;
        }
    });

    function formatTipoff(ts: number): string {
        return new Date(ts * 1000).toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
        });
    }
</script>

<div class="tab-content">
    {#if loading}
        <p class="muted">Loading games…</p>
    {:else if error}
        <p class="error">{error}</p>
    {:else if games.length === 0}
        <p class="muted">No games scheduled today.</p>
    {:else}
        <div class="games-list">
            {#each games as game (game.game_id)}
                <div class="game-card">
                    <div class="matchup">
                        <span class="tricode">{game.away_team.teamTricode}</span
                        >
                        <span class="team-name"
                            >{game.away_team.teamCity}
                            {game.away_team.teamName}</span
                        >
                    </div>
                    <div class="vs">vs</div>
                    <div class="matchup">
                        <span class="tricode">{game.home_team.teamTricode}</span
                        >
                        <span class="team-name"
                            >{game.home_team.teamCity}
                            {game.home_team.teamName}</span
                        >
                    </div>
                    <div class="tipoff">🕐 {formatTipoff(game.tipoff_ts)}</div>
                </div>
            {/each}
        </div>
    {/if}
</div>

<style>
    .games-list {
        display: flex;
        flex-direction: column;
        gap: 10px;
    }

    .game-card {
        background: var(--card-bg);
        border: 1px solid var(--border);
        border-radius: 8px;
        padding: 14px 16px;
        display: flex;
        align-items: center;
        gap: 12px;
    }

    .matchup {
        display: flex;
        flex-direction: column;
        flex: 1;
    }

    .tricode {
        font-weight: 700;
        font-size: 1.1rem;
        color: var(--accent);
    }

    .team-name {
        font-size: 0.8rem;
        color: var(--muted);
    }

    .vs {
        color: var(--muted);
        font-size: 0.85rem;
        font-weight: 600;
    }

    .tipoff {
        font-size: 0.8rem;
        color: var(--muted);
        white-space: nowrap;
    }
</style>
