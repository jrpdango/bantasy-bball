<script lang="ts">
    import { onMount } from "svelte";
    import { getGames, getPlayerCosts, submitRoster } from "./api";
    import type { Game, PlayerCost } from "./types";

    interface Props {
        userId: string;
        guildId: string;
        onRosterSubmitted: () => void;
    }

    let { userId, guildId, onRosterSubmitted }: Props = $props();

    const BUDGET = 300;
    const ROSTER_SIZE = 5;

    let players = $state<PlayerCost[]>([]);
    let games = $state<Game[]>([]);
    let selected = $state<Set<number>>(new Set());
    let loading = $state(true);
    let error = $state<string | null>(null);
    let submitting = $state(false);
    let submitError = $state<string | null>(null);
    let submitted = $state(false);

    let totalCost = $derived(
        [...selected].reduce((sum, id) => {
            const p = players.find((p) => p.PLAYER_ID === id);
            return sum + (p?.COST ?? 0);
        }, 0),
    );

    let draftClosed = $derived(
        games.length > 0 &&
            Date.now() / 1000 >= Math.min(...games.map((g) => g.tipoff_ts)),
    );

    let canSubmit = $derived(
        selected.size === ROSTER_SIZE &&
            totalCost <= BUDGET &&
            !draftClosed &&
            !submitting,
    );

    onMount(async () => {
        try {
            [players, games] = await Promise.all([
                getPlayerCosts(),
                getGames(),
            ]);
        } catch (e) {
            error = e instanceof Error ? e.message : "Failed to load players";
        } finally {
            loading = false;
        }
    });

    function toggle(playerId: number, cost: number) {
        const next = new Set(selected);
        if (next.has(playerId)) {
            next.delete(playerId);
        } else if (next.size < ROSTER_SIZE && totalCost + cost <= BUDGET) {
            next.add(playerId);
        }
        selected = next;
    }

    async function submit() {
        submitting = true;
        submitError = null;
        try {
            await submitRoster({
                discord_user_id: userId,
                guild_id: guildId,
                player_ids: [...selected],
            });
            submitted = true;
            setTimeout(onRosterSubmitted, 1200);
        } catch (e) {
            submitError = e instanceof Error ? e.message : "Submission failed";
        } finally {
            submitting = false;
        }
    }
</script>

<div class="tab-content">
    {#if loading}
        <p class="muted">Loading players…</p>
    {:else if error}
        <p class="error">{error}</p>
    {:else if submitted}
        <p class="success">Roster submitted! Loading your results…</p>
    {:else}
        <div class="draft-header">
            <div class="budget-info">
                <span>Budget: <strong>{totalCost}/{BUDGET}</strong></span>
                <div class="budget-bar">
                    <div
                        class="budget-fill"
                        style="width: {Math.min(
                            (totalCost / BUDGET) * 100,
                            100,
                        )}%; background: {totalCost > BUDGET
                            ? 'var(--error)'
                            : 'var(--accent)'}"
                    ></div>
                </div>
            </div>
            <div class="pick-count">{selected.size}/{ROSTER_SIZE} players</div>
        </div>

        {#if draftClosed}
            <p class="warning">Draft window is closed for today.</p>
        {/if}

        <div class="player-list">
            {#each players as player (player.PLAYER_ID)}
                {@const isSelected = selected.has(player.PLAYER_ID)}
                {@const canAdd =
                    !isSelected &&
                    selected.size < ROSTER_SIZE &&
                    totalCost + player.COST <= BUDGET &&
                    !draftClosed}
                <button
                    class="player-row"
                    class:selected={isSelected}
                    class:disabled={!isSelected && !canAdd}
                    disabled={!isSelected && !canAdd}
                    onclick={() => toggle(player.PLAYER_ID, player.COST)}
                >
                    <div class="player-info">
                        <span class="player-name">{player.PLAYER_NAME}</span>
                        <span class="player-matchup"
                            >{player.TEAM} vs {player.OPP}</span
                        >
                    </div>
                    <div class="player-stats">
                        <span class="fp"
                            >{player.FP.toFixed(1)} <small>proj FP</small></span
                        >
                        <span class="cost">{player.COST}</span>
                    </div>
                </button>
            {/each}
        </div>

        {#if submitError}
            <p class="error">{submitError}</p>
        {/if}

        <button class="submit-btn" disabled={!canSubmit} onclick={submit}>
            {submitting ? "Submitting…" : "Submit Roster"}
        </button>
    {/if}
</div>

<style>
    .draft-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 14px;
        gap: 16px;
    }

    .budget-info {
        flex: 1;
        display: flex;
        flex-direction: column;
        gap: 4px;
        font-size: 0.85rem;
    }

    .budget-bar {
        height: 4px;
        background: var(--border);
        border-radius: 2px;
        overflow: hidden;
    }

    .budget-fill {
        height: 100%;
        transition:
            width 0.2s,
            background 0.2s;
    }

    .pick-count {
        font-size: 0.85rem;
        color: var(--muted);
        white-space: nowrap;
    }

    .player-list {
        display: flex;
        flex-direction: column;
        gap: 6px;
        margin-bottom: 16px;
    }

    .player-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        background: var(--card-bg);
        border: 1px solid var(--border);
        border-radius: 8px;
        padding: 10px 14px;
        cursor: pointer;
        text-align: left;
        transition:
            border-color 0.15s,
            background 0.15s;
        color: inherit;
        width: 100%;
    }

    .player-row:not(:disabled):hover {
        border-color: var(--accent);
    }

    .player-row.selected {
        border-color: var(--accent);
        background: var(--accent-dim);
    }

    .player-row.disabled {
        opacity: 0.4;
        cursor: not-allowed;
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
        font-size: 1rem;
        color: var(--accent);
    }

    .submit-btn {
        width: 100%;
        padding: 12px;
        background: var(--accent);
        color: #fff;
        font-weight: 700;
        font-size: 0.95rem;
        border: none;
        border-radius: 8px;
        cursor: pointer;
        transition: opacity 0.15s;
    }

    .submit-btn:disabled {
        opacity: 0.4;
        cursor: not-allowed;
    }
</style>
