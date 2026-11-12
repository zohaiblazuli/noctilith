from server import cache


def test_cache_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(cache.SETTINGS, "cache_dir", tmp_path)
    k = cache.key("a", 1, 2.5)
    assert cache.get_json(k) is None
    cache.put_json(k, {"x": [1, 2]})
    assert cache.get_json(k) == {"x": [1, 2]}


def test_key_is_stable_and_distinct():
    assert cache.key("a", 1) == cache.key("a", 1)
    assert cache.key("a", 1) != cache.key("a", 2)
