import os
import unittest


class TestConfig(unittest.TestCase):
    def test_config_has_required_attributes(self):
        import app.config as config

        self.assertIsInstance(config.DEBUG, bool)
        self.assertIsInstance(config.DELETE_MODE, bool)
        self.assertIsInstance(config.tesseract_cmd_path, str)

    def test_max_runtime_default(self):
        import app.config as config

        self.assertIsNone(config.MAX_RUNTIME)

    def test_sharepoint_path_uses_home(self):
        import app.config as config

        self.assertIn(config.user_folder, config.SHAREPOINT_PATH)

    def test_log_file_path_suffix(self):
        import app.config as config

        # LOG_FILE may be patched by conftest; just check it's a string
        self.assertIsInstance(config.LOG_FILE, str)

    def test_po_dict_file_path(self):
        import app.config as config

        self.assertIn("DoNotMoveThisFile.json.gz", config.PO_DICT_FILE)

    def test_qualer_endpoints(self):
        import app.config as config

        self.assertIn("qualer.com", config.QUALER_ENDPOINT)

    def test_config_has_two_watched_folders(self):
        from app.config_manager import get_config, WatchedFolder

        cfg = get_config()
        self.assertEqual(len(cfg.watched_folders), 2)
        for wf in cfg.watched_folders:
            self.assertIsInstance(wf, WatchedFolder)
            self.assertIsInstance(wf.input_dir, str)
            self.assertIsInstance(wf.output_dir, str)
            self.assertIsInstance(wf.reject_dir, str)
            self.assertIsInstance(wf.qualer_document_type, str)
            self.assertIsInstance(wf.validate_po, bool)


class TestDevSecrets(unittest.TestCase):
    """Tests for secret loading in development (non-frozen) mode."""

    def setUp(self):
        self._original = {
            k: os.environ.get(k) for k in ("QUALER_API_KEY", "GEMINI_API_KEY")
        }
        for k in ("QUALER_API_KEY", "GEMINI_API_KEY"):
            os.environ.pop(k, None)

    def tearDown(self):
        for k, v in self._original.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_load_secrets_dev_reads_env(self):
        """_load_secrets reads plain-text values from the environment."""
        os.environ["QUALER_API_KEY"] = "test_qualer"
        os.environ["GEMINI_API_KEY"] = "test_gemini"

        # Reload so load_dotenv picks up the current env.
        import app.config_manager as cm

        secrets = cm._load_secrets()
        self.assertEqual(secrets.get("QUALER_API_KEY"), "test_qualer")
        self.assertEqual(secrets.get("GEMINI_API_KEY"), "test_gemini")


class TestEncryptedSecrets(unittest.TestCase):
    """Tests for encrypted secret storage (secrets.enc + keyring)."""

    def setUp(self):
        import tempfile
        from cryptography.fernet import Fernet
        from unittest.mock import patch

        self._tmpdir = tempfile.mkdtemp()
        self._test_key = Fernet.generate_key().decode()
        self._fernet = Fernet(self._test_key.encode())

        # Patch keyring so tests don't touch the real OS keychain.
        self._keyring_patcher = patch(
            "keyring.get_password", return_value=self._test_key
        )
        self._keyring_patcher.start()
        self._keyring_set_patcher = patch("keyring.set_password")
        self._keyring_set_patcher.start()

    def tearDown(self):
        import shutil

        self._keyring_patcher.stop()
        self._keyring_set_patcher.stop()
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_save_secrets_encrypts_values(self):
        """_save_secrets writes encrypted JSON, not plain text."""
        import json
        from pathlib import Path
        from app.config_manager import _save_secrets

        secrets_file = Path(self._tmpdir) / "secrets.enc"
        _save_secrets(
            qualer_api_key="qualer_val",
            gemini_api_key="gemini_val",
            _path=secrets_file,
        )

        raw = json.loads(secrets_file.read_text())
        # Values must not be plain text.
        self.assertNotEqual(raw.get("QUALER_API_KEY"), "qualer_val")
        self.assertNotEqual(raw.get("GEMINI_API_KEY"), "gemini_val")
        # Values must be Fernet-decryptable.
        self.assertEqual(
            self._fernet.decrypt(raw["QUALER_API_KEY"].encode()).decode(), "qualer_val"
        )
        self.assertEqual(
            self._fernet.decrypt(raw["GEMINI_API_KEY"].encode()).decode(), "gemini_val"
        )

    def test_load_frozen_secrets_roundtrip(self):
        """Values saved by _save_secrets are recovered by _load_frozen_secrets."""
        from pathlib import Path
        from app.config_manager import _save_secrets, _load_frozen_secrets

        secrets_file = Path(self._tmpdir) / "secrets.enc"
        _save_secrets(
            qualer_api_key="qualer_val",
            gemini_api_key="gemini_val",
            _path=secrets_file,
        )

        loaded = _load_frozen_secrets(_path=secrets_file)
        self.assertEqual(loaded.get("QUALER_API_KEY"), "qualer_val")
        self.assertEqual(loaded.get("GEMINI_API_KEY"), "gemini_val")

    def test_save_secrets_preserves_unrelated_keys(self):
        """_save_secrets keeps keys it isn't updating."""
        import json
        from pathlib import Path
        from app.config_manager import _save_secrets

        secrets_file = Path(self._tmpdir) / "secrets.enc"
        # Seed the file with an existing key.
        existing = {"OTHER_KEY": self._fernet.encrypt(b"other_val").decode()}
        secrets_file.write_text(json.dumps(existing))

        _save_secrets(qualer_api_key="new_qualer", _path=secrets_file)

        raw = json.loads(secrets_file.read_text())
        self.assertIn("OTHER_KEY", raw)
        self.assertEqual(
            self._fernet.decrypt(raw["OTHER_KEY"].encode()).decode(), "other_val"
        )
        self.assertEqual(
            self._fernet.decrypt(raw["QUALER_API_KEY"].encode()).decode(), "new_qualer"
        )

    def test_empty_string_clears_credential(self):
        """Passing '' for a secret removes it from the store."""
        from pathlib import Path
        from app.config_manager import _save_secrets, _load_frozen_secrets

        secrets_file = Path(self._tmpdir) / "secrets.enc"
        # Seed with username and password.
        _save_secrets(
            qualer_username="alice",
            qualer_password="s3cret",
            _path=secrets_file,
        )
        loaded = _load_frozen_secrets(_path=secrets_file)
        self.assertEqual(loaded["QUALER_USERNAME"], "alice")
        self.assertEqual(loaded["QUALER_PASSWORD"], "s3cret")

        # Now clear them by passing empty strings.
        _save_secrets(
            qualer_username="",
            qualer_password="",
            _path=secrets_file,
        )
        loaded = _load_frozen_secrets(_path=secrets_file)
        self.assertNotIn("QUALER_USERNAME", loaded)
        self.assertNotIn("QUALER_PASSWORD", loaded)

    def test_none_leaves_credential_unchanged(self):
        """Passing None (default) for a secret preserves its stored value."""
        from pathlib import Path
        from app.config_manager import _save_secrets, _load_frozen_secrets

        secrets_file = Path(self._tmpdir) / "secrets.enc"
        _save_secrets(
            qualer_api_key="key1",
            qualer_username="alice",
            _path=secrets_file,
        )

        # Update only api_key; username should be untouched.
        _save_secrets(qualer_api_key="key2", _path=secrets_file)

        loaded = _load_frozen_secrets(_path=secrets_file)
        self.assertEqual(loaded["QUALER_API_KEY"], "key2")
        self.assertEqual(loaded["QUALER_USERNAME"], "alice")

    def test_load_frozen_secrets_missing_file_returns_empty(self):
        """_load_frozen_secrets returns an empty dict when secrets.enc is absent."""
        from pathlib import Path
        from app.config_manager import _load_frozen_secrets

        missing = Path(self._tmpdir) / "secrets.enc"
        self.assertEqual(_load_frozen_secrets(_path=missing), {})

    def test_load_frozen_secrets_corrupt_file_logs_warning(self):
        """_load_frozen_secrets warns and returns empty dict on corrupt data."""
        import logging
        from pathlib import Path
        from app.config_manager import _load_frozen_secrets

        secrets_file = Path(self._tmpdir) / "secrets.enc"
        secrets_file.write_text("not valid json or fernet data")

        with self.assertLogs(level=logging.WARNING):
            result = _load_frozen_secrets(_path=secrets_file)
        self.assertEqual(result, {})


class TestConfigDialogObfuscation(unittest.TestCase):
    """UI-level checks that API key fields are never pre-populated."""

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication

        if QApplication.instance() is None:
            cls._app = QApplication([])

    def _make_dialog(self, qualer="", gemini=""):
        from unittest.mock import patch
        from app.config_manager import AppConfig
        from app.gui.config_dialog import ConfigDialog

        cfg = AppConfig(qualer_api_key=qualer, gemini_api_key=gemini)
        with patch("app.gui.config_dialog.get_config", return_value=cfg):
            dlg = ConfigDialog()
        return dlg

    def test_key_fields_are_always_blank(self):
        """QLineEdit fields must be empty regardless of whether a key is stored."""
        dlg = self._make_dialog(qualer="secret_key", gemini="another_secret")
        self.assertEqual(dlg.qualer_key.text(), "")
        self.assertEqual(dlg.gemini_key.text(), "")

    def test_placeholder_indicates_saved_key(self):
        """Placeholder text says '(saved — type to replace)' when a key exists."""
        dlg = self._make_dialog(qualer="secret_key", gemini="another_secret")
        self.assertIn("saved", dlg.qualer_key.placeholderText())
        self.assertIn("saved", dlg.gemini_key.placeholderText())

    def test_placeholder_indicates_no_key(self):
        """Placeholder text says '(not set)' when no key is stored."""
        dlg = self._make_dialog(qualer="", gemini="")
        self.assertIn("not set", dlg.qualer_key.placeholderText())
        self.assertIn("not set", dlg.gemini_key.placeholderText())

    def test_echo_mode_is_password(self):
        """Fields must stay in Password echo mode (no Show button to bypass)."""
        from PyQt6.QtWidgets import QLineEdit

        dlg = self._make_dialog(qualer="key", gemini="key")
        self.assertEqual(dlg.qualer_key.echoMode(), QLineEdit.EchoMode.Password)
        self.assertEqual(dlg.gemini_key.echoMode(), QLineEdit.EchoMode.Password)

    def test_no_show_buttons_for_api_keys(self):
        """Show buttons must only exist inside the credentials group (for password),
        not for API key fields."""
        from PyQt6.QtWidgets import QPushButton

        dlg = self._make_dialog(qualer="key", gemini="key")
        show_buttons = [w for w in dlg.findChildren(QPushButton) if w.text() == "Show"]
        for btn in show_buttons:
            self.assertTrue(
                dlg.credentials_group.isAncestorOf(btn),
                "Show button found outside credentials group",
            )


if __name__ == "__main__":
    unittest.main()
