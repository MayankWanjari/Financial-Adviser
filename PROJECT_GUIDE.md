# Financial Advisor AI — Complete Project Guide

> A personal AI-powered research assistant for Indian stock market investing.
> Built by a solo developer. Budget: ₹0. Stack: Python + Gemini + Streamlit.

---

## Table of Contents

1. [What This Project Does](#1-what-this-project-does)
2. [How to Run It](#2-how-to-run-it)
3. [Architecture Overview](#3-architecture-overview)
4. [How a Single Chat Message Works (End-to-End)](#4-how-a-single-chat-message-works-end-to-end)
5. [Every File Explained](#5-every-file-explained)
6. [Every Tool the Agent Can Use](#6-every-tool-the-agent-can-use)
7. [The Scoring System (0–100)](#7-the-scoring-system-0100)
8. [Caching System](#8-caching-system)
9. [Configuration Files](#9-configuration-files)
10. [Data Sources](#10-data-sources)
11. [Limitations and Known Issues](#11-limitations-and-known-issues)
12. [Project History and Phases](#12-project-history-and-phases)

---

## 1. What This Project Does

This is a conversational AI assistant for Indian equity research. You open a chat window in your browser, type a question in Hindi or English, and the AI:

- Fetches **live stock data** (price, PE ratio, ROE, debt, etc.) from Yahoo Finance
- Reads **today's market news** from Indian RSS feeds and summarizes it using AI
- Estimates **intrinsic value** using Benjamin Graham's formula and PE-based models
- Scores stocks **0–100** on six fundamental criteria to surface value opportunities
- Tracks a **personal portfolio** with live P&L
- Shows **technical indicators** (moving averages, RSI, golden/death cross)
- Compares a stock with its **sector peers**
- Shows **historical PE bands** (is the stock cheap or expensive vs its own history?)
- Shows **dividend history** (how consistently does a company pay and grow dividends?)

**What it is NOT:** A trading bot. A stock tipster. A SEBI-registered advisor. Every response ends with a disclaimer: the user makes all decisions.

---

## 2. How to Run It

```bash
# 1. Clone and enter the project
cd financial-advisor-ai

# 2. Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate         # Windows
# source .venv/bin/activate    # Mac/Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set your Gemini API key
# Create a .env file in the project root:
# GEMINI_API_KEY=your_key_here
# Get a free key at: https://aistudio.google.com/app/apikey

# 5. Launch the app
streamlit run app.py
```

The browser opens at `http://localhost:8501`. Type any question in the chat box.

---

## 3. Architecture Overview

```
Browser (Streamlit Chat UI)
         │
         │  User types: "RELIANCE ka PE kya hai?"
         ▼
┌─────────────────────────────────────────────────────────┐
│  app.py  (Streamlit UI layer)                            │
│  - Renders chat messages                                 │
│  - Calls agent.chat(user_message, history)               │
│  - Renders Plotly price chart for single-stock queries   │
│  - Saves/loads session from disk                         │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│  agent/brain.py  (FinancialAgent class)                  │
│  - Holds a Gemini 2.5 Flash model instance               │
│  - Sends user message to Gemini                          │
│  - Loops: Gemini calls tools → we run them → send back   │
│  - Returns final text answer + updated history           │
└──────────────────────┬──────────────────────────────────┘
                       │
          ┌────────────┴────────────┐
          │                         │
          ▼                         ▼
┌──────────────────┐    ┌──────────────────────────────────┐
│  agent/tools.py  │    │  agent/dispatch.py               │
│  (declarations)  │    │  (executes each tool call)       │
│  - Tells Gemini  │    │  - Routes function_call.name     │
│    what tools    │    │    to the right data/ function   │
│    exist + their │    │  - Returns raw dict result       │
│    parameters    │    │    back to Gemini                │
└──────────────────┘    └──────────────────┬───────────────┘
                                           │
          ┌────────────────────────────────┤
          │                                │
          ▼                                ▼
┌──────────────────────┐    ┌──────────────────────────────┐
│  data/ modules       │    │  config/ files               │
│  (pure data funcs)   │    │  watchlist.txt               │
│  stock_data.py       │    │  feeds.json                  │
│  news_fetcher.py     │    │  nifty50.txt                 │
│  news_analyzer.py    │    │  midcap150.txt               │
│  screener.py         │    │  sector_peers.json           │
│  valuation.py        │    │  portfolio.json              │
│  scorer.py           │    │  scoring.json                │
│  pe_bands.py         │    └──────────────────────────────┘
│  technicals.py       │
│  peers.py            │
│  dividends.py        │
│  portfolio.py        │
│  cache.py            │
│  session.py          │
└──────────────────────┘
          │
          ▼
   Yahoo Finance (yfinance)
   Indian RSS Feeds (feedparser)
   Gemini API (news analysis)
```

---

## 4. How a Single Chat Message Works (End-to-End)

Let's trace `"RELIANCE ka PE kya hai?"` through the whole system:

**Step 1 — User types in Streamlit**
`app.py` captures the text from `st.chat_input()` and calls:
```python
response_text, updated_history = agent.chat("RELIANCE ka PE kya hai?", history)
```

**Step 2 — Gemini reads the message**
`brain.py` creates a Gemini chat session seeded with the conversation history, then sends the message. Gemini reads the question and the tool descriptions in `agent/tools.py` and decides: *"I should call `get_stock_snapshot` with ticker=RELIANCE."*

**Step 3 — Tool dispatch**
`brain.py` sees a `function_call` in the Gemini response. It calls `dispatch.handle_tool_call(function_call, agent)`, which routes to `data/stock_data.get_stock_snapshot("RELIANCE")`.

**Step 4 — Data fetch**
`stock_data.py` checks the cache first. If no fresh data exists, it calls `yf.Ticker("RELIANCE.NS").info` (Yahoo Finance API). It extracts price, PE, ROE, D/E, margins, market cap, etc. and returns a dict. The result is stored in the cache for 15 minutes.

**Step 5 — Result sent back to Gemini**
`brain.py` wraps the dict in a `FunctionResponse` object and sends it back to Gemini in the same chat session.

**Step 6 — Gemini formats the answer**
Gemini reads the raw data dict (numbers, metrics) and formats a natural-language response according to the system prompt rules in `agent/prompts.py`. It writes a markdown table with PE, ROE, etc., explains what each metric means, and appends the disclaimer line.

**Step 7 — Render in browser**
`app.py` receives the text and calls `st.markdown(response_text)`. Because `agent.last_chart_ticker` was set to "RELIANCE" during the tool call, `app.py` also renders a 1-month Plotly price chart below the text.

**Step 8 — Session saved**
`app.py` appends the turn to `session_state.messages` and calls `data/session.save_session()` to persist the conversation to disk, so it survives a page refresh.

---

## 5. Every File Explained

### Entry Point

| File | What it does |
|------|--------------|
| `app.py` | The entire Streamlit UI. Initializes the agent once per browser session. Renders the chat, sidebar watchlist, and price chart. Saves conversation to disk after each turn. |

### Agent Layer (`agent/`)

| File | What it does |
|------|--------------|
| `agent/brain.py` | `FinancialAgent` class. Holds the Gemini model. Runs the function-calling loop (send message → execute tools → send results → repeat until text answer). Has retry logic (exponential backoff) for 503/timeout errors. Handles quota/network errors with friendly Hinglish messages. |
| `agent/tools.py` | Gemini `FunctionDeclaration` objects — the schema that tells Gemini what tools exist, what each does, and what parameters each takes. Gemini reads these descriptions to decide which tool to call. |
| `agent/dispatch.py` | The router. When Gemini calls a tool by name (e.g. `"get_stock_snapshot"`), this file maps it to the correct Python function in `data/`. Also contains `_make_json_safe()` to serialize datetimes and other non-JSON types. |
| `agent/prompts.py` | The system prompt — 300 lines of instructions that define the agent's personality, language rules, data rules, output formatting templates (tables, PE bands, scoring, portfolio), and the investing philosophy. Edit this to change how the agent speaks or formats responses. |

### Data Layer (`data/`)

All `data/` modules are **pure functions** — they take arguments, return dicts/lists, and never print or call `sys.exit()`. The agent formats and displays the returned data.

| File | What it does |
|------|--------------|
| `data/stock_data.py` | Core stock fetching via yfinance. `get_stock_snapshot(ticker)` fetches all fundamental fields for one stock. `get_multiple_stocks(tickers)` batches multiple tickers. Number formatting helpers (`fmt_crore`, `fmt_price`, `fmt_pct`, etc.). Cache-aware — uses 15-min TTL. |
| `data/news_fetcher.py` | Fetches headlines from Indian RSS feeds defined in `config/feeds.json`. Deduplicates similar headlines (75% similarity threshold). Tags articles to watchlist stocks. Returns a list of article dicts. |
| `data/news_analyzer.py` | Sends the fetched headlines to Gemini and asks it to produce a structured markdown briefing: top stories, sector impacts, FII/DII flows, global context, watchlist mentions. Returns the briefing as a string. Cache-aware — same briefing for the whole day. |
| `data/screener.py` | Scans Nifty 50 / Midcap 150 tickers and filters by PE, ROE, D/E, market cap, sector. Takes 1–5 minutes depending on universe size. Supports `universe` parameter: `"nifty50"`, `"midcap150"`, or `"both"`. |
| `data/valuation.py` | Three valuation models: `graham_number(eps, bv)` (Benjamin Graham's √(22.5 × EPS × BV) formula), `margin_of_safety(price, intrinsic)` (% gap), `pe_valuation(pe, eps, benchmark_pe)` (fair value by PE). `valuation_summary(ticker)` pulls it all together with live data. |
| `data/scorer.py` | Scores a stock 0–100 across 6 criteria (PE, ROE, D/E, Graham gap, net margin, dividend yield). Config-driven via `config/scoring.json`. `find_opportunities()` scans all Nifty 50 and returns them sorted by score. |
| `data/pe_bands.py` | Downloads 5 years of daily prices, divides by current trailing EPS to get implied historical PE, then computes percentile bands (low / 25th / median / 75th / high). Labels current PE as cheap / fair / expensive / very expensive relative to its own history. |
| `data/technicals.py` | Computes SMA50, SMA200, RSI-14 (Wilder smoothing), trend signal (bullish/bearish/neutral/mixed), golden cross / death cross detection (30-day scan window), and 20-day support/resistance. All from yfinance daily OHLC data. 15-min cache. |
| `data/peers.py` | Loads sector groupings from `config/sector_peers.json`. `compare_with_peers(ticker)` scores the target stock AND every stock in its sector, sorts by score, and returns the ranking. Takes 30–60 seconds. |
| `data/dividends.py` | Fetches dividend payment history via `yf.Ticker.dividends`. Aggregates by year, computes CAGR, classifies consistency as Growing / Consistent / Irregular / No dividends. 1-hour cache. |
| `data/portfolio.py` | Manages `config/portfolio.json`. Adds holdings with weighted average price merge, removes holdings, computes live P&L for the whole portfolio by fetching current prices. Integrates with `scorer.py` to show opportunity scores alongside P&L. |
| `data/cache.py` | Simple file-based JSON cache stored in `cache/`. Two TTLs: `STOCK_TTL = 900s` (15 min) for stock data, `NEWS_TTL = 86400s` (24 h) for news briefings (keyed by date, so one fetch per day). |
| `data/session.py` | Saves and loads the chat conversation to/from disk so the session survives page refreshes. Stores both the display messages and the Gemini history (which includes tool calls/results). |

### Configuration (`config/`)

| File | What it contains |
|------|-----------------|
| `config/watchlist.txt` | User's tracked stocks, one per line. Format: `TICKER  # Optional alt name`. Editable plain text — add or remove tickers directly or via chat commands. |
| `config/feeds.json` | List of Indian RSS feed URLs and their display names (MoneyControl, Economic Times, LiveMint, etc.). |
| `config/nifty50.txt` | ~50 NSE tickers that make up the Nifty 50 index. Used by the screener and opportunity scanner. |
| `config/midcap150.txt` | ~80 NSE tickers from the Nifty Midcap 150 index. Used by the screener. |
| `config/sector_peers.json` | 10 sector groupings (IT, Banking Private, Banking PSU, Auto, Energy, Pharma, FMCG, Metals, Insurance, Infra) with their member tickers. Used by `data/peers.py`. |
| `config/portfolio.json` | User's stock holdings. Gitignored. Structure: `{"holdings": [...], "last_updated": "..."}`. Each holding: `{ticker, quantity, avg_price, added_on}`. |
| `config/scoring.json` | Scoring thresholds and point allocations for all 6 criteria. Edit this to tune how stocks are scored without touching Python code. |

---

## 6. Every Tool the Agent Can Use

Gemini picks which tool(s) to call based on the user's question. Tools are declared in `agent/tools.py` and executed in `agent/dispatch.py`.

| Tool Name | What it does | Example questions |
|-----------|-------------|-------------------|
| `get_stock_snapshot` | Live price + fundamentals for one stock (PE, ROE, D/E, margins, market cap) | "RELIANCE ka PE kya hai?", "Show HDFCBANK fundamentals" |
| `compare_stocks` | Side-by-side comparison table for 2+ stocks | "Compare TCS and Infosys", "RELIANCE vs ONGC" |
| `get_market_news` | Today's full market briefing from 10+ RSS feeds, AI-summarized | "Aaj market mein kya hua?", "Today's briefing" |
| `get_stock_news` | Recent headlines filtered to one specific stock | "TATAMOTORS news kya hai?", "Any news on Infosys?" |
| `get_watchlist` | Show the user's current watchlist | "Meri watchlist dikhao", "What's on my watchlist?" |
| `add_to_watchlist` | Add a ticker to `config/watchlist.txt` | "WIPRO watchlist mein add karo" |
| `remove_from_watchlist` | Remove a ticker from `config/watchlist.txt` | "TCS hata do watchlist se" |
| `calculate_valuation` | Graham Number + PE-based fair value + margin of safety | "RELIANCE ki intrinsic value?", "Is TCS overvalued?" |
| `screen_stocks` | Filter Nifty 50 / Midcap 150 by PE, ROE, D/E, sector, market cap | "PE under 15 stocks dikhao", "IT stocks with ROE above 20%" |
| `score_stock` | Score one stock 0–100 on 6 fundamental criteria | "RELIANCE ka score kya hai?", "Rate HDFCBANK fundamentals" |
| `find_opportunities` | Score all Nifty 50, return ranked top opportunities | "Best Nifty 50 stocks dikhao", "Top undervalued stocks" |
| `analyze_watchlist` | Score every stock in the user's watchlist at once | "Meri poori watchlist analyze karo" |
| `add_portfolio_holding` | Add/update a holding in the portfolio | "RELIANCE ke 10 shares add karo at 2450" |
| `remove_portfolio_holding` | Remove a holding from the portfolio | "TCS portfolio se hata do" |
| `get_portfolio_summary` | Full portfolio with live P&L per holding + total | "Mera portfolio dikhao", "Portfolio P&L kya hai?" |
| `get_pe_history` | Historical PE range (5Y min/max/median/percentiles) vs current PE | "RELIANCE ka PE history dikhao", "Is TCS PE historically high?" |
| `get_technicals` | SMA50/200, RSI-14, trend signal, golden/death cross, support/resistance | "RELIANCE technical kya keh raha hai?", "RSI check karo" |
| `compare_with_peers` | Score target stock + all sector peers, return ranked table | "TCS apne sector mein kaisa hai?", "INFY vs IT sector" |
| `get_dividend_history` | Annual dividend payouts, CAGR, consistency rating | "ITC ka dividend history dikhao", "COALINDIA kitna dividend deta hai?" |
| `generate_daily_master_report` | Full market briefing + top underrated Nifty 50 picks in one report | "Daily report banao", "Underrated stocks for 1-2 years" |

---

## 7. The Scoring System (0–100)

Every stock can be scored via `data/scorer.py`. The score surfaces fundamental attractiveness on a fixed set of measurable criteria. **It is not a buy signal.**

| Criterion | Max Points | What is measured |
|-----------|-----------|-----------------|
| Value (PE) | 20 | How cheap the stock is relative to earnings. Lower PE = higher score. |
| Quality (ROE) | 20 | Return on Equity — how efficiently the company earns profit from shareholder capital. Higher ROE = higher score. |
| Safety (D/E) | 15 | Debt-to-Equity ratio — how leveraged the company is. Lower debt = higher score. |
| Graham Gap | 20 | How far the current price is below the Graham Number (Benjamin Graham's intrinsic value estimate). Greater discount = higher score. |
| Profitability | 15 | Net profit margin — what % of revenue becomes profit. Higher margin = higher score. |
| Dividend | 10 | Dividend yield. Any yield > 0 scores points; higher yield scores more. |

**Grade thresholds** (configurable in `config/scoring.json`):
- A: ≥ 70 pts — Strong fundamentals
- B: ≥ 55 pts — Good fundamentals
- C: ≥ 40 pts — Decent but mixed
- D: ≥ 25 pts — Weak fundamentals
- F: < 25 pts — Very weak

---

## 8. Caching System

`data/cache.py` stores API responses in `cache/` as JSON files (gitignored). This prevents re-fetching the same data multiple times and avoids hitting free-tier rate limits.

| Data type | Cache TTL | Why |
|-----------|-----------|-----|
| Stock snapshot | 15 minutes | Prices change intraday; 15 min is fresh enough for research |
| News briefing | 24 hours (keyed by date) | News is fetched once per day; same briefing for all queries that day |
| PE history | 1 hour | Historical data changes slowly; 1 hr is fine |
| Technical indicators | 15 minutes | Same as stock prices |
| Dividend history | 1 hour | Dividends change quarterly at most |

Cache files are named like `stock_snapshot_RELIANCE.json`, `news_briefing_2026-05-15.json`, etc.

---

## 9. Configuration Files

### `config/watchlist.txt`

```
# My tracked stocks
RELIANCE  # Reliance Industries
TCS       # Tata Consultancy Services
HDFCBANK  # HDFC Bank
```

Lines starting with `#` are comments. After the ticker, everything after `#` is treated as an alternate name (not a comment — it's used for news matching). Edit this file directly OR ask the agent: *"WIPRO watchlist mein add karo"*.

### `config/feeds.json`

A JSON array of RSS feed objects:
```json
[
  {"name": "MoneyControl Markets", "url": "https://..."},
  {"name": "Economic Times Markets", "url": "https://..."}
]
```
Add or remove feeds here to change what news sources the agent reads.

### `config/scoring.json`

Defines the point tiers for each scoring criterion. For example, the PE scoring might look like:
```json
"value": {
  "max_points": 20,
  "tiers": [
    {"threshold": 10, "points": 20, "label": "Very cheap"},
    {"threshold": 15, "points": 15, "label": "Cheap"},
    {"threshold": 22, "points": 10, "label": "Near market average"},
    {"threshold": null, "points": 5, "label": "Expensive"}
  ]
}
```
Editing this file changes how stocks are scored without touching Python.

---

## 10. Data Sources

| Data | Source | How accessed |
|------|--------|--------------|
| Stock prices, fundamentals (PE, ROE, D/E, margins, market cap, EPS, book value) | Yahoo Finance | `yfinance` Python library |
| Historical OHLC prices (for technicals, PE bands, dividend history) | Yahoo Finance | `yfinance` library |
| Market news | 10+ Indian RSS feeds (MoneyControl, ET, LiveMint, etc.) | `feedparser` Python library |
| News AI summarization | Google Gemini 2.5 Flash | `google-generativeai` library |
| Agent conversation | Google Gemini 2.5 Flash (free tier) | `google-generativeai` library |

**What is NOT available:**
- Promoter holding — Yahoo Finance doesn't carry this for Indian stocks. Future: NSE or Screener.in scraping.
- Quarterly results, concall transcripts — not implemented yet.
- Insider trading data — not implemented yet.

---

## 11. Limitations and Known Issues

1. **yfinance inconsistencies** — Yahoo Finance sometimes returns stale, incorrect, or missing data for Indian stocks. The code normalizes the D/E ratio (which yfinance returns inconsistently as either a ratio or a percentage). Always cross-check important numbers from a second source.

2. **Promoter holding** — Not available via yfinance. The agent tells the user this when asked.

3. **Screener takes time** — Scanning 50 stocks takes ~1–2 minutes because each requires a separate API call with a 1-second delay to avoid rate limiting. The UI shows a progress bar.

4. **Free-tier Gemini quota** — The free Gemini API has daily and per-minute limits. If you hit them, you'll see a friendly message with the estimated reset time. The `_send_with_retry()` function in `brain.py` retries on 503/timeout errors (NOT 429 quota errors, which won't self-resolve in seconds).

5. **PE bands are approximate** — `data/pe_bands.py` calculates historical PE by dividing past prices by TODAY's trailing EPS. The actual EPS in the past was different, so the historical PE band is a directional estimate only, not historically precise.

6. **Graham Number limitations** — This formula was designed for US industrial companies in the 1970s. It underestimates the fair value of high-growth, asset-light businesses (tech companies, consumer brands). The agent notes this caveat when presenting Graham Number results.

7. **Sector peer groupings are manual** — `config/sector_peers.json` is a curated list of ~40 tickers across 10 sectors. Not every NSE stock is covered. If a stock isn't in the file, it shows as "Unknown" sector.

---

## 12. Project History and Phases

The project started as a simple CLI news briefing tool and evolved into a full conversational agent.

| Phase | What was built | Date |
|-------|---------------|------|
| Stage 1 | CLI news briefing — RSS fetcher + Gemini summarizer + markdown saver | 2026-05-05 |
| Stage 2 | CLI stock data — yfinance snapshot + multi-stock watchlist tracker | 2026-05-13 |
| **Architecture pivot** | Switched from 5-stage CLI pipeline to single Streamlit chat agent | 2026-05-14 |
| Phase 1 | Agent core — Gemini function calling + Streamlit chat UI + legacy code refactored into `data/` modules | 2026-05-14 |
| Phase 2 | Stock screener — filter Nifty 50 by PE/ROE/D/E/sector | 2026-05-14 |
| Phase 3 | Valuation models — Graham Number + PE-based fair value | 2026-05-14 |
| Phase 4 | Polish — file-based cache, Plotly price chart, error messages, README | 2026-05-14 |
| Phase 5 | Opportunity scorer — 0–100 score across 6 criteria | 2026-05-14 |
| Phase 6 | Bulk watchlist analysis — score all watchlist stocks at once | 2026-05-14 |
| Phase 7 | Portfolio tracker — holdings, weighted avg price, live P&L | 2026-05-14 |
| Phase 8 | PE bands + technical indicators — SMA, RSI, golden/death cross | 2026-05-14 |
| Phase 9 | Sector peer comparison + dividend history | 2026-05-14 |
| Quality hardening | Test suite (147 tests), retry logic, pure helper extraction, midcap universe | 2026-05-15 |

The legacy CLI code still lives in `stage1_news/` and `stage2_stock_data/` for reference but is no longer used by the agent.

---

*This file was generated 2026-05-15. Update it after major structural changes.*
