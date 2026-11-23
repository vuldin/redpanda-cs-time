"""
Display utilities for formatting output.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Tuple
from tabulate import tabulate
from src.calendar.processor import ProcessedEvent, EventType


def format_time(dt: datetime) -> str:
    """Format datetime for display (e.g., 'Mon 19 08:00')."""
    return dt.strftime('%a %d %H:%M')


def format_time_range(start: datetime, end: datetime) -> str:
    """Format time range (e.g., 'Mon 19 08:00-09:00')."""
    if start.date() == end.date():
        return f"{start.strftime('%a %d %H:%M')}-{end.strftime('%H:%M')}"
    else:
        return f"{start.strftime('%a %d %H:%M')}-{end.strftime('%a %d %H:%M')}"


def format_duration(duration: timedelta) -> str:
    """Format duration (e.g., '2h 30m' or '1h 0m')."""
    total_minutes = int(duration.total_seconds() / 60)
    hours = total_minutes // 60
    minutes = total_minutes % 60
    return f"{hours}h {minutes}m"


def format_duration_hours(duration: timedelta) -> str:
    """Format duration as decimal hours (e.g., '2.5h')."""
    hours = duration.total_seconds() / 3600
    return f"{hours:.1f}h"


def format_event_type(event_type: str) -> str:
    """Format event type for display."""
    type_map = {
        EventType.FOCUS_TIME: 'Focus Time',
        EventType.CUSTOMER_MEETING: 'Meeting',
        EventType.INTERNAL_MEETING: 'Internal',
        EventType.IGNORED: 'Ignored',
        EventType.UNKNOWN: 'Unknown'
    }
    return type_map.get(event_type, event_type)


def display_events_table(events: List[ProcessedEvent]) -> None:
    """
    Display all events in a formatted table.

    Args:
        events: List of processed events
    """
    table_data = []

    for event in sorted(events, key=lambda e: e.start):
        table_data.append([
            format_time(event.start),
            format_time(event.end),
            format_duration_hours(event.duration),
            format_event_type(event.event_type),
            event.customer_name or '-',
            event.title
        ])

    print(tabulate(
        table_data,
        headers=['Start', 'End', 'Duration', 'Type', 'Customer', 'Title'],
        tablefmt='grid'
    ))


def display_overlap_adjustments(focus_adjustments: List[Tuple[ProcessedEvent, timedelta, List[Tuple[ProcessedEvent, timedelta]]]]) -> None:
    """
    Display focus time adjustments due to overlaps.

    Args:
        focus_adjustments: List of (focus_event, adjusted_duration, overlap_details)
    """
    if not focus_adjustments:
        print("No focus time blocks found.")
        return

    print("\nFOCUS TIME ADJUSTMENTS:")
    print("=" * 80)

    for focus_event, adjusted_duration, overlaps in focus_adjustments:
        original_hours = focus_event.duration_hours()
        adjusted_hours = adjusted_duration.total_seconds() / 3600

        print(f"\n{focus_event.title} ({focus_event.customer_name or 'Unknown'})")
        print(f"  Time: {format_time_range(focus_event.start, focus_event.end)}")
        print(f"  Original duration: {format_duration_hours(focus_event.duration)}")

        if overlaps:
            print(f"  Overlapping meetings:")
            for overlap_event, overlap_duration in overlaps:
                print(f"    - {overlap_event.title}: {format_duration_hours(overlap_duration)} "
                      f"({format_event_type(overlap_event.event_type)})")

            total_overlap = sum((o.total_seconds() for _, o in overlaps), 0.0) / 3600
            print(f"  Total overlap: {total_overlap:.1f}h")
            print(f"  Adjusted duration: {adjusted_hours:.1f}h")
        else:
            print(f"  No overlaps")
            print(f"  Adjusted duration: {adjusted_hours:.1f}h (unchanged)")


def display_aggregated_time(events: List[ProcessedEvent],
                           focus_adjustments: List[Tuple[ProcessedEvent, timedelta, List]],
                           rounding_mode: str = 'nearest',
                           internal_rounding_mode: str = 'up') -> Dict[str, float]:
    """
    Display aggregated time by customer with rounding.

    Args:
        events: All processed events
        focus_adjustments: Focus time adjustments
        rounding_mode: Rounding mode for regular time
        internal_rounding_mode: Rounding mode for internal meetings

    Returns:
        Dictionary of customer -> rounded hours
    """
    from src.utils.date_utils import round_hours

    # Aggregate raw hours by customer
    customer_hours: Dict[str, float] = {}

    # Add adjusted focus time
    for focus_event, adjusted_duration, _ in focus_adjustments:
        customer = focus_event.customer_name or 'Unknown'
        hours = adjusted_duration.total_seconds() / 3600
        customer_hours[customer] = customer_hours.get(customer, 0) + hours

    # Add customer meetings (that aren't focus time)
    for event in events:
        if event.event_type == EventType.CUSTOMER_MEETING:
            customer = event.customer_name or 'Unknown'
            hours = event.duration_hours()
            customer_hours[customer] = customer_hours.get(customer, 0) + hours

    # Add internal meetings
    internal_hours = sum(
        event.duration_hours()
        for event in events
        if event.event_type == EventType.INTERNAL_MEETING
    )

    if internal_hours > 0:
        customer_hours['Internal Meetings'] = internal_hours

    # Round hours
    rounded_hours = {}
    for customer, hours in customer_hours.items():
        # Use internal rounding mode for internal meetings
        if customer == 'Internal Meetings':
            rounded = round_hours(hours, internal_rounding_mode)
        else:
            rounded = round_hours(hours, rounding_mode)
        rounded_hours[customer] = rounded

    # Display table
    print("\nAGGREGATED TIME BY CUSTOMER:")
    print("=" * 80)

    table_data = []
    for customer in sorted(rounded_hours.keys()):
        raw = customer_hours[customer]
        rounded = rounded_hours[customer]
        table_data.append([customer, f"{raw:.1f}h", f"{rounded}h"])

    print(tabulate(
        table_data,
        headers=['Customer', 'Raw Hours', 'Rounded Hours'],
        tablefmt='grid'
    ))

    total_raw = sum(customer_hours.values())
    total_rounded = sum(rounded_hours.values())
    print(f"\nTotal: {total_raw:.1f}h raw, {total_rounded}h rounded")

    return rounded_hours


def display_ignored_events(events: List[ProcessedEvent]) -> None:
    """
    Display list of ignored events.

    Args:
        events: All processed events
    """
    ignored = [e for e in events if e.event_type == EventType.IGNORED]

    if not ignored:
        return

    print("\nIGNORED EVENTS:")
    print("=" * 80)

    for event in sorted(ignored, key=lambda e: e.start):
        print(f"  - {event.title} ({format_time_range(event.start, event.end)})")
