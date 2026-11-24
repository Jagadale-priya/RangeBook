"""Single knowledge.db location for analysis, session calls, and training rows."""

from __future__ import annotations

import os
import shutil

import path_setup
ROOT = str(path_setup.ROOT)
DATA_DIR = os.path.join(ROOT, "stock_signal_data")
LEGACY_PATH = os.path.join(ROOT, "knowledge.db")


def default_db_path() -> str:
    return os.path.join(DATA_DIR, "knowledge.db")


def ensure_db_dir() -> str:
    path = default_db_path()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    if not os.path.isfile(path) and os.path.isfile(LEGACY_PATH):
        try:
            shutil.copy2(LEGACY_PATH, path)
        except Exception:
            pass
    return path
