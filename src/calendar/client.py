"""
Google Calendar API client for fetching calendar events.
"""

from datetime import datetime, timezone
from typing import List, Dict, Any
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials


class CalendarClient:
    """Client for interacting with Google Calendar API."""

    def __init__(self, credentials: Credentials, calendar_id: str = 'primary'):
        """
        Initialize the Calendar client.

        Args:
            credentials: Google OAuth2 credentials
            calendar_id: Calendar ID to use (default: 'primary' for main calendar)
        """
        self.credentials = credentials
        self.calendar_id = calendar_id
        self.service = build('calendar', 'v3', credentials=credentials)

    def get_events(self, time_min: datetime, time_max: datetime,
                   max_results: int = 250) -> List[Dict[str, Any]]:
        """
        Fetch all events within a time range.

        IMPORTANT: This fetches ALL events, not just focus time blocks.
        This is necessary for detecting overlaps between focus time and meetings.

        Args:
            time_min: Start of time range (inclusive)
            time_max: End of time range (exclusive)
            max_results: Maximum number of events to return (default: 250)

        Returns:
            List of event dictionaries with the following structure:
            [
                {
                    'id': 'event_id',
                    'summary': 'Event title',
                    'start': {'dateTime': '2026-01-20T09:00:00-08:00', ...},
                    'end': {'dateTime': '2026-01-20T10:00:00-08:00', ...},
                    'description': 'Event description',
                    ...
                }
            ]

        Raises:
            HttpError: If API request fails
        """
        try:
            # Convert datetime to RFC3339 format (ISO 8601)
            time_min_str = time_min.isoformat()
            time_max_str = time_max.isoformat()

            print(f"Fetching events from {time_min_str} to {time_max_str}...")

            # Call the Calendar API
            events_result = self.service.events().list(
                calendarId=self.calendar_id,
                timeMin=time_min_str,
                timeMax=time_max_str,
                maxResults=max_results,
                singleEvents=True,  # Expand recurring events
                orderBy='startTime'  # Order by start time
            ).execute()

            events = events_result.get('items', [])

            print(f"Found {len(events)} events")

            # Filter out all-day events (they don't have 'dateTime' field)
            timed_events = []
            for event in events:
                start = event.get('start', {})
                end = event.get('end', {})

                # Skip all-day events (they have 'date' instead of 'dateTime')
                if 'dateTime' not in start or 'dateTime' not in end:
                    continue

                timed_events.append(event)

            print(f"Filtered to {len(timed_events)} timed events (excluding all-day events)")

            return timed_events

        except HttpError as error:
            print(f"An error occurred: {error}")
            raise

    def get_calendar_info(self) -> Dict[str, Any]:
        """
        Get information about the calendar.

        Returns:
            Dictionary with calendar metadata (name, timezone, etc.)

        Raises:
            HttpError: If API request fails
        """
        try:
            calendar = self.service.calendars().get(calendarId=self.calendar_id).execute()
            return calendar
        except HttpError as error:
            print(f"An error occurred: {error}")
            raise

    def list_calendars(self) -> List[Dict[str, Any]]:
        """
        List all calendars accessible to the user.

        Returns:
            List of calendar dictionaries with id, summary, description, etc.

        Raises:
            HttpError: If API request fails
        """
        try:
            calendar_list = self.service.calendarList().list().execute()
            return calendar_list.get('items', [])
        except HttpError as error:
            print(f"An error occurred: {error}")
            raise


def format_event(event: Dict[str, Any]) -> str:
    """
    Format an event for display.

    Args:
        event: Event dictionary from Calendar API

    Returns:
        Formatted string representation of the event
    """
    summary = event.get('summary', '(No title)')
    start = event.get('start', {}).get('dateTime', 'Unknown')
    end = event.get('end', {}).get('dateTime', 'Unknown')

    return f"{summary}: {start} to {end}"
