"""Bounded, ephemeral UI signals. Never write business state or invoke a model."""
from __future__ import annotations

from copy import deepcopy
from threading import Lock
from time import monotonic


class DemoObserverSessions:
    def __init__(self, capacity: int = 128, ttl: float = 1800):
        self.capacity = capacity
        self.ttl = ttl
        self._entries: dict[tuple[str, str], tuple[float, dict]] = {}
        self._lock = Lock()

    def _expire(self, now: float):
        for key, (updated, _) in list(self._entries.items()):
            if now - updated > self.ttl:
                del self._entries[key]

    def publish(self, project_id: str, source_id: str, payload: dict) -> dict:
        with self._lock:
            now = monotonic()
            self._expire(now)
            key = (project_id, source_id)
            previous = self._entries.get(key)
            if previous and payload["sequence"] <= previous[1]["sequence"]:
                return {
                    "status": "duplicate" if payload == previous[1] else "ignored",
                    "sequence": previous[1]["sequence"],
                }
            if key not in self._entries and len(self._entries) >= self.capacity:
                oldest = min(self._entries, key=lambda entry: self._entries[entry][0])
                del self._entries[oldest]
            self._entries[key] = (now, deepcopy(payload))
            return {"status": "accepted", "sequence": payload["sequence"]}

    def read(self, project_id: str, source_id: str) -> dict | None:
        with self._lock:
            self._expire(monotonic())
            entry = self._entries.get((project_id, source_id))
            return deepcopy(entry[1]) if entry else None


sessions = DemoObserverSessions()
