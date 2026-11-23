"""
Date and time utility functions for week calculations.
"""

from datetime import datetime, date, time, timedelta, timezone
from typing import Tuple


def get_week_range(week_start: date = None) -> Tuple[datetime, datetime]:
    """
    Get the start and end datetime for a work week (Monday-Friday).

    Args:
        week_start: Optional date for the start of the week (Monday).
                   If None, uses the current week.

    Returns:
        Tuple of (week_start_datetime, week_end_datetime)
        - week_start_datetime: Monday at 00:00:00 (local timezone)
        - week_end_datetime: Saturday at 00:00:00 (local timezone)

    Example:
        >>> get_week_range(date(2026, 1, 20))  # Monday
        (datetime(2026, 1, 20, 0, 0, 0), datetime(2026, 1, 25, 0, 0, 0))
    """
    if week_start is None:
        # Get current week's Monday
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
    else:
        # Ensure it's a Monday
        if week_start.weekday() != 0:
            # Adjust to the Monday of that week
            week_start = week_start - timedelta(days=week_start.weekday())

    # Create datetime objects with timezone awareness
    start_dt = datetime.combine(week_start, time(0, 0, 0))
    # End is Saturday 00:00:00 (i.e., end of Friday)
    end_dt = start_dt + timedelta(days=5)

    # Make timezone-aware (local timezone)
    start_dt = start_dt.replace(tzinfo=timezone.utc).astimezone()
    end_dt = end_dt.replace(tzinfo=timezone.utc).astimezone()

    return start_dt, end_dt


def format_week_range(start_dt: datetime, end_dt: datetime) -> str:
    """
    Format a week range for display.

    Args:
        start_dt: Start datetime
        end_dt: End datetime

    Returns:
        Formatted string like "Week: 2026-01-20 to 2026-01-24"
    """
    start_date = start_dt.date()
    # End is Saturday 00:00, so Friday is the last working day
    end_date = (end_dt - timedelta(days=1)).date()

    return f"Week: {start_date} to {end_date}"


def parse_week_start(week_str: str) -> date:
    """
    Parse a week start date from string.

    Args:
        week_str: Date string in YYYY-MM-DD format

    Returns:
        date object (will be adjusted to Monday if not already)

    Raises:
        ValueError: If date string is invalid
    """
    try:
        parsed_date = datetime.strptime(week_str, '%Y-%m-%d').date()
        # Adjust to Monday if needed
        if parsed_date.weekday() != 0:
            parsed_date = parsed_date - timedelta(days=parsed_date.weekday())
        return parsed_date
    except ValueError as e:
        raise ValueError(f"Invalid date format: {week_str}. Expected YYYY-MM-DD") from e


def format_duration(hours: float) -> str:
    """
    Format hours as a human-readable string.

    Args:
        hours: Number of hours (can be fractional)

    Returns:
        Formatted string like "2h 30m" or "1h 0m"
    """
    total_minutes = int(hours * 60)
    h = total_minutes // 60
    m = total_minutes % 60
    return f"{h}h {m}m"


def round_hours(hours: float, mode: str = 'nearest') -> int:
    """
    Round hours according to the specified mode.

    Args:
        hours: Hours to round (can be fractional)
        mode: Rounding mode ('nearest', 'up', 'down', 'none')

    Returns:
        Rounded hours as integer (or float if mode='none')
    """
    if mode == 'nearest':
        return round(hours)
    elif mode == 'up':
        import math
        return math.ceil(hours)
    elif mode == 'down':
        import math
        return math.floor(hours)
    elif mode == 'none':
        return hours
    else:
        raise ValueError(f"Invalid rounding mode: {mode}. Must be 'nearest', 'up', 'down', or 'none'")
