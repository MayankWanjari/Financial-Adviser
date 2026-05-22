"""Tests for data/cache.py — uses isolated_cache fixture from conftest.py."""

import hashlib
import json

from data.cache import cache_get, cache_set


def test_miss_on_empty_cache(isolated_cache):
    assert cache_get("missing_key", ttl_seconds=60) is None


def test_roundtrip_dict(isolated_cache):
    payload = {"ticker": "RELIANCE", "pe": 25.4, "roe": 0.12}
    cache_set("test_dict", payload)
    assert cache_get("test_dict", ttl_seconds=3600) == payload


def test_roundtrip_list(isolated_cache):
    cache_set("test_list", ["TCS", "INFY", "WIPRO"])
    assert cache_get("test_list", ttl_seconds=3600) == ["TCS", "INFY", "WIPRO"]


def test_roundtrip_string(isolated_cache):
    cache_set("test_str", "hello world")
    assert cache_get("test_str", ttl_seconds=3600) == "hello world"


def test_expiry_returns_none(isolated_cache):
    """TTL=0 means everything is immediately stale."""
    cache_set("expiry_key", {"data": "fresh"})
    assert cache_get("expiry_key", ttl_seconds=0) is None


def test_corrupt_file_returns_none(isolated_cache):
    filename = hashlib.md5(b"corrupt_key").hexdigest() + ".json"
    (isolated_cache / filename).write_text("not valid json {{{", encoding="utf-8")
    assert cache_get("corrupt_key", ttl_seconds=60) is None


def test_missing_timestamp_returns_none(isolated_cache):
    filename = hashlib.md5(b"no_ts_key").hexdigest() + ".json"
    (isolated_cache / filename).write_text(
        json.dumps({"key": "no_ts_key", "data": {"x": 1}}), encoding="utf-8"
    )
    assert cache_get("no_ts_key", ttl_seconds=60) is None


def test_creates_cache_dir_if_missing(tmp_path, monkeypatch):
    import data.cache as cache_module
    missing_dir = tmp_path / "new_cache_subdir"
    monkeypatch.setattr(cache_module, "_CACHE_DIR", missing_dir)
    assert not missing_dir.exists()
    cache_set("dir_test", {"ok": True})
    assert missing_dir.exists()


def test_overwrite_updates_data(isolated_cache):
    cache_set("ow_key", {"v": 1})
    cache_set("ow_key", {"v": 2})
    assert cache_get("ow_key", ttl_seconds=3600) == {"v": 2}
