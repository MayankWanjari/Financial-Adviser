"""Tests for data/session.py — uses isolated_session fixture from conftest.py."""

import json

from data.session import save_session, load_latest_session


def test_load_returns_none_when_no_file(isolated_session):
    assert load_latest_session() is None


def test_save_creates_session_directory(isolated_session, tmp_path):
    session_dir = tmp_path / "sessions"
    assert not session_dir.exists()
    save_session([{"role": "assistant", "content": "hi"}], [])
    assert session_dir.exists()


def test_messages_roundtrip(isolated_session):
    messages = [
        {"role": "assistant", "content": "Namaste! Research assistant hoon."},
        {"role": "user",      "content": "TCS ka PE kya hai?"},
        {"role": "assistant", "content": "TCS ka trailing PE 28x hai."},
    ]
    save_session(messages, [])
    loaded_messages, _ = load_latest_session()
    assert loaded_messages == messages


def test_empty_gemini_history_roundtrip(isolated_session):
    save_session([{"role": "assistant", "content": "hello"}], [])
    _, loaded_history = load_latest_session()
    assert loaded_history == []


def test_saved_file_contains_timestamp(isolated_session):
    save_session([{"role": "user", "content": "hi"}], [])
    raw = json.loads(isolated_session.read_text(encoding="utf-8"))
    assert "saved_at" in raw
    assert raw["saved_at"]


def test_load_corrupt_file_returns_none(isolated_session):
    isolated_session.parent.mkdir(parents=True, exist_ok=True)
    isolated_session.write_text("not valid json {{{", encoding="utf-8")
    assert load_latest_session() is None


def test_overwrite_session(isolated_session):
    save_session([{"role": "assistant", "content": "first session"}], [])
    save_session([{"role": "assistant", "content": "second session"}], [])
    loaded_messages, _ = load_latest_session()
    assert loaded_messages[0]["content"] == "second session"
