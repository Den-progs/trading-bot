import os
from dotenv import load_dotenv
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from datetime import datetime, timedelta
from alpaca.data.enums import DataFeed

load_dotenv()

client = StockHistoricalDataClient(
    os.getenv("ALPACA_API_KEY"),
    os.getenv("ALPACA_SECRET_KEY")
)

request = StockBarsRequest(
    symbol_or_symbols="AAPL",
    timeframe=TimeFrame.Minute,
    start=datetime.now() - timedelta(days=1),
    end=datetime.now(),
    feed=DataFeed.IEX
)

bars = client.get_stock_bars(request)

print(bars)