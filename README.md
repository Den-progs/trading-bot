# AI Trading Bot

A crypto day-trading bot that uses a local LLM (Ollama / Llama 3.2) to make trading decisions, with paper-money execution through Alpaca.

## Stack

- **Python 3.14**
- **Alpaca** — paper trading + market data
- **Ollama** — local LLM inference (Llama 3.2:3b)
- **python-dotenv** — credentials management

## How it works

1. Every N seconds, fetch the last 20 minute-bars of price data
2. Send to local Llama 3.2 with a structured prompt asking BUY / SELL / HOLD
3. If confidence is above threshold, place a market order via Alpaca
4. Log every trade to a journal with P&L tracking

## Running

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
# Add your API keys to .env (see .env.example)
python main.py
```

## Configuration

All knobs are at the top of `main.py`:
- `TICKER` — what to trade (e.g. `DOGE/USD`)
- `CHECK_INTERVAL` — seconds between AI decisions
- `QUANTITY` — how many units per trade
- `OLLAMA_MODEL` — which local model to use
- `MAX_TRADES_PER_RUN` — safety cap
- `CONFIDENCE_THRESHOLD` — minimum AI confidence to act

## Disclaimer

This is a learning project. The strategy is intentionally simple and is not profitable. Do not run with real money.