"""
Configuration management for the calendar sync application.
"""

import os
import yaml
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field


@dataclass
class GoogleConfig:
    """Google Calendar API configuration."""
    credentials_path: str = 'credentials/credentials.json'
    token_path: str = 'credentials/token.json'
    calendar_id: str = 'primary'


@dataclass
class ClockifyConfig:
    """Clockify API configuration."""
    workspace_id: Optional[str] = None
    default_project_id: Optional[str] = None


@dataclass
class SyncConfig:
    """Sync behavior configuration."""
    focus_time_patterns: List[str] = field(default_factory=list)
    customer_name_patterns: List[str] = field(default_factory=list)
    internal_meeting_patterns: List[str] = field(default_factory=list)
    ignore_patterns: List[str] = field(default_factory=list)
    minimum_duration_minutes: int = 15
    rounding_mode: str = 'nearest'
    internal_rounding_mode: str = 'up'
    description_template: str = 'Focus time: {customer_name}'
    internal_meetings_name: str = 'Internal Meetings'


@dataclass
class LoggingConfig:
    """Logging configuration."""
    level: str = 'INFO'
    console: bool = True
    file: Optional[str] = None


@dataclass
class AppConfig:
    """Main application configuration."""
    google: GoogleConfig = field(default_factory=GoogleConfig)
    clockify: ClockifyConfig = field(default_factory=ClockifyConfig)
    sync: SyncConfig = field(default_factory=SyncConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)


def load_config(config_path: str = 'config/config.yaml') -> AppConfig:
    """
    Load configuration from YAML file.

    Args:
        config_path: Path to the configuration file

    Returns:
        AppConfig object with loaded configuration

    Raises:
        FileNotFoundError: If config file doesn't exist
        yaml.YAMLError: If config file is invalid
    """
    if not os.path.exists(config_path):
        raise FileNotFoundError(
            f"Configuration file not found: {config_path}\n"
            f"Please copy config/config.yaml.example to config/config.yaml and customize it."
        )

    with open(config_path, 'r') as f:
        data = yaml.safe_load(f)

    # Parse Google config
    google_data = data.get('google', {})
    google_config = GoogleConfig(
        credentials_path=google_data.get('credentials_path', 'credentials/credentials.json'),
        token_path=google_data.get('token_path', 'credentials/token.json'),
        calendar_id=google_data.get('calendar_id', 'primary')
    )

    # Parse Clockify config
    clockify_data = data.get('clockify', {})
    clockify_config = ClockifyConfig(
        workspace_id=clockify_data.get('workspace_id'),
        default_project_id=clockify_data.get('default_project_id')
    )

    # Parse Sync config
    sync_data = data.get('sync', {})
    sync_config = SyncConfig(
        focus_time_patterns=sync_data.get('focus_time_patterns', []),
        customer_name_patterns=sync_data.get('customer_name_patterns', []),
        internal_meeting_patterns=sync_data.get('internal_meeting_patterns', []),
        ignore_patterns=sync_data.get('ignore_patterns', []),
        minimum_duration_minutes=sync_data.get('minimum_duration_minutes', 15),
        rounding_mode=sync_data.get('rounding_mode', 'nearest'),
        internal_rounding_mode=sync_data.get('internal_rounding_mode', 'up'),
        description_template=sync_data.get('description_template', 'Focus time: {customer_name}'),
        internal_meetings_name=sync_data.get('internal_meetings_name', 'Internal Meetings')
    )

    # Parse Logging config
    logging_data = data.get('logging', {})
    logging_config = LoggingConfig(
        level=logging_data.get('level', 'INFO'),
        console=logging_data.get('console', True),
        file=logging_data.get('file')
    )

    return AppConfig(
        google=google_config,
        clockify=clockify_config,
        sync=sync_config,
        logging=logging_config
    )


def validate_config(config: AppConfig) -> List[str]:
    """
    Validate configuration and return list of errors.

    Args:
        config: AppConfig object to validate

    Returns:
        List of error messages (empty if valid)
    """
    errors = []

    # Validate Google config
    if not os.path.exists(config.google.credentials_path):
        errors.append(f"Google credentials file not found: {config.google.credentials_path}")

    # Validate sync patterns
    if not config.sync.focus_time_patterns:
        errors.append("No focus time patterns configured")

    if not config.sync.customer_name_patterns:
        errors.append("No customer name patterns configured")

    # Validate rounding mode
    valid_rounding = ['nearest', 'up', 'down', 'none']
    if config.sync.rounding_mode not in valid_rounding:
        errors.append(f"Invalid rounding_mode: {config.sync.rounding_mode}")

    if config.sync.internal_rounding_mode not in valid_rounding:
        errors.append(f"Invalid internal_rounding_mode: {config.sync.internal_rounding_mode}")

    return errors
