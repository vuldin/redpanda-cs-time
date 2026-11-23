"""
Event processing and classification logic.
"""

import re
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from config.settings import SyncConfig


class EventType:
    """Event type constants."""
    FOCUS_TIME = 'focus_time'
    CUSTOMER_MEETING = 'customer_meeting'
    INTERNAL_MEETING = 'internal_meeting'
    IGNORED = 'ignored'
    UNKNOWN = 'unknown'


class ProcessedEvent:
    """
    Represents a processed calendar event with classification.
    """

    def __init__(self, raw_event: Dict[str, Any], event_type: str,
                 customer_name: Optional[str] = None,
                 exclude_from_sync: bool = False):
        """
        Initialize a processed event.

        Args:
            raw_event: Original event dict from Google Calendar API
            event_type: EventType constant
            customer_name: Extracted customer name (if applicable)
            exclude_from_sync: Whether to exclude this event from Clockify sync
        """
        self.raw_event = raw_event
        self.event_type = event_type
        self.customer_name = customer_name
        self.exclude_from_sync = exclude_from_sync

        # Extract basic fields
        self.title = raw_event.get('summary', '(No title)')
        self.event_id = raw_event.get('id', '')

        # Parse timestamps
        start_str = raw_event.get('start', {}).get('dateTime', '')
        end_str = raw_event.get('end', {}).get('dateTime', '')

        self.start = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
        self.end = datetime.fromisoformat(end_str.replace('Z', '+00:00'))
        self.duration = self.end - self.start

    def duration_hours(self) -> float:
        """Get duration in hours."""
        return self.duration.total_seconds() / 3600

    def __repr__(self) -> str:
        return (f"ProcessedEvent(title='{self.title}', type={self.event_type}, "
                f"customer={self.customer_name}, duration={self.duration_hours():.1f}h)")


def is_ignored_event(title: str, ignore_patterns: List[str]) -> bool:
    """
    Check if event should be ignored based on patterns.

    Args:
        title: Event title
        ignore_patterns: List of regex patterns

    Returns:
        True if event matches any ignore pattern
    """
    for pattern in ignore_patterns:
        if re.search(pattern, title):
            return True
    return False


def is_focus_time_event(title: str, focus_patterns: List[str]) -> bool:
    """
    Check if event is a focus time block.

    Args:
        title: Event title
        focus_patterns: List of regex patterns

    Returns:
        True if event matches any focus time pattern
    """
    for pattern in focus_patterns:
        if re.search(pattern, title):
            return True
    return False


def is_internal_meeting(title: str, internal_patterns: List[str]) -> bool:
    """
    Check if event is an internal meeting.

    Args:
        title: Event title
        internal_patterns: List of regex patterns

    Returns:
        True if event matches any internal meeting pattern
    """
    for pattern in internal_patterns:
        if re.search(pattern, title):
            return True
    return False


def extract_customer_name(title: str, patterns: List[str]) -> Optional[str]:
    """
    Extract customer name from event title using regex patterns.

    Args:
        title: Event title
        patterns: List of regex patterns with capture groups

    Returns:
        Extracted customer name or None
    """
    for pattern in patterns:
        match = re.search(pattern, title)
        if match and match.groups():
            # Return first capture group
            customer = match.group(1).strip()
            if customer:
                return customer
    return None


def classify_event(event: Dict[str, Any], config: SyncConfig,
                   cache_manager=None, require_cache: bool = False) -> ProcessedEvent:
    """
    Classify an event and extract metadata.

    Args:
        event: Raw event dict from Google Calendar API
        config: Sync configuration with patterns
        cache_manager: Optional CacheManager for cached classifications
        require_cache: If True, non-cached events are marked as UNKNOWN (forces manual review)

    Returns:
        ProcessedEvent with classification and extracted data
    """
    title = event.get('summary', '(No title)')

    # Check cache first (if available)
    if cache_manager:
        cached = cache_manager.get(title)
        if cached:
            exclude = cached.exclude_from_sync
            # Use cached classification
            if cached.classification == 'ignored':
                return ProcessedEvent(event, EventType.IGNORED, exclude_from_sync=exclude)
            elif cached.classification == 'internal_meeting':
                return ProcessedEvent(event, EventType.INTERNAL_MEETING,
                                    customer_name=cached.customer_name or config.internal_meetings_name,
                                    exclude_from_sync=exclude)
            elif cached.classification == 'customer_meeting':
                return ProcessedEvent(event, EventType.CUSTOMER_MEETING,
                                    customer_name=cached.customer_name,
                                    exclude_from_sync=exclude)
            elif cached.classification == 'focus_time':
                return ProcessedEvent(event, EventType.FOCUS_TIME,
                                    customer_name=cached.customer_name,
                                    exclude_from_sync=exclude)

    # If require_cache is True and we don't have a cached classification,
    # mark as UNKNOWN to force manual review
    if require_cache:
        return ProcessedEvent(event, EventType.UNKNOWN)

    # No cache hit - use pattern matching
    # Check if event should be ignored
    if is_ignored_event(title, config.ignore_patterns):
        return ProcessedEvent(event, EventType.IGNORED)

    # Check if it's a focus time block
    if is_focus_time_event(title, config.focus_time_patterns):
        customer = extract_customer_name(title, config.customer_name_patterns)
        return ProcessedEvent(event, EventType.FOCUS_TIME, customer_name=customer)

    # Check if it's an internal meeting
    if is_internal_meeting(title, config.internal_meeting_patterns):
        return ProcessedEvent(event, EventType.INTERNAL_MEETING,
                            customer_name=config.internal_meetings_name)

    # Otherwise, try to extract customer name (it's a customer meeting)
    customer = extract_customer_name(title, config.customer_name_patterns)
    if customer:
        return ProcessedEvent(event, EventType.CUSTOMER_MEETING, customer_name=customer)

    # Unknown event type
    return ProcessedEvent(event, EventType.UNKNOWN)


def filter_by_duration(events: List[ProcessedEvent],
                      min_duration_minutes: int) -> List[ProcessedEvent]:
    """
    Filter out events shorter than minimum duration.

    Args:
        events: List of processed events
        min_duration_minutes: Minimum duration in minutes

    Returns:
        Filtered list of events
    """
    min_duration = timedelta(minutes=min_duration_minutes)
    return [e for e in events if e.duration >= min_duration]


def process_events(raw_events: List[Dict[str, Any]],
                   config: SyncConfig,
                   cache_manager=None,
                   require_cache: bool = False) -> List[ProcessedEvent]:
    """
    Process and classify all events.

    Args:
        raw_events: List of raw event dicts from Google Calendar API
        config: Sync configuration
        cache_manager: Optional CacheManager for cached classifications
        require_cache: If True, non-cached events require manual classification

    Returns:
        List of ProcessedEvent objects
    """
    # Classify all events
    processed = [classify_event(event, config, cache_manager, require_cache) for event in raw_events]

    # Filter by minimum duration
    filtered = filter_by_duration(processed, config.minimum_duration_minutes)

    return filtered
