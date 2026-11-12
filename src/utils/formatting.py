"""Defensive date/time formatting helpers shared by signals and admin."""
from datetime import time


def short_date(value):
    """Format a date value as ``dd/mm``, tolerating strings and ``None``."""
    if value is None:
        return ""
    if hasattr(value, "strftime"):
        return value.strftime("%d/%m")
    return str(value)


def short_time(value):
    """Format a time value as ``HH:MM``.

    Values can reach a ``post_save`` receiver as strings (for example when an
    instance is built with a string value and has not been refreshed from the
    DB), so fall back to ISO parsing or plain stringification instead of
    assuming a ``datetime.time`` object.
    """
    if value is None:
        return ""
    if hasattr(value, "strftime"):
        return value.strftime("%H:%M")
    try:
        return time.fromisoformat(str(value)).strftime("%H:%M")
    except (TypeError, ValueError):
        return str(value)
