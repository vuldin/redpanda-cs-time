#!/usr/bin/env python3
"""
Generate timesheet from Google Calendar events for submission to Clockify.

All customer names, Clockify project/task IDs, and classification patterns
come from config/config.yaml (see config/config.yaml.example, or run through
SETUP.md to build one with an agent's help).

Usage:
    python scripts/generate_timesheet.py --start 2026-03-09 --end 2026-04-11
    python scripts/generate_timesheet.py --start 2026-03-09 --end 2026-04-11 --submit
    python scripts/generate_timesheet.py --start 2026-03-09 --end 2026-04-11 --output timesheet.json
"""

import argparse
import json
import math
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.clockify.client import ClockifyClient
from config.timesheet_config import (
    TimesheetConfig,
    build_customer_aliases,
    build_domain_aliases,
    load_timesheet_config,
    resolve_project_id,
    validate_timesheet_config,
)


def infer_customer_from_domain(event: Dict, domain_aliases: Dict[str, str]) -> Optional[str]:
    """Fallback customer inference from attendee email domains."""
    for attendee in (event.get('attendees') or []):
        email = attendee.get('email', '')
        if '@' not in email:
            continue
        domain = email.split('@', 1)[1].lower()
        if domain in domain_aliases:
            return domain_aliases[domain]
    return None


def classify_event(summary: str, event_type: str, num_attendees: int,
                    response_status: str, cfg: TimesheetConfig,
                    customer_aliases: Dict[str, str]) -> Tuple[str, Optional[str]]:
    """
    Classify a calendar event.

    Returns: (category, customer_name_or_none)
        category: 'customer', 'internal', 'technical', 'interview', 'pto', 'ignore', 'unknown'
    """
    if not summary:
        return ('ignore', None)

    # Check explicit title overrides first
    override = cfg.title_overrides.get(summary.lower().strip())
    if override:
        return ('customer', override)

    for pattern, cust in cfg.title_regex_overrides:
        if re.search(pattern, summary):
            return ('customer', cust)

    # PTO patterns take precedence over ignore so calendar-driven OOO events
    # become 8h PTO days instead of being dropped.
    for pattern in cfg.patterns.pto_patterns:
        if re.search(pattern, summary):
            return ('pto', None)

    # Check ignore patterns
    for pattern in cfg.patterns.ignore_patterns:
        if re.search(pattern, summary):
            return ('ignore', None)

    # Check if declined
    if response_status == 'declined':
        return ('ignore', None)

    # Check for interview
    for pattern in cfg.patterns.interview_patterns:
        if re.search(pattern, summary):
            return ('interview', None)

    # Check internal patterns
    for pattern in cfg.patterns.internal_patterns:
        if re.search(pattern, summary):
            return ('internal', None)

    # Try to extract customer name from title
    for pattern, group in cfg.patterns.customer_title_patterns:
        m = re.search(pattern, summary)
        if m:
            raw_name = m.group(group).strip()
            normalized = customer_aliases.get(raw_name.lower())
            if normalized:
                return ('customer', normalized)
            # Try partial match. Use word boundaries so short aliases like
            # "ti" don't match substrings of unrelated words (e.g. "Tire").
            raw_lower = raw_name.lower()
            for alias, norm in customer_aliases.items():
                if re.search(r'\b' + re.escape(alias) + r'\b', raw_lower):
                    return ('customer', norm)
                if re.search(r'\b' + re.escape(raw_lower) + r'\b', alias):
                    return ('customer', norm)

    # Check if summary contains a known customer name. Use word boundaries
    # so short aliases don't match substrings of unrelated words.
    summary_lower = summary.lower()
    for alias, norm in customer_aliases.items():
        if re.search(r'\b' + re.escape(alias) + r'\b', summary_lower):
            return ('customer', norm)

    # Internal meetings with "sync" in the name but no customer match
    if (re.search(r'(?i)sync|meeting|standup', summary)
            and num_attendees <= cfg.patterns.internal_fallback_max_attendees):
        return ('internal', None)

    # Bare generic-engineering-topic titles configured as technical literals
    if summary.strip().lower() in cfg.patterns.technical_title_literals:
        return ('technical', None)

    # Generic/unlabeled focus-time and working-location blocks carry no real
    # topic, so only ignore them here - AFTER customer/internal matching -
    # so a focus-time block labeled with an actual customer name still counts
    # as that customer's time instead of being silently dropped.
    if event_type in ('focusTime', 'workingLocation'):
        return ('ignore', None)

    return ('unknown', None)


def parse_events_from_gcal(events: List[Dict], cfg: TimesheetConfig,
                            customer_aliases: Dict[str, str],
                            domain_aliases: Dict[str, str]) -> List[Dict]:
    """Parse raw gcal events into classified entries."""
    entries = []
    tz = ZoneInfo(cfg.timezone)
    for event in events:
        if event.get('allDay', False):
            continue
        # Normalize the gcal eventType enum. The MCP export returns
        # UPPERCASE enum values (FOCUS_TIME, WORKING_LOCATION, ...); the
        # classification logic below expects the camelCase API values.
        _ET_MAP = {'FOCUS_TIME': 'focusTime', 'WORKING_LOCATION': 'workingLocation',
                   'OUT_OF_OFFICE': 'outOfOffice', 'DEFAULT': 'default',
                   'FROM_GMAIL': 'default'}
        _raw_et = event.get('eventType') or 'default'
        event_type = _ET_MAP.get(_raw_et, _raw_et)
        if event_type == 'workingLocation':
            continue

        summary = event.get('summary', '')
        start_info = event.get('start', {})
        end_info = event.get('end', {})

        # All-day events (multi-day OOO/vacation blocks included) carry a
        # 'date' instead of 'dateTime'. Detect the user's own all-day
        # OOO/vacation/holiday events here and expand them into one 8h PTO
        # entry per weekday, so a calendar-side OOO block is picked up
        # automatically instead of requiring a manual config edit every run.
        # Other people's OOO on the calendar (creator is not self) and
        # unrelated all-day events are ignored.
        if not start_info.get('dateTime') and start_info.get('date'):
            is_self = (event.get('creator', {}).get('self')
                       or event.get('organizer', {}).get('self'))
            if is_self and re.search(r'(?i)\bOOO\b|\bvacation\b|\bpublic holiday\b', summary):
                d_dt = datetime.fromisoformat(start_info['date']).replace(tzinfo=tz)
                end_date_str = end_info.get('date')
                end_dt = (datetime.fromisoformat(end_date_str).replace(tzinfo=tz)
                          if end_date_str else d_dt + timedelta(days=1))
                while d_dt < end_dt:
                    if (d_dt.weekday() < 5
                            and d_dt.strftime('%Y-%m-%d') not in cfg.ooo.partial_pto_exclude_dates):
                        entries.append({
                            'date': d_dt.strftime('%Y-%m-%d'),
                            'day': d_dt.strftime('%a'),
                            'start': '00:00', 'end': '23:59',
                            'start_dt': d_dt,
                            'end_dt': d_dt + timedelta(hours=23, minutes=59),
                            'duration_hours': 8, 'rounded_hours': 8,
                            'summary': summary, 'category': 'pto', 'customer': None,
                            'event_type': event_type, 'num_attendees': 1,
                        })
                    d_dt += timedelta(days=1)
            continue

        start_str = start_info.get('dateTime', '')
        end_str = end_info.get('dateTime', '')

        if not start_str or not end_str:
            continue

        start = datetime.fromisoformat(start_str)
        end = datetime.fromisoformat(end_str)
        duration_hours = (end - start).total_seconds() / 3600

        # numAttendees is null in the current MCP shape; fall back to the
        # length of the attendees array (self-only blocks => 1).
        num_attendees = event.get('numAttendees')
        if num_attendees is None:
            num_attendees = len(event.get('attendees') or []) or 1
        response_status = event.get('myResponseStatus')
        if response_status is None:
            self_attendee = next(
                (a for a in (event.get('attendees') or []) if a.get('self')), None
            )
            response_status = (
                self_attendee.get('responseStatus', 'accepted')
                if self_attendee else 'accepted'
            )

        category, customer = classify_event(
            summary, event_type, num_attendees, response_status, cfg, customer_aliases
        )

        # Domain evidence beats the generic title-based fallbacks ('unknown',
        # and 'internal' via the catch-all "sync|meeting|standup" pattern) -
        # a meeting with a known customer's employees on it is customer work
        # even if the title is generic. It does NOT override anything
        # classify_event matched explicitly (ignore/PTO/interview/title
        # overrides/named internal patterns), since those return before ever
        # falling through to the generic fallback.
        if category in ('unknown', 'internal') and not customer:
            domain_customer = infer_customer_from_domain(event, domain_aliases)
            if domain_customer:
                category, customer = 'customer', domain_customer

        if category == 'ignore':
            continue

        # Round up to 1 hour minimum
        rounded_hours = max(1, math.ceil(duration_hours))

        entries.append({
            'date': start.strftime('%Y-%m-%d'),
            'day': start.strftime('%a'),
            'start': start.strftime('%H:%M'),
            'end': end.strftime('%H:%M'),
            'start_dt': start,
            'end_dt': end,
            'duration_hours': duration_hours,
            'rounded_hours': rounded_hours,
            'summary': summary,
            'category': category,
            'customer': customer,
            'event_type': event_type,
            'num_attendees': num_attendees,
        })

    return entries


def handle_overlaps(entries: List[Dict]) -> List[Dict]:
    """
    Handle overlapping events per user's rule:
    - Subtract smaller from larger
    - Round both up to nearest hour
    """
    # Sort by start time
    entries.sort(key=lambda e: e['start_dt'])

    for i in range(len(entries)):
        for j in range(i + 1, len(entries)):
            a = entries[i]
            b = entries[j]

            # Check overlap
            overlap_start = max(a['start_dt'], b['start_dt'])
            overlap_end = min(a['end_dt'], b['end_dt'])

            if overlap_start < overlap_end:
                overlap_hours = (overlap_end - overlap_start).total_seconds() / 3600

                # Determine larger and smaller
                if a['duration_hours'] >= b['duration_hours']:
                    a['duration_hours'] -= overlap_hours
                    a['rounded_hours'] = max(1, math.ceil(a['duration_hours']))
                    b['rounded_hours'] = max(1, math.ceil(b['duration_hours']))
                else:
                    b['duration_hours'] -= overlap_hours
                    b['rounded_hours'] = max(1, math.ceil(b['duration_hours']))
                    a['rounded_hours'] = max(1, math.ceil(a['duration_hours']))

    return entries


def aggregate_by_day_and_customer(entries: List[Dict], cfg: TimesheetConfig) -> Dict:
    """Aggregate hours by date and customer/category."""
    daily = defaultdict(lambda: defaultdict(lambda: {'hours': 0, 'events': []}))

    ooo_weekdays = {d for d in cfg.ooo.dates
                    if datetime.strptime(d, '%Y-%m-%d').weekday() < 5}

    # Calendar-detected PTO dates merged with the static ooo.dates override.
    # Filter ooo_weekdays to the date range covered by entries so prior PTO
    # dates aren't re-injected every run.
    dynamic_pto = {e['date'] for e in entries if e['category'] == 'pto'}
    entry_dates = {e['date'] for e in entries if e.get('date')}
    if entry_dates:
        range_min, range_max = min(entry_dates), max(entry_dates)
        ooo_in_range = {d for d in ooo_weekdays if range_min <= d <= range_max}
    else:
        ooo_in_range = ooo_weekdays
    all_pto_weekdays = ooo_in_range | {
        d for d in dynamic_pto
        if datetime.strptime(d, '%Y-%m-%d').weekday() < 5
    }

    # Add PTO days first
    for pto_date in sorted(all_pto_weekdays):
        daily[pto_date]['_pto']['hours'] = 8
        daily[pto_date]['_pto']['events'] = ['PTO - Vacation']

    for entry in entries:
        date = entry['date']

        # Skip PTO entries themselves (already handled above)
        if entry['category'] == 'pto':
            continue

        # Skip events on PTO days
        if date in all_pto_weekdays:
            continue

        if entry['category'] == 'customer' and entry['customer']:
            key = entry['customer']
        elif entry['category'] == 'internal':
            key = '_internal'
        elif entry['category'] == 'interview':
            key = '_interview'
        elif entry['category'] == 'technical':
            key = '_technical'
        else:
            key = f"_unknown:{entry['summary'][:40]}"

        daily[date][key]['hours'] += entry['rounded_hours']
        daily[date][key]['events'].append(entry['summary'])

    return daily


def get_clockify_mapping(key: str, cfg: TimesheetConfig) -> Tuple[str, str]:
    """Get (project_id, task_id) for a customer/category key."""
    slack_catchup = (resolve_project_id(cfg, 'admin'), cfg.tasks.slack_catchup)

    if key == '_internal':
        return (resolve_project_id(cfg, 'admin'), cfg.tasks.internal_meetings)
    elif key == '_interview':
        if cfg.tasks.interviewing:
            return (resolve_project_id(cfg, 'admin'), cfg.tasks.interviewing)
        return slack_catchup
    elif key == '_technical':
        tech_task = cfg.tasks.technical.get(cfg.tasks.generic_technical_category_task)
        if tech_task:
            return (resolve_project_id(cfg, 'technical_assets'), tech_task)
        return slack_catchup
    elif key == '_pto':
        return (resolve_project_id(cfg, 'pto'), cfg.tasks.pto_vacation)
    elif key.startswith('_unknown'):
        return slack_catchup
    else:
        customer = cfg.customers.get(key)
        if customer and customer.task_id and customer.task_id != "TBD":
            return (resolve_project_id(cfg, customer.project), customer.task_id)
        return slack_catchup


def display_timesheet(daily: Dict, cfg: TimesheetConfig, week_start: str = None):
    """Display timesheet in a readable format."""
    dates = sorted(daily.keys())

    if week_start:
        print(f"\n{'='*70}")
        print(f"  Week of {week_start}")
        print(f"{'='*70}")

    weekly_total = 0
    weekly_by_category = defaultdict(int)

    for date in dates:
        day_data = daily[date]
        day_total = sum(v['hours'] for v in day_data.values())
        weekly_total += day_total

        # Get day name
        dt = datetime.strptime(date, '%Y-%m-%d')
        day_name = dt.strftime('%a %b %d')

        print(f"\n  {day_name} ({day_total}h)")
        print(f"  {'-'*50}")

        for key in sorted(day_data.keys()):
            data = day_data[key]
            hours = data['hours']
            events = data['events']

            if key.startswith('_'):
                display_name = key.replace('_', '').replace('unknown:', 'UNKNOWN: ').title()
            else:
                display_name = key.title()

            weekly_by_category[display_name] += hours

            project_id, task_id = get_clockify_mapping(key, cfg)
            marker = "" if task_id and task_id != "TBD" else " [NO CLOCKIFY TASK]"

            print(f"    {display_name:25s} {hours:2d}h  ({', '.join(events[:3])}){marker}")

    print(f"\n  {'='*50}")
    print(f"  Weekly Total: {weekly_total}h")
    print(f"  By category:")
    for cat in sorted(weekly_by_category.keys()):
        print(f"    {cat:25s} {weekly_by_category[cat]:2d}h")

    return weekly_total


def _format_tz_offset(dt: datetime) -> str:
    """'+0500' -> '+05:00' (colon-separated ISO-8601 offset)."""
    off = dt.strftime('%z')
    return f"{off[:3]}:{off[3:]}" if off else "+00:00"


def generate_clockify_entries(daily: Dict, cfg: TimesheetConfig) -> List[Dict]:
    """Generate Clockify time entry payloads from the daily aggregation."""
    entries = []
    tz = ZoneInfo(cfg.timezone)

    for date in sorted(daily.keys()):
        # Stack entries starting at 9 AM, using actual meeting times where available.
        # Cap the stack so it never crosses midnight (which would produce invalid
        # hour values like T24/T25) - on unusually long days, start earlier instead
        # so the full day's hours still land on this same calendar date.
        total_hours = sum(data['hours'] for data in daily[date].values())
        hour_cursor = min(9, 24 - total_hours) if total_hours > 15 else 9
        day_start = datetime.strptime(date, '%Y-%m-%d').replace(tzinfo=tz)

        for key in sorted(daily[date].keys()):
            data = daily[date][key]
            hours = data['hours']
            project_id, task_id = get_clockify_mapping(key, cfg)

            if not task_id or task_id == "TBD":
                print(f"  WARNING: Skipping {key} on {date} — no Clockify task mapped")
                continue

            for h in range(hours):
                start_time = day_start + timedelta(hours=hour_cursor)
                end_time = day_start + timedelta(hours=hour_cursor + 1)
                hour_cursor += 1

                entry = {
                    "start": start_time.strftime('%Y-%m-%dT%H:%M:%S') + _format_tz_offset(start_time),
                    "end": end_time.strftime('%Y-%m-%dT%H:%M:%S') + _format_tz_offset(end_time),
                    "projectId": project_id,
                    "taskId": task_id,
                    "description": "",
                    "billable": True,
                }
                entries.append(entry)

    return entries


def submit_to_clockify(entries: List[Dict], cfg: TimesheetConfig, dry_run: bool = True):
    """Submit time entries to Clockify."""
    if dry_run:
        print(f"\n[DRY RUN] Would create {len(entries)} time entries:")
        for e in entries[:5]:
            print(f"  {e['start'][:16]} - {e['end'][:16]} | project: {e['projectId'][:8]}... | task: {e['taskId'][:8]}...")
        if len(entries) > 5:
            print(f"  ... and {len(entries) - 5} more")
        return

    try:
        from dotenv import load_dotenv
        load_dotenv('credentials/.env')
    except ImportError:
        # python-dotenv not installed; rely on shell having sourced credentials/.env
        # (e.g. `set -a && source credentials/.env && set +a`).
        pass

    if not os.getenv('CLOCKIFY_API_KEY'):
        print("ERROR: CLOCKIFY_API_KEY not set. Either install python-dotenv "
              "or run: set -a && source credentials/.env && set +a")
        sys.exit(1)

    if not cfg.workspace_id:
        print("ERROR: clockify.workspace_id is not set in config/config.yaml")
        sys.exit(1)

    client = ClockifyClient()
    created = 0
    errors = 0

    for entry in entries:
        try:
            client.create_time_entry(cfg.workspace_id, entry)
            created += 1
            if created % 10 == 0:
                print(f"  Created {created}/{len(entries)} entries...")
        except Exception as e:
            errors += 1
            print(f"  ERROR creating entry {entry['start']}: {e}")

    print(f"\nDone: {created} created, {errors} errors")


def main():
    parser = argparse.ArgumentParser(description='Generate timesheet from Google Calendar')
    parser.add_argument('--start', required=True, help='Start date (YYYY-MM-DD, should be a Monday)')
    parser.add_argument('--end', required=True, help='End date (YYYY-MM-DD)')
    parser.add_argument('--calendar-json', help='Path to calendar events JSON (from gcal MCP export)')
    parser.add_argument('--output', help='Output timesheet as JSON file')
    parser.add_argument('--submit', action='store_true', help='Actually submit to Clockify (default: dry run)')
    parser.add_argument('--extra', help='Path to JSON file with extra entries to add (Slack-based estimates)')
    parser.add_argument('--config', default='config/config.yaml', help='Path to config file')
    args = parser.parse_args()

    cfg = load_timesheet_config(args.config)
    config_errors = validate_timesheet_config(cfg)
    if config_errors:
        print("Config is missing required fields:")
        for err in config_errors:
            print(f"  - {err}")
        if args.submit:
            print("\nRefusing to submit with an incomplete config. "
                  "Fill in the missing fields (see config/config.yaml.example "
                  "or SETUP.md) and try again.")
            sys.exit(1)
        print("\nContinuing in dry-run mode, but entries for missing "
              "buckets will be skipped.\n")

    customer_aliases = build_customer_aliases(cfg.customers)
    domain_aliases = build_domain_aliases(cfg.customers)

    start_date = datetime.strptime(args.start, '%Y-%m-%d')
    end_date = datetime.strptime(args.end, '%Y-%m-%d')

    # Load calendar events
    if args.calendar_json:
        with open(args.calendar_json) as f:
            raw = json.load(f)
            if isinstance(raw, list) and len(raw) > 0 and 'text' in raw[0]:
                cal_data = json.loads(raw[0]['text'])
            elif 'events' in raw:
                cal_data = raw
            else:
                cal_data = raw
            events = cal_data.get('events', [])
    else:
        # Use Google Calendar API directly
        from src.auth.google_auth import GoogleAuthenticator
        from src.calendar.client import CalendarClient

        creds_path, token_path = 'credentials/credentials.json', 'credentials/token.json'
        try:
            from config.settings import load_config as load_app_config
            google_cfg = load_app_config(args.config).google
            creds_path, token_path = google_cfg.credentials_path, google_cfg.token_path
        except Exception:
            pass

        auth = GoogleAuthenticator(creds_path, token_path)
        creds = auth.authenticate()
        cal_client = CalendarClient(creds)

        events = cal_client.get_events(
            time_min=start_date.isoformat() + 'Z',
            time_max=(end_date + timedelta(days=1)).isoformat() + 'Z',
            max_results=500
        )

    # Parse and classify
    entries = parse_events_from_gcal(events, cfg, customer_aliases, domain_aliases)
    entries = handle_overlaps(entries)

    # Load extra entries (Slack-based)
    if args.extra:
        with open(args.extra) as f:
            extras = json.load(f)
            for ex in extras:
                # Convert string datetimes to datetime objects for overlap handling
                if isinstance(ex.get('start_dt'), str):
                    ex['start_dt'] = datetime.fromisoformat(ex['start_dt'])
                if isinstance(ex.get('end_dt'), str):
                    ex['end_dt'] = datetime.fromisoformat(ex['end_dt'])
            entries.extend(extras)

    # Aggregate by day
    daily = aggregate_by_day_and_customer(entries, cfg)

    # Display by week
    current = start_date
    grand_total = 0
    while current <= end_date:
        week_end = current + timedelta(days=5)
        week_daily = {d: daily[d] for d in daily if current.strftime('%Y-%m-%d') <= d < week_end.strftime('%Y-%m-%d')}
        if week_daily:
            total = display_timesheet(week_daily, cfg, current.strftime('%Y-%m-%d'))
            grand_total += total
        current += timedelta(days=7)

    print(f"\n{'='*70}")
    print(f"  GRAND TOTAL: {grand_total}h across {(end_date - start_date).days // 7 + 1} weeks")
    print(f"{'='*70}")

    # Generate Clockify entries
    clockify_entries = generate_clockify_entries(daily, cfg)

    if args.output:
        with open(args.output, 'w') as f:
            json.dump(clockify_entries, f, indent=2)
        print(f"\nSaved {len(clockify_entries)} entries to {args.output}")

    # Submit or dry run
    submit_to_clockify(clockify_entries, cfg, dry_run=not args.submit)


if __name__ == '__main__':
    main()
