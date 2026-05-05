"""
main.py — Entry point for the Stage 1 daily market briefing.

This script orchestrates the whole pipeline:
  1. Parse command-line flags
  2. Fetch + filter + deduplicate headlines  (rss_fetcher.py)
  3. Analyze with Google Gemini             (ai_analyzer.py)
  4. Save files + print to terminal         (briefing_saver.py)

USAGE:
  python main.py              Normal briefing
  python main.py --eli12      Explain everything like I'm 12 years old
  python main.py --dry-run    Fetch headlines but skip the AI call (for testing)

Run from inside the stage1_news/ folder, or from the project root:
  cd stage1_news
  python main.py

  OR from project root:
  python stage1_news/main.py
"""

import argparse
import sys

# ── Windows UTF-8 fix ─────────────────────────────────────────────────────────
# Without this, emojis in console.print() crash on Windows terminals that use
# the cp1252 encoding (the default on many Windows systems).
# Must run before any library (including rich) writes to stdout.
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from pathlib import Path

from rich.console import Console  # pip install rich

# ── Import our own modules ────────────────────────────────────────────────────
# These files must be in the same directory as this script (stage1_news/).
from rss_fetcher import fetch_headlines, SYMBOL_NAME_MAP
from ai_analyzer import analyze_headlines
from briefing_saver import save_briefing, save_raw_headlines

console = Console()

# ── Path constants ────────────────────────────────────────────────────────────
# __file__ is the path to THIS script. .parent is the folder it lives in.
# Everything is relative to stage1_news/ so the script works no matter where
# you run it from.
SCRIPT_DIR     = Path(__file__).parent   # = .../financial-advisor-ai/stage1_news/
WATCHLIST_PATH = SCRIPT_DIR / "watchlist.txt"


def parse_args() -> argparse.Namespace:
    """
    Parse and return command-line arguments.

    Returns an object where:
      args.eli12    → True if --eli12 was passed
      args.dry_run  → True if --dry-run was passed
    """
    parser = argparse.ArgumentParser(
        description="Indian stock market daily briefing — powered by Google Gemini",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                Run the full briefing
  python main.py --eli12        Explain everything in plain language
  python main.py --dry-run      Test headline fetching without using the AI
  python main.py --eli12 --dry-run  Combine flags
        """,
    )
    parser.add_argument(
        "--eli12",
        action="store_true",  # presence of the flag sets this to True
        help="ELI12 mode: write the briefing as if explaining to a 12-year-old",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        dest="dry_run",  # --dry-run → args.dry_run (Python can't use hyphens in var names)
        help="Fetch and deduplicate headlines but skip the Gemini AI call",
    )
    return parser.parse_args()


def _print_feed_health(feed_results: list[dict]) -> None:
    """
    Print a one-line status for each RSS feed.

    Three possible states per feed:
      ✅ Working   — connected and returned fresh articles
      ⚠️ Stale     — connected OK but 0 articles within the last 24 hours
      ❌ Failed    — network error, dead URL, or completely broken XML

    This runs at the end of every dry-run and full run so you always know
    which feeds are healthy without having to dig through warning messages.
    """
    console.print()
    console.rule("[bold]Feed Health[/bold]")

    # Sort: working first (by fresh_count desc), then stale, then failed
    def _sort_key(r: dict) -> tuple:
        if not r["success"]:
            return (2, 0)           # Failed — last
        if r["fresh_count"] == 0:
            return (1, 0)           # Stale — middle
        return (0, -r["fresh_count"])  # Working — first, most articles at top

    for r in sorted(feed_results, key=_sort_key):
        source = r["source"]
        if not r["success"]:
            # Shorten the error to the exception type only (e.g., "URLError", "SAXParseException")
            exc_type = (r["error"] or "unknown error").split(":")[0]
            console.print(f"  [red]❌ {source}[/red] — FAILED ({exc_type})")
            # Print the URL on the next line so you know what to fix or replace
            console.print(f"       {r['url']}", markup=False)
        elif r["fresh_count"] == 0:
            console.print(
                f"  [yellow]⚠  {source}[/yellow] — connected but 0 articles in last 24h "
                f"({r['raw_count']} total in feed)"
            )
        else:
            console.print(
                f"  [green]✅ {source}[/green] — "
                f"{r['fresh_count']} fresh articles"
            )

    console.print()


def main() -> None:
    """
    Run the full briefing pipeline. Called when you run `python main.py`.

    Exits with sys.exit(1) on unrecoverable errors, always with a friendly
    message explaining what went wrong and how to fix it.
    """
    args = parse_args()

    # ── Step 1: Fetch headlines ───────────────────────────────────────────────
    console.print()
    console.print("[bold cyan]📡 Fetching headlines from news sources...[/bold cyan]")

    try:
        # fetch_headlines now returns three values:
        #   articles     — the cleaned, deduped, tagged article list
        #   symbols      — your watchlist stock symbols
        #   feed_results — per-feed health data (used for the health summary below)
        articles, symbols, feed_results = fetch_headlines(WATCHLIST_PATH)
    except Exception as exc:
        console.print(f"\n[bold red]❌ Could not fetch headlines: {exc}[/bold red]")
        console.print("   → Check your internet connection and try again.")
        console.print("   → If the problem persists, one of the RSS feed URLs may have changed.")
        console.print("     Open rss_fetcher.py and look for the FEEDS list to verify the URLs.\n")
        sys.exit(1)

    # ── Check: did we get anything? ───────────────────────────────────────────
    if not articles:
        console.print()
        console.print("[yellow]⚠️  No articles found in the last 24 hours.[/yellow]")
        console.print("   This can happen when:")
        console.print("   - The feeds are slow to update (try again in a few hours)")
        console.print("   - All news is older than 24h (unusual but possible on weekends)")
        console.print("   - All feeds returned errors (check feed health below)")
        _print_feed_health(feed_results)  # Show why nothing was found
        sys.exit(0)

    # ── Report what we found ──────────────────────────────────────────────────
    # Count how many feeds actually contributed at least one fresh article.
    # This is different from len(FEEDS) — some feeds may have failed or been stale.
    feeds_with_data = sum(1 for r in feed_results if r["fresh_count"] > 0)
    total_feeds     = len(feed_results)
    watchlist_count = sum(1 for a in articles if a.get("watchlist_hits"))
    multi_source    = sum(1 for a in articles if len(a.get("sources", [])) > 1)

    console.print(
        f"[green]✅ Found {len(articles)} unique headlines[/green] "
        f"({feeds_with_data}/{total_feeds} feeds active, "
        f"{multi_source} stories covered by multiple sources)"
    )

    if symbols:
        console.print(f"   Watchlist: {', '.join(symbols)}")
        console.print(f"   Watchlist hits in today's news: {watchlist_count} article(s)")
    else:
        console.print("   [yellow]No watchlist loaded — edit stage1_news/watchlist.txt[/yellow]")

    # ── Step 2: Dry run — stop here if --dry-run was passed ──────────────────
    if args.dry_run:
        console.print()
        console.rule("[bold yellow]🔍 DRY RUN — Skipping AI analysis[/bold yellow]")
        console.print(f"\n   Would send {len(articles)} headlines to Gemini. First 15:\n")

        for article in articles[:15]:
            sources = ", ".join(article["sources"])
            wl_tag  = " ⭐" if article.get("watchlist_hits") else ""

            # markup=False on both lines prevents Rich from interpreting
            # [SourceName] as a markup tag and eating it silently.
            console.print(f"   • {article['title']}{wl_tag}", markup=False)
            console.print(f"     [{sources}]", markup=False)

        if len(articles) > 15:
            console.print(f"\n   ... and {len(articles) - 15} more headlines.")

        # Feed health is especially useful in dry-run (no other output to check)
        _print_feed_health(feed_results)
        console.rule("[bold yellow]Dry run complete[/bold yellow]")
        console.print()
        return  # Exit without calling the AI

    # ── Step 3: Analyze with Gemini ───────────────────────────────────────────
    mode_label = "[bold magenta]ELI12 mode[/bold magenta]" if args.eli12 else "normal mode"
    console.print()
    console.print(f"[bold cyan]🤖 Analyzing with Gemini ({mode_label})...[/bold cyan]")
    console.print("   Sending headlines to Google's AI. This usually takes 10–30 seconds.")
    console.print("   [dim](The AI is reading all the headlines and writing your briefing)[/dim]")

    # analyze_headlines() handles its own error messages and calls sys.exit(1) on failure.
    # For quota errors specifically, it returns None so we can save raw headlines first.
    briefing_text = analyze_headlines(
        articles        = articles,
        symbols         = symbols,
        symbol_name_map = SYMBOL_NAME_MAP,
        eli12_mode      = args.eli12,
    )

    if briefing_text is None:
        # Quota exceeded — save raw headlines so the day's data isn't lost
        console.print()
        console.print("[yellow]💾 Saving raw headlines so today's data isn't lost...[/yellow]")
        raw_path = save_raw_headlines(articles=articles, symbols=symbols, base_dir=SCRIPT_DIR)
        console.print(f"   Saved → {raw_path}")
        console.print("   Once quota resets, re-run the same command to generate the briefing.")
        _print_feed_health(feed_results)
        sys.exit(1)

    console.print("[green]✅ AI analysis complete.[/green]")

    # ── Step 4: Save files and print the briefing ─────────────────────────────
    briefing_path, raw_path = save_briefing(
        briefing_text = briefing_text,
        articles      = articles,
        symbols       = symbols,
        base_dir      = SCRIPT_DIR,
        eli12_mode    = args.eli12,
    )

    # Final summary
    console.print("[bold green]💾 Files saved:[/bold green]")
    console.print(f"   Briefing  → {briefing_path}")
    console.print(f"   Raw data  → {raw_path}")
    console.print()
    console.print(
        "[dim]Tip: Open the .md file in VS Code (or any markdown viewer) "
        "for nicely formatted output.[/dim]"
    )

    # Always show feed health at the end of a full run too
    _print_feed_health(feed_results)


# ── Script entry point ────────────────────────────────────────────────────────
# This block only runs when you execute the file directly (python main.py).
# It does NOT run when another file imports main.py as a module.
if __name__ == "__main__":
    main()
