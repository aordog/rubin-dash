"""Thread-safe shared state between the data pipeline and the web layer."""

from __future__ import annotations
import threading

class SharedState:
    """Thin, lockable wrapper around the dashboard's mutable state."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._data: dict = {
            "date":         None,
            "fig1_html":    "",
            "fig2_html":    "",
            "fig3_html":    "",
            "table":        None,
            "version":      0,
            "updating":     False,
            "progress":     0.0,
            "progress_msg": "",
            "next_update":  0.0,
        }

    # -- Backward-compatible accessors for populate_database() --------
    @property
    def lock(self) -> threading.Lock:
        return self._lock

    @property
    def raw(self) -> dict:
        return self._data

    # -- Convenience helpers ------------------------------------------
    def snapshot(self) -> dict:
        """Return a shallow copy of the full state (atomic read)."""
        with self._lock:
            return dict(self._data)

    def write(self, **kwargs) -> None:
        """Atomically update one or more keys."""
        with self._lock:
            self._data.update(kwargs)