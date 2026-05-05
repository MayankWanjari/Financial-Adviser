"""
ai_analyzer.py — Send headlines to Google Gemini and get back a structured briefing.

This module owns ALL AI-related logic for Stage 1. The things you're most likely
to want to edit here are:
  - MODEL_NAME         if you need to swap to a different free-tier model
  - SYSTEM_INSTRUCTION if you want to change the briefing structure or tone
  - ELI12_ADDON        if you want to tweak the "explain like I'm 12" override

Nothing in this file fetches RSS or writes files — it just takes headlines in
and returns a markdown string out.
"""

import os
import sys

import google.generativeai as genai  # pip install google-generativeai
from dotenv import load_dotenv       # pip install python-dotenv

# ─── Model configuration ──────────────────────────────────────────────────────
#
# Primary: gemini-2.5-flash (recommended, 500 RPD free tier)
# Alternatives if quota hit:
#   - gemini-2.5-flash-lite (1000 RPD, lower quality)
#   - gemini-1.5-flash (older but reliable)
# Avoid: gemini-2.0-flash (retiring March 2026)
#
# You can check which models are available at: https://aistudio.google.com/
MODEL_NAME = "gemini-2.5-flash"

# ─── System instruction ───────────────────────────────────────────────────────
#
# This is the "job description" we give the AI before it reads any headlines.
# It tells Gemini exactly what format to produce, what tone to use, and what
# NOT to do (no buy/sell calls). Edit this carefully — small wording changes
# can have a large effect on the output.
#
SYSTEM_INSTRUCTION = """You are a senior research analyst (NOT a financial advisor) producing a daily briefing for an Indian retail investor who is learning. Your job is to organize information clearly so the user can think — not to give buy/sell calls. Never recommend specific buy/sell actions.

Produce a markdown briefing with these sections in this exact order:

1. ## 📰 Top 7 Stories of the Day
   - Ranked by likely market impact, not by source
   - Each: bold one-line headline + 2–3 line explanation of WHY it matters and which sectors it affects
   - Note if a story appeared in multiple sources (signal of importance)

2. ## 🏭 Sector Impact
   - Special callouts for IT, Banking, Auto (user's interest sectors)
   - Plus any other sector with major news today
   - Format: sector name, what happened, likely direction of impact

3. ## 🌍 Global Context
   - US Fed, oil, China, USD/INR — anything affecting Indian markets
   - Skip this section entirely if nothing relevant today

4. ## 🏦 RBI / Regulatory
   - RBI announcements, SEBI rulings, policy news
   - Skip this section entirely if nothing relevant

5. ## 💰 FII/DII Activity
   - Foreign and domestic institutional flows if reported
   - Skip this section entirely if nothing relevant

6. ## 📊 Earnings Highlights
   - Notable results, guidance changes, profit warnings

7. ## 👀 Stocks To Watch
   - Names that came up repeatedly (for good or bad reasons)
   - For each: stock name, why it's in the news, sentiment (positive/negative/mixed)

8. ## ⭐ Your Watchlist News
   - News specifically about the user's watchlist stocks (the list is provided in the prompt)
   - Skip this section entirely if no watchlist stocks appeared in today's headlines

9. ## 🤔 Skeptic's Corner
   - What could be wrong with today's prevailing narrative?
   - What's NOT being talked about that maybe should be?
   - Steelman the bear case for any bullish story above, and the bull case for any bearish story
   - THIS SECTION IS CRITICAL — never skip it, even if the news seems uniformly positive

10. ## 📚 Jargon Decoded
    - Pick 2–3 financial terms that appeared in today's briefing
    - Explain each in plain English, in 2–3 sentences

End the briefing with this exact line:
⚠️ This is research, not advice. Decide for yourself. Paper-trade ideas before risking real money.

Tone rules (follow these carefully):
  - Clear, calm, and beginner-friendly
  - Explain any financial jargon the first time you use it
  - Never make price predictions
  - Never say "will rise", "will fall", "expected to reach X" — say instead:
    "could face pressure", "may benefit depending on...", "worth watching if..."

Numerical accuracy (follow these carefully):
  - When different sources report different numbers for the same event, report the RANGE
    or the most commonly cited value — never cherry-pick the highest or most dramatic figure
  - Example: if sources say Brent was $112, $114, and $115, write
    "Brent traded between $112–115, mostly cited near $114" — not "Brent touched $115"
  - Apply this to any figure: index levels, FII flows, earnings numbers, rate changes
  - Always lean toward sober, conservative reporting over drama
"""

# ─── ELI12 addon ──────────────────────────────────────────────────────────────
#
# This text is appended to SYSTEM_INSTRUCTION when --eli12 is passed.
# It overrides the tone to be suitable for a complete beginner.
#
ELI12_ADDON = """
IMPORTANT TONE OVERRIDE — ELI12 MODE IS ACTIVE:
Write everything as if explaining to a curious 12-year-old who has never heard of the stock market before.
  - Use everyday analogies (e.g., "the stock market is like a giant shop where people buy and sell tiny pieces of companies")
  - Avoid all jargon; if a financial term absolutely must appear, explain it immediately in brackets
  - Keep sentences short
  - It's okay to be a little playful — this should feel like a knowledgeable older sibling explaining, not a textbook
"""


# ─── Internal helpers ─────────────────────────────────────────────────────────


def _build_prompt(
    articles: list[dict],
    symbols: list[str],
    symbol_name_map: dict[str, list[str]],
) -> str:
    """
    Build the text prompt that gets sent to Gemini alongside the system instruction.

    The prompt has two parts:
      1. The user's watchlist (so the AI knows what to look for in section 8)
      2. All the headlines, numbered, with source names and summaries

    The system instruction (the briefing format rules) is sent separately as a
    system-level message, not as part of this prompt text.
    """
    # ── Part 1: Watchlist ─────────────────────────────────────────────────────
    if symbols:
        watchlist_lines = []
        for sym in symbols:
            # Include alternate names so AI can match "Tata Consultancy" as TCS, etc.
            names = symbol_name_map.get(sym, [sym])
            watchlist_lines.append(f"  - {sym} (also watch for: {', '.join(names)})")
        watchlist_section = "USER WATCHLIST SYMBOLS:\n" + "\n".join(watchlist_lines)
    else:
        watchlist_section = "USER WATCHLIST SYMBOLS: (none loaded — skip section 8)"

    # ── Part 2: Headlines ─────────────────────────────────────────────────────
    headline_blocks = []
    for i, article in enumerate(articles, start=1):
        source_count = len(article["sources"])
        sources_str  = ", ".join(article["sources"])
        # Tell the AI how many sources covered this story — it uses this for ranking
        source_note  = f"[{source_count} source{'s' if source_count > 1 else ''}: {sources_str}]"

        watchlist_note = ""
        if article.get("watchlist_hits"):
            watchlist_note = f" ⭐ WATCHLIST MATCH: {', '.join(article['watchlist_hits'])}"

        # Truncate summaries at 300 chars to keep the prompt a reasonable size
        summary = article.get("summary", "") or ""
        if len(summary) > 300:
            summary = summary[:297] + "..."

        headline_blocks.append(
            f"{i}. {article['title']}{watchlist_note}\n"
            f"   Coverage: {source_note}\n"
            f"   Summary: {summary or '(no summary available)'}\n"
        )

    headlines_section = (
        f"TODAY'S HEADLINES ({len(articles)} unique stories after deduplication):\n\n"
        + "\n".join(headline_blocks)
    )

    return f"{watchlist_section}\n\n{headlines_section}\n\nPlease produce the full briefing as specified."


# ─── Public API ───────────────────────────────────────────────────────────────


def analyze_headlines(
    articles: list[dict],
    symbols: list[str],
    symbol_name_map: dict[str, list[str]],
    eli12_mode: bool = False,
) -> str | None:
    """
    Send the collected headlines to Gemini and return the AI briefing as a string.

    Args:
        articles:        Deduplicated, tagged article list from rss_fetcher.fetch_headlines()
        symbols:         Watchlist symbols (e.g., ["RELIANCE", "TCS"])
        symbol_name_map: Dict of symbol → alternate name list (from rss_fetcher.SYMBOL_NAME_MAP)
        eli12_mode:      If True, appends the ELI12 tone override to the system instruction

    Returns:
        The AI-generated briefing as a markdown-formatted string, or None if the
        Gemini quota was exceeded (the quota error message is already printed).

    Raises:
        SystemExit(1): If the API key is missing or a non-quota API error occurs.
                       Exits with a friendly error message instead of a stack trace.
    """
    # ── Step 1: Load the API key from .env ────────────────────────────────────
    load_dotenv()  # Reads .env file in the current working directory
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        # Give a clear, actionable error message — not a cryptic KeyError
        print("\n❌  GEMINI_API_KEY not found.")
        print("    To fix this:")
        print("    1. Copy .env.example to .env  (in the project root folder)")
        print("    2. Get a free key at https://aistudio.google.com/app/apikey")
        print("    3. Open .env and change: GEMINI_API_KEY=your_key_here")
        print("       to use your actual key.\n")
        sys.exit(1)

    # ── Step 2: Configure the Gemini client ───────────────────────────────────
    genai.configure(api_key=api_key)

    # Build the system instruction (optionally with ELI12 tone override)
    system_instr = SYSTEM_INSTRUCTION + (ELI12_ADDON if eli12_mode else "")

    # Create the model instance with our system instruction "baked in"
    model = genai.GenerativeModel(
        model_name=MODEL_NAME,
        system_instruction=system_instr,
    )

    # ── Step 3: Build the prompt and call the API ─────────────────────────────
    prompt = _build_prompt(articles, symbols, symbol_name_map)

    try:
        response = model.generate_content(prompt)

        # response.text is a shortcut to the first candidate's text.
        # It will raise ValueError if the response was blocked by safety filters.
        briefing_text = response.text

        if not briefing_text or not briefing_text.strip():
            print("\n❌  Gemini returned an empty response.")
            print("    This sometimes happens when the safety filter blocks content.")
            print("    Try running again — it's usually transient.\n")
            sys.exit(1)

        return briefing_text

    except ValueError as exc:
        # Safety filter blocked the response
        print(f"\n❌  Gemini's safety filter blocked the response: {exc}")
        print("    This is unusual for financial news. Try running again.\n")
        sys.exit(1)

    except Exception as exc:
        # Check specifically for quota / rate-limit errors (HTTP 429)
        exc_text = str(exc)
        is_quota_error = (
            "429" in exc_text
            or "resource_exhausted" in exc_text.lower()
            or "quota" in exc_text.lower()
            or "rateLimitExceeded" in exc_text
        )

        if is_quota_error:
            from datetime import datetime, timezone as _tz
            now_utc = datetime.now(_tz.utc)
            # Free-tier daily quotas typically reset around midnight Pacific Time (~08:00 UTC)
            hours_left = (8 - now_utc.hour) % 24 or 24

            print(f"\n❌  Gemini quota exceeded.")
            print("    Possible causes:")
            print(f"    - You hit today's free-tier daily limit (resets in ~{hours_left} hours)")
            print("    - Your project doesn't have Generative Language API enabled")
            print(f"    - The model '{MODEL_NAME}' isn't available on free tier in your region")
            print()
            print("    Try:")
            print("    1. Wait 1 minute and run again (per-minute rate limit)")
            print("    2. Verify your API key at https://aistudio.google.com/app/apikey")
            print(f"    3. Alternative models: change MODEL_NAME in ai_analyzer.py to")
            print("       'gemini-1.5-flash' or 'gemini-2.5-flash'")
            print()
            # Return None so main.py can save raw headlines before exiting
            return None

        # All other errors: network issues, invalid key, bad model name, etc.
        print(f"\n❌  Gemini API call failed: {exc}")
        print(f"    Model used: {MODEL_NAME}")
        print("    Things to check:")
        print("    - Is your internet connection working?")
        print("    - Is your API key correct in the .env file?")
        print(f"    - If '{MODEL_NAME}' is unavailable, change MODEL_NAME at the top")
        print("      of ai_analyzer.py to one of the alternatives listed there.")
        print("    - Free tier has daily limits — try again tomorrow if you hit them.\n")
        sys.exit(1)
