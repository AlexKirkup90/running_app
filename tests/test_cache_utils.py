from core.services.cache_utils import ttl_get, ttl_set, counter


def test_ttl_cache_hit():
    ttl_set("a", 1)
    assert ttl_get("a", 999) == 1
    assert counter.hits >= 1
