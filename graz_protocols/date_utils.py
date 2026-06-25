from __future__ import annotations

from datetime import date


MIN_PUBLIC_RECORD_YEAR = 2000
DEFAULT_FUTURE_YEAR_WINDOW = 2


def parse_compact_public_date(
    year: str,
    month: str,
    day: str,
    *,
    min_year: int = MIN_PUBLIC_RECORD_YEAR,
    max_year: int | None = None,
) -> str:
    """Return ISO date for compact two-digit year parts, or empty for invalid dates."""
    try:
        year_int = 2000 + int(year)
        month_int = int(month)
        day_int = int(day)
        parsed = date(year_int, month_int, day_int)
    except ValueError:
        return ""
    upper_year = max_year if max_year is not None else date.today().year + DEFAULT_FUTURE_YEAR_WINDOW
    if not (min_year <= parsed.year <= upper_year):
        return ""
    return parsed.isoformat()
