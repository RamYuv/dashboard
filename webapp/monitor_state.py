import json
import os
from copy import deepcopy
from datetime import datetime, timezone
from threading import Lock

from flask import current_app, has_app_context

class MonitorState:
    def __init__(self):
        self.lock = Lock()
        self._previous = {}
        self._snapshot = {}
        self._delta = {}
        self._last_update_ts = None
        self._cache_mtime = None

    def update(self, snapshot, delta=None):
        with self.lock:
            self._previous = deepcopy(self._snapshot)
            self._snapshot = deepcopy(snapshot or {})
            self._delta = deepcopy(delta or {})
            self._last_update_ts = datetime.now(timezone.utc).isoformat()
            self._persist_locked()

    def snapshot(self):
        with self.lock:
            return deepcopy(self._snapshot), self._last_update_ts

    def delta(self):
        with self.lock:
            return deepcopy(self._delta), self._last_update_ts

    def previous(self):
        with self.lock:
            return deepcopy(self._previous)

    def load_persisted(self):
        with self.lock:
            cache_data = self._read_cache_file()
            if cache_data is None:
                return False

            self._snapshot = self._parse_json(cache_data.get("snapshot"))
            self._delta = self._parse_json(cache_data.get("delta"))
            self._previous = {}
            self._last_update_ts = cache_data.get("last_update_ts")
            self._cache_mtime = cache_data.get("_cache_mtime")
            return True

    def refresh_from_persisted(self):
        with self.lock:
            cache_data = self._read_cache_file()
            if cache_data is None:
                return False

            cache_mtime = cache_data.get("_cache_mtime")
            if self._cache_mtime is not None and cache_mtime == self._cache_mtime:
                return False

            self._snapshot = self._parse_json(cache_data.get("snapshot"))
            self._delta = self._parse_json(cache_data.get("delta"))
            self._last_update_ts = cache_data.get("last_update_ts")
            self._cache_mtime = cache_mtime
            return True

    def _persist_locked(self):
        if not has_app_context():
            return

        cache_path = current_app.config.get("MONITOR_CACHE_FILE")
        if not cache_path:
            return

        cache_data = {
            "snapshot": self._snapshot or {},
            "delta": self._delta or {},
            "last_update_ts": self._last_update_ts,
        }
        temp_path = cache_path + ".tmp"
        try:
            with open(temp_path, "w", encoding="utf-8") as cache_file:
                json.dump(cache_data, cache_file)
            os.replace(temp_path, cache_path)
        except (IOError, OSError, PermissionError) as exc:
            current_app.logger.warning(
                "Unable to persist monitoring cache to %s: %s",
                cache_path,
                exc,
            )
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            except (IOError, OSError, PermissionError):
                pass
            self._cache_mtime = None
            return
        try:
            self._cache_mtime = os.path.getmtime(cache_path)
        except (IOError, OSError):
            self._cache_mtime = None

    def _parse_json(self, value):
        if not isinstance(value, dict):
            return {}
        return value

    def _read_cache_file(self):
        if not has_app_context():
            return None

        cache_path = current_app.config.get("MONITOR_CACHE_FILE")
        if not cache_path or not os.path.exists(cache_path):
            return None

        try:
            cache_mtime = os.path.getmtime(cache_path)
            with open(cache_path, "r") as cache_file:
                data = json.load(cache_file)
        except (IOError, OSError, TypeError, ValueError):
            return None

        if not isinstance(data, dict):
            return None
        data["_cache_mtime"] = cache_mtime
        return data

monitor_state = MonitorState()
