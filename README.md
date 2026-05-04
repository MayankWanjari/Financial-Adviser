# Indian Stock Market Research Tool — Stage 1: Daily Briefing

Run one command. Get a structured, AI-written market briefing in your terminal and saved as a markdown file. Powered by Google Gemini (free tier). No paid subscriptions needed.

---

## What this does

Every time you run `python main.py`, the tool:

1. **Fetches headlines** from 6 Indian financial news sources simultaneously:
   Moneycontrol, Economic Times, Livemint, Business Standard, Reuters Business

2. **Filters and deduplicates** — keeps only the last 24 hours, merges similar stories
   (and tracks how many outlets covered each one — a signal of importance)

3. **Sends everything to Gemini** — Google's free AI reads the headlines and writes
   a structured briefing covering market stories, sector impacts, global context,
   earnings, stocks to watch, and more

4. **Saves the briefing** as a dated markdown file (`briefings/YYYY-MM-DD.md`)
   and saves the raw data as JSON for your audit trail

5. **Prints the briefing** to your terminal with colors and formatting

---

## Setup (step by step for Windows)

### Prerequisites

- Python 3.10 or newer. Check with:
  ```
  python --version
  ```
  If Python isn't installed, download it from https://www.python.org/downloads/
  During installation, tick **"Add Python to PATH"**.

- A Google account (for the free Gemini API key)

---

### Step 1 — Download / clone the project

If you have git:
```powershell
git clone <your-repo-url>
cd financial-advisor-ai
```

Or just download and unzip the project folder.

---

### Step 2 — Create a virtual environment (recommended)

A virtual environment keeps this project's packages separate from your system Python.

```powershell
cd financial-advisor-ai
python -m venv .venv
.venv\Scripts\activate
```

Your terminal prompt will change to show `(.venv)` — that means it's active.

> **Mac/Linux:** Use `source .venv/bin/activate` instead of the last line.

---

### Step 3 — Install dependencies

```powershell
pip install -r requirements.txt
```

This installs: feedparser, google-generativeai, python-dotenv, rich.

---

### Step 4 — Get a free Gemini API key

1. Go to **https://aistudio.google.com/app/apikey**
2. Sign in with your Google account
3. Click **"Create API Key"**
4. Copy the key (it starts with `AIza...`)

---

### Step 5 — Create your `.env` file

1. In the project root folder, find the file called `.env.example`
2. Copy it and rename the copy to `.env` (no `.example` at the end)

   In PowerShell:
   ```powershell
   Copy-Item .env.example .env
   ```

3. Open `.env` in your editor and replace `your_key_here` with your actual API key:
   ```
   GEMINI_API_KEY=AIzaSyABC123...your_actual_key_here
   ```

4. Save the file. **Never share this file or commit it to git** — it's already in `.gitignore`.

---

### Step 6 — Run it!

```powershell
cd stage1_news
python main.py
```

You should see progress messages, then the full briefing printed to your terminal.
A saved copy appears in `stage1_news/briefings/`.

---

## Usage

### Normal briefing
```powershell
python main.py
```

### ELI12 mode — explains everything simply
```powershell
python main.py --eli12
```
Good for when you encounter unfamiliar topics. Uses plain language and analogies.

### Dry run — test the fetcher without using the AI
```powershell
python main.py --dry-run
```
Fetches and deduplicates headlines but stops before calling Gemini. Useful for:
- Checking that your internet connection and RSS feeds work
- Debugging without spending your free API quota

### Combine flags
```powershell
python main.py --eli12 --dry-run
```

---

## Customizing your watchlist

Open `stage1_news/watchlist.txt` in your editor. Replace the example stocks with
the ones you actually follow. Use NSE symbols (uppercase, no spaces):

```
WIPRO
BAJFINANCE
LTIM
NESTLEIND
```

The AI will give these stocks their own section (**⭐ Your Watchlist News**) if
any of them appear in today's headlines.

**If your stock isn't being recognized:** Its name in news headlines might differ
from its NSE symbol. Open `stage1_news/rss_fetcher.py` and find `SYMBOL_NAME_MAP`.
Add an entry like:

```python
"BAJFINANCE": ["Bajaj Finance", "BAF"],
```

---

## Output files

| File | What it is |
|------|-----------|
| `stage1_news/briefings/YYYY-MM-DD.md` | Your daily briefing. Open in VS Code or any markdown viewer. |
| `stage1_news/raw_headlines/YYYY-MM-DD.json` | The raw headlines the AI was given. Good for fact-checking. |

If you run the script twice in one day, the second file gets a `-2` suffix, etc.

---

## Troubleshooting

### "GEMINI_API_KEY not found"
- Make sure `.env` exists in the project root (not `.env.example`)
- Make sure the key is on the line: `GEMINI_API_KEY=AIza...`
- Make sure there are no spaces around the `=`

### "No articles found in the last 24 hours"
- Try again — feeds are sometimes slow to update
- This can happen on weekends or market holidays
- Run `python main.py --dry-run` to check if the fetcher is working

### Gemini API errors / "model not available"
The model name is set at the top of `stage1_news/ai_analyzer.py`:
```python
MODEL_NAME = "gemini-2.0-flash"
```
If this model becomes unavailable on the free tier, swap it for one of these:

| Model name | Notes |
|---|---|
| `gemini-1.5-flash` | Older, very reliable, still free |
| `gemini-1.5-flash-8b` | Smallest and fastest, good for testing |
| `gemini-2.0-flash-lite` | Lighter version of 2.0-flash, also free |

Check currently available models at: https://aistudio.google.com/

### "Rate limit exceeded"
The free tier has daily limits. If you hit them, wait until the next day (limits reset at midnight Pacific time). To reduce usage, use `--dry-run` when just testing.

### A feed keeps failing
If one of the 6 sources gives repeated warnings, it may have changed its RSS URL.
Check the URL in `stage1_news/rss_fetcher.py` (look for the `FEEDS` list).
One failing feed doesn't break the tool — the other 5 continue normally.

### pip install fails
Try removing the version numbers from `requirements.txt` and running again:
```powershell
pip install feedparser google-generativeai python-dotenv rich
```

### `.venv\Scripts\activate` gives an error about execution policy
Run this in PowerShell (one time only):
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```
Then try activating again.

---

## What's coming in later stages

| Stage | What it adds |
|---|---|
| **Stage 2** | Pull live price data for your watchlist (NSE/BSE via free APIs) |
| **Stage 3** | Stock screener — filter by PE ratio, ROE, debt, etc. |
| **Stage 4** | Ask questions to a library of investing books (RAG system) |
| **Stage 5** | Web dashboard (Streamlit) — see everything in a browser |

Each stage builds on the previous one. Stage 1 output feeds into Stage 2, and so on.
