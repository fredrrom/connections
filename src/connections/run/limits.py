"""Process-level guards around a run.

Everything here is cooperative or best-effort. A step that never returns is not
interruptible from inside the process, which is why the guarantee that a problem
ends belongs to whatever supervises the process rather than to these.
"""

from __future__ import annotations

from contextlib import contextmanager
import logging
import signal
from typing import Any


class WallClockExceeded(BaseException):
    """Raised by the SIGALRM handler; BaseException so policy code with broad
    `except Exception` handlers cannot swallow it."""


@contextmanager
def _wall_clock_alarm(seconds: float | None):
    """Enforce a wall-clock budget over the enclosed block via SIGALRM.

    The prover self-limits the way E does with --cpu-limit: the OS interrupts
    the attempt wherever it is (parsing, clausification, search) and the
    signal handler raises. Requires the main thread; when signals are
    unavailable (non-main thread, non-POSIX) the budget is not enforced and
    external supervision must cover it. Nested use is unsupported: the
    enclosed block must not arm ITIMER_REAL itself.
    """

    if seconds is None or not hasattr(signal, "SIGALRM"):
        yield
        return
    if seconds <= 0:
        # setitimer(0) would disarm rather than fire; an exhausted budget
        # times out before any work happens.
        raise WallClockExceeded

    def _raise(_signum: int, _frame: Any) -> None:
        raise WallClockExceeded

    try:
        previous = signal.signal(signal.SIGALRM, _raise)
    except ValueError:  # not the main thread
        yield
        return
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


@contextmanager
def _memory_limit(limit_mb: int | None):
    """Best-effort process memory cap (E's --memory-limit analog).

    On Linux, lowering RLIMIT_AS makes a runaway allocation raise MemoryError
    at the failing allocation site, which the prover reports as MemoryOut.
    macOS rejects lowering memory rlimits, so there this is a no-op and only
    external supervision bounds memory.
    """

    if limit_mb is None:
        yield
        return
    try:
        import resource
    except ImportError:
        yield
        return
    res = getattr(resource, "RLIMIT_AS", None)
    if res is None:
        yield
        return
    try:
        soft, hard = resource.getrlimit(res)
        resource.setrlimit(res, (limit_mb * 1024**2, hard))
    except (ValueError, OSError):
        yield
        return
    try:
        yield
    finally:
        try:
            resource.setrlimit(res, (soft, hard))
        except (ValueError, OSError):
            # A failed restore leaves the process under the lowered cap;
            # surface it instead of failing silently.
            logging.getLogger(__name__).warning(
                "failed to restore RLIMIT_AS to (%d, %d)", soft, hard
            )


__all__ = [
    "WallClockExceeded",
]
