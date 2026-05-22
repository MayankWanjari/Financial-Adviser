"""Tests for data/peers.py — get_sector_peers reads config files, no network needed."""

import json
import pytest

import data.peers as peers_module
from data.peers import get_sector_peers


@pytest.fixture
def mock_sector_peers(tmp_path, monkeypatch):
    """Create a temp sector_peers.json and redirect _SECTOR_PEERS_PATH to it."""
    sector_data = {
        "IT": ["TCS", "INFY", "WIPRO"],
        "Banking": ["HDFCBANK", "ICICIBANK"],
    }
    peers_file = tmp_path / "sector_peers.json"
    peers_file.write_text(json.dumps(sector_data), encoding="utf-8")
    monkeypatch.setattr(peers_module, "_SECTOR_PEERS_PATH", peers_file)
    return peers_file


def test_get_sector_peers_finds_known_ticker(mock_sector_peers):
    sector, peers = get_sector_peers("TCS")
    assert sector == "IT"
    assert "INFY" in peers
    assert "WIPRO" in peers


def test_get_sector_peers_excludes_target_from_peers(mock_sector_peers):
    _, peers = get_sector_peers("TCS")
    assert "TCS" not in peers


def test_get_sector_peers_case_insensitive(mock_sector_peers):
    sector, peers = get_sector_peers("tcs")
    assert sector == "IT"
    assert "INFY" in peers


def test_get_sector_peers_second_sector(mock_sector_peers):
    sector, peers = get_sector_peers("HDFCBANK")
    assert sector == "Banking"
    assert "ICICIBANK" in peers
    assert "HDFCBANK" not in peers


def test_get_sector_peers_unknown_ticker_returns_empty(mock_sector_peers):
    sector, peers = get_sector_peers("UNKNOWN_CO")
    assert sector == "Unknown"
    assert peers == []


def test_get_sector_peers_missing_config_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(peers_module, "_SECTOR_PEERS_PATH", tmp_path / "missing.json")
    with pytest.raises(FileNotFoundError):
        get_sector_peers("TCS")
