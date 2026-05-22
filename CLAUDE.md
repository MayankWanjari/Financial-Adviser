# CLAUDE.md — Project Context Map

> **Read this file first.** It's the compressed map of this project. Don't read the full codebase unless this file points you to specific files. Update this file at the end of any session where the project structure or state changes.

## Project: Financial Advisor AI (Indian Markets)

A personal AI-powered **conversational research assistant** for Indian stock market investing. The user chats in natural language (Hindi/English) and the AI fetches data, analyzes news, screens stocks, and answers questions — all from a single Streamlit chat interface.

Built by a Python-beginner solo developer. Budget: ₹0 (only free tools).

**Current phase: Phase 1 — Agent Core + Chat UI.** Legacy Stage 1 (news) and Stage 2 (stock data) code exists and must be refactored into callable tool functions for the agent.

**Important framing:** This is a "research analyst" tool, not a "financial advisor." Never write code or prompts that produce buy/sell recommendations. Always frame AI output as information for the user to decide on.

## Architecture

This is a **Gemini-powered AI agent** with function calling. The user types a question, Gemini decides which tool functions to call, fetches real data, and responds in natural language.

```
User (Streamlit chat)
       │
       ▼
┌─────────────────────────┐
│    GEMINI 2.5 FLASH      │
│    with Function Calling │
│                          │
│  Decides which tools     │
│  to call based on the    │
│  user's question         │
└──────────┬──────────────┘
           │
           ▼
┌─────────────────────────┐
│    TOOL FUNCTIONS        │
│                          │
│  get_stock_snapshot()    │  ← from stock_data.py
│  compare_stocks()        │  ← from stock_data.py
│  get_market_news()       │  ← from news_fetcher.py + news_analyzer.py
│  get_stock_news()        │  ← from news_fetcher.py
│  screen_stocks()         │  ← from screener.py (Phase 2)
│  calculate_valuation()   │  ← from valuation.py (Phase 3)
└──────────┬──────────────┘
           │
           ▼
     Gemini formats response
     → shown in chat UI
```

## Stack

- Python 3.10+
- Google Gemini API (free tier) — model: gemini-2.5-flash
- Streamlit — chat UI
- Libraries: feedparser, google-generativeai, python-dotenv, rich, yfinance, streamlit
- Storage: local markdown files + JSON for raw archives
- No databases yet

## Project structure (target)

```
financial-advisor-ai/
├── CLAUDE.md                    ← this file
├── PHILOSOPHY.md                ← user's investing principles; agent's system prompt references this
├── JOURNAL.md                   ← user fills; do not modify unless asked
├── README.md                    ← user-facing setup guide
├── .env                         ← secrets (NEVER read or echo this file)
├── .env.example                 ← template
├── .gitignore
├── requirements.txt
├── app.py                       ← Streamlit chat UI (SINGLE ENTRY POINT)
├── agent/
│   ├── __init__.py
│   ├── brain.py                 ← Gemini agent with function calling + tool dispatch
│   ├── tools.py                 ← Tool function declarations for Gemini API
│   └── prompts.py               ← System prompt + personality configuration
├── data/
│   ├── __init__.py
│   ├── stock_data.py            ← ♻️ Refactored from stage2_stock_data/stock_snapshot.py
│   ├── news_fetcher.py          ← ♻️ Refactored from stage1_news/rss_fetcher.py
│   ├── news_analyzer.py         ← ♻️ Refactored from stage1_news/ai_analyzer.py
│   ├── screener.py              ← 🆕 Stock screener (Phase 2)
│   └── valuation.py             ← 🆕 Valuation calculator (Phase 3)
├── config/
│   ├── watchlist.txt            ← user's tracked stocks (merged from both old watchlists)
│   └── feeds.json               ← RSS feed URLs and names
├── cache/                       ← gitignored; stores cached API responses
├── stage1_news/                 ← 🗄️ LEGACY — kept for reference, not used by agent
│   ├── main.py
│   ├── rss_fetcher.py
│   ├── ai_analyzer.py
│   ├── briefing_saver.py
│   ├── watchlist.txt
│   ├── briefings/
│   └── raw_headlines/
└── stage2_stock_data/           ← 🗄️ LEGACY — kept for reference, not used by agent
    ├── stock_snapshot.py
    ├── watchlist_tracker.py
    └── watchlist.txt
```

## Phase status

- ✅ Legacy Stage 1: News briefing — COMPLETE (2026-05-05, now in stage1_news/)
- ✅ Legacy Stage 2a/2b: Stock data — COMPLETE (2026-05-13, now in stage2_stock_data/)
- ✅ Phase 1: Agent Core + Chat UI — COMPLETE (2026-05-14)
  - ✅ Step 1.1: Refactor legacy code into data/ modules — DONE (2026-05-14)
  - ✅ Step 1.2: Build agent/brain.py (Gemini function calling) — DONE (2026-05-14)
  - ✅ Step 1.3: Build app.py (Streamlit chat) — DONE (2026-05-14)
  - ✅ Step 1.4: Integration test — DONE (2026-05-14)
- ✅ Phase 2: Data Superpowers (news tools, screener) — COMPLETE (2026-05-14)
  - ✅ Screener: data/screener.py + screen_stocks tool in agent/brain.py — DONE (2026-05-14)
- ✅ Phase 3: Intelligence (valuation, portfolio) — COMPLETE (2026-05-14)
  - ✅ Valuation: data/valuation.py + calculate_valuation tool in agent/brain.py — DONE (2026-05-14)
- ✅ Phase 4: Polish (memory, charts, caching) — COMPLETE (2026-05-14)
  - ✅ Caching: data/cache.py; stock snapshots cached 15 min, news briefing cached by date
  - ✅ Charts: Plotly 1-month price chart in app.py for single-stock queries
  - ✅ System prompt: response format examples, table rules, Hindi example, disclaimer rule
  - ✅ Error messages: quota/network detection in brain.py chat(); friendly Hinglish messages
  - ✅ README: full rewrite with setup guide, feature list, examples, troubleshooting
- ✅ Phase 5: Opportunity Scorer — COMPLETE (2026-05-14)
  - ✅ data/scorer.py — scores stocks 0-100 on 6 criteria (PE, ROE, D/E, Graham gap, net margin, dividend yield)
  - ✅ score_stock tool + find_opportunities tool added to agent/brain.py
  - ✅ Scoring format rules added to agent/prompts.py
- ✅ Phase 6: Bulk Watchlist Analysis — COMPLETE (2026-05-14)
  - ✅ analyze_watchlist tool in agent/brain.py — scores all watchlist stocks, returns sorted results + summary stats (avg, top, weakest, grade distribution)
  - ✅ Watchlist analysis format added to agent/prompts.py
- ✅ Phase 7: Portfolio Tracker — COMPLETE (2026-05-14)
  - ✅ config/portfolio.json (gitignored) — empty holdings array, last_updated field
  - ✅ data/portfolio.py — load_portfolio, save_portfolio, add_holding (weighted avg merge), remove_holding, portfolio_summary (live P&L + scorer integration)
  - ✅ Three tools in agent/brain.py: add_portfolio_holding, remove_portfolio_holding, get_portfolio_summary
  - ✅ Portfolio table format added to agent/prompts.py
- ✅ Phase 8: Historical PE Bands + Basic Technicals — COMPLETE (2026-05-14)
  - ✅ data/pe_bands.py — get_pe_history(): 5-year PE range, percentiles, position label, interpretation, caveat. Cached 1 hr.
  - ✅ get_pe_history tool in agent/brain.py (ticker required, years optional default 5)
  - ✅ PE band table format + position colour labels added to agent/prompts.py
  - ✅ data/technicals.py — get_technical_indicators(): SMA50/200, price vs MAs, trend signal, golden/death cross (last 30 days), RSI-14 (Wilder smoothing), 20-day support/resistance. Cached 15 min.
  - ✅ get_technicals tool in agent/brain.py (ticker required)
  - ✅ Technical analysis table format + backward-looking caveat added to agent/prompts.py
- ✅ Phase 9: Sector Peers + Dividend History — COMPLETE (2026-05-14)
  - ✅ config/sector_peers.json — 10 sector groupings (IT, Banking Private/PSU, Auto, Energy, Pharma, FMCG, Metals, Insurance, Infra)
  - ✅ data/peers.py — get_sector_peers() (finds sector + returns peers), compare_with_peers() (scores all sector stocks, ranks target, returns comparison_summary)
  - ✅ compare_with_peers tool in agent/brain.py (ticker required)
  - ✅ data/dividends.py — get_dividend_history() (annual payouts, CAGR, consistency label, interpretation, 1-hr cache)
  - ✅ get_dividend_history tool in agent/brain.py (ticker required, years optional default 5)
  - ✅ Peer comparison table + dividend history table formats added to agent/prompts.py

**🎉 Product is feature-complete as of 2026-05-14.**

## Coding conventions

- Type hints on function signatures
- Docstrings on every function (one-line OK for simple ones)
- No hardcoded secrets — always via python-dotenv
- User-facing errors are friendly messages, not stack traces
- Modules under 200 lines — split if growing
- Comment generously — primary reader is a Python beginner
- All data/ modules must return data (dicts/lists), never print() or sys.exit()
- Only app.py and agent/ should handle display logic

## Important rules

1. Never expose API keys in code, comments, or example output
2. The agent must NEVER give buy/sell recommendations — research only
3. All Gemini prompts for the agent live in agent/prompts.py — don't scatter prompt strings
4. data/ modules are pure functions: data in → data out. No UI, no sys.exit(), no print()
5. The watchlist is user-editable plain text; treat it as data, not code
6. Cache expensive API calls (yfinance, Gemini) to avoid hitting free-tier limits
7. Hindi/English both supported in chat — the agent should respond in whichever language the user uses

## Where to look for what

| Need to change... | Look at... |
|---|---|
| Chat UI layout | `app.py` |
| Agent personality / system prompt | `agent/prompts.py` |
| How the agent calls tools | `agent/brain.py` |
| Tool function definitions (for Gemini) | `agent/tools.py` |
| Stock data fetching logic | `data/stock_data.py` |
| RSS feed sources | `config/feeds.json` |
| News fetching + dedup logic | `data/news_fetcher.py` |
| News AI analysis | `data/news_analyzer.py` |
| Stock screening | `data/screener.py` |
| Valuation models | `data/valuation.py` |
| User's watchlist | `config/watchlist.txt` |
| Investing principles / tone | `PHILOSOPHY.md` |
| Legacy news CLI | `stage1_news/` (reference only) |
| Legacy stock CLI | `stage2_stock_data/` (reference only) |

## Key design decisions

- AI model: gemini-2.5-flash (free tier, supports function calling)
- Function calling: Gemini decides which tools to call based on user's question
- Data modules return dicts/lists, never formatted strings — formatting is agent's job
- Legacy code kept in stage1_news/ and stage2_stock_data/ for reference during refactor
- Watchlist merged from both legacy locations into config/watchlist.txt
- RSS feeds extracted from hardcoded list into config/feeds.json
- Agent responds in the language the user uses (Hindi/English/Hinglish)

## Legacy code reference (for refactoring)

These are the key functions from legacy code that need to be refactored into data/ modules:

### From stage2_stock_data/stock_snapshot.py:
- `fetch_stock_data(ticker: str) -> dict` — fetches one stock's fundamentals via yfinance. Returns dict with price, PE, ROE, margins, D/E, etc. Calls sys.exit() on error (must change to raise exception).
- `fmt_crore()`, `fmt_price()`, `fmt_pct()`, `fmt_ratio()`, `fmt_div_yield()` — number formatters. Keep these.
- `_indian_number_format(n)` — converts to Indian comma format (1,92,54,000).

### From stage2_stock_data/watchlist_tracker.py:
- `fetch_all(tickers) -> (results, failed)` — fetches multiple stocks with progress. Uses fetch_stock_data() internally.
- `compute_from_52w_high(data) -> float` — % below 52W high.
- `read_watchlist(path) -> list[str]` — reads ticker file.

### From stage1_news/rss_fetcher.py:
- `fetch_headlines(watchlist_path) -> (articles, symbols, feed_results)` — parallel RSS fetch + dedup + tag. FEEDS list is hardcoded (must move to config).
- SYMBOL_NAME_MAP — dict of ticker → alternate names for matching.
- DEDUP_SIMILARITY_THRESHOLD = 0.75

### From stage1_news/ai_analyzer.py:
- `analyze_headlines(articles, symbols, symbol_name_map, eli12_mode) -> str|None` — sends headlines to Gemini, returns markdown briefing.
- SYSTEM_INSTRUCTION — the news briefing prompt (very long, carefully tuned).
- MODEL_NAME = "gemini-2.5-flash"

### From stage1_news/briefing_saver.py:
- `save_briefing(text, date, mode, symbols, count) -> Path` — saves markdown with YAML frontmatter.
- `save_raw_headlines(articles, date) -> Path` — saves raw JSON.

## Recent changes log

(Update this section after each major change. Keep last 10 entries.)

- 2026-05-05: Project initialized with Stage 1 scaffolding
- 2026-05-05: Stage 1 fully complete — RSS fetcher, AI analyzer, briefing saver, CLI
- 2026-05-05: Bug fixes — replaced dead feeds, added feed health summary, Windows UTF-8 fix
- 2026-05-05: Switched to gemini-2.5-flash; added 429 error handler
- 2026-05-13: Stage 2a — stock_snapshot.py; single-stock via yfinance
- 2026-05-13: Stage 2b — watchlist_tracker.py; multi-stock table with --sort
- 2026-05-14: ARCHITECTURE PIVOT — from 5-stage CLI tools to single conversational AI agent with Streamlit chat UI. Legacy code preserved in stage1_news/ and stage2_stock_data/. New structure: app.py + agent/ + data/ + config/
- 2026-05-14: Phase 1 Step 1.1 (partial) — created data/__init__.py and data/stock_data.py. Refactored fetch_stock_data→get_stock_snapshot (raises exceptions), fetch_all→get_multiple_stocks (no printing), compute_from_52w_high and read_watchlist (raises FileNotFoundError). All fmt_* helpers preserved.
- 2026-05-14: Phase 1 Step 1.1 COMPLETE — created data/news_fetcher.py and data/news_analyzer.py. FEEDS moved to config/feeds.json; SYMBOL_NAME_MAP moved to config/watchlist.txt (TICKER  # Alt, Names format) with build_symbol_name_map() loader. fetch_headlines() now takes feeds_path arg. analyze_headlines() raises exceptions instead of sys.exit()/returning None. config/watchlist.txt merges both legacy watchlists.
- 2026-05-14: Phase 1 Step 1.2 COMPLETE — created agent/__init__.py, agent/prompts.py, agent/brain.py. FinancialAgent class with 7 tools (get_stock_snapshot, compare_stocks, get_market_news, get_stock_news, get_watchlist, add/remove_from_watchlist). Full function-calling loop with max_rounds safety cap. Watchlist file helpers (_add/_remove/_read). Added yfinance + streamlit to requirements.txt.
- 2026-05-14: Phase 1 Step 1.3 COMPLETE — created app.py (Streamlit chat UI). Agent init once per session in session_state; Gemini history kept separate from display history; sidebar shows watchlist + agent status; welcome message with example questions (Hindi+English); spinner during tool calls; watchlist sidebar auto-refreshes after watchlist commands. Rewrote README.md for new Streamlit-first workflow.
- 2026-05-14: Phase 1 Step 1.4 + PHASE 1 COMPLETE — full integration test passed. All imports clean; get_stock_snapshot/get_multiple_stocks/fetch_headlines all return correct data; FinancialAgent init OK; end-to-end chat test confirmed function-calling loop works (4 history entries: user→tool_call→tool_result→answer); Streamlit starts HTTP 200 with no errors. Installed streamlit into venv; pinned yfinance==1.3.0 and streamlit==1.57.0 in requirements.txt.
- 2026-05-14: Phase 2 screener DONE — created data/screener.py (screen_stocks function, load_nifty50_tickers) and config/nifty50.txt (~50 Nifty 50 tickers). Added screen_stocks tool to agent/brain.py (FunctionDeclaration + _handle_tool_call dispatch). Filters: pe_max, pe_min, roe_min (%), de_max, market_cap_min (₹ Cr), sector. 1-second delay between fetches; takes ~1-2 min for full scan.
- 2026-05-14: Phase 3 valuation DONE — created data/valuation.py with graham_number(), margin_of_safety(), pe_valuation(), valuation_summary(). Added eps_trailing + book_value fields to get_stock_snapshot() in stock_data.py. Added calculate_valuation tool to agent/brain.py. Models skip gracefully when yfinance lacks EPS/book value; each result includes a plain-English interpretation string for the beginner user.
- 2026-05-14: Phase 4 DONE / FEATURE-COMPLETE — (1) data/cache.py: file-based JSON cache, STOCK_TTL=15min, NEWS_TTL=24h keyed by date; wired into get_stock_snapshot() and analyze_headlines(). (2) app.py: Plotly 1-month price chart rendered after single-stock snapshots (agent.last_chart_ticker); quota/network errors rendered as friendly Hinglish markdown. (3) agent/prompts.py: added Response Format section with table templates, Hindi example, explicit disclaimer rule, valuation caveat. (4) agent/brain.py: last_chart_ticker attribute; improved last-resort error handler with quota/network detection. (5) README.md: full rewrite. (6) requirements.txt: added plotly==6.1.2. (7) .gitignore: added cache/*.json.
- 2026-05-14: Phase 5 DONE — created data/scorer.py with score_stock() (0-100 score across 6 criteria: PE, ROE, D/E, Graham gap, net margin, dividend yield; returns breakdown dict + grade A-F + interpretation string) and find_opportunities() (scans all Nifty 50, returns list sorted by score descending). Added score_stock and find_opportunities FunctionDeclarations + dispatch in agent/brain.py. Added scoring format templates to agent/prompts.py.
- 2026-05-14: Phase 6 DONE — added analyze_watchlist tool to agent/brain.py. Reads watchlist tickers, calls scorer.score_stock() for each with 1-sec delay, sorts by score, returns results + summary dict (total_stocks, avg_score, top_performer, weakest, grade_distribution). Added watchlist analysis format template to agent/prompts.py.
- 2026-05-14: Phase 7 DONE — created config/portfolio.json (gitignored, empty structure) and data/portfolio.py (load/save, add_holding with weighted avg merge, remove_holding, portfolio_summary with live P&L + scorer integration). Added 3 tools to agent/brain.py: add_portfolio_holding, remove_portfolio_holding, get_portfolio_summary. Portfolio format template added to agent/prompts.py.
- 2026-05-14: Phase 8 part 1 DONE — created data/pe_bands.py with get_pe_history() (daily close / current EPS → implied PE series, computes low/high/median/25th/75th percentiles, cheap/fair/expensive/very_expensive position, 1-hr cache). Added get_pe_history tool to agent/brain.py. PE band table format added to agent/prompts.py.
- 2026-05-14: CODE REVIEW — Independent verification of all 8 build prompts. All imports pass, all unit tests pass, Streamlit starts successfully. 1 bug found and fixed: read_watchlist() in data/stock_data.py wasn't splitting on '#' for the new TICKER # Alt Names format, causing yfinance lookups to fail with full line as ticker.
- 2026-05-14: Phase 8 part 2 DONE — created data/technicals.py with get_technical_indicators() (SMA50/200, price vs MAs, trend signal, golden/death cross via 30-day window scan, RSI-14 with Wilder smoothing, 20-day support/resistance, 15-min cache). Added get_technicals tool to agent/brain.py. Technical analysis table format + backward-looking caveat added to agent/prompts.py. Phase 8 now fully complete.
- 2026-05-14: Phase 9 DONE — (1) config/sector_peers.json: 10 sectors, 40+ tickers. (2) data/peers.py: get_sector_peers() + compare_with_peers() (scores target + all sector peers, sorts by score, returns rank). (3) compare_with_peers tool in agent/brain.py. (4) data/dividends.py: get_dividend_history() (annual totals from yfinance .dividends, CAGR, Growing/Consistent/Irregular/No dividends label, 1-hr cache). (5) get_dividend_history tool in agent/brain.py. (6) Both format templates added to agent/prompts.py.
- 2026-05-15: Quality hardening session — test isolation, pure helpers, retry logic, midcap universe.
  - (1) tests/conftest.py: shared fixtures (temp_portfolio, isolated_cache, isolated_session) — portfolio fixture pre-writes empty file before monkeypatching to guarantee clean state.
  - (2) test_portfolio.py / test_cache.py / test_session.py: removed local fixture duplicates, all use conftest. Strict count assertions restored.
  - (3) data/technicals.py: extracted _calculate_rsi() + _get_trend_signal() as module-level pure helpers; replaced inline blocks with calls to helpers.
  - (4) data/pe_bands.py: extracted _pe_position_label() pure helper; get_pe_history() now calls it.
  - (5) data/dividends.py: extracted _calculate_cagr() + _classify_consistency() pure helpers; get_dividend_history() now calls them.
  - (6) tests/test_technicals.py, test_pe_bands.py, test_dividends.py, test_news_fetcher.py, test_peers.py: 5 new test files covering pure helpers and config-driven functions (no network). Total: 147 tests, 0 failures.
  - (7) agent/brain.py: added _send_with_retry() with exponential backoff (2s/4s/8s) for transient 503/timeout errors; both send_message() call sites wired to it.
  - (8) agent/dispatch.py: analyze_watchlist now records exception message per failed ticker (not just ticker name) so user sees WHY a stock was skipped.
  - (9) config/midcap150.txt: Nifty Midcap 150 ticker file (80 tickers, editable quarterly).
  - (10) data/screener.py: added universe parameter ('nifty50'/'midcap150'/'both'); _load_tickers_from_file() helper used by both load_nifty50_tickers() and load_midcap150_tickers().
  - (11) agent/tools.py: screen_stocks FunctionDeclaration updated with universe parameter description.

## Open questions / TODO

- Screener data source: yfinance alone vs Screener.in scraping (for more fields)
- Promoter holding: yfinance doesn't have it; need NSE or Screener.in
- Gemini function calling: using google-generativeai or switch to google-genai (newer SDK)?