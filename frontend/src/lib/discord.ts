import { DiscordSDK } from "@discord/embedded-app-sdk";
import { setAuthToken } from "./api";

const clientId = import.meta.env.VITE_DISCORD_CLIENT_ID as string;

export const discordSdk = new DiscordSDK(clientId);

export interface DiscordAuth {
  userId: string;
  guildId: string | null;
  username: string;
  avatar: string | null;
}

export async function initDiscord(): Promise<DiscordAuth> {
  await discordSdk.ready();

  const { code } = await discordSdk.commands.authorize({
    client_id: clientId,
    response_type: "code",
    state: "",
    prompt: "none",
    scope: ["identify"],
  });

  const tokenRes = await fetch("/api/auth/token", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ code }),
  });

  if (!tokenRes.ok) {
    throw new Error("Failed to exchange Discord auth code");
  }

  const { access_token, supabase_access_token } = await tokenRes.json();

  if (!supabase_access_token) {
    throw new Error("Failed to establish Supabase session: no token returned");
  }

  setAuthToken(supabase_access_token);

  const auth = await discordSdk.commands.authenticate({ access_token });

  return {
    userId: auth.user.id,
    guildId: discordSdk.guildId,
    username: auth.user.username,
    avatar: auth.user.avatar ?? null,
  };
}
