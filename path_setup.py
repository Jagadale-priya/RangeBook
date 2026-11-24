"""Repo bootstrap: sys.path + REPO_ROOT for data paths.

Import first from any entrypoint:

    import path_setup  # noqa: F401
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT

# Allow `import fno_model` after modules move under app/*/
for _sub in ("app/api", "app/fno", "app/market", "app/desk", "app/core", "app/legacy"):
    _p = ROOT / _sub
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Load .env early (replaces groww_data side-effect loader for prod).
# Desk channel flags ALWAYS win from .env — stale shell/process env was keeping
# ENABLE_PRE_DUAL_SINGLE=1 / USE_DUAL_TRACK=0 after .env was flipped to dual-only,
# which caused BN/SENSEX soft NEW→cancel and blocked proven dual listing.
_DESK_ENV_OVERRIDE = {
    "USE_DUAL_TRACK",
    "ENABLE_PRE_DUAL_SINGLE",
    "PRE_DUAL_SOFT_GATES",
    "ENABLE_STACKED_CALLS",
    "ENABLE_5M_CROWN",
    "ENABLE_EXTRA_TREES_SINGLE",
    "DUAL_CHAMPION_SL_PTS",
    "DUAL_CHAMPION_T1_PTS",
    "ENABLE_NSE_MID_GATE",
    "OVERLAY_ACC_MIN",
    "OVERLAY_NOTIFY",
    "ENABLE_15M_CLASSIC",
    "ENABLE_DAILY_FILL",
    "ENABLE_MOVE_CAPTURE",
}
_env = ROOT / ".env"
if _env.is_file():
    try:
        for _line in _env.read_text(encoding="utf-8", errors="ignore").splitlines():
            _line = _line.strip()
            if not _line or _line.startswith("#") or "=" not in _line:
                continue
            _k, _v = _line.split("=", 1)
            _k, _v = _k.strip(), _v.strip().strip('"').strip("'")
            if not _k:
                continue
            if _k in _DESK_ENV_OVERRIDE or _k not in os.environ:
                os.environ[_k] = _v
    except Exception:
        pass
