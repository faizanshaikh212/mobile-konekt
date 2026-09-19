"""Small, resilient JSON persistence for the host registry."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from threading import RLock


def data_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "userdata"
    return Path(__file__).resolve().parent.parent / ".dev-data"


class JsonStore:
    def __init__(self, filename="state.json", root=None):
        self.root = Path(root or data_root())
        self.path = self.root / filename
        self._lock = RLock()
        self.data = self._load()

    def _load(self):
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
            return (
                value
                if isinstance(value, dict)
                and isinstance(value.get("devices", {}), dict)
                else {"devices": {}}
            )
        except (OSError, ValueError, TypeError):
            return {"devices": {}}

    def save(self):
        with self._lock:
            self.root.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(self.path.suffix + ".tmp")
            temporary.write_text(
                json.dumps(self.data, indent=2, sort_keys=True), encoding="utf-8"
            )
            os.replace(temporary, self.path)

    def get(self, token):
        with self._lock:
            item = self.data["devices"].get(token, {})
            return dict(item) if isinstance(item, dict) else {}

    def update(self, token, **values):
        with self._lock:
            item = self.data["devices"].setdefault(token, {})
            item.update(values)
            self.save()
            return dict(item)

    def snapshot(self):
        with self._lock:
            return {
                key: dict(value)
                for key, value in self.data["devices"].items()
                if isinstance(value, dict)
            }
