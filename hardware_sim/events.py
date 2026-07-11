from collections import deque
from dataclasses import dataclass
from datetime import datetime
from threading import Lock
from typing import Callable


@dataclass(frozen=True)
class LogEntry:
    timestamp: datetime
    node_id: str
    message: str

    def format(self):
        return f"{self.timestamp.strftime('%H:%M:%S')} {self.node_id}: {self.message}"


class EventLog:
    def __init__(self, max_entries: int = 1000):
        if max_entries < 1:
            raise ValueError("max_entries must be greater than 0")

        self.max_entries = max_entries
        self._entries = deque(maxlen=max_entries)
        self._lock = Lock()

    def record(self, node_id: str, message: str):
        with self._lock:
            self._entries.append(
                LogEntry(
                    timestamp=datetime.now(),
                    node_id=node_id,
                    message=message,
                )
            )

    def sink(self, node_id: str) -> Callable[[str], None]:
        return lambda message: self.record(node_id, message)

    def entries(self, node_id: str | None = None, limit: int | None = None):
        with self._lock:
            entries = list(self._entries)

        if node_id is not None:
            entries = [entry for entry in entries if entry.node_id == node_id]

        if limit is not None:
            entries = entries[-limit:]

        return tuple(entries)
