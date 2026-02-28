"""
config.py -- Backward-compatible facade over config_manager.

All existing imports like ``from app.config import LIVEAPI`` continue to work.
Values are loaded from config.yaml (or defaults) via config_manager.
"""

import os

from app.config_manager import get_config


def __getattr__(name):
    """Module-level __getattr__ for lazy access to config values (PEP 562)."""
    cfg = get_config()
    _MAP = {
        "MAX_RUNTIME": cfg.max_runtime,
        "LIVEAPI": cfg.live_api,
        "DEBUG": cfg.debug,
        "DELETE_MODE": cfg.delete_mode,
        "tesseract_cmd_path": cfg.tesseract_cmd_path,
        "user_folder": os.path.expanduser("~"),
        "SHAREPOINT_PATH": cfg.sharepoint_path,
        "LOG_FILE": cfg.log_file,
        "PO_DICT_FILE": cfg.po_dict_file,
        "QUALER_ENDPOINT": cfg.qualer_endpoint,
        "QUALER_STAGING_ENDPOINT": cfg.qualer_staging_endpoint,
        "CONFIG": [
            {
                "INPUT_DIR": wf.input_dir,
                "OUTPUT_DIR": wf.output_dir,
                "REJECT_DIR": wf.reject_dir,
                "QUALER_DOCUMENT_TYPE": wf.qualer_document_type,
                "VALIDATE_PO": wf.validate_po,
            }
            for wf in cfg.watched_folders
        ],
    }
    if name in _MAP:
        return _MAP[name]
    raise AttributeError(f"module 'app.config' has no attribute {name!r}")
