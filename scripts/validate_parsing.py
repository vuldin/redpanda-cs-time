#!/usr/bin/env python3
"""
Interactive validation script to review calendar parsing before syncing to Clockify.

This script:
1. Fetches all calendar events for a week
2. Classifies them using cache + patterns
3. Prompts for unknown events interactively
4. Allows review/edit of ALL classifications
5. Displays aggregated time by customer
6. Allows excluding specific events from sync

Usage:
    python scripts/validate_parsing_v2.py [--week YYYY-MM-DD] [--config path/to/config.yaml]
"""

import argparse
import sys
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv('credentials/.env')

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.auth.google_auth import get_credentials
from src.calendar.client import CalendarClient
from src.calendar.processor import process_events, EventType
from src.calendar.overlap import process_overlaps
from src.utils.date_utils import get_week_range, format_week_range, parse_week_start
from src.utils.cache_manager import CacheManager
from src.utils.classification_buckets import BucketManager
from src.utils.interactive import handle_unknown_events, interactive_review_mode
from src.utils.display import (
    display_overlap_adjustments, display_ignored_events,
    format_time_range
)
from src.clockify.client import get_clockify_client
from config.settings import load_config, validate_config


def display_aggregated_time_with_exclusions(events, focus_adjustments, config, show_excluded=True):
    """Display aggregated time, optionally showing excluded events."""
    from src.utils.date_utils import round_hours
    from tabulate import tabulate

    # Aggregate by customer (excluding events marked for exclusion)
    customer_hours = {}
    excluded_hours = {}

    # Add adjusted focus time
    for focus_event, adjusted_duration, _ in focus_adjustments:
        customer = focus_event.customer_name or 'Unknown'
        hours = adjusted_duration.total_seconds() / 3600

        if focus_event.exclude_from_sync:
            excluded_hours[customer] = excluded_hours.get(customer, 0) + hours
        else:
            customer_hours[customer] = customer_hours.get(customer, 0) + hours

    # Add customer meetings
    for event in events:
        if event.event_type == EventType.CUSTOMER_MEETING:
            customer = event.customer_name or 'Unknown'
            hours = event.duration_hours()

            if event.exclude_from_sync:
                excluded_hours[customer] = excluded_hours.get(customer, 0) + hours
            else:
                customer_hours[customer] = customer_hours.get(customer, 0) + hours

    # Add internal meetings
    internal_hours = 0
    excluded_internal_hours = 0

    for event in events:
        if event.event_type == EventType.INTERNAL_MEETING:
            hours = event.duration_hours()
            if event.exclude_from_sync:
                excluded_internal_hours += hours
            else:
                internal_hours += hours

    if internal_hours > 0:
        customer_hours['Internal Meetings'] = internal_hours

    if excluded_internal_hours > 0:
        excluded_hours['Internal Meetings'] = excluded_internal_hours

    # Round hours
    rounded_hours = {}
    for customer, hours in customer_hours.items():
        if customer == 'Internal Meetings':
            rounded = round_hours(hours, config.sync.internal_rounding_mode)
        else:
            rounded = round_hours(hours, config.sync.rounding_mode)
        rounded_hours[customer] = rounded

    # Display table
    print("\n" + "="*80)
    print("TIME TO SYNC TO CLOCKIFY")
    print("="*80)

    if not rounded_hours:
        print("\nNo time to sync (all events excluded or ignored).")
        return rounded_hours

    table_data = []
    for bucket_name in sorted(rounded_hours.keys()):
        raw = customer_hours[bucket_name]
        rounded = rounded_hours[bucket_name]
        bucket_type = "Internal" if bucket_name == "Internal Meetings" else "Customer"
        table_data.append([bucket_name, bucket_type, f"{raw:.1f}h", f"{rounded}h"])

    print(tabulate(
        table_data,
        headers=['Bucket', 'Type', 'Raw Hours', 'Rounded Hours'],
        tablefmt='grid'
    ))

    total_raw = sum(customer_hours.values())
    total_rounded = sum(rounded_hours.values())
    print(f"\nTotal: {total_raw:.1f}h raw, {total_rounded}h rounded")

    # Show excluded events if any
    if show_excluded and excluded_hours:
        print("\n" + "="*80)
        print("EXCLUDED FROM SYNC")
        print("="*80)
        print("\nThe following time will NOT be synced to Clockify:\n")

        for customer in sorted(excluded_hours.keys()):
            print(f"  {customer}: {excluded_hours[customer]:.1f}h")

        total_excluded = sum(excluded_hours.values())
        print(f"\nTotal excluded: {total_excluded:.1f}h")

    return rounded_hours


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Interactive validation and review before syncing to Clockify'
    )
    parser.add_argument(
        '--week',
        type=str,
        help='Week start date (YYYY-MM-DD, defaults to current week)'
    )
    parser.add_argument(
        '--config',
        type=str,
        default='config/config.yaml',
        help='Path to config file (default: config/config.yaml)'
    )
    parser.add_argument(
        '--no-interactive',
        action='store_true',
        help='Skip interactive review mode'
    )

    args = parser.parse_args()

    # Load configuration
    print("Loading configuration...")
    try:
        config = load_config(args.config)
        errors = validate_config(config)
        if errors:
            print("Configuration errors:", file=sys.stderr)
            for error in errors:
                print(f"  - {error}", file=sys.stderr)
            return 1
        print("✓ Configuration loaded")
    except Exception as e:
        print(f"Error loading configuration: {e}", file=sys.stderr)
        return 1

    # Load cache
    print("Loading classification cache...")
    cache_manager = CacheManager()
    print(f"✓ Loaded {len(cache_manager.list_all())} cached classifications")

    # Initialize Clockify client (optional, for project list)
    clockify_client = None
    if os.getenv('CLOCKIFY_API_KEY'):
        try:
            print("Connecting to Clockify...")
            clockify_client = get_clockify_client()
            # Test connection
            user = clockify_client.get_user()
            print(f"✓ Connected to Clockify as {user.get('name', 'Unknown')}")
        except Exception as e:
            print(f"Warning: Could not connect to Clockify: {e}")
            print("Classification will work without Clockify project list.")
            clockify_client = None
    else:
        print("Note: CLOCKIFY_API_KEY not set. Classification will work without Clockify project list.")

    # Create bucket manager
    bucket_manager = BucketManager(
        cache_manager,
        clockify_client,
        config.clockify.workspace_id
    )

    # Determine week range
    if args.week:
        try:
            week_start = parse_week_start(args.week)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
    else:
        week_start = None

    start_dt, end_dt = get_week_range(week_start)

    print("\n" + "="*80)
    print("CALENDAR PARSING & VALIDATION")
    print("="*80)
    print(format_week_range(start_dt, end_dt))
    print("="*80)

    # Authenticate
    try:
        print("\nAuthenticating with Google Calendar...")
        credentials = get_credentials(config.google.credentials_path,
                                     config.google.token_path)
        print("✓ Authentication successful")
    except Exception as e:
        print(f"Authentication error: {e}", file=sys.stderr)
        return 1

    # Fetch events
    try:
        print(f"Fetching events from calendar: {config.google.calendar_id}...")
        calendar_client = CalendarClient(credentials, config.google.calendar_id)
        raw_events = calendar_client.get_events(start_dt, end_dt)
        print(f"✓ Found {len(raw_events)} events")
    except Exception as e:
        print(f"Error fetching events: {e}", file=sys.stderr)
        return 1

    if not raw_events:
        print("\nNo events found for this week.")
        return 0

    # Process events (with cache, require manual classification for non-cached events)
    print("\nProcessing and classifying events...")
    events = process_events(raw_events, config.sync, cache_manager, require_cache=True)

    # Count by type
    type_counts = {}
    for event in events:
        type_counts[event.event_type] = type_counts.get(event.event_type, 0) + 1

    print(f"✓ Classified {len(events)} events:")
    for event_type, count in sorted(type_counts.items()):
        print(f"  - {event_type}: {count}")

    # Handle unknown events interactively (manual classification required)
    unknown_count = type_counts.get(EventType.UNKNOWN, 0)
    if unknown_count > 0:
        events = handle_unknown_events(events, cache_manager, bucket_manager)
        if events is None:
            return 1

    # Process overlaps
    print("\nCalculating focus time adjustments...")
    focus_adjustments = process_overlaps(events)
    print(f"✓ Processed {len(focus_adjustments)} focus time blocks")

    # Display results
    display_overlap_adjustments(focus_adjustments)
    display_aggregated_time_with_exclusions(events, focus_adjustments, config)
    display_ignored_events(events)

    # Interactive review mode
    if not args.no_interactive:
        print("\n" + "="*80)
        print("Would you like to review/edit classifications before syncing?")
        review = input("Enter 'y' for interactive review, or press Enter to continue: ").strip().lower()

        if review == 'y':
            events = interactive_review_mode(events, focus_adjustments, cache_manager, bucket_manager)
            if events is None:
                print("\nExiting without sync.")
                return 0

            # Recalculate after edits
            focus_adjustments = process_overlaps(events)
            display_aggregated_time_with_exclusions(events, focus_adjustments, config)

    # Final summary
    print("\n" + "="*80)
    print("✓ VALIDATION COMPLETE")
    print("="*80)
    print("\nNext steps:")
    print("1. If everything looks correct, proceed to Phase 2 (Clockify sync)")
    print("2. Classifications are cached for future runs")
    print("3. You can re-run this script anytime to review")

    return 0


if __name__ == '__main__':
    sys.exit(main())
