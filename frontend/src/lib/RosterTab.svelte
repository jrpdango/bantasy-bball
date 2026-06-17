<script lang="ts">
    import { onMount } from "svelte";
    import { getRoster } from "./api";
    import type { Roster } from "./types";

    interface Props {
        userId: string;
        guildId: string;
        onGoDraft: () => void;
    }

    let { userId, guildId, onGoDraft }: Props = $props();

    let roster = $state<Roster | null>(null);
    let loading = $state(true);
    let error = $state<string | null>(null);
    let noRoster = $state(false);

    onMount(async () => {
        await load();
    });

    async function load() {
        loading = true;
        error = null;
        noRoster = false;
        try {
            roster = await getRoster(userId, guildId);
        } catch (e) {
            const msg = e instanceof Error ? e.message : "";
            if (msg === "Roster not found") {
                noRoster = true;
            } else {
                error = msg || "Failed to load roster";
            }
        } finally {
            loading = false;
        }
    }
</script>

<div class="tab-content">
    {#if loading}
        <p class="muted">Loading roster…</p>
    {:else if error}
        <p class="error">{error}</p>
    {:else if noRoster}
        <div class="empty-state">
            <p class="muted">You haven't submitted a roster for today.</p>
            <button class="go-draft-btn" onclick={onGoDraft}>Go to Draft</button
            >
        </div>
    {:else if roster}
        <div class="roster-meta">
            <span class="date">{roster.game_date}</span>
            <span class="total-fp">
                {roster.total_fp !== null
                    ? `${roster.total_fp.toFixed(1)} FP`
                    : "Pending"}
            </span>
        </div>

        <div class="player-list">
            {#each roster.players as player (player.player_id)}
                <div class="player-row">
                    <div class="player-info">
                        <span class="player-name"
                            >{player.player_name ?? "Unknown"}</span
                        >
                        <span class="player-matchup">
                            {player.team ?? "?"} vs {player.opp ?? "?"}
                        </span>
                    </div>
                    <div class="player-stats">
                        <span class="fp">
                            {player.fp !== null ? player.fp.toFixed(1) : "—"}
                            <small>FP</small>
                        </span>
                        <span class="cost">{player.cost ?? "—"}</span>
                    </div>
                </div>
            {/each}
        </div>

        <div class="roster-footer">
            <span>Total cost: <strong>{roster.total_cost}</strong></span>
            <span>
                Total FP: <strong
                    >{roster.total_fp !== null
                        ? roster.total_fp.toFixed(1)
                        : "Pending"}</strong
                >
            </span>
        </div>

        <button class="refresh-btn" onclick={load}>Refresh</button>
    {/if}
</div>

<style>
    .empty-state {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 14px;
        padding: 32px 0;
    }

    .go-draft-btn {
        padding: 10px 24px;
        background: var(--accent);
        color: #fff;
        font-weight: 700;
        border: none;
        border-radius: 8px;
        cursor: pointer;
    }

    .roster-meta {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 14px;
        font-size: 0.85rem;
    }

    .date {
        color: var(--muted);
    }

    .total-fp {
        font-weight: 700;
        font-size: 1.1rem;
        color: var(--accent);
    }

    .player-list {
        display: flex;
        flex-direction: column;
        gap: 6px;
        margin-bottom: 14px;
    }

    .player-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        background: var(--card-bg);
        border: 1px solid var(--border);
        border-radius: 8px;
        padding: 10px 14px;
    }

    .player-info {
        display: flex;
        flex-direction: column;
        gap: 2px;
    }

    .player-name {
        font-weight: 600;
        font-size: 0.9rem;
    }

    .player-matchup {
        font-size: 0.75rem;
        color: var(--muted);
    }

    .player-stats {
        display: flex;
        flex-direction: column;
        align-items: flex-end;
        gap: 2px;
    }

    .fp {
        font-size: 0.8rem;
        color: var(--muted);
    }

    .fp small {
        font-size: 0.7rem;
    }

    .cost {
        font-weight: 700;
        color: var(--accent);
    }

    .roster-footer {
        display: flex;
        justify-content: space-between;
        font-size: 0.85rem;
        padding: 10px 14px;
        background: var(--card-bg);
        border-radius: 8px;
        border: 1px solid var(--border);
        margin-bottom: 12px;
    }

    .refresh-btn {
        width: 100%;
        padding: 9px;
        background: transparent;
        color: var(--muted);
        border: 1px solid var(--border);
        border-radius: 8px;
        cursor: pointer;
        font-size: 0.85rem;
        transition: border-color 0.15s;
    }

    .refresh-btn:hover {
        border-color: var(--accent);
        color: var(--accent);
    }
</style>
