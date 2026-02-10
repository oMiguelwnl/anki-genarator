from __future__ import annotations

from pathlib import Path
from typing import Any

from ..utils.file_utils import atomic_write_json, ensure_dir, read_json


class CacheManager:
    def __init__(self, base_path: str | Path, language: str, autosave_every: int = 10) -> None:
        self.base_path = Path(base_path)
        self.language = language
        self.autosave_every = autosave_every
        self.caches: dict[str, dict[str, Any]] = {}
        ensure_dir(self.base_path)

    def _cache_file(self, kind: str) -> Path:
        return self.base_path / f"{self.language}_{kind}.json"

    def load(self, kind: str) -> dict[str, Any]:
        if kind in self.caches:
            return self.caches[kind]
        data = read_json(self._cache_file(kind), default={})
        self.caches[kind] = data
        return data

    def get(self, kind: str, key: str) -> Any | None:
        cache = self.load(kind)
        return cache.get(key)

    def set(self, kind: str, key: str, value: Any) -> None:
        cache = self.load(kind)
        cache[key] = value

    def save(self, kind: str) -> None:
        cache = self.load(kind)
        atomic_write_json(self._cache_file(kind), cache)

    def save_all(self) -> None:
        for kind in list(self.caches.keys()):
            self.save(kind)
