#!/usr/bin/env python3
"""
Development script to fetch and display calendar events.

This script is used to test the Google Calendar API integration and verify
that we can fetch all events for a given week.

Usage:
    python scripts/fetch_events.py [--week YYYY-MM-DD]
"""

import argparse
import sys
import os
from datetime import datetime
from tabulate import tabulate

# Add parent directory to path so we can import from src
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.auth.google_auth import get_credentials
from src.calendar.client import CalendarClient
from src.utils.date_utils import get_week_range, format_week_range, parse_week_start


def format_datetime(dt_str: str) -> str:
    """Format datetime string for display."""
    try:
        dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        return dt.strftime('%a %d %H:%M')
    except:
        return dt_str


def format_duration(start_str: str, end_str: str) -> str:
    """Calculate and format duration between start and end times."""
    try:
        start = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
        end = datetime.fromisoformat(end_str.replace('Z', '+00:00'))
        duration = end - start
        hours = duration.total_seconds() / 3600
        return f"{hours:.1f}h"
    except:
        return "N/A"


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description='Fetch and display Google Calendar events for a week'
    )
    parser.add_argument(
        '--week',
        type=str,
        help='Week start date (YYYY-MM-DD, defaults to current week)'
    )
    parser.add_argument(
        '--credentials',
        type=str,
        default='credentials/credentials.json',
        help='Path to credentials.json (default: credentials/credentials.json)'
    )
    parser.add_argument(
        '--token',
        type=str,
        default='credentials/token.json',
        help='Path to token.json (default: credentials/token.json)'
    )
    parser.add_argument(
        '--calendar-id',
        type=str,
        default='primary',
        help='Calendar ID to use (default: primary)'
    )

    args = parser.parse_args()

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

    print("=" * 80)
    print(format_week_range(start_dt, end_dt))
    print("=" * 80)
    print()

    # Authenticate with Google
    try:
        print("Authenticating with Google Calendar...")
        credentials = get_credentials(args.credentials, args.token)
        print("✓ Authentication successful")
        print()
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        print("\nSetup Instructions:", file=sys.stderr)
        print("1. Go to https://console.cloud.google.com/", file=sys.stderr)
        print("2. Create a project and enable Google Calendar API", file=sys.stderr)
        print("3. Create OAuth 2.0 credentials (Desktop app)", file=sys.stderr)
        print("4. Download credentials.json to credentials/ directory", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Authentication error: {e}", file=sys.stderr)
        return 1

    # Create Calendar client
    calendar_client = CalendarClient(credentials, args.calendar_id)

    # Fetch events
    try:
        events = calendar_client.get_events(start_dt, end_dt)
    except Exception as e:
        print(f"Error fetching events: {e}", file=sys.stderr)
        return 1

    if not events:
        print("No events found for this week.")
        return 0

    # Display events in a table
    table_data = []
    for event in events:
        summary = event.get('summary', '(No title)')
        start = event.get('start', {}).get('dateTime', '')
        end = event.get('end', {}).get('dateTime', '')

        table_data.append([
            format_datetime(start),
            format_datetime(end),
            format_duration(start, end),
            summary
        ])

    print(tabulate(
        table_data,
        headers=['Start', 'End', 'Duration', 'Title'],
        tablefmt='grid'
    ))

    print()
    print(f"Total events: {len(events)}")
    print()

    return 0


if __name__ == '__main__':
    sys.exit(main())
