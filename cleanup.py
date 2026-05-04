import os
from dotenv import load_dotenv
from alpaca.trading.client import TradingClient

load_dotenv()
trading_client = TradingClient(
    os.getenv("ALPACA_API_KEY"),
    os.getenv("ALPACA_SECRET_KEY"),
    paper=True
)

trading_client.cancel_orders()
print("All open orders cancelled")

trading_client.close_all_positions(cancel_orders=True)
print("All positions closed")