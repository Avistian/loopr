"""Small shared helpers."""

from __future__ import annotations

import os


def pid_alive(pid: int) -> bool:
    """True if a process with ``pid`` currently exists."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True
