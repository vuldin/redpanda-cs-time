"""
Management of classification buckets (customers, internal, ignore, etc.)
"""

from typing import List, Dict, Optional, Set
from src.utils.cache_manager import CacheManager
from src.clockify.client import ClockifyClient


class ClassificationBucket:
    """Represents a classification bucket option."""

    def __init__(self, name: str, bucket_type: str, project_id: Optional[str] = None):
        """
        Initialize a classification bucket.

        Args:
            name: Display name (e.g., "ArcticWolf", "Internal Meetings")
            bucket_type: Type ('customer', 'internal', 'ignore')
            project_id: Optional Clockify project ID
        """
        self.name = name
        self.bucket_type = bucket_type
        self.project_id = project_id

    def __repr__(self):
        return f"ClassificationBucket(name='{self.name}', type={self.bucket_type})"


class BucketManager:
    """Manages available classification buckets."""

    def __init__(self, cache_manager: CacheManager,
                 clockify_client: Optional[ClockifyClient] = None,
                 workspace_id: Optional[str] = None):
        """
        Initialize bucket manager.

        Args:
            cache_manager: Cache manager for stored classifications
            clockify_client: Optional Clockify client for fetching projects
            workspace_id: Clockify workspace ID
        """
        self.cache_manager = cache_manager
        self.clockify_client = clockify_client
        self.workspace_id = workspace_id
        self._clockify_projects: Optional[List[Dict]] = None

    def _fetch_clockify_projects(self) -> List[Dict]:
        """Fetch projects from Clockify API (cached)."""
        if self._clockify_projects is None and self.clockify_client and self.workspace_id:
            try:
                self._clockify_projects = self.clockify_client.get_projects(self.workspace_id)
            except Exception as e:
                print(f"Warning: Could not fetch Clockify projects: {e}")
                self._clockify_projects = []
        return self._clockify_projects or []

    def get_customer_buckets(self) -> List[ClassificationBucket]:
        """
        Get all customer classification buckets.

        Returns customers from:
        1. Clockify projects (if available)
        2. Cached classifications

        Returns:
            List of customer buckets, sorted alphabetically
        """
        buckets = {}

        # Get from Clockify projects
        projects = self._fetch_clockify_projects()
        for project in projects:
            name = project.get('name', '')
            project_id = project.get('id', '')
            if name:
                buckets[name] = ClassificationBucket(name, 'customer', project_id)

        # Get from cache (may add customers not in Clockify)
        cached = self.cache_manager.list_all()
        for title, classification in cached.items():
            if classification.classification == 'customer_meeting' and classification.customer_name:
                customer = classification.customer_name
                if customer not in buckets:
                    # Not in Clockify, but was used before
                    buckets[customer] = ClassificationBucket(customer, 'customer', None)

        return sorted(buckets.values(), key=lambda b: b.name)

    def get_all_buckets(self) -> List[ClassificationBucket]:
        """
        Get all classification buckets (customers, internal, ignore).

        Returns:
            List of all available buckets
        """
        buckets = []

        # Add customer buckets
        buckets.extend(self.get_customer_buckets())

        # Add internal meetings bucket
        buckets.append(ClassificationBucket("Internal Meetings", 'internal'))

        # Add ignore bucket
        buckets.append(ClassificationBucket("Ignore", 'ignore'))

        return buckets

    def get_bucket_by_name(self, name: str) -> Optional[ClassificationBucket]:
        """
        Get a bucket by name.

        Args:
            name: Bucket name

        Returns:
            ClassificationBucket or None
        """
        for bucket in self.get_all_buckets():
            if bucket.name == name:
                return bucket
        return None
