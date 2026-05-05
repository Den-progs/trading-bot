import os
import time
from datetime import datetime
from dotenv import load_dotenv
from alpaca.trading.client import TradingClient
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.data.enums import DataFeed

# Load centralized .env
load_dotenv()

# Configuration
TICKERS = ["GLD", "USO", "NVDA", "SPY"] # Gold, Oil, Tech, S&P 500
THRESHOLD = 0.03  # 3% Sniper Rule
TRADE_QTY = 1     # Start small for testing

# Clients
trading_client = TradingClient(os.getenv("ALPACA_API_KEY"), os.getenv("ALPACA_SECRET_KEY"), paper=True)
data_client = StockHistoricalDataClient(os.getenv("ALPACA_API_KEY"), os.getenv("ALPACA_SECRET_KEY"))

def check_for_snipes():
    for ticker in TICKERS:
        # Request IEX data (Free Tier compatible)
        request_params = StockBarsRequest(
            symbol_or_symbols=ticker,
            timeframe=TimeFrame.Minute,
            limit=60, # Look at the last hour
            feed=DataFeed.IEX 
        )
        
        bars = data_client.get_stock_bars(request_params)
        if not bars.data.get(ticker): continue

        prices = [b.close for b in bars.data[ticker]]
        price_now = prices[-1]
        price_start = prices[0]
        change = (price_now - price_start) / price_start

        print(f"[{ticker}] Change: {change:.2%}")

        if change <= -THRESHOLD:
            print(f"!!! SNIPE TRIGGERED: Buying {ticker} at {price_now}")
            # Insert execution logic here (similar to your main.py)

while True:
    try:
        clock = trading_client.get_clock()
        if clock.is_open:
            check_for_snipes()
            time.sleep(600) # Check every 10 mins (matches IEX delay)
        else:
            # Sleep until next market open
            time_to_wait = (clock.next_open - clock.timestamp).total_seconds()
            print(f"Market closed. Sleeping {int(time_to_wait // 3600)} hours.")
            time.sleep(time_to_wait)
    except Exception as e:
        print(f"Error: {e}")
        time.sleep(60)