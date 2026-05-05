"""
Backtester for the crypto trading strategy.

Simulates a deterministic version of what the AI does: buy small dips,
sell small rallies. Results show whether the core strategy has edge,
independent of LLM noise.

Usage:
  python backtest.py                      # 30 days, all 4 coins
  python backtest.py --days 7             # 7 days
  python backtest.py --coin AVAX/USD      # single coin
  python backtest.py --threshold 0.001    # 0.1% move threshold (default 0.05%)
  python backtest.py --refresh            # ignore cache, re-download data
  python backtest.py --sweep              # test 5 thresholds, find the best
"""

import os
import csv
import sys
import argparse
import statistics
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

from alpaca.data.historical import CryptoHistoricalDataClient
from alpaca.data.requests import CryptoBarsRequest
from alpaca.data.timeframe import TimeFrame

PORTFOLIO = [
    {"ticker": "DOGE/USD", "qty": 200},
    {"ticker": "AVAX/USD", "qty": 2},
    {"ticker": "ETH/USD",  "qty": 0.02},
    {"ticker": "SHIB/USD", "qty": 5000000},
]
LOOKBACK_BARS = 240 # 4 hours of 1-min bars to measure move size for buy/sell decisions
CONFIDENCE_THRESHOLD = 0.3
DATA_DIR = "data"


# ===== DATA =====

def fetch_bars(ticker, days, refresh=False):
    os.makedirs(DATA_DIR, exist_ok=True)
    cache = os.path.join(DATA_DIR, f"{ticker.replace('/', '_')}_{days}d.csv")

    if not refresh and os.path.exists(cache):
        age_h = (datetime.now().timestamp() - os.path.getmtime(cache)) / 3600
        if age_h < 24:
            rows = []
            with open(cache, newline="") as f:
                for row in csv.DictReader(f):
                    rows.append({"timestamp": row["timestamp"], "close": float(row["close"])})
            print(f"  {len(rows):,} bars from cache ({age_h:.1f}h old)")
            return rows

    print(f"  Downloading {days}d of {ticker} 1-min bars (may take ~30s)...")
    client = CryptoHistoricalDataClient()
    end = datetime.now()
    start = end - timedelta(days=days)

    try:
        result = client.get_crypto_bars(CryptoBarsRequest(
            symbol_or_symbols=ticker,
            timeframe=TimeFrame.Minute,
            start=start,
            end=end,
        ))
    except Exception as e:
        print(f"  Download failed: {e}")
        return []

    if ticker not in result.data or not result.data[ticker]:
        print(f"  No data returned.")
        return []

    rows = [{"timestamp": str(b.timestamp), "close": float(b.close)} for b in result.data[ticker]]

    with open(cache, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["timestamp", "close"])
        w.writeheader()
        w.writerows(rows)

    print(f"  {len(rows):,} bars downloaded, cached to {cache}")
    return rows


# ===== STRATEGY =====

def decide(prices, has_position, threshold):
    """
    Rule-based proxy for the AI: buy on dips, sell on rallies.
    Measures % move from start of lookback window to current bar.
    """
    if len(prices) < 2 or prices[0] == 0:
        return "HOLD", 0.0
    change = (prices[-1] - prices[0]) / prices[0]
    if not has_position and change <= -threshold:
        conf = min(0.9, 0.5 + abs(change) / threshold * 0.1)
        return "BUY", conf
    if has_position and change >= threshold:
        conf = min(0.9, 0.5 + change / threshold * 0.1)
        return "SELL", conf
    return "HOLD", 0.0


# ===== SIMULATION =====

def simulate(ticker, qty, bars, threshold):
    closes = [b["close"] for b in bars]
    position = None
    trades = []
    equity = []
    running_pnl = 0.0

    for i in range(LOOKBACK_BARS, len(bars)):
        price = closes[i]
        unrealized = (price - position["buy_price"]) * qty if position else 0.0
        equity.append(running_pnl + unrealized)

        action, conf = decide(closes[i - LOOKBACK_BARS:i + 1], position is not None, threshold)
        if conf < CONFIDENCE_THRESHOLD:
            continue

        if action == "BUY" and position is None:
            position = {"buy_price": price, "buy_idx": i, "buy_ts": bars[i]["timestamp"]}

        elif action == "SELL" and position is not None:
            # RUTHLESS REALISM: 0.1% slippage/spread on each side
            SLIPPAGE = 0.001 
            real_buy_price = position["buy_price"] * (1 + SLIPPAGE)
            real_sell_price = price * (1 - SLIPPAGE)
            pnl = (real_sell_price - real_buy_price) * qty
            trades.append({
                "ticker": ticker,
                "buy_price": position["buy_price"],
                "sell_price": price,
                "qty": qty,
                "pnl": round(pnl, 6),
                "held_bars": i - position["buy_idx"],
                "buy_ts": position["buy_ts"],
                "sell_ts": bars[i]["timestamp"],
            })
            running_pnl += pnl
            position = None

    return trades, equity


# ===== METRICS =====

def calc_metrics(trades, equity):
    if not trades:
        return None

    pnls = [t["pnl"] for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    total_pnl = sum(pnls)

    # Max drawdown on running P&L
    peak, max_dd, running = 0.0, 0.0, 0.0
    for p in pnls:
        running += p
        peak = max(peak, running)
        max_dd = max(max_dd, peak - running)

    # Sharpe: annualized from daily equity snapshots (1440 bars = 1 day)
    sharpe = 0.0
    if len(equity) >= 2880:
        daily = [equity[i] for i in range(0, len(equity), 1440)]
        daily_ret = [daily[i] - daily[i - 1] for i in range(1, len(daily))]
        if len(daily_ret) > 1:
            mu = statistics.mean(daily_ret)
            sigma = statistics.stdev(daily_ret)
            sharpe = round(mu / sigma * (252 ** 0.5), 2) if sigma > 0 else 0.0

    return {
        "n": len(trades),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": len(wins) / len(trades) * 100,
        "total_pnl": total_pnl,
        "avg_win": sum(wins) / len(wins) if wins else 0.0,
        "avg_loss": sum(losses) / len(losses) if losses else 0.0,
        "max_dd": max_dd,
        "sharpe": sharpe,
        "avg_hold": sum(t["held_bars"] for t in trades) / len(trades),
    }


# ===== OUTPUT =====

def ascii_curve(equity, width=62, height=7):
    if not equity:
        return
    step = max(1, len(equity) // width)
    pts = equity[::step][:width]
    lo, hi = min(pts), max(pts)
    rng = hi - lo if hi != lo else 1.0

    for row in range(height, 0, -1):
        thresh = lo + (row / height) * rng
        bar = "".join("*" if v >= thresh else " " for v in pts)
        if row == height:
            label = f"${hi:+.3f}"
        elif row == 1:
            label = f"${lo:+.3f}"
        else:
            label = ""
        print(f"  {label:>9} |{bar}|")
    print(f"  {'start':>9} |{'-' * len(pts)}| end")


def print_coin_result(ticker, m):
    if m is None:
        print(f"  {ticker}: no closed trades")
        return
    wr_flag = " <-- check this" if m["win_rate"] == 100 and m["n"] < 20 else ""
    print(f"  trades   : {m['n']}  ({m['wins']}W / {m['losses']}L){wr_flag}")
    print(f"  win rate : {m['win_rate']:.1f}%")
    print(f"  total P&L: ${m['total_pnl']:+.4f}")
    print(f"  avg win  : ${m['avg_win']:+.4f}  avg loss: ${m['avg_loss']:+.4f}")
    if m["avg_loss"] != 0:
        print(f"  W/L ratio: {abs(m['avg_win'] / m['avg_loss']):.2f}x")
    print(f"  max DD   : ${m['max_dd']:.4f}")
    print(f"  Sharpe   : {m['sharpe']:.2f}  (0 = not enough data for daily calc)")
    print(f"  avg hold : {m['avg_hold']:.0f} bars (~{m['avg_hold']:.0f} min)")


def save_csv(trades):
    if not trades:
        return
    fname = f"backtest_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    with open(fname, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=trades[0].keys())
        w.writeheader()
        w.writerows(trades)
    print(f"Trade log saved: {fname}")


# ===== SWEEP MODE =====

def run_sweep(coins, bars_by_ticker, days):
    # Testing 0.5%, 1%, 2%, 3%, and 5% moves
    thresholds = [0.005, 0.01, 0.02, 0.03, 0.05]
    print(f"\n{'THRESHOLD SWEEP':^60}")
    print(f"{'threshold':>12}  {'trades':>7}  {'win%':>6}  {'total P&L':>12}  {'max DD':>10}  {'Sharpe':>8}")
    print("-" * 65)
    for t in thresholds:
        all_trades = []
        for asset in coins:
            bars = bars_by_ticker.get(asset["ticker"], [])
            if bars:
                trd, _ = simulate(asset["ticker"], asset["qty"], bars, t)
                all_trades.extend(trd)
        if not all_trades:
            print(f"  {t*100:.3f}%{'':>8}  (no trades)")
            continue
        m = calc_metrics(all_trades, [])
        print(f"  {t*100:.3f}%  {m['n']:>8}  {m['win_rate']:>5.1f}%  ${m['total_pnl']:>+11.4f}  ${m['max_dd']:>9.4f}  {m['sharpe']:>8.2f}")
    print()


# ===== MAIN =====

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days",      type=int,   default=30)
    parser.add_argument("--coin",      type=str,   default=None)
    parser.add_argument("--threshold", type=float, default=0.0005)
    parser.add_argument("--refresh",   action="store_true")
    parser.add_argument("--sweep",     action="store_true", help="Test multiple thresholds")
    args = parser.parse_args()

    coins = PORTFOLIO
    if args.coin:
        coins = [a for a in PORTFOLIO if a["ticker"] == args.coin]
        if not coins:
            print(f"Unknown coin. Options: {[a['ticker'] for a in PORTFOLIO]}")
            sys.exit(1)

    print(f"\n{'='*60}")
    print(f"BACKTEST  {args.days}d  |  threshold {args.threshold*100:.3f}%  |  conf >= {CONFIDENCE_THRESHOLD}")
    print(f"Strategy: rule-based proxy (buy dips / sell rallies, same as AI prompt logic)")
    print(f"{'='*60}\n")

    # Download all data first
    bars_by_ticker = {}
    for asset in coins:
        print(f"[{asset['ticker']}]")
        bars = fetch_bars(asset["ticker"], args.days, args.refresh)
        bars_by_ticker[asset["ticker"]] = bars
        print()

    if args.sweep:
        run_sweep(coins, bars_by_ticker, args.days)
        return

    # Single threshold run
    all_trades = []
    combined_equity = []
    results = []

    for asset in coins:
        ticker, qty = asset["ticker"], asset["qty"]
        bars = bars_by_ticker.get(ticker, [])
        if not bars:
            continue

        trades, equity = simulate(ticker, qty, bars, args.threshold)
        m = calc_metrics(trades, equity)
        all_trades.extend(trades)

        print(f"[{ticker}]")
        print_coin_result(ticker, m)

        if m:
            results.append({"ticker": ticker, **m})
            if not combined_equity:
                combined_equity = list(equity)
            else:
                for i in range(min(len(combined_equity), len(equity))):
                    combined_equity[i] += equity[i]
        print()

    if not results:
        print("No results to show.")
        return

    # Portfolio totals
    total_pnl = sum(r["total_pnl"] for r in results)
    total_n    = sum(r["n"]         for r in results)
    total_wins = sum(r["wins"]      for r in results)
    max_dd     = max(r["max_dd"]    for r in results)
    overall_wr = total_wins / total_n * 100 if total_n else 0

    print("=" * 60)
    print("PORTFOLIO TOTALS")
    print(f"  Total trades : {total_n}")
    print(f"  Win rate     : {overall_wr:.1f}%")
    print(f"  Total P&L    : ${total_pnl:+.4f}")
    print(f"  Max drawdown : ${max_dd:.4f}")

    if len(results) > 1:
        print()
        for r in results:
            print(f"  {r['ticker']:<12} {r['n']:5d} trades  {r['win_rate']:.0f}% win  ${r['total_pnl']:+.4f}")

    if combined_equity:
        print("\nEquity curve (combined running P&L):")
        ascii_curve(combined_equity)

    save_csv(all_trades)


if __name__ == "__main__":
    main()
