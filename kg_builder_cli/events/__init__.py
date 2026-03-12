"""KGF pipeline event system using blinker signals.

Re-exports signals and event types for convenient access.
"""

from . import signals, types
from .handlers import (
    clear_event_log,
    get_event_log_count,
    register_default_handlers,
    register_event_accumulator,
    register_verbose_handlers,
)

__all__ = [
    "signals",
    "types",
    "register_default_handlers",
    "register_verbose_handlers",
    "register_event_accumulator",
    "get_event_log_count",
    "clear_event_log",
]
