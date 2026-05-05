import os
from dotenv import load_dotenv
load_dotenv()  # must load env BEFORE importing notify

import notify

notify.notify_startup(
    portfolio=[{"ticker": "TEST/USD"}],
    model="test-model",
    interval=30,
    max_trades=10
)
print("Sent test message — check your Discord channel!")