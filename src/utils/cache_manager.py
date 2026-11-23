"""
Cache manager for storing meeting classifications and user preferences.
"""

import os
import json
from datetime import datetime
from typing import Dict, Optional, Any
from dataclasses import dataclass, asdict


@dataclass
class MeetingClassification:
    """Cached classification for a meeting title."""
    classification: str  # 'customer_meeting', 'internal_meeting', 'ignored'
    customer_name: Optional[str] = None
    last_seen: Optional[str] = None
    exclude_from_sync: bool = False  # User can mark events to not sync

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'classification': self.classification,
            'customer_name': self.customer_name,
            'last_seen': self.last_seen,
            'exclude_from_sync': self.exclude_from_sync
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MeetingClassification':
        """Create from dictionary."""
        return cls(
            classification=data.get('classification', 'unknown'),
            customer_name=data.get('customer_name'),
            last_seen=data.get('last_seen'),
            exclude_from_sync=data.get('exclude_from_sync', False)
        )


class CacheManager:
    """Manages cached meeting classifications."""

    def __init__(self, cache_path: str = 'cache/meeting_classifications.json'):
        """
        Initialize cache manager.

        Args:
            cache_path: Path to cache file
        """
        self.cache_path = cache_path
        self.cache: Dict[str, MeetingClassification] = {}
        self.load()

    def load(self) -> None:
        """Load cache from file."""
        if not os.path.exists(self.cache_path):
            self.cache = {}
            return

        try:
            with open(self.cache_path, 'r') as f:
                data = json.load(f)

            self.cache = {
                title: MeetingClassification.from_dict(classification)
                for title, classification in data.get('meeting_titles', {}).items()
            }
        except Exception as e:
            print(f"Warning: Could not load cache: {e}")
            self.cache = {}

    def save(self) -> None:
        """Save cache to file."""
        # Ensure directory exists
        os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)

        data = {
            'meeting_titles': {
                title: classification.to_dict()
                for title, classification in self.cache.items()
            },
            'last_updated': datetime.now().isoformat()
        }

        with open(self.cache_path, 'w') as f:
            json.dump(data, f, indent=2)

    def get(self, title: str) -> Optional[MeetingClassification]:
        """
        Get cached classification for a meeting title.

        Args:
            title: Meeting title

        Returns:
            MeetingClassification or None if not cached
        """
        return self.cache.get(title)

    def set(self, title: str, classification: str,
            customer_name: Optional[str] = None,
            exclude_from_sync: bool = False) -> None:
        """
        Store classification for a meeting title.

        Args:
            title: Meeting title
            classification: Classification type
            customer_name: Customer name (if applicable)
            exclude_from_sync: Whether to exclude from Clockify sync
        """
        self.cache[title] = MeetingClassification(
            classification=classification,
            customer_name=customer_name,
            last_seen=datetime.now().date().isoformat(),
            exclude_from_sync=exclude_from_sync
        )
        self.save()

    def update_classification(self, title: str, classification: str,
                             customer_name: Optional[str] = None) -> None:
        """
        Update classification for an existing meeting.

        Args:
            title: Meeting title
            classification: New classification
            customer_name: New customer name (if applicable)
        """
        cached = self.cache.get(title)
        if cached:
            cached.classification = classification
            cached.customer_name = customer_name
            cached.last_seen = datetime.now().date().isoformat()
        else:
            self.set(title, classification, customer_name)
        self.save()

    def set_exclude_from_sync(self, title: str, exclude: bool) -> None:
        """
        Mark a meeting to be excluded from Clockify sync.

        Args:
            title: Meeting title
            exclude: True to exclude, False to include
        """
        cached = self.cache.get(title)
        if cached:
            cached.exclude_from_sync = exclude
            self.save()

    def is_excluded_from_sync(self, title: str) -> bool:
        """
        Check if a meeting is excluded from sync.

        Args:
            title: Meeting title

        Returns:
            True if excluded, False otherwise
        """
        cached = self.cache.get(title)
        return cached.exclude_from_sync if cached else False

    def list_all(self) -> Dict[str, MeetingClassification]:
        """Get all cached classifications."""
        return self.cache.copy()

    def clear(self) -> None:
        """Clear all cached classifications."""
        self.cache = {}
        self.save()
