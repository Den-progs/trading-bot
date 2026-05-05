# AI Crypto Trading Bot

A crypto day-trading bot that uses a local LLM (Ollama / Llama 3.2:3b) to make trading decisions, executed through Alpaca's paper trading API. Built as a learning project — **paper money only**.

## Stack

- **Python 3.14**
- **Alpaca** — paper trading + crypto market data
- **Ollama** — local LLM inference (Llama 3.2:3b, runs on GPU)
- **Discord webhooks** — trade notifications
- **python-dotenv** — credentials management

## How it works

1. Every 30 seconds, fetch the last 20 minute-bars of price data for each coin
2. Send prices to local Llama 3.2:3b with a structured prompt asking BUY / SELL / HOLD + confidence
3. If confidence exceeds threshold, place a market order via Alpaca
4. Log every trade to a journal with P&L tracking and send a Discord notification

## Scripts

| Script | Purpose |
|---|---|
| `main.py` | Main trading loop — runs continuously |
| `cleanup.py` | Flatten all positions and cancel open orders |
| `analyze.py` | Post-mortem analysis of `trade_journal.json` |
| `backtest.py` | 30-day backtester with data caching and threshold sweep |

## Running

```bash
python -m venv .venv
.venv\Scripts\activate
pip install alpaca-py ollama python-dotenv requests
# Copy .env.example to .env and fill in your keys
python main.py
```

## Backtesting

```bash
python backtest.py              # 30 days, all coins
python backtest.py --days 7     # 7 days
python backtest.py --coin AVAX/USD
python backtest.py --sweep      # compare 5 thresholds side by side
```

Data is cached to `data/` after the first download, so subsequent runs are instant.

## Configuration

All knobs are at the top of `main.py`:

| Setting | Default | Description |
|---|---|---|
| `PORTFOLIO` | 4 coins | Tickers and quantities per trade |
| `CHECK_INTERVAL` | 30s | Seconds between AI decisions |
| `OLLAMA_MODEL` | `llama3.2:3b` | Local model to use |
| `LOOKBACK_BARS` | 20 | Minutes of history sent to AI |
| `CONFIDENCE_THRESHOLD` | 0.3 | Minimum AI confidence to act |
| `MAX_TRADES_PER_RUN` | 100 | Safety cap per session |

## Required `.env` keys

```
ALPACA_API_KEY=...
ALPACA_SECRET_KEY=...
ALPACA_BASE_URL=https://paper-api.alpaca.markets
DISCORD_WEBHOOK_URL=...
```

## Disclaimer

This is a learning project. Paper trading only. Do not run with real money.
