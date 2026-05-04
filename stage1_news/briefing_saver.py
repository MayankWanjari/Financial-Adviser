"""
briefing_saver.py — Save the AI briefing to files and print it to the terminal.

Two files are saved on every run:
  1. stage1_news/briefings/YYYY-MM-DD.md
       The AI's formatted markdown briefing with a metadata header.
       Open this file in any markdown viewer (VS Code, Obsidian, GitHub, etc.)
       for a nicely formatted reading experience.

  2. stage1_news/raw_headlines/YYYY-MM-DD.json
       The raw article data that was sent to the AI — your audit trail.
       If the AI's briefing ever seems off or you want to fact-check it,
       open this file to see exactly what information it was given.

If you run the script more than once on the same day, files get a suffix:
  briefings/2024-01-15.md  →  briefings/2024-01-15-2.md  →  -3.md  etc.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console    # pip install rich
from rich.markdown import Markdown  # part of rich

# A single Console instance — reused across calls for consistent formatting
console = Console()


def _next_available_path(directory: Path, date_str: str, extension: str) -> Path:
    """
    Return a file path that doesn't already exist in 'directory'.

    Tries: YYYY-MM-DD.ext, then YYYY-MM-DD-2.ext, YYYY-MM-DD-3.ext, etc.

    Args:
        directory:  The folder to check (e.g., briefings/)
        date_str:   Today's date as "YYYY-MM-DD"
        extension:  File extension without dot (e.g., "md" or "json")

    Returns:
        A Path object pointing to a filename that does not yet exist.
    """
    # First attempt: plain date filename
    candidate = directory / f"{date_str}.{extension}"
    if not candidate.exists():
        return candidate

    # Already exists — find the next available numbered suffix
    counter = 2
    while True:
        candidate = directory / f"{date_str}-{counter}.{extension}"
        if not candidate.exists():
            return candidate
        counter += 1


def save_briefing(
    briefing_text: str,
    articles: list[dict],
    symbols: list[str],
    base_dir: Path,
    eli12_mode: bool = False,
) -> tuple[Path, Path]:
    """
    Save the AI briefing and raw headlines, then print the briefing to terminal.

    Args:
        briefing_text: The markdown string returned by ai_analyzer.analyze_headlines()
        articles:      The list of article dicts that were sent to the AI
        symbols:       The watchlist symbols used in this run
        base_dir:      The stage1_news/ directory. briefings/ and raw_headlines/
                       will be created inside it if they don't exist.
        eli12_mode:    Whether ELI12 mode was active (recorded in the file header)

    Returns:
        A tuple of (briefing_path, raw_path) — the two files that were saved.
        main.py uses these to tell you where to find your files.
    """
    # ── Create output directories (safe — does nothing if they already exist) ──
    briefings_dir = base_dir / "briefings"
    raw_dir       = base_dir / "raw_headlines"
    briefings_dir.mkdir(exist_ok=True)
    raw_dir.mkdir(exist_ok=True)

    # ── Timestamp for filenames and headers ───────────────────────────────────
    now_utc  = datetime.now(timezone.utc)
    date_str = now_utc.strftime("%Y-%m-%d")
    time_str = now_utc.strftime("%H:%M UTC")
    mode_str = "ELI12" if eli12_mode else "Normal"

    # ── 1. Save the markdown briefing ────────────────────────────────────────
    briefing_path = _next_available_path(briefings_dir, date_str, "md")

    # A YAML-style frontmatter header so you always know when/how a briefing was made
    header = (
        "---\n"
        f"date: {date_str}\n"
        f"generated_at: {time_str}\n"
        f"mode: {mode_str}\n"
        f"watchlist: {', '.join(symbols) if symbols else 'none'}\n"
        f"headlines_analyzed: {len(articles)}\n"
        "---\n\n"
    )

    briefing_path.write_text(header + briefing_text, encoding="utf-8")

    # ── 2. Save the raw JSON audit trail ─────────────────────────────────────
    raw_path = _next_available_path(raw_dir, date_str, "json")

    # datetime objects can't be serialized to JSON by default, so convert them
    serializable_articles = []
    for article in articles:
        entry = article.copy()
        entry["published"] = entry["published"].isoformat()  # e.g., "2024-01-15T08:30:00+00:00"
        serializable_articles.append(entry)

    raw_data = {
        "generated_at":    now_utc.isoformat(),
        "mode":            mode_str,
        "watchlist":       symbols,
        "article_count":   len(articles),
        "articles":        serializable_articles,
    }

    raw_path.write_text(
        json.dumps(raw_data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # ── 3. Print the briefing to the terminal ─────────────────────────────────
    # rich's Markdown renderer gives you nicely formatted output with colors,
    # bold headers, bullet points, etc. — much nicer than raw markdown text.
    console.print()
    console.rule("[bold cyan]📊 Daily Market Briefing[/bold cyan]")
    console.print()
    console.print(Markdown(briefing_text))
    console.print()
    console.rule("[bold cyan]End of Briefing[/bold cyan]")
    console.print()

    return briefing_path, raw_path
