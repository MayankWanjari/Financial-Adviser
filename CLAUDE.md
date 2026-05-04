# CLAUDE.md — Project Context Map

> **Read this file first.** It's the compressed map of this project. Don't read the full codebase unless this file points you to specific files. Update this file at the end of any session where the project structure or state changes.

## Project: Financial Advisor AI (Indian Markets)

A personal AI-powered research tool for Indian stock market investing. Built in 5 stages by a Python-beginner solo developer using Google Antigravity. Budget: ₹0 (only free tools).

**Current stage: Stage 1 — News Briefing.** Stages 2–5 not started.

**Important framing:** This is a "research analyst" tool, not a "financial advisor." Never write code or prompts that produce buy/sell recommendations. Always frame AI output as information for the user to decide on.

## Stack

- Python 3.10+
- Google Gemini API (free tier) — model: gemini-2.0-flash
- Libraries: feedparser, google-generativeai, python-dotenv, rich
- Storage: local markdown files + JSON for raw archives
- No databases yet (added in Stage 2)
- No frontend yet (Stage 5)

## Project structure

financial-advisor-ai/
├── CLAUDE.md                ← this file
├── PHILOSOPHY.md            ← user's investing principles, read for tone alignment
├── JOURNAL.md               ← user fills daily; do not modify unless asked
├── README.md                ← user-facing setup guide
├── .env                     ← secrets (NEVER read or echo this file)
├── .env.example             ← template
├── .gitignore
├── requirements.txt
└── stage1_news/
    ├── main.py              ← orchestrator, CLI entry point
    ├── rss_fetcher.py       ← parallel RSS fetching + dedup + watchlist tagging
    ├── ai_analyzer.py       ← Gemini API call with structured prompt
    ├── briefing_saver.py    ← saves markdown + raw JSON
    ├── watchlist.txt        ← user's tracked stocks
    ├── briefings/           ← AI output archive (gitignored)
    └── raw_headlines/       ← raw fetched data archive (gitignored)

## Stage status

- ✅ Stage 1: News briefing — COMPLETE (all files created 2026-05-05)
- ⏳ Stage 2: Stock data fetcher — not started
- ⏳ Stage 3: Screener — not started
- ⏳ Stage 4: Books RAG — not started
- ⏳ Stage 5: Streamlit dashboard — not started

## Coding conventions

- Type hints on function signatures
- Docstrings on every function (one-line OK for simple ones)
- No hardcoded secrets — always via python-dotenv
- User-facing errors are friendly messages, not stack traces
- Modules under 200 lines — split if growing
- Print progress with `rich` for color
- Comment generously — primary reader is a Python beginner

## Important rules

1. Never produce specific buy/sell recommendations in prompts or code
2. Never expose API keys in code, comments, or example output
3. When adding new RSS feeds, test them first with feedparser before committing
4. Gemini prompts live in `ai_analyzer.py` only — don't scatter prompt strings across files
5. The watchlist symbol→name mapping is user-editable; treat it as data, not code
6. If a file exceeds 200 lines, suggest a refactor before adding more

## Where to look for what

| Need to change... | Look at... |
|---|---|
| News sources | `stage1_news/rss_fetcher.py` (FEEDS list) |
| AI briefing structure / sections | `stage1_news/ai_analyzer.py` (SYSTEM_INSTRUCTION) |
| Output formatting / file naming | `stage1_news/briefing_saver.py` |
| CLI flags / orchestration | `stage1_news/main.py` |
| User's stock watchlist | `stage1_news/watchlist.txt` |
| Investing principles / tone | `PHILOSOPHY.md` |

## Recent changes log

(Update this section after each major change. Keep last 10 entries.)

- 2026-05-05: Project initialized with Stage 1 scaffolding
- 2026-05-05: Stage 1 Python files created — rss_fetcher.py, ai_analyzer.py, briefing_saver.py, main.py, watchlist.txt
- 2026-05-05: Stage 1 config + docs created — .env.example, .gitignore, requirements.txt, README.md, PHILOSOPHY.md, JOURNAL.md
- 2026-05-05: Stage 1 fully complete. git repo initialized with initial commit.
- 2026-05-05: Bug fixes — replaced 4 dead/stale feeds (Moneycontrol x2, Business Standard, Reuters) with Hindu BusinessLine + CNBC TV18 + NDTV Profit; fixed source count display; fixed Rich markup eating [SourceName]; removed [:75] headline truncation in dry-run; added feed health summary to every run; added Windows UTF-8 encoding fix in main.py

## Key design decisions (helpful for Stage 2 planning)

- Deduplication threshold: 0.75 (constant DEDUP_SIMILARITY_THRESHOLD in rss_fetcher.py)
- AI model: gemini-2.0-flash (constant MODEL_NAME in ai_analyzer.py)
- Article data shape: {title, summary, link, published (datetime), sources (list[str]), watchlist_hits (list[str])}
- fetch_headlines() returns 3-tuple: (articles, symbols, feed_results) — feed_results has per-feed health data
- Briefing saved with YAML frontmatter header (date, mode, watchlist, count)
- ELI12 mode: CLI flag --eli12, appends ELI12_ADDON to system instruction
- Dry run mode: CLI flag --dry-run, skips AI call entirely
- Windows-primary setup; Mac/Linux alternatives noted in README
- Active feeds (as of 2026-05): Economic Times, Livemint, Hindu BusinessLine, CNBC TV18, NDTV Profit
- Dead feeds removed: Moneycontrol (stale since Apr 2024), Business Standard (broken XML), Reuters (URL dead since ~2020)

## Open questions / TODO

- Stage 2: decide data source for live NSE prices (yfinance? unofficial NSE API?)
- Stage 2: consider SQLite for storing price history locally (free, no server)