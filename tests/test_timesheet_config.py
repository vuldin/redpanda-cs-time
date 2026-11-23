import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.timesheet_config import (
    build_customer_aliases,
    build_domain_aliases,
    load_timesheet_config,
    resolve_project_id,
    validate_timesheet_config,
)

MINIMAL_CONFIG = """
clockify:
  workspace_id: "ws-1"
  projects:
    customer: "proj-customer"
    admin: "proj-admin"
    technical_assets: "proj-tech"
    pto: "proj-pto"
  tasks:
    pto_vacation: "task-pto"
    internal_meetings: "task-internal"
    slack_catchup: "task-catchup"
    technical:
      kubernetes: "task-k8s"
    generic_technical_category_task: kubernetes
timezone: "America/Chicago"
customers:
  acme:
    project: customer
    task_id: "task-acme"
    aliases: ["acme corp"]
    domains: ["acme.com"]
"""


def write_config(tmp_path, content):
    path = os.path.join(tmp_path, "config.yaml")
    with open(path, "w") as f:
        f.write(content)
    return path


def test_load_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        load_timesheet_config("/nonexistent/config.yaml")


def test_load_minimal_config_and_validate_clean(tmp_path):
    path = write_config(tmp_path, MINIMAL_CONFIG)
    cfg = load_timesheet_config(path)
    assert cfg.workspace_id == "ws-1"
    assert cfg.timezone == "America/Chicago"
    assert cfg.tasks.generic_technical_category_task == "kubernetes"
    assert "acme" in cfg.customers
    assert validate_timesheet_config(cfg) == []


def test_validate_reports_each_missing_required_field(tmp_path):
    path = write_config(tmp_path, "clockify:\n  workspace_id: null\n")
    cfg = load_timesheet_config(path)
    errors = validate_timesheet_config(cfg)
    assert any("workspace_id" in e for e in errors)
    assert any("projects.customer" in e for e in errors)
    assert any("tasks.pto_vacation" in e for e in errors)
    assert any("tasks.technical" in e for e in errors)


def test_validate_rejects_bad_timezone(tmp_path):
    bad = MINIMAL_CONFIG.replace('timezone: "America/Chicago"', 'timezone: "Not/AZone"')
    path = write_config(tmp_path, bad)
    cfg = load_timesheet_config(path)
    errors = validate_timesheet_config(cfg)
    assert any("timezone" in e for e in errors)


def test_validate_catches_generic_technical_task_not_in_technical_dict(tmp_path):
    bad = MINIMAL_CONFIG.replace(
        "generic_technical_category_task: kubernetes",
        "generic_technical_category_task: nonexistent",
    )
    path = write_config(tmp_path, bad)
    cfg = load_timesheet_config(path)
    errors = validate_timesheet_config(cfg)
    assert any("generic_technical_category_task" in e for e in errors)


def test_build_customer_aliases_includes_canonical_key_and_aliases(tmp_path):
    path = write_config(tmp_path, MINIMAL_CONFIG)
    cfg = load_timesheet_config(path)
    aliases = build_customer_aliases(cfg.customers)
    assert aliases["acme"] == "acme"
    assert aliases["acme corp"] == "acme"


def test_build_domain_aliases(tmp_path):
    path = write_config(tmp_path, MINIMAL_CONFIG)
    cfg = load_timesheet_config(path)
    domains = build_domain_aliases(cfg.customers)
    assert domains["acme.com"] == "acme"


def test_resolve_project_id_key_vs_literal(tmp_path):
    path = write_config(tmp_path, MINIMAL_CONFIG)
    cfg = load_timesheet_config(path)
    assert resolve_project_id(cfg, "customer") == "proj-customer"
    assert resolve_project_id(cfg, "literal-project-id") == "literal-project-id"
