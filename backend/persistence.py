"""Encrypted JSON persistence for host devices and shared layouts."""

from __future__ import annotations

import json
import os
import secrets
import sys
from pathlib import Path
from threading import RLock

from cryptography.fernet import Fernet, InvalidToken


def data_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "userdata"
    return Path(__file__).resolve().parent.parent / ".dev-data"


class EncryptedStore:
    def __init__(self, filename, root=None, default=None):
        self.root = Path(root or data_root())
        self.path = self.root / filename
        self.default = default if default is not None else {}
        self._lock = RLock()
        self._cipher = Fernet(self._load_key())
        self.data = self._load()

    def _load_key(self):
        key_path = self.root / ".storage-key"
        try:
            key = key_path.read_bytes()
            Fernet(key)
            return key
        except (OSError, ValueError):
            key = Fernet.generate_key()
            self.root.mkdir(parents=True, exist_ok=True)
            flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
            fd = os.open(key_path, flags, 0o600)
            try:
                os.write(fd, key)
            finally:
                os.close(fd)
            return key

    def _load(self):
        try:
            raw = self.path.read_bytes()
            try:
                decoded = self._cipher.decrypt(raw)
                value = json.loads(decoded.decode("utf-8"))
            except InvalidToken:
                # One-time migration for the earlier plaintext JSON format.
                value = json.loads(raw.decode("utf-8"))
            return value if isinstance(value, type(self.default)) else self.default.copy()
        except (OSError, ValueError, TypeError, UnicodeDecodeError):
            return self.default.copy()

    def save(self):
        with self._lock:
            self.root.mkdir(parents=True, exist_ok=True)
            payload = json.dumps(self.data, separators=(",", ":")).encode("utf-8")
            temporary = self.path.with_suffix(self.path.suffix + ".tmp")
            temporary.write_bytes(self._cipher.encrypt(payload))
            os.replace(temporary, self.path)


class JsonStore(EncryptedStore):
    def __init__(self, filename="state.json", root=None):
        super().__init__(filename, root, {"devices": {}})
        decoded = {}
        for token, item in self.data.get("devices", {}).items():
            try:
                token = self._cipher.decrypt(token.encode()).decode()
            except (InvalidToken, AttributeError, ValueError):
                pass
            decoded[token] = item
        self.data["devices"] = decoded
        legacy = self.data.pop("layouts", {})
        self.legacy_layouts = legacy if isinstance(legacy, dict) else {}
        if legacy or decoded:
            self.save()

    def save(self):
        with self._lock:
            self.root.mkdir(parents=True, exist_ok=True)
            encoded = {
                self._cipher.encrypt(token.encode()).decode(): value
                for token, value in self.data["devices"].items()
            }
            payload = json.dumps({"devices": encoded}, indent=2, sort_keys=True)
            temporary = self.path.with_suffix(self.path.suffix + ".tmp")
            temporary.write_text(payload, encoding="utf-8")
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

    def delete(self, token):
        with self._lock:
            if token not in self.data["devices"]:
                return False
            del self.data["devices"][token]
            self.save()
            return True


class LayoutStore(EncryptedStore):
    def __init__(self, root=None):
        super().__init__("layouts.json", root, {})
        self.save()

    def save(self):
        with self._lock:
            self.root.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(self.path.suffix + ".tmp")
            temporary.write_text(
                json.dumps(self.data, indent=2, sort_keys=True), encoding="utf-8"
            )
            os.replace(temporary, self.path)

    def save_layout(self, layout_id, layout, device_ref, label):
        with self._lock:
            self.data[str(layout_id)] = {
                "layout": dict(layout),
                "device_ref": device_ref,
                "label": label,
            }
            self.save()

    def get_layout(self, layout_id):
        with self._lock:
            item = self.data.get(str(layout_id))
            return dict(item) if isinstance(item, dict) else None

    def update_device(self, device_ref, label):
        with self._lock:
            changed = False
            for item in self.data.values():
                if isinstance(item, dict) and item.get("device_ref") == device_ref:
                    if item.get("label") != label:
                        item["label"] = label
                        changed = True
            if changed:
                self.save()

    def sync_device_labels(self, devices, root=None):
        """Replace stale client-supplied labels with server-owned labels."""
        with self._lock:
            labels = {
                device_ref(token, root): item.get("label")
                for token, item in devices.items()
                if isinstance(item, dict) and isinstance(item.get("label"), str)
            }
            changed = False
            for item in self.data.values():
                if not isinstance(item, dict):
                    continue
                label = labels.get(item.get("device_ref"))
                if label and item.get("label") != label:
                    item["label"] = label
                    changed = True
            if changed:
                self.save()

    def delete_device(self, device_ref):
        with self._lock:
            removed = [
                layout_id
                for layout_id, item in self.data.items()
                if isinstance(item, dict) and item.get("device_ref") == device_ref
            ]
            for layout_id in removed:
                del self.data[layout_id]
            if removed:
                self.save()


def device_ref(token: str, root=None) -> str:
    """Return a stable opaque reference for a device token."""
    import hmac
    import hashlib

    key_path = Path(root or data_root()) / ".storage-key"
    try:
        key = key_path.read_bytes()
    except OSError:
        key = b""
    return hmac.new(key, token.encode("utf-8"), hashlib.sha256).hexdigest()
