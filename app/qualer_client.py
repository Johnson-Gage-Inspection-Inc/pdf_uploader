# app/qualer_client.py
from os import getenv
from threading import Lock
from typing import Optional
from uuid import UUID
from dotenv import load_dotenv
from qualer_sdk.client import AuthenticatedClient
from app.config import LIVEAPI, QUALER_ENDPOINT, QUALER_STAGING_ENDPOINT

load_dotenv()  # Load environment variables from .env file (if present)

# Module-level cached client and a lock for thread-safe lazy initialization
_QUALER_CLIENT: Optional[AuthenticatedClient] = None
_QUALER_CLIENT_LOCK = Lock()
_QUALER_CLIENT_OVERRIDE: Optional[AuthenticatedClient] = None  # for tests/overrides


def make_qualer_client() -> AuthenticatedClient:
    """
    Lazily create and return a shared Qualer API client (singleton per process).

    This function is safe to call repeatedly and from concurrent threads. The
    first caller will create the underlying AuthenticatedClient using the
    `QUALER_API_KEY` env var; subsequent calls will return the same instance.

    Environment variables:
    - QUALER_API_KEY: API key for authentication
    - LIVEAPI (from app.config): selects production vs staging base URL

    Returns:
        AuthenticatedClient: Client for Qualer API (shared instance)

    Note: Prefer recording HTTP interactions using `pytest-vcr` for stable unit
    tests and replaying them via `@pytest.mark.vcr()`. Use `unittest.mock`
    sparingly for non-HTTP internal units.
    """
    # Only _QUALER_CLIENT is assigned in this function; no need to declare
    # _QUALER_CLIENT_OVERRIDE as global when just reading it.
    global _QUALER_CLIENT

    # Fast path without locking
    if _QUALER_CLIENT_OVERRIDE is not None:
        return _QUALER_CLIENT_OVERRIDE
    if _QUALER_CLIENT is not None:
        return _QUALER_CLIENT

    # Slow path: acquire lock and initialize once
    with _QUALER_CLIENT_LOCK:
        if _QUALER_CLIENT_OVERRIDE is not None:
            return _QUALER_CLIENT_OVERRIDE
        if _QUALER_CLIENT is None:
            # Get API token

            api_token = getenv("QUALER_API_KEY")
            if not api_token:
                raise EnvironmentError("QUALER_API_KEY environment variable is not set")

            # Validate token format
            try:
                UUID(api_token)
            except ValueError:
                raise ValueError("Invalid API token format")

            # Select base URL based on LIVEAPI flag (strip /api suffix used by SDK internally)
            endpoint = QUALER_ENDPOINT if LIVEAPI else QUALER_STAGING_ENDPOINT
            base_url = endpoint.removesuffix("/api")

            _QUALER_CLIENT = AuthenticatedClient(
                token=api_token,
                base_url=base_url,
            )
    return _QUALER_CLIENT


def set_qualer_client_override(client: Optional[AuthenticatedClient]) -> None:
    """Override the shared Qualer client (primarily for tests).

    Pass None to clear the override. When set, make_qualer_client() returns the
    override instead of the cached instance.
    """
    global _QUALER_CLIENT_OVERRIDE
    _QUALER_CLIENT_OVERRIDE = client


def reset_qualer_client() -> None:
    """Clear the cached Qualer client (for test isolation or env changes)."""
    global _QUALER_CLIENT
    _QUALER_CLIENT = None
