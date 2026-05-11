"""
Discord remote-control for the trading bot.

Runs a discord.py bot in a background daemon thread so the main trading loop
can stay purely synchronous. The two sides share a BotState object; all flag
reads/writes go through a threading.Lock so they are safe.

Required env var:
    DISCORD_BOT_TOKEN   — bot token from the Discord Developer Portal

Optional env var:
    DISCORD_CONTROL_CHANNEL — channel name the bot will accept commands from
                              (default: any channel the bot can see)

Commands (prefix "!"):
    !status   — show whether the bot is running or paused
    !pause    — stop placing new orders (loop keeps running)
    !resume   — re-enable order placement
    !summary  — print the trade-journal P&L summary
    !stop     — ask the bot to exit after the current cycle
    !help     — list commands
"""

import os
import asyncio
import threading

import discord
from discord.ext import commands


COMMAND_PREFIX = "!"


class BotState:
    """Thread-safe flags shared between the trading loop and the Discord thread."""

    def __init__(self):
        self.paused = False
        self.running = True
        self._lock = threading.Lock()

    def pause(self):
        with self._lock:
            self.paused = True

    def resume(self):
        with self._lock:
            self.paused = False

    def stop(self):
        with self._lock:
            self.running = False


class RemoteControl:
    """Wraps a discord.py bot running on a background thread."""

    def __init__(self, state: BotState, get_summary_fn):
        self.state = state
        self.get_summary = get_summary_fn
        self._token = os.getenv("DISCORD_BOT_TOKEN")
        self._control_channel = os.getenv("DISCORD_CONTROL_CHANNEL")
        self._loop: asyncio.AbstractEventLoop | None = None
        self._bot: commands.Bot | None = None
        self._thread: threading.Thread | None = None

    def start(self):
        """Start the Discord bot on a daemon thread. No-op if no token is set."""
        if not self._token:
            return

        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run, name="discord-remote", daemon=True)
        self._thread.start()

    def stop(self):
        """Close the Discord bot gracefully (called from main thread on shutdown)."""
        if self._bot and self._loop and not self._loop.is_closed():
            asyncio.run_coroutine_threadsafe(self._bot.close(), self._loop)

    def _in_control_channel(self, ctx: commands.Context) -> bool:
        if not self._control_channel:
            return True
        return ctx.channel.name == self._control_channel

    def _run(self):
        asyncio.set_event_loop(self._loop)

        intents = discord.Intents.default()
        intents.message_content = True

        bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents, help_command=None)
        self._bot = bot

        state = self.state
        get_summary = self.get_summary
        check = self._in_control_channel

        @bot.event
        async def on_ready():
            print(f"[Remote] Discord bot connected as {bot.user}")

        @bot.event
        async def on_command_error(ctx, error):
            if isinstance(error, commands.CommandNotFound):
                return  # ignore unknown commands silently

        @bot.command(name="pause")
        async def cmd_pause(ctx):
            if not check(ctx):
                return
            state.pause()
            await ctx.send("⏸️ Trading **paused** — monitoring continues, no new orders.")

        @bot.command(name="resume")
        async def cmd_resume(ctx):
            if not check(ctx):
                return
            state.resume()
            await ctx.send("▶️ Trading **resumed**.")

        @bot.command(name="status")
        async def cmd_status(ctx):
            if not check(ctx):
                return
            label = "⏸️ PAUSED" if state.paused else "▶️ RUNNING"
            await ctx.send(f"Bot status: **{label}**")

        @bot.command(name="summary")
        async def cmd_summary(ctx):
            if not check(ctx):
                return
            text = get_summary()
            await ctx.send(f"```\n{text}\n```")

        @bot.command(name="stop")
        async def cmd_stop(ctx):
            if not check(ctx):
                return
            await ctx.send("🛑 Stop requested — bot will exit after the current cycle.")
            state.stop()

        @bot.command(name="help")
        async def cmd_help(ctx):
            if not check(ctx):
                return
            await ctx.send(
                "**Trading Bot Remote Control**\n"
                f"`{COMMAND_PREFIX}status`  — running or paused?\n"
                f"`{COMMAND_PREFIX}pause`   — suspend order placement\n"
                f"`{COMMAND_PREFIX}resume`  — re-enable order placement\n"
                f"`{COMMAND_PREFIX}summary` — portfolio P&L summary\n"
                f"`{COMMAND_PREFIX}stop`    — gracefully shut down the bot\n"
            )

        self._loop.run_until_complete(bot.start(self._token))
