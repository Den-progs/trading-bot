import os
import csv
import sys
import argparse
import statistics
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Alpaca Stock Data Imports
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.data.enums import DataFeed

load_dotenv()

TICKER_CONFIGS = {
    "NVDA": 0.015,  # 1.5%
    "GLD": 0.015,   # 1.5% (Avoid the 0.5% trap!)
    "USO": 0.03,    # 3.0% (Only buy the big oil crashes)
    "SPY": 0.005    # 0.5% (The reliable earner)
}

# How much to buy of each
QUANTITIES = {
    "NVDA": 10,
    "GLD": 5,
    "USO": 10,
    "SPY": 1
}

LOOKBACK_BARS = 60 
DATA_DIR = "data_stocks"
# ===== CONFIGURATION END =====
# ===== DATA FETCHING (IEX COMPATIBLE) =====

def fetch_stock_bars(ticker, days, refresh=False):
    os.makedirs(DATA_DIR, exist_ok=True)
    cache = os.path.join(DATA_DIR, f"{ticker}_{days}d.csv")

    if not refresh and os.path.exists(cache):
        rows = []
        with open(cache, newline="") as f:
            for row in csv.DictReader(f):
                rows.append({"timestamp": row["timestamp"], "close": float(row["close"])})
        print(f"  {len(rows):,} bars from cache.")
        return rows

    print(f"  Downloading {days}d of {ticker} from IEX (Free Tier)...")
    client = StockHistoricalDataClient(os.getenv("ALPACA_API_KEY"), os.getenv("ALPACA_SECRET_KEY"))
    
    request_params = StockBarsRequest(
        symbol_or_symbols=ticker,
        timeframe=TimeFrame.Minute,
        start=datetime.now() - timedelta(days=days),
        end=datetime.now(),
        feed=DataFeed.IEX  # CRITICAL: Bypasses SIP error
    )

    try:
        result = client.get_stock_bars(request_params)
        if not result.data.get(ticker):
            return []
        
        rows = [{"timestamp": str(b.timestamp), "close": float(b.close)} for b in result.data[ticker]]
        
        with open(cache, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["timestamp", "close"])
            w.writeheader()
            w.writerows(rows)
        return rows
    except Exception as e:
        print(f"  Error: {e}")
        return []

# ===== STRATEGY & SIMULATION (Same as your Core Logic) =====

def decide(prices, has_position, threshold):
    if len(prices) < 2: return "HOLD"
    change = (prices[-1] - prices[0]) / prices[0]
    
    if not has_position and change <= -threshold:
        return "BUY"
    if has_position and change >= threshold:
        return "SELL"
    return "HOLD"

def simulate(ticker, qty, bars, threshold):
    position = None
    trades = []
    equity = []
    running_pnl = 0.0
    SLIPPAGE = 0.001 # 0.1% fee/spread penalty

    for i in range(LOOKBACK_BARS, len(bars)):
        price = bars[i]["close"]
        action = decide([b["close"] for b in bars[i-LOOKBACK_BARS:i+1]], position is not None, threshold)

        if action == "BUY" and position is None:
            # Buy with slippage penalty
            buy_price = price * (1 + SLIPPAGE)
            position = {"price": buy_price, "idx": i}

        elif action == "SELL" and position is not None:
            # Sell with slippage penalty
            sell_price = price * (1 - SLIPPAGE)
            pnl = (sell_price - position["price"]) * qty
            trades.append({"ticker": ticker, "pnl": pnl})
            running_pnl += pnl
            position = None
        
        unrealized = (price - position["price"]) * qty if position else 0
        equity.append(running_pnl + unrealized)

    return trades, equity

# 1. First, define the function so Python knows it exists
def run_sweep(ticker):
    print(f"\n--- THRESHOLD SWEEP: {ticker} ---")
    bars = fetch_stock_bars(ticker, 30)
    if not bars: 
        print("No data found.")
        return

    # Test thresholds from 0.5% to 3%
    thresholds = [0.005, 0.01, 0.015, 0.02, 0.03]
    
    print(f"{'Threshold':<12} {'Trades':<8} {'Total P&L':<15}")
    print("-" * 35)
    for t in thresholds:
        # --- CHANGE THIS LINE BELOW ---
        qty = QUANTITIES.get(ticker, 1) # Get the quantity for this specific ticker
        trades, _ = simulate(ticker, qty, bars, t) # Pass 'qty' instead of '1'
        # ------------------------------
        
        pnl = sum(tr['pnl'] for tr in trades)
        print(f"{t*100:>8.1f}% {len(trades):>8}    ${pnl:>10.2f}")

# 2. Second, define the main execution logic
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--coin", type=str, default="NVDA")
    parser.add_argument("--threshold", type=float, default=0.03)
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--sweep", action="store_true") 
    
    args = parser.parse_args()

    if args.sweep:
        run_sweep(args.coin) # Now Python knows what this is!
    else:
        print(f"\nSTOCK BACKTEST | {args.days} Days | Threshold: {args.threshold*100}%")
        print("-" * 50)
        bars = fetch_stock_bars(args.coin, args.days)
        if bars:
            trades, equity = simulate(args.coin, 1, bars, args.threshold)
            pnl = sum(t["pnl"] for t in trades)
            print(f"{args.coin}: {len(trades)} trades | Total P&L: ${pnl:+.2f}")

# 3. Last, trigger the main function
if __name__ == "__main__":
    main()