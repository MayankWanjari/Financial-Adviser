"""tests/conftest.py — shared fixtures available to every test file.

Fixtures here guarantee each test starts from a clean, isolated state —
no real config/portfolio.json, no real cache directory, no real session file.

How isolation works:
  - monkeypatch replaces the module-level Path variable (_PORTFOLIO_PATH etc.)
    so every call inside the module uses the temp path.
  - The portfolio fixture also pre-writes an empty file so load_portfolio()
    never falls back to reading the real config/portfolio.json.
"""

import json
import pytest

import data.cache     as cache_module
import data.portfolio as portfolio_module
import data.session   as session_module


@pytest.fixture
def temp_portfolio(tmp_path, monkeypatch):
    """
    Redirect _PORTFOLIO_PATH to a fresh temp file pre-populated with empty holdings.

    Writing the file BEFORE monkeypatching ensures load_portfolio() always finds a
    clean slate regardless of what data is in the real config/portfolio.json.
    """
    portfolio_file = tmp_path / "portfolio.json"
    portfolio_file.write_text(
        json.dumps({"holdings": [], "last_updated": None}, indent=2),
        encoding="utf-8",
    )
    monkeypatch.setattr(portfolio_module, "_PORTFOLIO_PATH", portfolio_file)
    return portfolio_file


@pytest.fixture
def isolated_cache(tmp_path, monkeypatch):
    """Redirect _CACHE_DIR to a temp directory so tests never touch real cache files."""
    monkeypatch.setattr(cache_module, "_CACHE_DIR", tmp_path)
    return tmp_path


@pytest.fixture
def isolated_session(tmp_path, monkeypatch):
    """Redirect _SESSION_DIR and _SESSION_FILE to temp locations."""
    session_dir  = tmp_path / "sessions"
    session_file = session_dir / "latest_session.json"
    monkeypatch.setattr(session_module, "_SESSION_DIR",  session_dir)
    monkeypatch.setattr(session_module, "_SESSION_FILE", session_file)
    return session_file
