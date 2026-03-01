"""Tests for app.auth module."""

import os
from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Ensure auth-related env vars don't leak between tests."""
    monkeypatch.delenv("QUALER_AUTH_MODE", raising=False)
    monkeypatch.delenv("QUALER_USERNAME", raising=False)
    monkeypatch.delenv("QUALER_PASSWORD", raising=False)
    monkeypatch.delenv("QUALER_API_KEY", raising=False)


class TestQualerLogin:
    """Tests for the qualer_login function."""

    @patch("app.auth.sdk_login")
    def test_login_success(self, mock_sdk_login):
        from app.auth import qualer_login

        token_uuid = UUID("12345678-1234-5678-1234-567812345678")
        mock_response = MagicMock()
        mock_response.token = token_uuid
        mock_sdk_login.sync.return_value = mock_response

        result = qualer_login("user@example.com", "password123", "https://example.com")

        assert result == str(token_uuid)
        mock_sdk_login.sync.assert_called_once()
        call_kwargs = mock_sdk_login.sync.call_args
        assert call_kwargs.kwargs["body"].user_name == "user@example.com"
        assert call_kwargs.kwargs["body"].password == "password123"

    @patch("app.auth.sdk_login")
    def test_login_returns_none(self, mock_sdk_login):
        from app.auth import AuthenticationError, qualer_login

        mock_sdk_login.sync.return_value = None

        with pytest.raises(AuthenticationError, match="Login failed"):
            qualer_login("user@example.com", "bad_password", "https://example.com")

    @patch("app.auth.sdk_login")
    def test_login_token_is_none(self, mock_sdk_login):
        from app.auth import AuthenticationError, qualer_login

        mock_response = MagicMock()
        mock_response.token = None
        mock_sdk_login.sync.return_value = mock_response

        with pytest.raises(AuthenticationError, match="Login failed"):
            qualer_login("user@example.com", "bad_password", "https://example.com")


class TestEnsureAuthenticated:
    """Tests for the ensure_authenticated function."""

    @patch("app.auth.get_config")
    def test_api_key_mode_sets_env_var(self, mock_get_config):
        from app.auth import ensure_authenticated

        mock_cfg = MagicMock()
        mock_cfg.qualer_auth_mode = "api_key"
        mock_cfg.qualer_api_key = "test-api-key"
        mock_get_config.return_value = mock_cfg

        ensure_authenticated()

        assert os.environ.get("QUALER_API_KEY") == "test-api-key"

    @patch("app.auth.get_config")
    def test_api_key_mode_missing_key_raises(self, mock_get_config):
        from app.auth import AuthenticationError, ensure_authenticated

        mock_cfg = MagicMock()
        mock_cfg.qualer_auth_mode = "api_key"
        mock_cfg.qualer_api_key = ""
        mock_get_config.return_value = mock_cfg

        with pytest.raises(AuthenticationError, match="QUALER_API_KEY"):
            ensure_authenticated()

    @patch("app.auth.update_env_token")
    @patch("app.auth.qualer_login")
    @patch("app.auth.get_config")
    def test_credentials_mode_success(
        self, mock_get_config, mock_login, mock_update_token
    ):
        from app.auth import ensure_authenticated

        mock_cfg = MagicMock()
        mock_cfg.qualer_auth_mode = "credentials"
        mock_cfg.qualer_username = "user@example.com"
        mock_cfg.qualer_password = "password123"
        mock_get_config.return_value = mock_cfg

        mock_login.return_value = "new-token-uuid"

        ensure_authenticated()

        mock_login.assert_called_once()
        assert os.environ.get("QUALER_API_KEY") == "new-token-uuid"
        mock_update_token.assert_called_once_with("new-token-uuid")

    @patch("app.auth.qualer_login")
    @patch("app.auth.get_config")
    def test_credentials_mode_fallback_to_persisted_token(
        self, mock_get_config, mock_login
    ):
        from app.auth import AuthenticationError, ensure_authenticated

        mock_cfg = MagicMock()
        mock_cfg.qualer_auth_mode = "credentials"
        mock_cfg.qualer_username = "user@example.com"
        mock_cfg.qualer_password = "password123"
        mock_cfg.qualer_api_key = "persisted-token"
        mock_get_config.return_value = mock_cfg

        mock_login.side_effect = AuthenticationError("Login failed")

        # Should NOT raise because there's a fallback token
        ensure_authenticated()
        assert os.environ.get("QUALER_API_KEY") == "persisted-token"

    @patch("app.auth.qualer_login")
    @patch("app.auth.get_config")
    def test_credentials_mode_no_fallback_raises(self, mock_get_config, mock_login):
        from app.auth import AuthenticationError, ensure_authenticated

        mock_cfg = MagicMock()
        mock_cfg.qualer_auth_mode = "credentials"
        mock_cfg.qualer_username = "user@example.com"
        mock_cfg.qualer_password = "password123"
        mock_cfg.qualer_api_key = ""  # No fallback
        mock_get_config.return_value = mock_cfg

        mock_login.side_effect = AuthenticationError("Login failed")

        with pytest.raises(AuthenticationError):
            ensure_authenticated()

    @patch("app.auth.get_config")
    def test_credentials_mode_missing_username(self, mock_get_config):
        from app.auth import AuthenticationError, ensure_authenticated

        mock_cfg = MagicMock()
        mock_cfg.qualer_auth_mode = "credentials"
        mock_cfg.qualer_username = ""
        mock_cfg.qualer_password = "password123"
        mock_get_config.return_value = mock_cfg

        with pytest.raises(AuthenticationError, match="QUALER_USERNAME"):
            ensure_authenticated()

    @patch("app.auth.get_config")
    def test_credentials_mode_missing_password(self, mock_get_config):
        from app.auth import AuthenticationError, ensure_authenticated

        mock_cfg = MagicMock()
        mock_cfg.qualer_auth_mode = "credentials"
        mock_cfg.qualer_username = "user@example.com"
        mock_cfg.qualer_password = ""
        mock_get_config.return_value = mock_cfg

        with pytest.raises(AuthenticationError, match="QUALER_PASSWORD"):
            ensure_authenticated()
