import json
import os
from datetime import datetime
from collections import defaultdict

JOURNAL_FILE = "trade_journal.json"


def load_journal():
    if not os.path.exists(JOURNAL_FILE):
        print("No trade_journal.json found.")
        return []
    with open(JOURNAL_FILE) as f:
        return json.load(f)


def closed_trades(journal):
    return [t for t in journal if t["action"] == "SELL" and t["pnl"] is not None]


def trade_duration(journal, sell_trade):
    idx = sell_trade.get("linked_buy_index")
    if idx is None or idx >= len(journal):
        return None
    try:
        buy_time = datetime.fromisoformat(journal[idx]["timestamp"])
        sell_time = datetime.fromisoformat(sell_trade["timestamp"])
        minutes = int((sell_time - buy_time).total_seconds() / 60)
        return f"{minutes}m" if minutes < 60 else f"{minutes // 60}h {minutes % 60}m"
    except Exception:
        return None


def print_summary(trades):
    wins = [t for t in trades if t["pnl"] > 0]
    losses = [t for t in trades if t["pnl"] <= 0]
    total_pnl = sum(t["pnl"] for t in trades)
    win_rate = len(wins) / len(trades) * 100
    avg_win = sum(t["pnl"] for t in wins) / len(wins) if wins else 0
    avg_loss = sum(t["pnl"] for t in losses) / len(losses) if losses else 0

    print("\n=== OVERALL SUMMARY ===")
    print(f"  Closed trades : {len(trades)}")
    print(f"  Win rate      : {win_rate:.1f}%  ({len(wins)}W / {len(losses)}L)")
    print(f"  Total P&L     : ${total_pnl:+.4f}")
    print(f"  Avg win       : ${avg_win:+.4f}")
    print(f"  Avg loss      : ${avg_loss:+.4f}")
    if wins and losses:
        print(f"  Win/Loss ratio: {abs(avg_win / avg_loss):.2f}x")


def print_per_coin(trades):
    by_coin = defaultdict(list)
    for t in trades:
        by_coin[t["ticker"]].append(t["pnl"])

    print("\n=== PER-COIN BREAKDOWN ===")
    for ticker in sorted(by_coin):
        pnls = by_coin[ticker]
        wins = [p for p in pnls if p > 0]
        win_rate = len(wins) / len(pnls) * 100
        total = sum(pnls)
        avg = total / len(pnls)
        print(f"  {ticker:<12} {len(pnls):2d} trades | win {win_rate:.0f}% | P&L ${total:+.4f} | avg ${avg:+.4f}/trade")


def print_confidence_bands(trades):
    bands = [
        (0.0,  0.4,  "0.3-0.4"),
        (0.4,  0.5,  "0.4-0.5"),
        (0.5,  0.6,  "0.5-0.6"),
        (0.6,  0.7,  "0.6-0.7"),
        (0.7,  1.01, "0.7+   "),
    ]

    print("\n=== WIN RATE BY CONFIDENCE BAND ===")
    any_printed = False
    for lo, hi, label in bands:
        band = [t for t in trades if lo <= t["ai_confidence"] < hi]
        if not band:
            continue
        wins = [t for t in band if t["pnl"] > 0]
        win_rate = len(wins) / len(band) * 100
        total_pnl = sum(t["pnl"] for t in band)
        print(f"  {label}: {len(band):2d} trades | win {win_rate:.0f}% | P&L ${total_pnl:+.4f}")
        any_printed = True
    if not any_printed:
        print("  (not enough data)")


def print_best_worst(journal, trades, n=3):
    def fmt(t):
        dur = trade_duration(journal, t)
        parts = [f"{t['ticker']} @ ${t['price']}", f"conf {t['ai_confidence']}"]
        if dur:
            parts.append(f"held {dur}")
        return " | ".join(parts)

    sorted_trades = sorted(trades, key=lambda t: t["pnl"], reverse=True)

    print(f"\n=== TOP {n} TRADES ===")
    for t in sorted_trades[:n]:
        print(f"  +${t['pnl']:.4f} | {fmt(t)}")
        print(f"    \"{t['ai_reason']}\"")

    print(f"\n=== BOTTOM {n} TRADES ===")
    for t in sorted_trades[-n:][::-1]:
        print(f"  {t['pnl']:+.4f} | {fmt(t)}")
        print(f"    \"{t['ai_reason']}\"")


def main():
    journal = load_journal()
    if not journal:
        return

    trades = closed_trades(journal)
    open_buys = [t for t in journal if t["action"] == "BUY" and t["pnl"] is None]

    print(f"Journal: {len(journal)} entries | {len(trades)} closed trades | {len(open_buys)} open BUY entries")

    if not trades:
        print("No closed trades to analyze yet.")
        return

    print_summary(trades)
    print_per_coin(trades)
    print_confidence_bands(trades)
    print_best_worst(journal, trades)


if __name__ == "__main__":
    main()
