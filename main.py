import os
import sys
import time
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv
import ollama
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.data.historical import CryptoHistoricalDataClient
from alpaca.data.requests import CryptoLatestQuoteRequest, CryptoBarsRequest
from alpaca.data.timeframe import TimeFrame

# ===== CONFIG =====
TICKER = "DOGE/USD"
CHECK_INTERVAL = 15
QUANTITY = 200
LOOKBACK_BARS = 20
OLLAMA_MODEL = "llama3.2:3b"
MAX_TRADES_PER_RUN = 50
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

log_filename = f"bot_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
log_file = open(log_filename, "w", encoding="utf-8")
sys.stdout = Tee(sys.stdout, log_file)


def log(msg):
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {msg}")


# ===== TRADE JOURNAL =====
def load_journal():
    """Load existing journal or return empty list."""
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
    """Add a trade entry to the journal."""
    journal = load_journal()
    entry = {
        "timestamp": datetime.now().isoformat(),
        "action": action,
        "ticker": ticker,
        "price": price,
        "qty": qty,
        "ai_confidence": confidence,
        "ai_reason": reason,
        "pnl": None,        # filled in when position closes
        "linked_buy_index": None  # index of the BUY this SELL closes
    }

    # If this is a SELL, link it to the most recent open BUY and calculate P&L
    if action == "SELL":
        for i in range(len(journal) - 1, -1, -1):
            if journal[i]["action"] == "BUY" and journal[i]["pnl"] is None and journal[i]["ticker"] == ticker:
                buy_price = journal[i]["price"]
                buy_qty = journal[i]["qty"]
                pnl = (price - buy_price) * buy_qty
                entry["pnl"] = round(pnl, 4)
                entry["linked_buy_index"] = i
                # Mark the BUY as closed too (with the same pnl, for easier stats)
                journal[i]["pnl"] = round(pnl, 4)
                break

    journal.append(entry)
    save_journal(journal)
    return entry


def get_journal_stats():
    """Return a summary of bot performance from the journal."""
    journal = load_journal()
    closed_trades = [t for t in journal if t["action"] == "SELL" and t["pnl"] is not None]

    if not closed_trades:
        return "No completed trades yet."

    total_pnl = sum(t["pnl"] for t in closed_trades)
    wins = [t for t in closed_trades if t["pnl"] > 0]
    losses = [t for t in closed_trades if t["pnl"] < 0]
    win_rate = len(wins) / len(closed_trades) * 100 if closed_trades else 0

    last5 = closed_trades[-5:]
    last5_pnl = ", ".join(f"{t['pnl']:+.2f}" for t in last5)

    return (f"Trades: {len(closed_trades)} | "
            f"Win rate: {win_rate:.0f}% | "
            f"Total P&L: ${total_pnl:+.2f} | "
            f"Last 5: [{last5_pnl}]")


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

    return [round(float(bar.close), 4) for bar in bars.data[ticker][-num_bars:]]


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
    log(f"BUY executed: {qty} {ticker} at ~${price}")


def sell_all(ticker, price, confidence, reason):
    trading_client.close_position(ticker.replace("/", ""))
    entry = record_trade("SELL", ticker, price, QUANTITY, confidence, reason)
    pnl_str = f" (P&L: ${entry['pnl']:+.2f})" if entry["pnl"] is not None else ""
    log(f"SELL executed: {ticker} at ~${price}{pnl_str}")


# ===== MAIN LOOP =====
log(f"Local AI bot starting for {TICKER} using {OLLAMA_MODEL}")
log(f"Checking every {CHECK_INTERVAL}s. Max {MAX_TRADES_PER_RUN} trades. Logging to {log_filename}")
log(f"Journal: {get_journal_stats()}")

trades_today = 0

try:
    while True:
        try:
            prices = get_recent_prices(TICKER, LOOKBACK_BARS)
            if not prices:
                log("No recent price data — skipping iteration.")
                time.sleep(CHECK_INTERVAL)
                continue

            current_price = get_current_price(TICKER, fallback_prices=prices)
            owns = have_position(TICKER)

            log(f"Asking AI... price=${current_price}, holding={owns}, trades_done={trades_today}/{MAX_TRADES_PER_RUN}")
            decision = ask_ai_for_decision(TICKER, prices, current_price, owns)

            action = decision.get("action", "HOLD")
            confidence = decision.get("confidence", 0.0)
            reason = decision.get("reason", "(no reason given)")
            log(f"AI: {action} ({confidence}) — {reason}")

            if trades_today >= MAX_TRADES_PER_RUN:
                log(f"Trade cap reached. Holding only.")
            elif action == "BUY" and not owns and confidence >= CONFIDENCE_THRESHOLD:
                buy(TICKER, QUANTITY, current_price, confidence, reason)
                trades_today += 1
                time.sleep(5)
            elif action == "SELL" and owns and confidence >= CONFIDENCE_THRESHOLD:
                sell_all(TICKER, current_price, confidence, reason)
                trades_today += 1
                time.sleep(5)
                log(f"  └─ {get_journal_stats()}")  # show stats after each closed trade
            else:
                log("No action taken.")

        except Exception as e:
            log(f"Loop error: {e}")

        time.sleep(CHECK_INTERVAL)

except KeyboardInterrupt:
    log("Bot stopped by user.")
    log(f"Final stats: {get_journal_stats()}")