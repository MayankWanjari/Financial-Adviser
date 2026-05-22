"""
data/peers.py — Sector peer comparison for Indian stocks.

Answers: "How does this stock compare to its sector peers on fundamentals?"

Loads sector groupings from config/sector_peers.json, scores every stock in the
sector using the same 0-100 scorer as score_stock(), and ranks them.

All functions return dicts/tuples — no printing, no sys.exit().
"""

import json
import time
from pathlib import Path

from data import scorer

_PROJECT_ROOT      = Path(__file__).parent.parent
_SECTOR_PEERS_PATH = _PROJECT_ROOT / "config" / "sector_peers.json"
_FETCH_DELAY_SECS  = 1.0


def _load_sector_map() -> dict[str, list[str]]:
    """Load and return the full sector → tickers mapping from sector_peers.json."""
    if not _SECTOR_PEERS_PATH.exists():
        raise FileNotFoundError(
            f"Sector peers config not found: {_SECTOR_PEERS_PATH}"
        )
    return json.loads(_SECTOR_PEERS_PATH.read_text(encoding="utf-8"))


def get_sector_peers(ticker: str) -> tuple[str, list[str]]:
    """
    Find the sector a ticker belongs to and return its peers.

    Args:
        ticker: NSE ticker without .NS suffix, e.g. 'TCS'.

    Returns:
        (sector_name, peer_tickers) where peer_tickers excludes the input ticker.
        If ticker is not in any sector, returns ("Unknown", []).

    Raises:
        FileNotFoundError: If config/sector_peers.json does not exist.
    """
    ticker = ticker.strip().upper()
    sector_map = _load_sector_map()

    for sector, tickers in sector_map.items():
        if ticker in [t.upper() for t in tickers]:
            peers = [t.upper() for t in tickers if t.upper() != ticker]
            return sector, peers

    return "Unknown", []


def compare_with_peers(ticker: str) -> dict:
    """
    Score a stock and all its sector peers, then rank by fundamental score.

    Fetches live data for the target and each peer (with a 1-second delay between
    calls to avoid Yahoo Finance rate-limiting). Stocks that fail to fetch are
    skipped silently.

    Args:
        ticker: NSE ticker without .NS suffix, e.g. 'TCS'.

    Returns:
        A dict with:
            target           (dict)  — full score_stock() result for the input ticker
            peers            (list)  — list of score_stock() dicts for sector peers,
                                       sorted by total_score descending (best first)
            sector           (str)   — sector name, e.g. "IT"
            target_rank      (int)   — 1-based rank among all sector stocks
            total_in_sector  (int)   — number of stocks successfully scored
            comparison_summary (str) — plain-English rank statement

    Raises:
        ValueError:      If ticker not found on Yahoo Finance.
        ConnectionError: If Yahoo Finance cannot be reached.
        FileNotFoundError: If config/sector_peers.json is missing.
    """
    ticker = ticker.strip().upper()
    sector, peer_tickers = get_sector_peers(ticker)

    # Score the target stock first
    target_scored = scorer.score_stock(ticker)

    # Score each peer with a delay to be polite to Yahoo Finance
    peer_scores: list[dict] = []
    for i, peer in enumerate(peer_tickers):
        time.sleep(_FETCH_DELAY_SECS)
        try:
            peer_scores.append(scorer.score_stock(peer))
        except Exception:
            pass  # Delisted, bad ticker, network blip — skip silently

    # Combine target + peers and sort by score to find rank
    all_scored = [target_scored] + peer_scores
    all_scored.sort(key=lambda x: x["total_score"], reverse=True)

    # Find target's 1-based rank in the sorted list
    target_rank = next(
        (i + 1 for i, s in enumerate(all_scored) if s["ticker"] == ticker),
        len(all_scored),  # Fallback: last place if somehow not found
    )

    total_in_sector = len(all_scored)

    # Build the ordinal string (1st, 2nd, 3rd, 4th…)
    ordinal_suffixes = {1: "st", 2: "nd", 3: "rd"}
    suffix = ordinal_suffixes.get(target_rank if target_rank <= 3 else 0, "th")
    summary = (
        f"{ticker} ranks {target_rank}{suffix} of {total_in_sector} "
        f"{sector} stocks by fundamental score"
    )

    return {
        "target":             target_scored,
        "peers":              peer_scores,
        "sector":             sector,
        "target_rank":        target_rank,
        "total_in_sector":    total_in_sector,
        "comparison_summary": summary,
    }
