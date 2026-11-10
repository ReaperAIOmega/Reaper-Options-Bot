"""Discord delivery for informational, read-only option signal ideas. No order execution."""

import asyncio
from datetime import datetime

import discord

import config
from engine import CycleState, EngineConfig, run_cycle
from market_data import ET
from tradier_api import TradierClient

ALLOWED_MENTIONS = discord.AllowedMentions(everyone=config.MENTION_EVERYONE, roles=False, users=False, replied_user=False)


class SignalClient(discord.Client):
    async def setup_hook(self):
        self.loop.create_task(signal_loop(self))


client = SignalClient(intents=discord.Intents.default())


def check_channel_permissions(channel) -> list[str]:
    """Least privilege: the bot needs only View Channel + Send Messages in the signals channel."""
    if channel is None:
        return ["signals channel not found or not visible to the bot"]
    problems = []
    me = getattr(channel.guild, "me", None)
    perms = channel.permissions_for(me) if me else None
    if perms is None or not (perms.view_channel and perms.send_messages):
        problems.append("bot lacks View Channel / Send Messages in the signals channel")
    if perms is not None and (perms.administrator or perms.manage_guild or perms.manage_channels):
        print("WARNING: bot role is over-privileged (administrator/manage); reduce it to view + send.")
    if config.MENTION_EVERYONE and perms is not None and not perms.mention_everyone:
        problems.append("MENTION_EVERYONE=true but the bot lacks Mention Everyone permission")
    return problems


async def signal_loop(bot: discord.Client):
    await bot.wait_until_ready()
    channel = bot.get_channel(config.SIGNALS_CHANNEL_ID)
    problems = check_channel_permissions(channel)
    if problems:
        print("Refusing to start signal loop: " + "; ".join(problems))
        return
    tradier = TradierClient(config.TRADIER_API_KEY, config.TRADIER_BASE_URL)
    if config.REJECTED_SYMBOLS:
        print("Ignoring symbols outside policy:", config.REJECTED_SYMBOLS)
    cfg = EngineConfig(config.WATCHLIST, config.MAX_SIGNALS_PER_CYCLE,
                       config.MAX_SIGNALS_PER_DAY, config.DATA_DELAY, config.CONTRACT_RULES)
    state = CycleState()
    while not bot.is_closed():
        try:
            result = await asyncio.to_thread(run_cycle, tradier, cfg, state, datetime.now(ET))
            for message in result["messages"]:
                await channel.send(message, allowed_mentions=ALLOWED_MENTIONS)
            if result["skipped"]:
                print("Skipped:", result["skipped"])
        except Exception as exc:  # keep the loop alive on API/network errors
            print(f"Signal cycle failed: {exc!r}")
        await asyncio.sleep(config.CYCLE_SECONDS)


@client.event
async def on_ready():
    print(f"Logged in as {client.user}")


if __name__ == "__main__":
    client.run(config.DISCORD_BOT_TOKEN)
