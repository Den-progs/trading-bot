import os
import sys
import time
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables BEFORE importing anything that uses them
load_dotenv()

import ollama
import notify
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.data.historical import CryptoHistoricalDataClient
from alpaca.data.requests import CryptoLatestQuoteRequest, CryptoBarsRequest
from alpaca.data.timeframe import TimeFrame

# ===== CONFIG =====
# Each entry: ticker, quantity per trade
PORTFOLIO = [
    {"ticker": "DOGE/USD", "qty": 200},   # ~$60/trade
    {"ticker": "AVAX/USD", "qty": 2},     # ~$20/trade
    {"ticker": "ETH/USD",  "qty": 0.02},  # ~$70/trade
    {"ticker": "SHIB/USD", "qty": 5000000},  # ~$70/trade (SHIB is tiny)
]

CHECK_INTERVAL = 30          # seconds between full portfolio loops
LOOKBACK_BARS = 20
OLLAMA_MODEL = "llama3.2:3b"
MAX_TRADES_PER_RUN = 100     # higher cap since we have multiple coins
JOURNAL_FILE = "trade_journal.json"
CONFIDENCE_THRESHOLD = 0.3
# ==================

load_dotenv()

trading_client = TradingClient(
    os.getenv("ALPACA_API_KEY"),
    os.getenv("ALPACA_SECRET_KEY"),
    paper=True
)
data_client = CryptoHistoricalDataClient()


# ===== FILE LOGGING =====
class Tee:
    def __init__(self, *files):
        self.files = files
    def write(self, obj):
        for f in self.files:
            f.write(obj)
            f.flush()
    def flush(self):
        for f in self.files:
            f.flush()

os.makedirs("logs", exist_ok=True)
log_filename = f"logs/bot_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
log_file = open(log_filename, "w", encoding="utf-8")
sys.stdout = Tee(sys.stdout, log_file)


def log(msg):
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {msg}")


# ===== TRADE JOURNAL =====
def load_journal():
    if not os.path.exists(JOURNAL_FILE):
        return []
    try:
        with open(JOURNAL_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return []


def save_journal(journal):
    with open(JOURNAL_FILE, "w") as f:
        json.dump(journal, f, indent=2)


def record_trade(action, ticker, price, qty, confidence, reason):
    journal = load_journal()
    entry = {
        "timestamp": datetime.now().isoformat(),
        "action": action,
        "ticker": ticker,
        "price": price,
        "qty": qty,
        "ai_confidence": confidence,
        "ai_reason": reason,
        "pnl": None,
        "linked_buy_index": None
    }

    if action == "SELL":
        # Find the most recent open BUY for THIS ticker specifically
        for i in range(len(journal) - 1, -1, -1):
            if (journal[i]["action"] == "BUY"
                    and journal[i]["pnl"] is None
                    and journal[i]["ticker"] == ticker):
                buy_price = journal[i]["price"]
                buy_qty = journal[i]["qty"]
                pnl = (price - buy_price) * buy_qty
                entry["pnl"] = round(pnl, 4)
                entry["linked_buy_index"] = i
                journal[i]["pnl"] = round(pnl, 4)
                break

    journal.append(entry)
    save_journal(journal)
    return entry


def get_journal_stats(ticker=None):
    """Stats for one ticker (if specified) or for everything."""
    journal = load_journal()
    closed = [t for t in journal
              if t["action"] == "SELL" and t["pnl"] is not None
              and (ticker is None or t["ticker"] == ticker)]

    if not closed:
        return "no closed trades"

    total_pnl = sum(t["pnl"] for t in closed)
    wins = [t for t in closed if t["pnl"] > 0]
    win_rate = len(wins) / len(closed) * 100

    return f"{len(closed)} trades, win {win_rate:.0f}%, P&L ${total_pnl:+.2f}"


def get_portfolio_summary():
    """Multi-line summary of stats per coin + total."""
    lines = ["Portfolio summary:"]
    for asset in PORTFOLIO:
        lines.append(f"  {asset['ticker']}: {get_journal_stats(asset['ticker'])}")
    lines.append(f"  TOTAL: {get_journal_stats()}")
    return "\n".join(lines)


# ===== MARKET DATA =====
def get_current_price(ticker, fallback_prices=None):
    request = CryptoLatestQuoteRequest(symbol_or_symbols=ticker)
    quote = data_client.get_crypto_latest_quote(request)
    price = float(quote[ticker].ask_price)
    if price == 0.0 and fallback_prices:
        price = fallback_prices[-1]
    return price


def get_recent_prices(ticker, num_bars=20):
    end = datetime.now()
    start = end - timedelta(hours=4)

    request = CryptoBarsRequest(
        symbol_or_symbols=ticker,
        timeframe=TimeFrame.Minute,
        start=start,
        end=end
    )
    bars = data_client.get_crypto_bars(request)

    if ticker not in bars.data or len(bars.data[ticker]) == 0:
        return []

    return [round(float(bar.close), 6) for bar in bars.data[ticker][-num_bars:]]


def have_position(ticker):
    try:
        position = trading_client.get_open_position(ticker.replace("/", ""))
        return float(position.qty) > 0
    except Exception:
        return False


# ===== AI DECISION =====
def ask_ai_for_decision(ticker, prices, current_price, owns_position):
    position_status = "YES" if owns_position else "NO"
    prompt = f"""You are an active crypto day trader analyzing {ticker}.

Recent minute-bar closing prices (oldest to newest):
{prices}

Current price: ${current_price}
Currently holding position: {position_status}

Respond with ONLY a JSON object in this exact format, no markdown, no extra text:
{{"action":"BUY|SELL|HOLD","confidence":0.0,"reason":"short explanation"}}

Rules:
- If not holding: only BUY or HOLD allowed
- If holding: only SELL or HOLD allowed
- Day traders look for SMALL moves. A 0.05% drop is potentially a buying opportunity. A 0.05% rise from your buy could be worth taking.
- Be willing to act on weak signals — confidence around 0.5-0.7 is normal for active trading
- Only HOLD when the price is literally flat (no change at all) for many bars"""

    for attempt in range(3):
        try:
            response = ollama.chat(
                model=OLLAMA_MODEL,
                messages=[{"role": "user", "content": prompt}],
                format="json"
            )
            text = response.message.content.strip()
            return json.loads(text)
        except Exception as e:
            log(f"Ollama attempt {attempt + 1}/3 failed: {e}")
            time.sleep(2)

    return {"action": "HOLD", "confidence": 0.0, "reason": "AI unavailable"}


# ===== TRADING ACTIONS =====
def buy(ticker, qty, price, confidence, reason):
    order = MarketOrderRequest(
        symbol=ticker, qty=qty, side=OrderSide.BUY, time_in_force=TimeInForce.GTC
    )
    trading_client.submit_order(order_data=order)
    record_trade("BUY", ticker, price, qty, confidence, reason)
    log(f"  BUY: {qty} {ticker} at ~${price}")
    notify.notify_buy(ticker, qty, price, confidence, reason)


def sell_all(ticker, qty, price, confidence, reason):
    trading_client.close_position(ticker.replace("/", ""))
    entry = record_trade("SELL", ticker, price, qty, confidence, reason)
    pnl = entry["pnl"]
    pnl_str = f" (P&L: ${pnl:+.2f})" if pnl is not None else ""
    log(f"  SELL: {ticker} at ~${price}{pnl_str}")
    notify.notify_sell(ticker, price, pnl, confidence, reason)


# ===== PROCESS ONE COIN =====
def process_coin(asset, trades_done):
    """Run one full decision cycle for one coin. Returns 1 if a trade was placed, else 0."""
    ticker = asset["ticker"]
    qty = asset["qty"]

    try:
        prices = get_recent_prices(ticker, LOOKBACK_BARS)
        if not prices:
            log(f"[{ticker}] No price data — skip")
            return 0

        current_price = get_current_price(ticker, fallback_prices=prices)
        owns = have_position(ticker)

        log(f"[{ticker}] price=${current_price}, holding={owns}")
        decision = ask_ai_for_decision(ticker, prices, current_price, owns)

        action = decision.get("action", "HOLD")
        confidence = decision.get("confidence", 0.0)
        reason = decision.get("reason", "(no reason given)")
        log(f"[{ticker}] AI: {action} ({confidence}) — {reason}")

        if trades_done >= MAX_TRADES_PER_RUN:
            log(f"[{ticker}] Trade cap reached — holding only")
            return 0

        if action == "BUY" and not owns and confidence >= CONFIDENCE_THRESHOLD:
            buy(ticker, qty, current_price, confidence, reason)
            return 1
        elif action == "SELL" and owns and confidence >= CONFIDENCE_THRESHOLD:
            sell_all(ticker, qty, current_price, confidence, reason)
            return 1

    except Exception as e:
        log(f"[{ticker}] Error: {e}")

    return 0


# ===== MAIN LOOP =====
log(f"Multi-coin AI bot starting. Portfolio: {[a['ticker'] for a in PORTFOLIO]}")
log(f"Model: {OLLAMA_MODEL} | Interval: {CHECK_INTERVAL}s | Max trades: {MAX_TRADES_PER_RUN}")
log(f"Logging to {log_filename}")
print(get_portfolio_summary())
notify.notify_startup(PORTFOLIO, OLLAMA_MODEL, CHECK_INTERVAL, MAX_TRADES_PER_RUN)

trades_today = 0

try:
    while True:
        log("=" * 60)
        log(f"New cycle. Total trades so far: {trades_today}/{MAX_TRADES_PER_RUN}")

        for asset in PORTFOLIO:
            trades_today += process_coin(asset, trades_today)
            time.sleep(2)  # small breather between coins so we don't hammer APIs

        # End-of-cycle summary every 5 cycles
        if trades_today > 0 and trades_today % 5 == 0:
            print(get_portfolio_summary())

        time.sleep(CHECK_INTERVAL)

except KeyboardInterrupt:
    log("=" * 60)
    log("Bot stopped by user.")
    summary = get_portfolio_summary()
    print(summary)
    notify.notify_shutdown(summary)