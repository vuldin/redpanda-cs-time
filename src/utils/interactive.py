"""
Interactive prompts for event classification and review.
"""

from typing import List, Tuple, Optional
from src.calendar.processor import ProcessedEvent, EventType
from src.utils.cache_manager import CacheManager
from src.utils.classification_buckets import BucketManager, ClassificationBucket
from src.utils.display import format_time_range, format_duration_hours


def prompt_classify_unknown_event(event: ProcessedEvent,
                                  bucket_manager: BucketManager) -> Tuple[str, Optional[str]]:
    """
    Prompt user to classify an unknown event with dynamic bucket options.

    Args:
        event: Unknown event to classify
        bucket_manager: Bucket manager for available classifications

    Returns:
        Tuple of (classification, customer_name)
        classification: 'customer_meeting', 'internal_meeting', 'ignored'
        customer_name: Customer name if applicable
    """
    print(f"\n{'='*80}")
    print(f"UNKNOWN EVENT: {event.title}")
    print(f"{'='*80}")
    print(f"Time: {format_time_range(event.start, event.end)}")
    print(f"Duration: {format_duration_hours(event.duration)}")
    print()
    print("How should this event be classified?")
    print()

    # Get all available buckets
    buckets = bucket_manager.get_all_buckets()

    # Display numbered options
    for idx, bucket in enumerate(buckets, 1):
        print(f"  {idx}. {bucket.name}")

    # Add "New customer" option
    new_customer_idx = len(buckets) + 1
    print(f"  {new_customer_idx}. New customer (not in list)")
    print()

    while True:
        choice = input(f"Choose [1-{new_customer_idx}]: ").strip()

        try:
            choice_num = int(choice)
        except ValueError:
            print(f"Invalid choice. Please enter a number between 1 and {new_customer_idx}.")
            continue

        # Check if user selected an existing bucket
        if 1 <= choice_num <= len(buckets):
            bucket = buckets[choice_num - 1]

            if bucket.bucket_type == 'customer':
                return ('customer_meeting', bucket.name)
            elif bucket.bucket_type == 'internal':
                return ('internal_meeting', 'Internal Meetings')
            elif bucket.bucket_type == 'ignore':
                return ('ignored', None)

        # Check if user selected "New customer"
        elif choice_num == new_customer_idx:
            return prompt_new_customer(bucket_manager)

        else:
            print(f"Invalid choice. Please enter a number between 1 and {new_customer_idx}.")


def prompt_new_customer(bucket_manager: BucketManager) -> Tuple[str, Optional[str]]:
    """
    Prompt for a new customer, showing Clockify projects if available.

    Args:
        bucket_manager: Bucket manager with Clockify access

    Returns:
        Tuple of ('customer_meeting', customer_name)
    """
    print("\nNew customer classification:")

    # Try to fetch Clockify projects
    customer_buckets = bucket_manager.get_customer_buckets()

    # Show Clockify projects if available
    if customer_buckets:
        print("\nAvailable projects from Clockify:")
        for idx, bucket in enumerate(customer_buckets, 1):
            status = " [In Clockify]" if bucket.project_id else " [Previously used]"
            print(f"  {idx}. {bucket.name}{status}")

        manual_entry_idx = len(customer_buckets) + 1
        print(f"  {manual_entry_idx}. Enter custom name")
        print()

        while True:
            choice = input(f"Choose [1-{manual_entry_idx}]: ").strip()

            try:
                choice_num = int(choice)
            except ValueError:
                print(f"Invalid choice. Please enter a number between 1 and {manual_entry_idx}.")
                continue

            if 1 <= choice_num <= len(customer_buckets):
                bucket = customer_buckets[choice_num - 1]
                return ('customer_meeting', bucket.name)

            elif choice_num == manual_entry_idx:
                customer = input("Enter customer name: ").strip()
                if customer:
                    return ('customer_meeting', customer)
                print("Customer name cannot be empty. Try again.")

            else:
                print(f"Invalid choice. Please enter a number between 1 and {manual_entry_idx}.")

    else:
        # No Clockify projects available, just prompt for name
        while True:
            customer = input("Enter customer name: ").strip()
            if customer:
                return ('customer_meeting', customer)
            print("Customer name cannot be empty. Try again.")


def handle_unknown_events(events: List[ProcessedEvent],
                         cache_manager: CacheManager,
                         bucket_manager: BucketManager) -> List[ProcessedEvent]:
    """
    Interactively classify all unknown events and update cache.

    Args:
        events: List of all events (some may be unknown)
        cache_manager: Cache manager to store classifications
        bucket_manager: Bucket manager for available classifications

    Returns:
        Updated list of events with classifications applied
    """
    unknown_events = [e for e in events if e.event_type == EventType.UNKNOWN]

    if not unknown_events:
        return events

    print(f"\nFound {len(unknown_events)} unknown/unclear events.")
    print("Please classify each one:\n")

    # Update events list
    updated_events = []
    for event in events:
        if event.event_type == EventType.UNKNOWN:
            # Prompt for classification
            classification, customer_name = prompt_classify_unknown_event(event, bucket_manager)

            # Save to cache
            cache_manager.set(event.title, classification, customer_name)

            # Update event
            if classification == 'customer_meeting':
                event.event_type = EventType.CUSTOMER_MEETING
                event.customer_name = customer_name
            elif classification == 'internal_meeting':
                event.event_type = EventType.INTERNAL_MEETING
                event.customer_name = 'Internal Meetings'
            elif classification == 'ignored':
                event.event_type = EventType.IGNORED

            updated_events.append(event)
            print(f"✓ Saved classification for '{event.title}'")
        else:
            updated_events.append(event)

    print(f"\n✓ All events classified!")
    return updated_events


def display_event_list(events: List[ProcessedEvent],
                      focus_adjustments: List[Tuple]) -> None:
    """
    Display numbered list of events for review/editing.

    Args:
        events: List of processed events
        focus_adjustments: Focus time adjustments
    """
    from src.utils.display import format_event_type

    print(f"\n{'='*80}")
    print("ALL EVENTS - REVIEW")
    print(f"{'='*80}\n")

    # Create lookup for focus adjustments
    focus_adj_map = {}
    for focus_event, adjusted_duration, overlaps in focus_adjustments:
        focus_adj_map[focus_event.event_id] = (adjusted_duration, overlaps)

    idx = 1
    event_indices = {}

    # Sort events by start time
    sorted_events = sorted(events, key=lambda e: e.start)

    for event in sorted_events:
        if event.event_type == EventType.IGNORED:
            continue  # Skip ignored events in the list

        event_indices[idx] = event

        # Display event
        sync_status = " [EXCLUDED FROM SYNC]" if event.exclude_from_sync else ""
        print(f"{idx}. {event.title}{sync_status}")
        print(f"   Time: {format_time_range(event.start, event.end)}")
        print(f"   Type: {format_event_type(event.event_type)}")
        print(f"   Customer: {event.customer_name or 'N/A'}")

        # Show adjustment for focus time
        if event.event_type == EventType.FOCUS_TIME and event.event_id in focus_adj_map:
            adjusted_duration, overlaps = focus_adj_map[event.event_id]
            adj_hours = adjusted_duration.total_seconds() / 3600
            orig_hours = event.duration_hours()
            if len(overlaps) > 0:
                print(f"   Duration: {orig_hours:.1f}h → {adj_hours:.1f}h (adjusted for {len(overlaps)} overlaps)")
            else:
                print(f"   Duration: {orig_hours:.1f}h")
        else:
            print(f"   Duration: {format_duration_hours(event.duration)}")

        print()
        idx += 1

    return event_indices


def interactive_review_mode(events: List[ProcessedEvent],
                           focus_adjustments: List[Tuple],
                           cache_manager: CacheManager,
                           bucket_manager: BucketManager) -> List[ProcessedEvent]:
    """
    Interactive mode to review and edit event classifications.

    Args:
        events: List of all events
        focus_adjustments: Focus time adjustments
        cache_manager: Cache manager
        bucket_manager: Bucket manager

    Returns:
        Updated list of events
    """
    while True:
        print(f"\n{'='*80}")
        print("INTERACTIVE REVIEW MODE")
        print(f"{'='*80}")
        print("\nOptions:")
        print("  v - View all events")
        print("  e - Edit an event classification")
        print("  x - Exclude/include event from Clockify sync")
        print("  d - Done (proceed to sync)")
        print("  q - Quit without syncing")
        print()

        choice = input("Choose [v/e/x/d/q]: ").strip().lower()

        if choice == 'v':
            display_event_list(events, focus_adjustments)

        elif choice == 'e':
            event_indices = display_event_list(events, focus_adjustments)
            idx_input = input(f"\nEnter event number to edit [1-{len(event_indices)}]: ").strip()

            try:
                idx = int(idx_input)
                if idx not in event_indices:
                    print(f"Invalid event number. Please enter 1-{len(event_indices)}.")
                    continue

                event = event_indices[idx]
                print(f"\nEditing: {event.title}")

                # Use bucket manager for reclassification
                classification, customer_name = prompt_classify_unknown_event(event, bucket_manager)

                # Update event
                if classification == 'customer_meeting':
                    event.event_type = EventType.CUSTOMER_MEETING
                    event.customer_name = customer_name
                    cache_manager.update_classification(event.title, 'customer_meeting', customer_name)
                    print(f"✓ Updated '{event.title}' to customer meeting for {customer_name}")

                elif classification == 'internal_meeting':
                    event.event_type = EventType.INTERNAL_MEETING
                    event.customer_name = 'Internal Meetings'
                    cache_manager.update_classification(event.title, 'internal_meeting', 'Internal Meetings')
                    print(f"✓ Updated '{event.title}' to internal meeting")

                elif classification == 'ignored':
                    event.event_type = EventType.IGNORED
                    cache_manager.update_classification(event.title, 'ignored')
                    print(f"✓ Updated '{event.title}' to ignored")

            except ValueError:
                print("Invalid input. Please enter a number.")

        elif choice == 'x':
            event_indices = display_event_list(events, focus_adjustments)
            idx_input = input(f"\nEnter event number to exclude/include [1-{len(event_indices)}]: ").strip()

            try:
                idx = int(idx_input)
                if idx not in event_indices:
                    print(f"Invalid event number. Please enter 1-{len(event_indices)}.")
                    continue

                event = event_indices[idx]
                current_status = "EXCLUDED" if event.exclude_from_sync else "INCLUDED"
                print(f"\n'{event.title}' is currently {current_status} from Clockify sync.")
                print("  1. Exclude from sync")
                print("  2. Include in sync")
                print("  3. Cancel")

                exclude_choice = input("Choose [1-3]: ").strip()

                if exclude_choice == '1':
                    event.exclude_from_sync = True
                    cache_manager.set_exclude_from_sync(event.title, True)
                    print(f"✓ '{event.title}' will be EXCLUDED from sync")

                elif exclude_choice == '2':
                    event.exclude_from_sync = False
                    cache_manager.set_exclude_from_sync(event.title, False)
                    print(f"✓ '{event.title}' will be INCLUDED in sync")

                elif exclude_choice == '3':
                    print("Cancelled.")

            except ValueError:
                print("Invalid input. Please enter a number.")

        elif choice == 'd':
            print("\n✓ Review complete. Proceeding...")
            return events

        elif choice == 'q':
            print("\nExiting without syncing.")
            return None

        else:
            print("Invalid choice. Please enter v, e, x, d, or q.")
