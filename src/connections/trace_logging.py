from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
import logging
from typing import Any

TRACE_LEVEL = 5
TRACE_LOGGER_NAME = "connections.trace"
CLAUSIFICATION_TRACE_LOGGER_NAME = "connections.clausification_trace"

_trace_event_sink: Callable[[str], None] | None = None


def trace(logger: logging.Logger, message: object, *args: object, **kwargs: Any) -> None:
    if logger is trace_logger and _trace_event_sink is not None:
        if args:
            _trace_event_sink(str(message) % args)
        else:
            _trace_event_sink(str(message))
        return
    logger.log(TRACE_LEVEL, message, *args, **kwargs)


@contextmanager
def trace_event_sink(sink: Callable[[str], None]) -> Iterator[None]:
    global _trace_event_sink
    previous_sink = _trace_event_sink
    _trace_event_sink = sink
    try:
        yield
    finally:
        _trace_event_sink = previous_sink


logging.addLevelName(TRACE_LEVEL, "TRACE")
trace_logger = logging.getLogger(TRACE_LOGGER_NAME)
clausification_trace_logger = logging.getLogger(CLAUSIFICATION_TRACE_LOGGER_NAME)
