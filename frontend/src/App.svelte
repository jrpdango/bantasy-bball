<script lang="ts">
    import { onMount } from "svelte";
    import { initDiscord } from "./lib/discord";
    import type { DiscordAuth } from "./lib/discord";
    import GamesTab from "./lib/GamesTab.svelte";
    import DraftTab from "./lib/DraftTab.svelte";
    import RosterTab from "./lib/RosterTab.svelte";

    type Tab = "games" | "draft" | "roster";

    let auth = $state<DiscordAuth | null>(null);
    let initError = $state<string | null>(null);
    let activeTab = $state<Tab>("games");

    let rosterTabKey = $state(0);

    onMount(async () => {
        try {
            auth = await initDiscord();
        } catch (e) {
            initError = e instanceof Error ? e.message : "Discord auth failed";
        }
    });

    function switchTab(tab: Tab) {
        activeTab = tab;
    }

    function onRosterSubmitted() {
        rosterTabKey++;
        activeTab = "roster";
    }
</script>

{#if initError}
    <div class="init-error">
        <p>Failed to connect to Discord</p>
        <small>{initError}</small>
    </div>
{:else if !auth}
    <div class="loading-screen">
        <div class="spinner"></div>
        <p>Connecting…</p>
    </div>
{:else}
    <div class="app">
        <header class="app-header">
            <span class="app-title">Fantasy Hoops</span>
            <span class="user-chip">@{auth.username}</span>
        </header>

        <nav class="tab-bar">
            <button
                class:active={activeTab === "games"}
                onclick={() => switchTab("games")}>Games</button
            >
            <button
                class:active={activeTab === "draft"}
                onclick={() => switchTab("draft")}>Draft</button
            >
            <button
                class:active={activeTab === "roster"}
                onclick={() => switchTab("roster")}>My Roster</button
            >
        </nav>

        <main class="tab-panel">
            {#if activeTab === "games"}
                <GamesTab />
            {:else if activeTab === "draft"}
                <DraftTab
                    userId={auth.userId}
                    guildId={auth.guildId ?? ""}
                    {onRosterSubmitted}
                />
            {:else}
                {#key rosterTabKey}
                    <RosterTab
                        userId={auth.userId}
                        guildId={auth.guildId ?? ""}
                        onGoDraft={() => switchTab("draft")}
                    />
                {/key}
            {/if}
        </main>
    </div>
{/if}

<style>
    .loading-screen,
    .init-error {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        height: 100vh;
        gap: 12px;
        color: var(--muted);
    }

    .init-error p {
        color: var(--error);
        font-weight: 600;
    }

    .spinner {
        width: 28px;
        height: 28px;
        border: 3px solid var(--border);
        border-top-color: var(--accent);
        border-radius: 50%;
        animation: spin 0.7s linear infinite;
    }

    @keyframes spin {
        to {
            transform: rotate(360deg);
        }
    }

    .app {
        display: flex;
        flex-direction: column;
        height: 100vh;
        max-width: 480px;
        margin: 0 auto;
    }

    .app-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 12px 16px;
        border-bottom: 1px solid var(--border);
        flex-shrink: 0;
    }

    .app-title {
        font-weight: 700;
        font-size: 1rem;
        color: var(--accent);
    }

    .user-chip {
        font-size: 0.75rem;
        color: var(--muted);
        background: var(--card-bg);
        padding: 3px 8px;
        border-radius: 12px;
        border: 1px solid var(--border);
    }

    .tab-bar {
        display: flex;
        border-bottom: 1px solid var(--border);
        flex-shrink: 0;
    }

    .tab-bar button {
        flex: 1;
        padding: 10px 0;
        background: none;
        border: none;
        border-bottom: 2px solid transparent;
        color: var(--muted);
        font-size: 0.85rem;
        font-weight: 500;
        cursor: pointer;
        transition:
            color 0.15s,
            border-color 0.15s;
    }

    .tab-bar button.active {
        color: var(--accent);
        border-bottom-color: var(--accent);
    }

    .tab-panel {
        flex: 1;
        overflow-y: auto;
        padding: 16px;
    }
</style>
