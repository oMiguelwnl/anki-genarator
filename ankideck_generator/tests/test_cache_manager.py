from pathlib import Path

from ankideck_generator.core.cache_manager import CacheManager


def test_cache_manager_roundtrip(tmp_path: Path) -> None:
    cache = CacheManager(tmp_path, "en", autosave_every=1)
    cache.set("definitions", "hello", "greeting")
    cache.save("definitions")

    reload_cache = CacheManager(tmp_path, "en", autosave_every=1)
    assert reload_cache.get("definitions", "hello") == "greeting"
