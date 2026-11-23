"""
Configuration for the timesheet-generation pipeline (generate_timesheet.py,
check_coverage.py).

Independent of config/settings.py (which serves the separate, simpler
validate_parsing.py / src/calendar/processor.py pipeline) — both read the
same config/config.yaml file, under different top-level keys.
"""

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import yaml


@dataclass
class ClockifyProjectsConfig:
    customer: Optional[str] = None
    admin: Optional[str] = None
    technical_assets: Optional[str] = None
    pto: Optional[str] = None
    interviewing: Optional[str] = None


@dataclass
class ClockifyTasksConfig:
    pto_vacation: Optional[str] = None
    internal_meetings: Optional[str] = None
    slack_catchup: Optional[str] = None
    interviewing: Optional[str] = None
    technical: Dict[str, str] = field(default_factory=dict)
    generic_technical_category_task: Optional[str] = None


@dataclass
class CustomerConfig:
    project: str = ""      # key into ClockifyProjectsConfig, or a literal project id
    task_id: str = ""
    aliases: List[str] = field(default_factory=list)
    domains: List[str] = field(default_factory=list)


@dataclass
class ClassificationPatternsConfig:
    pto_patterns: List[str] = field(default_factory=list)
    ignore_patterns: List[str] = field(default_factory=list)
    internal_patterns: List[str] = field(default_factory=list)
    interview_patterns: List[str] = field(default_factory=list)
    customer_title_patterns: List[Tuple[str, int]] = field(default_factory=list)
    technical_title_literals: List[str] = field(default_factory=list)
    internal_fallback_max_attendees: int = 10


@dataclass
class OOOConfig:
    dates: List[str] = field(default_factory=list)
    partial_pto_exclude_dates: List[str] = field(default_factory=list)


@dataclass
class SessionScanConfig:
    mode: str = "none"   # none | this_repo | allowlist | all
    allowed_paths: List[str] = field(default_factory=list)


@dataclass
class YapaConfig:
    enabled: bool = False
    chroma_url: str = "http://localhost:8000"


@dataclass
class TimesheetConfig:
    workspace_id: Optional[str] = None
    timezone: str = "UTC"
    projects: ClockifyProjectsConfig = field(default_factory=ClockifyProjectsConfig)
    tasks: ClockifyTasksConfig = field(default_factory=ClockifyTasksConfig)
    customers: Dict[str, CustomerConfig] = field(default_factory=dict)
    title_overrides: Dict[str, str] = field(default_factory=dict)
    title_regex_overrides: List[Tuple[str, str]] = field(default_factory=list)
    patterns: ClassificationPatternsConfig = field(default_factory=ClassificationPatternsConfig)
    ooo: OOOConfig = field(default_factory=OOOConfig)
    session_scan: SessionScanConfig = field(default_factory=SessionScanConfig)
    yapa: YapaConfig = field(default_factory=YapaConfig)


def load_timesheet_config(path: str = "config/config.yaml") -> TimesheetConfig:
    """Load a TimesheetConfig from YAML. Raises FileNotFoundError pointing at
    config.yaml.example (or SETUP.md) if the file doesn't exist yet."""
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Configuration file not found: {path}\n"
            f"Copy config/config.yaml.example to {path} and fill it in, "
            f"or walk through SETUP.md."
        )

    with open(path) as f:
        data: Dict[str, Any] = yaml.safe_load(f) or {}

    clockify = data.get("clockify", {}) or {}
    projects_data = clockify.get("projects", {}) or {}
    tasks_data = clockify.get("tasks", {}) or {}

    projects = ClockifyProjectsConfig(
        customer=projects_data.get("customer"),
        admin=projects_data.get("admin"),
        technical_assets=projects_data.get("technical_assets"),
        pto=projects_data.get("pto"),
        interviewing=projects_data.get("interviewing"),
    )
    tasks = ClockifyTasksConfig(
        pto_vacation=tasks_data.get("pto_vacation"),
        internal_meetings=tasks_data.get("internal_meetings"),
        slack_catchup=tasks_data.get("slack_catchup"),
        interviewing=tasks_data.get("interviewing"),
        technical=dict(tasks_data.get("technical", {}) or {}),
        generic_technical_category_task=tasks_data.get("generic_technical_category_task"),
    )

    customers: Dict[str, CustomerConfig] = {}
    for key, c in (data.get("customers", {}) or {}).items():
        c = c or {}
        customers[key] = CustomerConfig(
            project=c.get("project", ""),
            task_id=str(c.get("task_id", "")),
            aliases=list(c.get("aliases", []) or []),
            domains=list(c.get("domains", []) or []),
        )

    title_regex_overrides = [
        (item["pattern"], item["customer"])
        for item in (data.get("title_regex_overrides", []) or [])
    ]

    cls_data = data.get("classification", {}) or {}
    customer_title_patterns = [
        (item["pattern"], item.get("group", 1))
        for item in (cls_data.get("customer_title_patterns", []) or [])
    ]
    patterns = ClassificationPatternsConfig(
        pto_patterns=list(cls_data.get("pto_patterns", []) or []),
        ignore_patterns=list(cls_data.get("ignore_patterns", []) or []),
        internal_patterns=list(cls_data.get("internal_patterns", []) or []),
        interview_patterns=list(cls_data.get("interview_patterns", []) or []),
        customer_title_patterns=customer_title_patterns,
        technical_title_literals=list(cls_data.get("technical_title_literals", []) or []),
        internal_fallback_max_attendees=cls_data.get("internal_fallback_max_attendees", 10),
    )

    ooo_data = data.get("ooo", {}) or {}
    ooo = OOOConfig(
        dates=list(ooo_data.get("dates", []) or []),
        partial_pto_exclude_dates=list(ooo_data.get("partial_pto_exclude_dates", []) or []),
    )

    ss_data = data.get("session_scan", {}) or {}
    session_scan = SessionScanConfig(
        mode=ss_data.get("mode", "none"),
        allowed_paths=list(ss_data.get("allowed_paths", []) or []),
    )

    yapa_data = data.get("yapa", {}) or {}
    yapa = YapaConfig(
        enabled=bool(yapa_data.get("enabled", False)),
        chroma_url=yapa_data.get("chroma_url", "http://localhost:8000"),
    )

    return TimesheetConfig(
        workspace_id=clockify.get("workspace_id"),
        timezone=data.get("timezone", "UTC"),
        projects=projects,
        tasks=tasks,
        customers=customers,
        title_overrides=dict(data.get("title_overrides", {}) or {}),
        title_regex_overrides=title_regex_overrides,
        patterns=patterns,
        ooo=ooo,
        session_scan=session_scan,
        yapa=yapa,
    )


def validate_timesheet_config(cfg: TimesheetConfig) -> List[str]:
    """Check every REQUIRED field is set. Returns a list of human-readable
    errors (empty if the config is complete enough to run the pipeline)."""
    errors: List[str] = []

    if not cfg.workspace_id:
        errors.append("clockify.workspace_id is not set")

    for name in ("customer", "admin", "technical_assets", "pto"):
        if not getattr(cfg.projects, name):
            errors.append(f"clockify.projects.{name} is not set")

    for name in ("pto_vacation", "internal_meetings", "slack_catchup"):
        if not getattr(cfg.tasks, name):
            errors.append(f"clockify.tasks.{name} is not set")

    if not cfg.tasks.technical:
        errors.append("clockify.tasks.technical needs at least one entry")

    if not cfg.tasks.generic_technical_category_task:
        errors.append("clockify.tasks.generic_technical_category_task is not set")
    elif cfg.tasks.generic_technical_category_task not in cfg.tasks.technical:
        errors.append(
            "clockify.tasks.generic_technical_category_task "
            f"({cfg.tasks.generic_technical_category_task!r}) is not a key "
            "in clockify.tasks.technical"
        )

    try:
        from zoneinfo import ZoneInfo
        ZoneInfo(cfg.timezone)
    except Exception:
        errors.append(f"timezone {cfg.timezone!r} is not a valid IANA timezone name")

    if cfg.session_scan.mode not in ("none", "this_repo", "allowlist", "all"):
        errors.append(
            f"session_scan.mode {cfg.session_scan.mode!r} must be one of "
            "none/this_repo/allowlist/all"
        )

    return errors


def resolve_project_id(cfg: TimesheetConfig, project_ref: str) -> str:
    """A customer's `project` field (or a hardcoded category like '_internal')
    names a key into clockify.projects; fall back to treating it as a literal
    project id if it isn't a known key (so power users can skip the indirection)."""
    projects_by_key = {
        "customer": cfg.projects.customer,
        "admin": cfg.projects.admin,
        "technical_assets": cfg.projects.technical_assets,
        "pto": cfg.projects.pto,
        "interviewing": cfg.projects.interviewing,
    }
    if project_ref in projects_by_key and projects_by_key[project_ref]:
        return projects_by_key[project_ref]
    return project_ref


def build_customer_aliases(customers: Dict[str, CustomerConfig]) -> Dict[str, str]:
    """alias-or-canonical-key -> canonical key, lowercased."""
    aliases: Dict[str, str] = {}
    for key, c in customers.items():
        aliases[key.lower()] = key
        for a in c.aliases:
            aliases[a.lower()] = key
    return aliases


def build_domain_aliases(customers: Dict[str, CustomerConfig]) -> Dict[str, str]:
    """email domain -> canonical customer key, lowercased."""
    domains: Dict[str, str] = {}
    for key, c in customers.items():
        for d in c.domains:
            domains[d.lower()] = key
    return domains
