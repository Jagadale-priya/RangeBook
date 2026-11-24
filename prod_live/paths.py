"""Resolve frozen NIFTY model paths under prod_live (env override supported)."""
from __future__ import annotations

import os
from pathlib import Path

PROD_LIVE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PROD_LIVE_ROOT.parent


def _env_path(key: str) -> Path | None:
    raw = str(os.environ.get(key) or "").strip()
    if not raw:
        return None
    p = Path(raw)
    if not p.is_absolute():
        p = REPO_ROOT / p
    return p


def nifty_prod2_pkl() -> Path:
    override = _env_path("PROD_LIVE_NIFTY_PROD2")
    if override is not None:
        return override
    return PROD_LIVE_ROOT / "models" / "nifty" / "prod2_15m" / "fno_NIFTY.pkl"


def nifty_crown_dir() -> Path:
    override = _env_path("PROD_LIVE_NIFTY_CROWN_DIR")
    if override is not None:
        return override
    return PROD_LIVE_ROOT / "models" / "nifty" / "crown"


def nifty_crown_pkl(symbol: str = "NIFTY") -> Path:
    override = _env_path("PROD_LIVE_NIFTY_CROWN")
    if override is not None and str(symbol).upper() == "NIFTY":
        return override
    return nifty_crown_dir() / f"fno_{str(symbol).upper()}_crown_5m.pkl"


def nifty_dual_dir() -> Path:
    override = _env_path("PROD_LIVE_NIFTY_DUAL")
    if override is not None:
        return override
    return PROD_LIVE_ROOT / "models" / "nifty" / "dual"
