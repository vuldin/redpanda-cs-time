import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.timesheet_config import (
    ClockifyProjectsConfig,
    ClockifyTasksConfig,
    CustomerConfig,
    TimesheetConfig,
)
from scripts.generate_timesheet import get_clockify_mapping


def make_cfg():
    return TimesheetConfig(
        projects=ClockifyProjectsConfig(customer="proj-customer", admin="proj-admin",
                                         technical_assets="proj-tech", pto="proj-pto"),
        tasks=ClockifyTasksConfig(pto_vacation="task-pto", internal_meetings="task-internal",
                                   slack_catchup="task-catchup", interviewing="task-interview",
                                   technical={"kubernetes": "task-k8s", "redpanda": "task-rp"},
                                   generic_technical_category_task="kubernetes"),
        customers={
            "acme": CustomerConfig(project="customer", task_id="task-acme"),
            "unmapped": CustomerConfig(project="customer", task_id="TBD"),
        },
    )


def test_internal_maps_to_admin_internal_task():
    cfg = make_cfg()
    assert get_clockify_mapping("_internal", cfg) == ("proj-admin", "task-internal")


def test_interview_maps_to_configured_task():
    cfg = make_cfg()
    assert get_clockify_mapping("_interview", cfg) == ("proj-admin", "task-interview")


def test_interview_falls_back_to_slack_catchup_when_unset():
    cfg = make_cfg()
    cfg.tasks.interviewing = None
    assert get_clockify_mapping("_interview", cfg) == ("proj-admin", "task-catchup")


def test_technical_maps_to_generic_technical_category_task():
    cfg = make_cfg()
    assert get_clockify_mapping("_technical", cfg) == ("proj-tech", "task-k8s")


def test_pto_maps_to_pto_task():
    cfg = make_cfg()
    assert get_clockify_mapping("_pto", cfg) == ("proj-pto", "task-pto")


def test_unknown_prefix_falls_back_to_slack_catchup():
    cfg = make_cfg()
    assert get_clockify_mapping("_unknown:some title", cfg) == ("proj-admin", "task-catchup")


def test_known_customer_resolves_to_its_own_task():
    cfg = make_cfg()
    assert get_clockify_mapping("acme", cfg) == ("proj-customer", "task-acme")


def test_customer_with_tbd_task_falls_back_to_slack_catchup():
    cfg = make_cfg()
    assert get_clockify_mapping("unmapped", cfg) == ("proj-admin", "task-catchup")


def test_unrecognized_key_falls_back_to_slack_catchup():
    cfg = make_cfg()
    assert get_clockify_mapping("never-heard-of-it", cfg) == ("proj-admin", "task-catchup")
