import os
from dotenv import load_dotenv
from alpaca.trading.client import TradingClient
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestQuoteRequest

# Load API keys from .env file
load_dotenv()
API_KEY = os.getenv("ALPACA_API_KEY")
SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")

# Connect to Alpaca (paper=True means fake-money mode)
trading_client = TradingClient(API_KEY, SECRET_KEY, paper=True)
data_client = StockHistoricalDataClient(API_KEY, SECRET_KEY)

# 1. Check account info
account = trading_client.get_account()
print(f"Account status: {account.status}")
print(f"Buying power: ${account.buying_power}")
print(f"Cash: ${account.cash}")
print(f"Portfolio value: ${account.portfolio_value}")
print("-" * 40)

# 2. Fetch latest quote for a ticker
ticker = "AAPL"
request = StockLatestQuoteRequest(symbol_or_symbols=ticker)
quote = data_client.get_stock_latest_quote(request)

print(f"{ticker} latest quote:")
print(f"  Bid price: ${quote[ticker].bid_price}")
print(f"  Ask price: ${quote[ticker].ask_price}")
print(f"  Timestamp: {quote[ticker].timestamp}")