# Project Handoff Context

> **Use this when starting a new conversation with any AI assistant.**
> Paste the entire file at the start of the chat so they have full context.

---

## Who I am
- Beginner-intermediate developer
- Estonia-based, trading US markets via Alpaca paper account
- Hardware: Gaming PC with RTX 3060 Ti (8GB VRAM), 32GB RAM, dual SSD + HDD
- Background: ~1 year of software dev classes years ago, refreshing now
- I work on this on a Windows account dedicated to coding

## What I'm building
**An AI-powered crypto day-trading bot** that uses a local LLM (Llama 3.2:3b via Ollama, runs on my GPU) to make trading decisions, executed through Alpaca's paper trading API.

This is a **learning project**. I am NOT trading real money. Don't help me bypass that — keep me on paper-only until I have proven backtest evidence of edge (target: 6+ months out).

GitHub repo: https://github.com/Den-progs/trading-bot (private)

---

## Current architecture

## Stack
- **Python 3.14.4** with virtualenv (`.venv`)
- **VS Code** as IDE
- **Git + GitHub** for version control
- **Alpaca** API for paper trading + crypto market data (free tier)
- **Ollama** for local LLM inference
- **Llama 3.2:3b** as the trading-decision model
- **python-dotenv** for credentials
- **Discord webhooks** for notifications
- **Windows 11** OS

## Files in the project
- `main.py` — the main bot loop (multi-coin, AI decisions, journaling, Discord)
- `notify.py` — Discord webhook helpers (silently fails if Discord is down)
- `cleanup.py` — flattens all positions and cancels open orders
- `analyze.py` — reads trade_journal.json; outputs per-coin stats, confidence bands, best/worst trades
- `backtest.py` — 30-day backtester; downloads 1-min bars, simulates strategy, outputs metrics + equity curve
- `test_ollama.py`, `test_discord.py` — sanity-check scripts
- `.env` — credentials (gitignored): ALPACA_API_KEY, ALPACA_SECRET_KEY, ALPACA_BASE_URL, DISCORD_WEBHOOK_URL
- `.gitignore` — excludes `.env`, `.venv/`, `bot_log_*.txt`, `trade_journal.json`
- `trade_journal.json` — every trade with AI reasoning + P&L (gitignored)
- `bot_log_*.txt` — full play-by-play per run (gitignored)
- `data/` — cached historical bar CSVs for backtester (gitignored)
- `backtest_*.csv` — per-run trade logs from backtester (gitignored)
- `README.md` — public-facing project description
- `ROADMAP.md` — full multi-phase development plan
- `notes.md` — my running observations
- `CONTEXT.md` — this file

## Current bot config
- **Portfolio:** DOGE/USD, AVAX/USD, ETH/USD, SHIB/USD
- **Check interval:** 30 seconds
- **Lookback:** 20 minute-bars
- **Confidence threshold:** 0.3 (aggressive)
- **Max trades per run:** 100 (safety cap)
- **Trade sizes:** ~$50-70 per trade per coin

---

## What's already done (Phase 0 — Foundation)

- [x] Dev environment fully set up (Python, venv, VS Code, Git, GitHub)
- [x] Alpaca paper account integrated (live data, real order placement)
- [x] Local Llama 3.2:3b running via Ollama on RTX 3060 Ti
- [x] Multi-coin trading loop working
- [x] Trade journal with P&L linking BUY → SELL pairs per ticker
- [x] File logging with timestamps
- [x] Discord notifications (startup, BUY, SELL, summaries, shutdown, errors)
- [x] Safety: max trade cap, 3-attempt retry on Ollama, graceful Ctrl+C shutdown
- [x] Clean state script (cleanup.py)
- [x] Wash-trade protection (5s sleep between buy and sell)
- [x] IEX/free-tier compatible data fetching
- [x] GitHub repo with README

## What's done (Phase 1 — Understand What I Built)

- [x] Post-mortem of overnight run (see observations below)
- [x] Built `analyze.py` — reads trade_journal.json, outputs per-coin breakdown, win rate by confidence band, best/worst trades with hold duration
- [x] Built `backtest.py` — 30-day backtester with 1-min bars, data caching, threshold sweep, equity curve, Sharpe

## What's next (Phase 2 — Improve the Edge)

1. **Add spread/fee model to backtester** — results are currently optimistic; real bid/ask spread likely eats most of the small wins
2. **Run longer backtest** — 90+ days to validate edge across more market regimes
3. **Experiment with thresholds** — sweep already built, now interpret results and tune CONFIDENCE_THRESHOLD in main.py
4. **Try a better model** — test `qwen2.5:7b` decisions vs `llama3.2:3b` on same data

---

## How I want to be helped

- **Be direct.** If my idea is bad, say so with reasoning. Don't humor me.
- **Don't enable bad financial decisions.** I will be tempted to: trade real money, increase position sizes, skip backtesting, trade other people's money. Push back hard on all of these.
- **Explain WHY, not just HOW.** I'm trying to learn, not just copy code.
- **Walk me through screen-by-screen** when doing setup/install steps.
- **Watch out for Windows quirks** (PATH issues, file case sensitivity, terminal sessions caching env vars, sleep mode killing long-running processes).
- **Verify with web search** when product details might have changed since training data.
- **Avoid late-night feature creep.** If I'm tinkering at 3 AM, suggest sleep.
- **No giant code dumps** unless I'm replacing a whole file. Prefer "find this, replace with this."
- **Reality-check my P&L expectations.** This bot won't beat the market. Treat profits as luck, losses as expected, learning as the actual goal.

## Things to remember about ME specifically
- I have used both Claude and ChatGPT during this build
- I sometimes paste code from one AI to another — always read what they gave me before running
- Earlier I almost trained ChatGPT-given code that traded REAL prices using FAKE simulated data — be alert for that pattern
- I once accidentally pasted a Discord webhook URL in chat (now rotated) — remind me about secrets if I do it again
- I have free time and want a heavy workload, but pace matters — burnout is real

## Hard rules I've committed to
- Paper trading ONLY until backtest proves edge across 1+ year of data
- No real money, no roommate money, no anyone-else's money
- Every new feature must be backtested before being deployed
- API keys never in code, never in chat, only in `.env`
- Commit to Git after every working chunk

---

## Quick start (when resuming)

```bash
# 1. Open the project
cd "D:\VISUAL CODE PROJECTS\TRADING BOT"

# 2. Activate virtual environment
.venv\Scripts\activate

# 3. Pull latest from GitHub (if working from another machine)
git pull

# 4. Verify Ollama is running and has the model
ollama list  # should show llama3.2:3b

# 5. Clean any stale positions
python cleanup.py

# 6. Run the bot
python main.py
```

---

## Open questions / things I'm curious about

- Does my bot actually make money over weeks of paper trading, or is it noise?
- Would `qwen2.5:7b` make smarter decisions than `llama3.2:3b`?
- Can sentiment from Reddit/news add real edge, or is it always priced in by the time I see it?
- What's the right confidence threshold? 0.3 is aggressive, 0.7 is conservative — backtester will tell me.
- Is there genuine edge anywhere for retail crypto traders, or is this purely educational?

---

**Last updated:** 2026-05-05, after Phase 1 complete

## Strategy ideas in flight (not yet built)

These are good ideas but only get built AFTER backtester exists:
- Chain of Thought prompting (force AI to reason step-by-step before deciding)
- Technical indicators as prompt inputs (compute RSI/MACD/Bollinger in Python, pass values to AI)
- Confidence bucketing analysis (find AI's edge zone)
- Slippage modeling in backtester (realistic costs)

Considered and rejected:
- Two-agent review system — same model = same biases, marginal benefit, use rule-based risk instead

## 2026-05-05 — Overnight run post-mortem

### Observations
1. **Bot ran stable all night** — no crashes, no errors, Discord notified correctly.
   7 closed trades: DOGE×1, AVAX×6, ETH×0, SHIB×0. 100% win rate = too small to mean anything.

2. **AVAX was the only active coin** — 6 round trips while DOGE/ETH/SHIB mostly held.
   Probably because AVAX had more price movement overnight than the others.
   Worth watching: does AVAX consistently move more than the others?

3. **Prices were mostly flat** — the bot made correct HOLD decisions most of the night.
   This is actually good behavior. Bad bots trade constantly regardless of signal.
   The aggressive 0.3 threshold didn't cause a trade storm — the flat prices suppressed it naturally.

### Questions this raises
- At 0.3 confidence threshold, are we leaving money on the table or avoiding bad trades?
- Would the 7 closed trades still be profitable if we subtract real bid/ask spread?
- Why did ETH never close? Was the AI always HOLDing, or did it just never get the right sell signal?

### Next actions
- Build analyze.py to dig into journal data properly
- Build backtester — 7 trades is not enough to know anything
- Close the stray SPY position manually