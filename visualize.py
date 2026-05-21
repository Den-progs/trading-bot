import json
import os
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from datetime import datetime
from collections import defaultdict

JOURNAL_FILE = "trade_journal.json"

def load_journal():
    if not os.path.exists(JOURNAL_FILE):
        print("No trade_journal.json found.")
        return []
    with open(JOURNAL_FILE) as f:
        return json.load(f)

def visualize():
    journal = load_journal()
    if not journal:
        return

    tickers = list({t["ticker"] for t in journal})
    colors = {"BUY": "#00c853", "SELL": "#ff1744", "HOLD": "#888888"}

    fig = plt.figure(figsize=(16, 10), facecolor="#0d0d0d")
    fig.suptitle("AI Brain Visualization — Trade Memory", color="white", fontsize=16, fontweight="bold")
    gs = gridspec.GridSpec(2, 3, figure=fig, hspace=0.45, wspace=0.35)

    # --- 1. Action distribution (pie) ---
    ax1 = fig.add_subplot(gs[0, 0])
    actions = [t["action"] for t in journal]
    counts = {a: actions.count(a) for a in ["BUY", "SELL", "HOLD"]}
    present = {k: v for k, v in counts.items() if v > 0}
    ax1.pie(present.values(), labels=present.keys(),
            colors=[colors[k] for k in present.keys()],
            autopct="%1.0f%%", textprops={"color": "white"})
    ax1.set_title("Decision Split", color="white")
    ax1.set_facecolor("#0d0d0d")

    # --- 2. Confidence over time ---
    ax2 = fig.add_subplot(gs[0, 1:])
    ax2.set_facecolor("#1a1a1a")
    for ticker in tickers:
        entries = [t for t in journal if t["ticker"] == ticker]
        times = list(range(len(entries)))
        confs = [t.get("ai_confidence", 0) for t in entries]
        ax2.plot(times, confs, label=ticker, linewidth=1.5, alpha=0.85)
    ax2.axhline(0.3, color="yellow", linestyle="--", linewidth=0.8, label="Threshold (0.3)")
    ax2.set_title("AI Confidence Over Time", color="white")
    ax2.set_xlabel("Trade #", color="gray")
    ax2.set_ylabel("Confidence", color="gray")
    ax2.tick_params(colors="gray")
    ax2.legend(facecolor="#1a1a1a", labelcolor="white", fontsize=8)
    for spine in ax2.spines.values():
        spine.set_edgecolor("#333")

    # --- 3. P&L per ticker (bar) ---
    ax3 = fig.add_subplot(gs[1, 0])
    ax3.set_facecolor("#1a1a1a")
    closed = [t for t in journal if t["action"] == "SELL" and t["pnl"] is not None]
    pnl_by_ticker = defaultdict(float)
    for t in closed:
        pnl_by_ticker[t["ticker"]] += t["pnl"]
    if pnl_by_ticker:
        bars = ax3.bar(pnl_by_ticker.keys(),
                       pnl_by_ticker.values(),
                       color=["#00c853" if v >= 0 else "#ff1744" for v in pnl_by_ticker.values()])
        ax3.set_title("Realized P&L by Coin", color="white")
        ax3.tick_params(colors="gray", axis="x", labelrotation=15)
        ax3.tick_params(colors="gray", axis="y")
        ax3.set_ylabel("P&L ($)", color="gray")
        for spine in ax3.spines.values():
            spine.set_edgecolor("#333")
    ax3.set_facecolor("#1a1a1a")

    # --- 4. Running equity curve ---
    ax4 = fig.add_subplot(gs[1, 1:])
    ax4.set_facecolor("#1a1a1a")
    running = 0
    equity = []
    trade_nums = []
    for i, t in enumerate(closed):
        running += t["pnl"]
        equity.append(running)
        trade_nums.append(i + 1)
    if equity:
        ax4.plot(trade_nums, equity, color="#00bcd4", linewidth=2)
        ax4.fill_between(trade_nums, equity, alpha=0.15, color="#00bcd4")
        ax4.axhline(0, color="#555", linewidth=0.8)
        ax4.set_title("Cumulative P&L Curve (AI Learning Progress)", color="white")
        ax4.set_xlabel("Closed Trade #", color="gray")
        ax4.set_ylabel("Cumulative P&L ($)", color="gray")
        ax4.tick_params(colors="gray")
        for spine in ax4.spines.values():
            spine.set_edgecolor("#333")

    plt.savefig("brain_visualization.png", dpi=150, bbox_inches="tight", facecolor="#0d0d0d")
    print("Saved brain_visualization.png")
    plt.show()

if __name__ == "__main__":
    visualize()
