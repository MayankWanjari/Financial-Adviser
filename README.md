# Financial Research AI — Indian Markets

A personal AI-powered research assistant for Indian stock market investing. Chat in Hindi or English, and the AI fetches real data, analyzes news, screens stocks, and estimates intrinsic value — all from a single browser interface.

**This is a research tool, not a financial advisor.** It organizes public information so you can think clearly. All decisions are yours.

---

## Features

| Feature | What it does |
|---------|-------------|
| 📊 **Stock Snapshot** | Live price, PE, ROE, D/E, margins, 52W range for any NSE stock |
| ⚖️ **Compare Stocks** | Side-by-side fundamental table for 2–5 stocks |
| 📰 **Market Briefing** | AI-analyzed daily news from 15+ Indian financial RSS feeds |
| 🔍 **Stock News** | News headlines filtered to a specific company |
| 🧮 **Valuation** | Graham Number + PE-based fair value with margin of safety |
| 🔎 **Screener** | Filter Nifty 50 or Nifty Midcap 150 by PE, ROE, D/E, market cap, sector |
| 🏆 **Opportunity Scorer** | Score any stock 0–100 on 6 fundamental criteria (PE, ROE, D/E, Graham gap, margin, yield) |
| 🔭 **Find Opportunities** | Scan all Nifty 50 stocks and rank by fundamental score |
| 📋 **Watchlist Analysis** | Score all your watchlist stocks at once and rank them |
| 💼 **Portfolio Tracker** | Track your holdings with live P&L and fundamental scores |
| 📈 **PE Band History** | See if a stock is cheap or expensive vs its own 5-year history |
| 📉 **Technical Indicators** | SMA 50/200, RSI-14, golden/death cross, support & resistance |
| 👥 **Sector Peer Comparison** | Rank a stock vs all its sector peers on fundamentals |
| 💰 **Dividend History** | Annual payouts, CAGR, consistency label (Growing/Consistent/Irregular) |
| 📅 **Daily Master Report** | One command for market news + top underrated picks |
| 📈 **Price Chart** | Auto-renders 1-month chart when you ask about a single stock |
| 🌐 **Hindi/Hinglish** | Responds in whatever language you write in |

---

## Prerequisites

- Python 3.10 or newer
- A free **Gemini API key** from Google AI Studio
- Internet connection (fetches live data from Yahoo Finance and RSS news feeds)

---

## Setup

### 1. Clone the repository

```bash
git clone <repo-url>
cd financial-advisor-ai
```

### 2. Create a virtual environment

```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Get a free Gemini API key

1. Go to [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)
2. Sign in with a Google account
3. Click **Create API key** → copy the key

The free tier gives you 500 requests/day on `gemini-2.5-flash`. That's enough for personal daily use.

### 5. Create your `.env` file

```bash
cp .env.example .env
```

Open `.env` and fill in your key:

```
GEMINI_API_KEY=your_key_here
```

> **Never commit `.env` to git.** It's already in `.gitignore`.

### 6. (Optional) Customize your watchlist

Edit `config/watchlist.txt` — one NSE ticker per line. Lines starting with `#` are ignored. You can add alternate names after `#` so the news briefing matches them in headlines:

```
RELIANCE   # Reliance, RIL, Mukesh Ambani
TCS        # Tata Consultancy, Tata Consulting
HDFCBANK
M&M        # Mahindra, M and M
```

---

## Running the app

```bash
streamlit run app.py
```

The app opens at `http://localhost:8501` in your browser. Keep the terminal open while you use it.

---

## Example questions

```
# Stock data
RELIANCE ka snapshot dikhao
Compare TCS, Infosys aur Wipro
HDFCBANK ka PE kya hai?

# Valuation
ONGC ki intrinsic value kya hai?
Is Nestle overvalued?

# Fundamental scoring
TATAMOTORS ka score kya hai?
Find the best opportunities in Nifty 50
Meri watchlist analyze karo

# Portfolio
Add 10 shares of RELIANCE at 2800 to my portfolio
Show my portfolio P&L
Remove WIPRO from portfolio

# Historical analysis
HDFC Bank ka PE band history dikhao — cheap hai ya expensive?
RELIANCE ka technical analysis karo
ITC ke dividend history dikhao (last 5 years)
TCS ko IT sector ke baaki stocks se compare karo

# News
Aaj market mein kya hua?
TATAMOTORS ke baare mein koi news hai?
Daily master report dikhao

# Screener (takes 1-2 min for Nifty 50, longer for midcap)
PE under 15 wale Nifty stocks dikhao
IT sector stocks with ROE above 20%
Low debt midcap stocks (D/E below 0.5)
Screen both Nifty 50 and midcap with ROE above 15%

# Watchlist
Meri watchlist dikhao
WIPRO add karo
INFY hata do
```

---

## Project structure

```
financial-advisor-ai/
├── app.py                    <- Streamlit chat UI — start here
├── agent/
│   ├── brain.py              <- Gemini agent with function calling + retry logic
│   ├── dispatch.py           <- Tool execution bridge (maps Gemini calls → data/)
│   ├── tools.py              <- FunctionDeclaration schemas for Gemini
│   └── prompts.py            <- Agent personality and response format rules
├── data/
│   ├── stock_data.py         <- yfinance wrapper (15-min cache)
│   ├── news_fetcher.py       <- RSS feed fetcher + deduplication
│   ├── news_analyzer.py      <- Gemini news briefing (daily cache)
│   ├── screener.py           <- Stock screener (Nifty 50 + Midcap 150)
│   ├── valuation.py          <- Graham Number + PE fair value
│   ├── scorer.py             <- 0-100 fundamental score across 6 criteria
│   ├── portfolio.py          <- Holdings tracker with live P&L
│   ├── pe_bands.py           <- Historical PE band analysis (1-hr cache)
│   ├── technicals.py         <- SMA, RSI, golden/death cross (15-min cache)
│   ├── peers.py              <- Sector peer comparison
│   ├── dividends.py          <- Dividend history + CAGR (1-hr cache)
│   ├── cache.py              <- File-based JSON cache with TTL
│   └── session.py            <- Cross-session conversation persistence
├── config/
│   ├── watchlist.txt         <- Your tracked stocks (edit freely)
│   ├── feeds.json            <- RSS feed URLs
│   ├── nifty50.txt           <- Nifty 50 screener universe
│   ├── midcap150.txt         <- Nifty Midcap 150 screener universe (update quarterly)
│   ├── sector_peers.json     <- Sector groupings for peer comparison
│   └── portfolio.json        <- Your holdings (auto-created, gitignored)
├── tests/                    <- 147 unit tests, all offline (no network)
│   ├── conftest.py           <- Shared test fixtures
│   └── test_*.py             <- One file per module
├── cache/                    <- Auto-generated cache files, gitignored
├── .env                      <- Your secrets (never commit this)
└── requirements.txt
```

---

## Caching

To stay within the free API quota, responses are cached locally:

| Data | Cache duration |
|------|----------------|
| Stock snapshots | 15 minutes |
| Technical indicators | 15 minutes |
| News briefing | Once per day (re-generates after midnight) |
| PE band history | 1 hour |
| Dividend history | 1 hour |

Cache files live in `cache/` and are gitignored. Delete them to force a fresh fetch.

---

## Running the tests

```bash
python -m pytest tests/ -v
```

All 147 tests are offline — they mock file paths and don't call Yahoo Finance or Gemini. They run in under 2 seconds.

---

## Troubleshooting

**"GEMINI_API_KEY not found"**
Add `GEMINI_API_KEY=your_key` to `.env` in the project root, then refresh the page.

**"Gemini quota exceeded (HTTP 429)"**
You've hit the free-tier daily limit. Wait until midnight Pacific Time (~08:00 UTC) for the daily quota to reset. For per-minute limits, wait 60 seconds and retry.

**Transient errors / "503 Service Unavailable"**
The agent retries automatically up to 3 times with exponential backoff (2s, 4s, 8s). If it still fails, try again in a minute.

**Stock data shows N/A for some fields**
Yahoo Finance doesn't carry all fields for all Indian stocks (especially PSUs and some midcaps). This is a data source limitation, not a bug.

**Screener takes a long time**
Screening requires one yfinance fetch per stock with a 1-second delay between each to avoid rate limiting. Expected times:
- Nifty 50: ~1–2 minutes
- Midcap 150: ~3–4 minutes
- Both combined: ~5–6 minutes

**"Module not found" errors**
Make sure you activated the virtual environment before running `pip install -r requirements.txt` and `streamlit run app.py`.

**Chart doesn't appear**
Charts only show for single-stock snapshot queries (not comparisons or news). If plotly isn't installed, run `pip install plotly`.
