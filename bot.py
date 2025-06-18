import discord
import asyncio
from datetime import datetime, time, timedelta
import pytz
from config import DISCORD_BOT_TOKEN, SIGNALS_CHANNEL_ID, WATCHLIST, KILLZONES, MAX_SIGNALS
from signals import generate_signals_for_symbol
from market import get_index_bias

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

EST = pytz.timezone("US/Eastern")

async def send_signals(channel, signals):
    if not signals:
        return
    msg = ""
    for sig in signals:
        msg += (
            f"**[{sig['symbol']}] {sig['direction']} Signal | Score: {sig['score']}**\n"
            f"Entry: {sig['entry']}\n"
            f"Strike: {sig['strike']} ({sig['expiry']})\n"
            f"Setups: {', '.join(sig['setups'])}\n"
            f"Time: {sig['time']}\n"
            f"Reason: {sig['reason']}\n\n"
        )
    await channel.send(msg)

def is_in_killzone(now):
    # now is aware datetime in EST
    # Check if current time is within any killzone window +/- 15min
    killzone_ranges = [
        (time(9, 0), time(9, 15)),
        (time(9, 30), time(9, 45)),
        (time(10, 0), time(10, 15)),
        (time(13, 30), time(13, 45)),  # NY Killzone open
        (time(15, 45), time(16, 0)),   # NY Killzone close (4pm EST)
        (time(15, 30), time(15, 45)),
    ]
    for start, end in killzone_ranges:
        if start <= now.time() <= end:
            return True
    return False

async def check_and_send_signals():
    await client.wait_until_ready()
    channel = client.get_channel(SIGNALS_CHANNEL_ID)

    sent_alerts = {
        "first_alert": False,
        "signals_sent": 0,
    }

    while not client.is_closed():
        now = datetime.now(EST)
        bias = get_index_bias()
        if bias == "bearish":
            # Send caution message once per day only
            if not sent_alerts.get("bias_warned", False):
                await channel.send(
                    "@everyone ⚠️ Market shows bearish bias. Trade signals may be less reliable."
                )
                sent_alerts["bias_warned"] = True
        else:
            sent_alerts["bias_warned"] = False

        max_signals = MAX_SIGNALS["subsequent_alerts"]
        if not sent_alerts["first_alert"]:
            # At 9 AM EST max 6 signals
            if now.time().hour == 9 and now.time().minute <= 15:
                max_signals = MAX_SIGNALS["first_alert"]

        signals_all = []
        for symbol in WATCHLIST:
            signals = generate_signals_for_symbol(symbol)
            if signals:
                signals_all.extend(signals)

        # Sort by score descending
        signals_all.sort(key=lambda s: s["score"], reverse=True)

        # Filter max signals
        to_send = signals_all[:max_signals]

        if to_send:
            await send_signals(channel, to_send)
            sent_alerts["first_alert"] = True
            sent_alerts["signals_sent"] += len(to_send)

        # Sleep until next target time (roughly every 15-30 min during market hours)
        await asyncio.sleep(900)

@client.event
async def on_ready():
    print(f"Logged in as {client.user}")

client.loop.create_task(check_and_send_signals())

client.run(DISCORD_BOT_TOKEN)
