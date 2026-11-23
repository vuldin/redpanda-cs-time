import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.timesheet_config import (
    ClassificationPatternsConfig,
    ClockifyProjectsConfig,
    ClockifyTasksConfig,
    CustomerConfig,
    TimesheetConfig,
    build_customer_aliases,
)
from scripts.generate_timesheet import classify_event


def make_cfg():
    cfg = TimesheetConfig(
        workspace_id="ws-1",
        timezone="America/Chicago",
        projects=ClockifyProjectsConfig(customer="proj-customer", admin="proj-admin",
                                         technical_assets="proj-tech", pto="proj-pto"),
        tasks=ClockifyTasksConfig(pto_vacation="task-pto", internal_meetings="task-internal",
                                   slack_catchup="task-catchup",
                                   technical={"kubernetes": "task-k8s"},
                                   generic_technical_category_task="kubernetes"),
        customers={
            "acme": CustomerConfig(project="customer", task_id="task-acme",
                                    aliases=["acme corp"], domains=["acme.com"]),
        },
        title_overrides={"exact override title": "acme"},
        title_regex_overrides=[(r"^Regex Override \d+$", "acme")],
        patterns=ClassificationPatternsConfig(
            pto_patterns=[r"(?i)\bOOO\b"],
            ignore_patterns=[r"(?i)doctor"],
            internal_patterns=[r"(?i)standup"],
            interview_patterns=[r"(?i)interview"],
            customer_title_patterns=[(r"(?i)(\w[\w\s.]+?)\s*<>\s*Redpanda", 1)],
            technical_title_literals=["wasm"],
            internal_fallback_max_attendees=10,
        ),
    )
    return cfg, build_customer_aliases(cfg.customers)


def classify(summary, event_type="default", num_attendees=2, response_status="accepted"):
    cfg, aliases = make_cfg()
    return classify_event(summary, event_type, num_attendees, response_status, cfg, aliases)


def test_empty_summary_is_ignored():
    assert classify("") == ("ignore", None)


def test_title_override_wins_over_everything():
    assert classify("Exact Override Title") == ("customer", "acme")


def test_title_regex_override():
    assert classify("Regex Override 42") == ("customer", "acme")


def test_pto_pattern():
    assert classify("OOO - vacation") == ("pto", None)


def test_ignore_pattern():
    assert classify("Doctor appointment") == ("ignore", None)


def test_declined_is_ignored():
    assert classify("Acme <> Redpanda sync", response_status="declined") == ("ignore", None)


def test_interview_pattern():
    assert classify("Candidate interview") == ("interview", None)


def test_internal_pattern():
    assert classify("Weekly standup") == ("internal", None)


def test_customer_title_pattern_match():
    assert classify("Acme <> Redpanda") == ("customer", "acme")


def test_customer_alias_substring_match():
    assert classify("Quick sync with Acme Corp") == ("customer", "acme")


def test_generic_sync_falls_back_to_internal():
    assert classify("Project sync", num_attendees=3) == ("internal", None)


def test_generic_sync_with_too_many_attendees_is_unknown():
    cfg, aliases = make_cfg()
    result = classify_event("Big sync", "default", 11, "accepted", cfg, aliases)
    assert result == ("unknown", None)


def test_technical_title_literal():
    assert classify("wasm") == ("technical", None)


def test_focus_time_with_no_match_is_ignored():
    assert classify("Focus Time", event_type="focusTime") == ("ignore", None)


def test_focus_time_with_customer_name_counts_as_customer():
    assert classify("Acme Corp", event_type="focusTime") == ("customer", "acme")


def test_unmatched_title_is_unknown():
    assert classify("Completely unrelated gibberish title xyz") == ("unknown", None)
