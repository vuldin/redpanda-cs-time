import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.timesheet_config import (
    ClockifyProjectsConfig,
    ClockifyTasksConfig,
    TimesheetConfig,
)
from scripts.generate_timesheet import generate_clockify_entries


def make_cfg(timezone):
    return TimesheetConfig(
        timezone=timezone,
        projects=ClockifyProjectsConfig(customer="proj-customer", admin="proj-admin",
                                         technical_assets="proj-tech", pto="proj-pto"),
        tasks=ClockifyTasksConfig(pto_vacation="task-pto", internal_meetings="task-internal",
                                   slack_catchup="task-catchup",
                                   technical={"kubernetes": "task-k8s"},
                                   generic_technical_category_task="kubernetes"),
    )


def test_standard_time_offset_before_dst_fallback():
    # 2026-10-15 is during US daylight saving time -> America/Chicago is CDT (-05:00)
    cfg = make_cfg("America/Chicago")
    daily = {"2026-10-15": {"_internal": {"hours": 1, "events": ["x"]}}}
    entries = generate_clockify_entries(daily, cfg)
    assert entries[0]["start"].endswith("-05:00")


def test_standard_time_offset_after_dst_fallback():
    # 2026-11-02 is after the Nov 1 2026 US DST fallback -> CST (-06:00)
    cfg = make_cfg("America/Chicago")
    daily = {"2026-11-02": {"_internal": {"hours": 1, "events": ["x"]}}}
    entries = generate_clockify_entries(daily, cfg)
    assert entries[0]["start"].endswith("-06:00")


def test_different_timezone_resolves_its_own_offset():
    cfg = make_cfg("America/New_York")
    daily = {"2026-11-02": {"_internal": {"hours": 1, "events": ["x"]}}}
    entries = generate_clockify_entries(daily, cfg)
    assert entries[0]["start"].endswith("-05:00")  # EST after fallback


def test_entries_never_cross_midnight_on_a_long_day():
    cfg = make_cfg("UTC")
    daily = {"2026-01-05": {"_internal": {"hours": 18, "events": ["x"]}}}
    entries = generate_clockify_entries(daily, cfg)
    for e in entries:
        assert e["start"][:10] == "2026-01-05"
        assert e["end"][:10] in ("2026-01-05", "2026-01-06")
        hour = int(e["start"][11:13])
        assert 0 <= hour <= 23
