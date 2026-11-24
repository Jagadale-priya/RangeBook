"""Cached Kite /instruments master for instrument_token lookup (no /quote per symbol)."""

from __future__ import annotations

import os
import json
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import kite_data
from kite_data import INDEX_KITE, kite_instrument_id

CACHE_TTL_HOURS = 20


def _data_dir() -> str:
    custom = os.environ.get("STOCK_SIGNAL_DATA_DIR", "").strip()
    if custom:
        return custom
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "stock_signal_data")


def cache_dir() -> str:
    path = os.path.join(_data_dir(), "cache", "kite_instruments")
    os.makedirs(path, exist_ok=True)
    return path


def _meta_path() -> str:
    return os.path.join(cache_dir(), "meta.json")


def _index_path() -> str:
    return os.path.join(cache_dir(), "token_index.json")


def _load_meta() -> Dict[str, Any]:
    p = _meta_path()
    if not os.path.isfile(p):
        return {}
    try:
        with open(p, encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError):
        return {}


def _save_meta(meta: Dict[str, Any]) -> None:
    with open(_meta_path(), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2)


def _load_index() -> Dict[str, int]:
    p = _index_path()
    if not os.path.isfile(p):
        return {}
    try:
        with open(p, encoding="utf-8") as fh:
            raw = json.load(fh)
        return {str(k): int(v) for k, v in raw.items()}
    except (json.JSONDecodeError, OSError, TypeError, ValueError):
        return {}


def _save_index(index: Dict[str, int]) -> None:
    with open(_index_path(), "w", encoding="utf-8") as fh:
        json.dump(index, fh, indent=2, sort_keys=True)


def cache_age_hours() -> Optional[float]:
    meta = _load_meta()
    ts = meta.get("refreshed_at")
    if not ts:
        return None
    try:
        refreshed = datetime.fromisoformat(ts)
        return (datetime.now() - refreshed).total_seconds() / 3600.0
    except ValueError:
        return None


def is_cache_fresh() -> bool:
    age = cache_age_hours()
    return age is not None and age < CACHE_TTL_HOURS and bool(_load_index())


def refresh_instruments(force: bool = False) -> Tuple[bool, Optional[str]]:
    try:
        import fno_instruments

        nfo_missing = fno_instruments.nfo_row_count() < 1
    except Exception:
        nfo_missing = True
    if not force and is_cache_fresh() and not nfo_missing:
        return True, None
    if not kite_data.kite_enabled():
        return False, "Kite not enabled"
    kite, err = kite_data._get_kite()
    if err or not kite:
        return False, err
    try:
        rows = kite.instruments()
        index: Dict[str, int] = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            ex = str(row.get("exchange") or "").upper()
            sym = str(row.get("tradingsymbol") or "").strip()
            tok = row.get("instrument_token")
            if not sym or tok is None:
                continue
            key = f"{ex}:{sym}"
            index[key] = int(tok)
        if len(index) < 1000:
            return False, f"Unexpected instrument count {len(index)}"
        _save_index(index)
        try:
            import fno_instruments

            nfo_count = fno_instruments.save_nfo_subset(rows)
        except Exception:
            nfo_count = 0
        catalog_count = 0
        try:
            import instrument_search

            catalog_count = instrument_search.rebuild_from_kite_rows(rows)
        except Exception:
            catalog_count = 0
        _save_meta(
            {
                "refreshed_at": datetime.now().isoformat(),
                "count": len(index),
                "nfo_rows": nfo_count,
                "search_catalog": catalog_count,
                "source": "kite.instruments()",
            }
        )
        return True, None
    except Exception as exc:
        return False, str(exc)


def ensure_cache(force: bool = False) -> Tuple[bool, Optional[str]]:
    if not force and is_cache_fresh():
        try:
            import instrument_search

            if not instrument_search.catalog_ready():
                return refresh_instruments(force=True)
        except Exception:
            pass
        return True, None
    return refresh_instruments(force=force)


def resolve_instrument_token(stock_key: str, *, auto_refresh: bool = True) -> Tuple[Optional[int], Optional[str]]:
    ins = kite_instrument_id(stock_key)
    index = _load_index()
    if ins in index:
        return index[ins], None
    if auto_refresh and kite_data.kite_enabled():
        ok, err = refresh_instruments(force=True)
        if ok:
            index = _load_index()
            if ins in index:
                return index[ins], None
        if err:
            return None, f"No token for {ins} (refresh: {err})"
    return None, f"Instrument not in cache for {ins}. Call GET /kite/instruments/refresh"


def resolve_tokens_for_keys(stock_keys: List[str]) -> Tuple[Dict[str, int], List[str]]:
    ensure_cache()
    index = _load_index()
    out: Dict[str, int] = {}
    missing: List[str] = []
    for k in stock_keys:
        ins = kite_instrument_id(k)
        tok = index.get(ins)
        if tok is not None:
            out[k.strip().upper()] = int(tok)
        else:
            missing.append(k)
    return out, missing


def get_status() -> Dict[str, Any]:
    meta = _load_meta()
    return {
        "cached": bool(_load_index()),
        "instrument_keys": len(_load_index()),
        "cache_age_hours": cache_age_hours(),
        "fresh": is_cache_fresh(),
        "meta": meta,
        "cache_dir": cache_dir(),
    }
