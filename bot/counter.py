import threading

_lock = threading.Lock()
_counters: dict[str, int] = {}


def next_index(key: str, modulo: int) -> int:
    """Return the next round-robin index for ``key`` in [0, modulo).

    Counter is kept in memory only — it resets when the bot restarts.
    """
    with _lock:
        current = _counters.get(key, 0)
        index = current % modulo
        _counters[key] = current + 1
        return index
