"""
config_manager.py -- YAML-based config with backward-compatible module-level attributes.

Loads config.yaml from:
  1. Next to the .exe (PyInstaller frozen)
  2. Project root (development)
  3. Falls back to hardcoded defaults (equivalent to original config.py)
"""

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


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
    live_api: bool = True
    debug: bool = False
    delete_mode: bool = False
    tesseract_cmd_path: str = r"C:/Program Files/Tesseract-OCR/tesseract.exe"
    sharepoint_path: str = ""
    log_file: str = ""
    po_dict_file: str = ""
    qualer_endpoint: str = "https://jgiquality.qualer.com/api"
    qualer_staging_endpoint: str = "https://jgiquality.staging.qualer.com/api"
    watched_folders: list[WatchedFolder] = field(default_factory=list)

    # Secrets (loaded from .env, never saved to YAML)
    qualer_api_key: str = ""
    gemini_api_key: str = ""


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

        _config = AppConfig(
            max_runtime=raw.get("max_runtime"),
            live_api=raw.get("live_api", True),
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
            qualer_staging_endpoint=raw.get(
                "qualer_staging_endpoint",
                "https://jgiquality.staging.qualer.com/api",
            ),
            watched_folders=folders,
        )
    else:
        _config = _build_defaults()

    # Load secrets from .env (never stored in YAML)
    from dotenv import load_dotenv

    load_dotenv()
    _config.qualer_api_key = os.getenv("QUALER_API_KEY", "")
    _config.gemini_api_key = os.getenv("GEMINI_API_KEY", "")

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
        "live_api": config.live_api,
        "debug": config.debug,
        "delete_mode": config.delete_mode,
        "tesseract_cmd_path": config.tesseract_cmd_path,
        "sharepoint_path": config.sharepoint_path,
        "log_file": config.log_file,
        "po_dict_file": config.po_dict_file,
        "qualer_endpoint": config.qualer_endpoint,
        "qualer_staging_endpoint": config.qualer_staging_endpoint,
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


def save_env(qualer_api_key: str, gemini_api_key: str) -> None:
    """Write API keys back to .env file."""
    if getattr(sys, "frozen", False):
        env_path = Path(sys.executable).parent / ".env"
    else:
        env_path = Path(__file__).parent.parent / ".env"

    lines = []
    if qualer_api_key:
        lines.append(f"QUALER_API_KEY={qualer_api_key}")
    if gemini_api_key:
        lines.append(f"GEMINI_API_KEY={gemini_api_key}")

    with open(env_path, "w") as f:
        f.write("\n".join(lines) + "\n")
