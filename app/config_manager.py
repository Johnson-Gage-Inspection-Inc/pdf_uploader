"""
config_manager.py -- YAML-based config with backward-compatible module-level attributes.

Loads config.yaml from:
  1. Next to the .exe (PyInstaller frozen)
  2. Project root (development)
  3. Falls back to hardcoded defaults (equivalent to original config.py)

Secret storage strategy
-----------------------
* Development (sys.frozen is False):
    Secrets are stored in plain text in a .env file at the project root.
    Standard python-dotenv behaviour; no encryption.

* Bundled executable (sys.frozen is True):
    Secrets are stored encrypted in ``secrets.enc`` next to the .exe.
    The file is a JSON object whose values are individual Fernet tokens.
    The Fernet key itself is kept in the OS keychain (Windows Credential
    Manager / macOS Keychain / Linux Secret Service) via the ``keyring``
    library under service ``"pdf_uploader"``.  On first run the key is
    generated automatically and stored in the keychain.
"""

import json
import logging
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import keyring
import yaml
from cryptography.fernet import Fernet
from dotenv import load_dotenv

_KEYRING_SERVICE = "pdf_uploader"
_KEYRING_KEY_NAME = "fernet_key"


@dataclass
class WatchedFolder:
    input_dir: str
    output_dir: str
    reject_dir: str
    qualer_document_type: str = "General"
    validate_po: bool = False


@dataclass
class AppConfig:
    max_runtime: Optional[int] = None
    debug: bool = False
    delete_mode: bool = False
    tesseract_cmd_path: str = r"C:/Program Files/Tesseract-OCR/tesseract.exe"
    sharepoint_path: str = ""
    log_file: str = ""
    po_dict_file: str = ""
    max_workers: int = 3
    qualer_endpoint: str = "https://jgiquality.qualer.com/api"
    watched_folders: list[WatchedFolder] = field(default_factory=list)

    # Secrets (loaded from .env in dev, from secrets.enc in frozen builds)
    qualer_api_key: str = ""
    gemini_api_key: str = ""
    qualer_auth_mode: str = "api_key"  # "api_key" or "credentials"
    qualer_username: str = ""
    qualer_password: str = ""


_config: Optional[AppConfig] = None


def _resolve_path(template: str, sharepoint_path: str) -> str:
    """Replace {sharepoint_path} and ~ in path templates."""
    result = template.replace("{sharepoint_path}", sharepoint_path)
    result = os.path.expanduser(result)
    return os.path.normpath(result)


def _find_config_file() -> Optional[Path]:
    """Locate config.yaml adjacent to executable or in project root."""
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
        candidate = exe_dir / "config.yaml"
        if candidate.exists():
            return candidate
    # Development: project root
    project_root = Path(__file__).parent.parent
    candidate = project_root / "config.yaml"
    if candidate.exists():
        return candidate
    return None


def _build_defaults() -> AppConfig:
    """Build the default config matching original config.py values."""
    user_folder = os.path.expanduser("~")
    sp = os.path.join(
        user_folder,
        "Johnson Gage and Inspection, Inc",
        "Johnson Gage and Inspection, Inc. - Documents",
        "Sysop's OneDrive",
        "Shared with Everyone",
        "access",
    )
    sp = sp.replace("\\", "/") + "/"
    return AppConfig(
        sharepoint_path=sp,
        log_file=os.path.normpath(sp + "Logs/pdfUploader.log"),
        po_dict_file=os.path.normpath(sp + "Logs/DoNotMoveThisFile.json.gz"),
        watched_folders=[
            WatchedFolder(
                input_dir=os.path.normpath(
                    sp + "!!! Front Office Scanned Docs - HOLDING"
                ),
                output_dir=os.path.normpath(
                    sp + "!!! Front Office Scanned Docs - HOLDING/Archives"
                ),
                reject_dir=os.path.normpath(
                    sp + "!!! Front Office Scanned Docs - HOLDING/No_Order_Found"
                ),
                qualer_document_type="General",
                validate_po=True,
            ),
            WatchedFolder(
                input_dir=os.path.normpath(sp + "!!! Scanned External Certs"),
                output_dir=os.path.normpath(sp + "!!! Scanned External Certs/Archives"),
                reject_dir=os.path.normpath(
                    sp + "!!! Scanned External Certs/No_Order_Found"
                ),
                qualer_document_type="ordercertificate",
                validate_po=False,
            ),
        ],
    )


def load_config() -> AppConfig:
    """Load config from YAML file, falling back to defaults."""
    global _config

    yaml_path = _find_config_file()
    if yaml_path:
        with open(yaml_path, "r") as f:
            raw = yaml.safe_load(f) or {}

        sp_raw = raw.get("sharepoint_path", "")
        if sp_raw:
            sp = os.path.expanduser(sp_raw)
            # Ensure trailing slash for path joining
            if not sp.endswith("/") and not sp.endswith("\\"):
                sp += "/"
        else:
            sp = _build_defaults().sharepoint_path

        folders = []
        for fd in raw.get("watched_folders", []):
            folders.append(
                WatchedFolder(
                    input_dir=_resolve_path(fd["input_dir"], sp),
                    output_dir=_resolve_path(fd["output_dir"], sp),
                    reject_dir=_resolve_path(fd["reject_dir"], sp),
                    qualer_document_type=fd.get("qualer_document_type", "General"),
                    validate_po=fd.get("validate_po", False),
                )
            )

        log_file_raw = raw.get("log_file", "{sharepoint_path}Logs/pdfUploader.log")
        po_dict_raw = raw.get(
            "po_dict_file", "{sharepoint_path}Logs/DoNotMoveThisFile.json.gz"
        )

        _mw_raw = raw.get("max_workers")
        try:
            _max_workers = max(1, int(_mw_raw)) if _mw_raw is not None else 3
        except (ValueError, TypeError):
            _max_workers = 3

        _config = AppConfig(
            max_runtime=raw.get("max_runtime"),
            max_workers=_max_workers,
            debug=raw.get("debug", False),
            delete_mode=raw.get("delete_mode", False),
            tesseract_cmd_path=raw.get(
                "tesseract_cmd_path", r"C:/Program Files/Tesseract-OCR/tesseract.exe"
            ),
            sharepoint_path=sp,
            log_file=_resolve_path(log_file_raw, sp),
            po_dict_file=_resolve_path(po_dict_raw, sp),
            qualer_endpoint=raw.get(
                "qualer_endpoint", "https://jgiquality.qualer.com/api"
            ),
            watched_folders=folders,
        )
    else:
        _config = _build_defaults()

    # Load secrets (plain text from .env in dev; decrypted from secrets.enc when frozen)
    secrets = _load_secrets()
    _config.qualer_api_key = secrets.get("QUALER_API_KEY", "")
    _config.gemini_api_key = secrets.get("GEMINI_API_KEY", "")
    _config.qualer_auth_mode = secrets.get("QUALER_AUTH_MODE", "api_key")
    _config.qualer_username = secrets.get("QUALER_USERNAME", "")
    _config.qualer_password = secrets.get("QUALER_PASSWORD", "")

    # Ensure non-password secrets are also available via environment variables so that
    # code which reads from os.environ (e.g., Qualer/Gemini clients) behaves
    # consistently in both dev (.env) and frozen modes. Do not export passwords.
    env_mappings = {
        "QUALER_API_KEY": _config.qualer_api_key,
        "GEMINI_API_KEY": _config.gemini_api_key,
        "QUALER_AUTH_MODE": _config.qualer_auth_mode,
        "QUALER_USERNAME": _config.qualer_username,
    }
    for key, value in env_mappings.items():
        if value:
            # Do not override an explicitly set environment variable.
            os.environ.setdefault(key, value)

    return _config


def get_config() -> AppConfig:
    """Get the current config, loading if necessary."""
    global _config
    if _config is None:
        return load_config()
    return _config


def reload_config() -> AppConfig:
    """Force-reload config from disk."""
    global _config
    _config = None
    return load_config()


def save_config(config: AppConfig, path: Optional[Path] = None) -> None:
    """Save config to YAML (used by Config dialog)."""
    if path is None:
        path = _find_config_file()
        if path is None:
            path = Path(__file__).parent.parent / "config.yaml"

    data = {
        "max_runtime": config.max_runtime,
        "max_workers": config.max_workers,
        "debug": config.debug,
        "delete_mode": config.delete_mode,
        "tesseract_cmd_path": config.tesseract_cmd_path,
        "sharepoint_path": config.sharepoint_path,
        "log_file": config.log_file,
        "po_dict_file": config.po_dict_file,
        "qualer_endpoint": config.qualer_endpoint,
        "watched_folders": [
            {
                "input_dir": wf.input_dir,
                "output_dir": wf.output_dir,
                "reject_dir": wf.reject_dir,
                "qualer_document_type": wf.qualer_document_type,
                "validate_po": wf.validate_po,
            }
            for wf in config.watched_folders
        ],
    }

    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    global _config
    _config = config


def _get_fernet() -> Fernet:
    """Return a Fernet instance whose key lives in the OS keychain.

    On first call for a given machine the key is generated automatically and
    stored via ``keyring``.  Subsequent calls retrieve the same key.
    """
    raw_key = keyring.get_password(_KEYRING_SERVICE, _KEYRING_KEY_NAME)
    if not raw_key:
        raw_key = Fernet.generate_key().decode()
        keyring.set_password(_KEYRING_SERVICE, _KEYRING_KEY_NAME, raw_key)
    return Fernet(raw_key.encode())


def _secrets_file() -> Path:
    """Absolute path to ``secrets.enc`` next to the bundled executable."""
    return Path(sys.executable).parent / "secrets.enc"


def _load_frozen_secrets(_path: Optional[Path] = None) -> dict[str, str]:
    """Load and decrypt secrets from ``secrets.enc``.  Frozen mode only.

    The optional *_path* parameter is for testing; callers should leave it
    unset so the default location (next to the .exe) is used.
    """
    path = _path if _path is not None else _secrets_file()
    if not path.exists():
        return {}
    try:
        fernet = _get_fernet()
        encrypted: dict[str, str] = json.loads(path.read_text())
        return {k: fernet.decrypt(v.encode()).decode() for k, v in encrypted.items()}
    except Exception as exc:
        logging.warning(
            "Failed to load secrets from %s (%s: %s).",
            path,
            type(exc).__name__,
            exc,
        )
        return {}


def _load_secrets() -> dict[str, str]:
    """Load secrets from the appropriate source for the current run mode.

    * Development: plain text ``.env`` via python-dotenv.
    * Frozen/bundled: encrypted ``secrets.enc`` via Fernet + OS keychain.
    """
    if not getattr(sys, "frozen", False):
        load_dotenv()
        return {
            "QUALER_API_KEY": os.getenv("QUALER_API_KEY", ""),
            "GEMINI_API_KEY": os.getenv("GEMINI_API_KEY", ""),
            "QUALER_AUTH_MODE": os.getenv("QUALER_AUTH_MODE", "api_key"),
            "QUALER_USERNAME": os.getenv("QUALER_USERNAME", ""),
            "QUALER_PASSWORD": os.getenv("QUALER_PASSWORD", ""),
        }
    return _load_frozen_secrets()


def _save_secrets(
    qualer_api_key: Optional[str] = None,
    gemini_api_key: Optional[str] = None,
    qualer_auth_mode: Optional[str] = None,
    qualer_username: Optional[str] = None,
    qualer_password: Optional[str] = None,
    _path: Optional[Path] = None,
) -> None:
    """Encrypt and persist secrets into ``secrets.enc``.

    Each parameter uses a ``None`` sentinel to mean "leave unchanged".
    Pass an empty string to explicitly clear a previously stored value.
    The optional *_path* parameter is for testing.
    """
    path = _path if _path is not None else _secrets_file()
    fernet = _get_fernet()

    # Preserve keys that aren't being updated.
    existing: dict[str, str] = {}
    if path.exists():
        try:
            raw: dict[str, str] = json.loads(path.read_text())
            existing = {k: fernet.decrypt(v.encode()).decode() for k, v in raw.items()}
        except Exception as exc:
            logging.warning(
                "Could not read existing secrets from %s (%s: %s); overwriting.",
                path,
                type(exc).__name__,
                exc,
            )

    _updates: dict[str, Optional[str]] = {
        "QUALER_API_KEY": qualer_api_key,
        "GEMINI_API_KEY": gemini_api_key,
        "QUALER_AUTH_MODE": qualer_auth_mode,
        "QUALER_USERNAME": qualer_username,
        "QUALER_PASSWORD": qualer_password,
    }
    for key, value in _updates.items():
        if value is None:
            continue  # not provided — leave existing value
        if value:
            existing[key] = value  # set / update
        else:
            existing.pop(key, None)  # empty string — clear

    encrypted = {k: fernet.encrypt(v.encode()).decode() for k, v in existing.items()}
    path.write_text(json.dumps(encrypted))


def _save_dev_env(
    qualer_api_key: Optional[str] = None,
    gemini_api_key: Optional[str] = None,
    qualer_auth_mode: Optional[str] = None,
    qualer_username: Optional[str] = None,
    qualer_password: Optional[str] = None,
) -> None:
    """Persist secrets into the project-root ``.env`` file (development only).

    Each parameter uses a ``None`` sentinel to mean "leave unchanged".
    Pass an empty string to explicitly clear a previously stored value.
    """
    from dotenv import set_key, unset_key

    env_path = Path(__file__).parent.parent / ".env"

    _updates = {
        "QUALER_API_KEY": qualer_api_key,
        "GEMINI_API_KEY": gemini_api_key,
        "QUALER_AUTH_MODE": qualer_auth_mode,
        "QUALER_USERNAME": qualer_username,
        "QUALER_PASSWORD": qualer_password,
    }
    for key, value in _updates.items():
        if value is None:
            continue  # not provided — leave unchanged
        if value:
            set_key(str(env_path), key, value)
        else:
            # empty string — clear from .env (unset_key ignores missing keys)
            if env_path.exists():
                unset_key(str(env_path), key)


def save_env(
    qualer_api_key: Optional[str] = None,
    gemini_api_key: Optional[str] = None,
    qualer_auth_mode: Optional[str] = None,
    qualer_username: Optional[str] = None,
    qualer_password: Optional[str] = None,
) -> None:
    """Persist secrets to the appropriate store for the current run mode.

    * Development: writes to ``.env`` at the project root.
    * Frozen/bundled: writes to encrypted ``secrets.enc`` next to the .exe.

    Pass ``None`` (the default) to leave a value unchanged, or an empty
    string to explicitly clear it from the store.
    """
    if not getattr(sys, "frozen", False):
        _save_dev_env(
            qualer_api_key=qualer_api_key,
            gemini_api_key=gemini_api_key,
            qualer_auth_mode=qualer_auth_mode,
            qualer_username=qualer_username,
            qualer_password=qualer_password,
        )
    else:
        _save_secrets(
            qualer_api_key=qualer_api_key,
            gemini_api_key=gemini_api_key,
            qualer_auth_mode=qualer_auth_mode,
            qualer_username=qualer_username,
            qualer_password=qualer_password,
        )


def update_env_token(new_token: str) -> None:
    """Update QUALER_API_KEY in the secrets store without disturbing other values."""
    existing = _load_secrets()
    current_auth_mode = existing.get("QUALER_AUTH_MODE") or "api_key"
    save_env(qualer_api_key=new_token, qualer_auth_mode=current_auth_mode)
