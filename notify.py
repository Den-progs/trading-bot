"""
Discord notification module.
Sends bot events to a Discord channel via webhook.
Fails silently if Discord is unavailable — never crashes the trading bot.
"""

import os
import requests
from datetime import datetime

WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")


def _send(content=None, embed=None):
    """Internal: post to Discord webhook. Silently swallows errors."""
    if not WEBHOOK_URL:
        return  # No webhook configured, skip silently

    payload = {}
    if content:
        payload["content"] = content
    if embed:
        payload["embeds"] = [embed]

    try:
        requests.post(WEBHOOK_URL, json=payload, timeout=5)
    except Exception:
        pass  # Don't crash the bot if Discord is down


def notify_startup(portfolio, model, interval, max_trades):
    """Sent when the bot boots up."""
    tickers = ", ".join(p["ticker"] for p in portfolio)
    embed = {
        "title": "🤖 Trading bot started",
        "description": f"Watching: **{tickers}**",
        "color": 0x00ff88,
        "fields": [
            {"name": "Model", "value": model, "inline": True},
            {"name": "Interval", "value": f"{interval}s", "inline": True},
            {"name": "Max trades", "value": str(max_trades), "inline": True},
        ],
        "timestamp": datetime.now().isoformat(),
    }
    _send(embed=embed)


def notify_buy(ticker, qty, price, confidence, reason):
    embed = {
        "title": f"📈 BUY {ticker}",
        "description": f"**{qty}** units at **${price}**",
        "color": 0x3498db,
        "fields": [
            {"name": "AI confidence", "value": f"{confidence}", "inline": True},
            {"name": "Reasoning", "value": reason or "(no reason)", "inline": False},
        ],
        "timestamp": datetime.now().isoformat(),
    }
    _send(embed=embed)


def notify_sell(ticker, price, pnl, confidence, reason):
    pnl_str = f"${pnl:+.4f}" if pnl is not None else "N/A"
    color = 0x2ecc71 if (pnl or 0) > 0 else (0xe74c3c if (pnl or 0) < 0 else 0x95a5a6)
    emoji = "✅" if (pnl or 0) > 0 else ("❌" if (pnl or 0) < 0 else "⚪")
    embed = {
        "title": f"{emoji} SELL {ticker}",
        "description": f"Closed at **${price}** | P&L: **{pnl_str}**",
        "color": color,
        "fields": [
            {"name": "AI confidence", "value": f"{confidence}", "inline": True},
            {"name": "Reasoning", "value": reason or "(no reason)", "inline": False},
        ],
        "timestamp": datetime.now().isoformat(),
    }
    _send(embed=embed)


def notify_summary(stats_text):
    """Periodic summary of bot performance."""
    embed = {
        "title": "📊 Portfolio summary",
        "description": f"```\n{stats_text}\n```",
        "color": 0xf1c40f,
        "timestamp": datetime.now().isoformat(),
    }
    _send(embed=embed)


def notify_shutdown(stats_text):
    embed = {
        "title": "🛑 Bot stopped",
        "description": f"```\n{stats_text}\n```",
        "color": 0xe74c3c,
        "timestamp": datetime.now().isoformat(),
    }
    _send(embed=embed)


def notify_error(message):
    """For unexpected errors you want to see immediately."""
    embed = {
        "title": "⚠️ Bot error",
        "description": str(message)[:1000],  # Discord field length limit
        "color": 0xff0000,
        "timestamp": datetime.now().isoformat(),
    }
    _send(embed=embed)