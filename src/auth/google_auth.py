"""
Google OAuth2 authentication handler for Google Calendar API.
"""

import os
import pickle
from typing import Optional
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow


# Scopes required for Google Calendar API (read-only)
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']


class GoogleAuthenticator:
    """Handles Google OAuth2 authentication flow."""

    def __init__(self, credentials_path: str, token_path: str):
        """
        Initialize the authenticator.

        Args:
            credentials_path: Path to the credentials.json file from Google Cloud Console
            token_path: Path to store/load the token.json file (auto-generated)
        """
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.creds: Optional[Credentials] = None

    def authenticate(self) -> Credentials:
        """
        Authenticate with Google and return valid credentials.

        This method:
        1. Loads existing token if available
        2. Refreshes token if expired
        3. Initiates OAuth flow if no valid token exists

        Returns:
            Google OAuth2 Credentials object

        Raises:
            FileNotFoundError: If credentials.json not found
            Exception: If authentication fails
        """
        # Check if credentials.json exists
        if not os.path.exists(self.credentials_path):
            raise FileNotFoundError(
                f"Credentials file not found at: {self.credentials_path}\n"
                f"Please follow the setup instructions to download credentials.json from Google Cloud Console."
            )

        # Load existing token if available
        if os.path.exists(self.token_path):
            try:
                self.creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)
            except Exception as e:
                print(f"Warning: Could not load existing token: {e}")
                self.creds = None

        # If no valid credentials, authenticate
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                # Token expired but can be refreshed
                print("Refreshing expired token...")
                self.creds.refresh(Request())
            else:
                # Need to run OAuth flow
                print("Starting OAuth flow...")
                print("Your browser will open for authentication.")
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, SCOPES
                )
                self.creds = flow.run_local_server(port=0)

            # Save the credentials for next run
            self._save_token()

        return self.creds

    def _save_token(self) -> None:
        """Save credentials to token file."""
        if self.creds:
            # Ensure the directory exists
            os.makedirs(os.path.dirname(self.token_path), exist_ok=True)

            # Save the credentials
            with open(self.token_path, 'w') as token:
                token.write(self.creds.to_json())
            print(f"Token saved to: {self.token_path}")

    def revoke(self) -> None:
        """Revoke credentials and delete token file."""
        if self.creds:
            self.creds.revoke(Request())
            if os.path.exists(self.token_path):
                os.remove(self.token_path)
                print(f"Token revoked and removed: {self.token_path}")


def get_credentials(credentials_path: str, token_path: str) -> Credentials:
    """
    Convenience function to get Google credentials.

    Args:
        credentials_path: Path to credentials.json
        token_path: Path to token.json

    Returns:
        Valid Google OAuth2 Credentials
    """
    authenticator = GoogleAuthenticator(credentials_path, token_path)
    return authenticator.authenticate()
