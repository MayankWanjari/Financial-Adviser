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
from pathlib import Path

from rich.console import Console  # pip install rich

# ── Import our own modules ────────────────────────────────────────────────────
# These files must be in the same directory as this script (stage1_news/).
from rss_fetcher import fetch_headlines, SYMBOL_NAME_MAP
from ai_analyzer import analyze_headlines
from briefing_saver import save_briefing

console = Console()

# ── Path constants ────────────────────────────────────────────────────────────
# __file__ is the path to THIS script. .parent is the folder it lives in.
# Everything is relative to stage1_news/ so the script works no matter where
# you run it from.
SCRIPT_DIR    = Path(__file__).parent   # = .../financial-advisor-ai/stage1_news/
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


def main() -> None:
    """
    Run the full briefing pipeline. Called when you run `python main.py`.

    Exits with sys.exit(1) on unrecoverable errors, always with a friendly
    message explaining what went wrong and how to fix it.
    """
    args = parse_args()

    # ── Step 1: Fetch headlines ───────────────────────────────────────────────
    console.print()
    console.print("[bold cyan]📡 Fetching headlines from 6 news sources...[/bold cyan]")

    try:
        articles, symbols = fetch_headlines(WATCHLIST_PATH)
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
        console.print("   - All feeds returned errors (check your internet connection)")
        console.print()
        sys.exit(0)

    # ── Report what we found ──────────────────────────────────────────────────
    watchlist_count = sum(1 for a in articles if a.get("watchlist_hits"))
    multi_source    = sum(1 for a in articles if len(a.get("sources", [])) > 1)

    console.print(f"[green]✅ Found {len(articles)} unique headlines[/green] "
                  f"(from {len(set(s for a in articles for s in a['sources']))} sources, "
                  f"{multi_source} covered by multiple outlets)")

    if symbols:
        console.print(f"   Watchlist: {', '.join(symbols)}")
        console.print(f"   Watchlist hits in today's news: {watchlist_count} article(s)")
    else:
        console.print("   [yellow]No watchlist loaded — edit stage1_news/watchlist.txt[/yellow]")

    # ── Step 2: Dry run — stop here if --dry-run was passed ──────────────────
    if args.dry_run:
        console.print()
        console.rule("[bold yellow]🔍 DRY RUN — Skipping AI analysis[/bold yellow]")
        console.print(f"\n   Would send {len(articles)} headlines to Gemini. Sample:\n")

        # Show first 10 headlines so you can verify the fetcher is working
        for article in articles[:10]:
            sources = ", ".join(article["sources"])
            wl_tag  = " ⭐" if article.get("watchlist_hits") else ""
            console.print(f"   • {article['title'][:75]}{wl_tag}")
            console.print(f"     [{sources}]")

        if len(articles) > 10:
            console.print(f"\n   ... and {len(articles) - 10} more headlines.")

        console.print()
        console.rule("[bold yellow]Dry run complete[/bold yellow]")
        console.print()
        return  # Exit without calling the AI

    # ── Step 3: Analyze with Gemini ───────────────────────────────────────────
    mode_label = "[bold magenta]ELI12 mode[/bold magenta]" if args.eli12 else "normal mode"
    console.print()
    console.print(f"[bold cyan]🤖 Analyzing with Gemini ({mode_label})...[/bold cyan]")
    console.print("   Sending headlines to Google's AI. This usually takes 10–30 seconds.")
    console.print("   [dim](The AI is reading all the headlines and writing your briefing)[/dim]")

    # analyze_headlines() handles its own error messages and calls sys.exit(1) on failure
    briefing_text = analyze_headlines(
        articles       = articles,
        symbols        = symbols,
        symbol_name_map = SYMBOL_NAME_MAP,
        eli12_mode     = args.eli12,
    )

    console.print("[green]✅ AI analysis complete.[/green]")

    # ── Step 4: Save files and print the briefing ─────────────────────────────
    briefing_path, raw_path = save_briefing(
        briefing_text = briefing_text,
        articles      = articles,
        symbols       = symbols,
        base_dir      = SCRIPT_DIR,
        eli12_mode    = args.eli12,
    )

    # Final summary — tell the user where to find their files
    console.print("[bold green]💾 Files saved:[/bold green]")
    console.print(f"   Briefing  → {briefing_path}")
    console.print(f"   Raw data  → {raw_path}")
    console.print()
    console.print("[dim]Tip: Open the .md file in VS Code (or any markdown viewer) for "
                  "nicely formatted output.[/dim]")
    console.print()


# ── Script entry point ────────────────────────────────────────────────────────
# This block only runs when you execute the file directly (python main.py).
# It does NOT run when another file imports main.py as a module.
if __name__ == "__main__":
    main()
