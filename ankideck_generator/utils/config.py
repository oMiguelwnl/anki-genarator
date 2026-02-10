from __future__ import annotations

from pathlib import Path
from typing import Any

from .file_utils import read_json

try:
    import yaml
except Exception:  # pragma: no cover - optional
    yaml = None


def load_config(path: str | Path) -> dict[str, Any]:
    path_obj = Path(path)
    if not path_obj.exists():
        raise FileNotFoundError(f"Config not found: {path_obj}")
    if yaml is None:
        raise RuntimeError("PyYAML is required to read config.yaml. Install pyyaml>=6.0")
    with path_obj.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def save_config(path: str | Path, data: dict[str, Any]) -> None:
    if yaml is None:
        raise RuntimeError("PyYAML is required to write config.yaml. Install pyyaml>=6.0")
    path_obj = Path(path)
    path_obj.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
