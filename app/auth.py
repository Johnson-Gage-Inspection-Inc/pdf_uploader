"""Authentication module for Qualer username/password login and token management."""

import os

from qualer_sdk.api.account import login as sdk_login
from qualer_sdk.client import Client
from qualer_sdk.models import (
    QualerWebMvcAreasApiModelsAccountToLoginModel as LoginModel,
)

import app.color_print as cp
from app.config import QUALER_ENDPOINT
from app.config_manager import get_config, update_env_token


class AuthenticationError(Exception):
    """Raised when Qualer authentication fails."""


def qualer_login(username: str, password: str, base_url: str) -> str:
    """Login to Qualer with username/password, return token string.

    Uses an unauthenticated Client for the /api/login endpoint.

    Args:
        username: Qualer username.
        password: Qualer password.
        base_url: Qualer base URL (without /api suffix).

    Returns:
        Token string (UUID).

    Raises:
        AuthenticationError: On 401 or missing token in response.
    """
    unauthenticated = Client(base_url=base_url)
    body = LoginModel(user_name=username, password=password)
    response = sdk_login.sync(client=unauthenticated, body=body)
    if response is None or response.token is None:
        raise AuthenticationError(
            "Login failed. Verify credentials and that the user has "
            "the API security role."
        )
    return str(response.token)


def ensure_authenticated() -> None:
    """Ensure a valid token is available at startup.

    For api_key mode: no-op (token comes from QUALER_API_KEY env var).
    For credentials mode: login to get a fresh token, persist it,
    fall back to persisted token if login fails.

    Raises:
        AuthenticationError: If credentials mode and login fails with no fallback.
    """
    cfg = get_config()
    if cfg.qualer_auth_mode != "credentials":
        return

    if not cfg.qualer_username or not cfg.qualer_password:
        raise AuthenticationError(
            "Credentials mode selected but QUALER_USERNAME or "
            "QUALER_PASSWORD not set in .env"
        )

    base_url = QUALER_ENDPOINT.removesuffix("/api")
    try:
        new_token = qualer_login(cfg.qualer_username, cfg.qualer_password, base_url)
        os.environ["QUALER_API_KEY"] = new_token
        update_env_token(new_token)
        cp.green("Qualer login successful.")
    except AuthenticationError:
        if cfg.qualer_api_key:
            cp.yellow(
                "Login failed but found persisted token. " "Using existing token."
            )
            os.environ["QUALER_API_KEY"] = cfg.qualer_api_key
        else:
            raise
