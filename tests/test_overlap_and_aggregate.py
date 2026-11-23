import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.timesheet_config import OOOConfig, TimesheetConfig
from scripts.generate_timesheet import aggregate_by_day_and_customer, handle_overlaps


def entry(date, start_h, end_h, category="customer", customer="acme", summary="Acme sync"):
    start_dt = datetime(2026, 1, int(date[-2:]), start_h, 0)
    end_dt = datetime(2026, 1, int(date[-2:]), end_h, 0)
    duration = (end_dt - start_dt).total_seconds() / 3600
    return {
        "date": date, "day": start_dt.strftime("%a"),
        "start": start_dt.strftime("%H:%M"), "end": end_dt.strftime("%H:%M"),
        "start_dt": start_dt, "end_dt": end_dt,
        "duration_hours": duration, "rounded_hours": int(duration),
        "summary": summary, "category": category, "customer": customer,
        "event_type": "default", "num_attendees": 2,
    }


def test_handle_overlaps_subtracts_smaller_from_larger():
    a = entry("2026-01-05", 9, 12, summary="Big block")   # 3h
    b = entry("2026-01-05", 10, 11, summary="Small meeting")  # 1h, fully inside a
    handle_overlaps([a, b])
    assert a["rounded_hours"] == 2  # 3h - 1h overlap
    assert b["rounded_hours"] == 1  # unaffected


def test_handle_overlaps_no_overlap_leaves_both_alone():
    a = entry("2026-01-05", 9, 10)
    b = entry("2026-01-05", 11, 12)
    handle_overlaps([a, b])
    assert a["rounded_hours"] == 1
    assert b["rounded_hours"] == 1


def test_aggregate_buckets_by_customer_and_date():
    entries = [
        entry("2026-01-05", 9, 11, customer="acme"),
        entry("2026-01-05", 11, 12, category="internal", customer=None),
    ]
    cfg = TimesheetConfig(ooo=OOOConfig(dates=[]))
    daily = aggregate_by_day_and_customer(entries, cfg)
    assert daily["2026-01-05"]["acme"]["hours"] == 2
    assert daily["2026-01-05"]["_internal"]["hours"] == 1


def test_aggregate_applies_ooo_dates_as_full_pto_day():
    entries = [entry("2026-01-05", 9, 11, customer="acme")]
    cfg = TimesheetConfig(ooo=OOOConfig(dates=["2026-01-05"]))
    daily = aggregate_by_day_and_customer(entries, cfg)
    assert daily["2026-01-05"]["_pto"]["hours"] == 8
    assert "acme" not in daily["2026-01-05"]


def test_aggregate_calendar_detected_pto_does_not_double_count():
    entries = [entry("2026-01-05", 0, 8, category="pto", customer=None)]
    cfg = TimesheetConfig(ooo=OOOConfig(dates=[]))
    daily = aggregate_by_day_and_customer(entries, cfg)
    assert daily["2026-01-05"]["_pto"]["hours"] == 8
    assert len(daily["2026-01-05"]) == 1
