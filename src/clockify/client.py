"""
Clockify API client for time entry management.
"""

import os
import requests
from typing import List, Dict, Any, Optional


class ClockifyClient:
    """Client for interacting with Clockify API."""

    BASE_URL = "https://api.clockify.me/api/v1"

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Clockify client.

        Args:
            api_key: Clockify API key (or loaded from CLOCKIFY_API_KEY env var)
        """
        self.api_key = api_key or os.getenv('CLOCKIFY_API_KEY')
        if not self.api_key:
            raise ValueError(
                "Clockify API key not found. "
                "Set CLOCKIFY_API_KEY environment variable or pass api_key parameter."
            )

        self.headers = {
            'X-Api-Key': self.api_key,
            'Content-Type': 'application/json'
        }

    def _request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """
        Make API request with error handling.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (e.g., '/user')
            **kwargs: Additional arguments for requests

        Returns:
            Response object

        Raises:
            requests.HTTPError: If request fails
        """
        url = f"{self.BASE_URL}{endpoint}"
        response = requests.request(method, url, headers=self.headers, **kwargs)
        response.raise_for_status()
        return response

    def get_user(self) -> Dict[str, Any]:
        """
        Get current user information.

        Returns:
            User dict with id, name, email, etc.
        """
        response = self._request('GET', '/user')
        return response.json()

    def get_workspaces(self) -> List[Dict[str, Any]]:
        """
        Get all workspaces accessible to the user.

        Returns:
            List of workspace dicts
        """
        response = self._request('GET', '/workspaces')
        return response.json()

    def get_projects(self, workspace_id: str) -> List[Dict[str, Any]]:
        """
        Get all projects in a workspace.

        Args:
            workspace_id: Workspace ID

        Returns:
            List of project dicts with id, name, clientName, etc.
        """
        response = self._request('GET', f'/workspaces/{workspace_id}/projects')
        return response.json()

    def get_tasks(self, workspace_id: str, project_id: str) -> List[Dict[str, Any]]:
        """
        Get all tasks in a project.

        Args:
            workspace_id: Workspace ID
            project_id: Project ID

        Returns:
            List of task dicts with id, name, etc.
        """
        response = self._request(
            'GET', f'/workspaces/{workspace_id}/projects/{project_id}/tasks'
        )
        return response.json()

    def get_clients(self, workspace_id: str) -> List[Dict[str, Any]]:
        """
        Get all clients in a workspace.

        Args:
            workspace_id: Workspace ID

        Returns:
            List of client dicts with id, name, etc.
        """
        response = self._request('GET', f'/workspaces/{workspace_id}/clients')
        return response.json()

    def get_time_entries(self, workspace_id: str, user_id: str,
                        start: str, end: str) -> List[Dict[str, Any]]:
        """
        Get time entries for a user within a date range.

        Args:
            workspace_id: Workspace ID
            user_id: User ID
            start: Start datetime in ISO format (e.g., '2026-01-20T00:00:00Z')
            end: End datetime in ISO format

        Returns:
            List of time entry dicts
        """
        params = {
            'start': start,
            'end': end
        }
        response = self._request(
            'GET',
            f'/workspaces/{workspace_id}/user/{user_id}/time-entries',
            params=params
        )
        return response.json()

    def create_time_entry(self, workspace_id: str, entry: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new time entry.

        Args:
            workspace_id: Workspace ID
            entry: Time entry dict with structure:
                {
                    "start": "2026-01-24T09:00:00Z",
                    "end": "2026-01-24T12:00:00Z",
                    "projectId": "project-id",
                    "description": "Time entry description"
                }

        Returns:
            Created time entry dict
        """
        response = self._request(
            'POST',
            f'/workspaces/{workspace_id}/time-entries',
            json=entry
        )
        return response.json()


def get_clockify_client(api_key: Optional[str] = None) -> ClockifyClient:
    """
    Get Clockify client instance.

    Args:
        api_key: Optional API key (defaults to CLOCKIFY_API_KEY env var)

    Returns:
        ClockifyClient instance
    """
    return ClockifyClient(api_key)
