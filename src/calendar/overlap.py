"""
Overlap detection and focus time adjustment logic.
"""

from datetime import datetime, timedelta
from typing import List, Tuple
from src.calendar.processor import ProcessedEvent, EventType


def calculate_overlap(event1: ProcessedEvent, event2: ProcessedEvent) -> timedelta:
    """
    Calculate overlap duration between two events.

    Args:
        event1: First event
        event2: Second event

    Returns:
        timedelta of overlap (0 if no overlap)
    """
    # Find the later start time
    overlap_start = max(event1.start, event2.start)

    # Find the earlier end time
    overlap_end = min(event1.end, event2.end)

    # If overlap_start is after overlap_end, there's no overlap
    if overlap_start >= overlap_end:
        return timedelta(0)

    return overlap_end - overlap_start


def find_overlapping_events(focus_event: ProcessedEvent,
                            all_events: List[ProcessedEvent]) -> List[ProcessedEvent]:
    """
    Find all events that overlap with a focus time block.

    Args:
        focus_event: Focus time event to check
        all_events: List of all events

    Returns:
        List of events that overlap with focus_event
    """
    overlapping = []

    for event in all_events:
        # Skip the focus event itself
        if event.event_id == focus_event.event_id:
            continue

        # Skip ignored events
        if event.event_type == EventType.IGNORED:
            continue

        # Skip other focus time events
        if event.event_type == EventType.FOCUS_TIME:
            continue

        # Check for overlap
        overlap = calculate_overlap(focus_event, event)
        if overlap > timedelta(0):
            overlapping.append(event)

    return overlapping


def adjust_focus_time(focus_event: ProcessedEvent,
                     overlapping_events: List[ProcessedEvent]) -> Tuple[timedelta, List[Tuple[ProcessedEvent, timedelta]]]:
    """
    Calculate actual focus time by subtracting overlaps.

    Args:
        focus_event: Focus time event
        overlapping_events: List of events that overlap

    Returns:
        Tuple of (adjusted_duration, list of (event, overlap_duration) pairs)
    """
    total_overlap = timedelta(0)
    overlap_details = []

    for event in overlapping_events:
        overlap = calculate_overlap(focus_event, event)
        if overlap > timedelta(0):
            total_overlap += overlap
            overlap_details.append((event, overlap))

    # Calculate adjusted focus time
    adjusted_duration = focus_event.duration - total_overlap

    # Ensure we don't go negative
    if adjusted_duration < timedelta(0):
        adjusted_duration = timedelta(0)

    return adjusted_duration, overlap_details


def process_overlaps(events: List[ProcessedEvent]) -> List[Tuple[ProcessedEvent, timedelta, List[Tuple[ProcessedEvent, timedelta]]]]:
    """
    Process all focus time events and calculate adjusted durations.

    Args:
        events: List of all processed events

    Returns:
        List of tuples: (focus_event, adjusted_duration, overlap_details)
        where overlap_details is a list of (overlapping_event, overlap_duration)
    """
    results = []

    # Find all focus time events
    focus_events = [e for e in events if e.event_type == EventType.FOCUS_TIME]

    for focus_event in focus_events:
        # Find overlapping events
        overlapping = find_overlapping_events(focus_event, events)

        # Calculate adjusted duration
        adjusted_duration, overlap_details = adjust_focus_time(focus_event, overlapping)

        results.append((focus_event, adjusted_duration, overlap_details))

    return results
