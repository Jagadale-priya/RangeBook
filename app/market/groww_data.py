"""
Groww live market data provider (NSE CASH + indices).

Credentials in .env (project root):
  GROWW_API_KEY + GROWW_API_SECRET — approval flow (approve key daily on Groww)
  GROWW_TOTP_KEY + GROWW_TOTP_SECRET — TOTP flow (auto token refresh)

Requires Groww Trading API subscription (₹499+tax/mo) for live quote/LTP.
"""

from __future__ import annotations

import hashlib
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None  # type: ignore

try:
    from dotenv import load_dotenv

    import path_setup
    _ROOT = str(path_setup.ROOT)

    def _strip_env_quotes(val: str) -> str:
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
            return val[1:-1]
        return val

    # Never let .env.example stomp live desk channel flags (caused dual→pre-dual drift).
    _DESK_ENV_KEYS = {
        "USE_DUAL_TRACK",
        "ENABLE_PRE_DUAL_SINGLE",
        "PRE_DUAL_SOFT_GATES",
        "ENABLE_STACKED_CALLS",
        "ENABLE_5M_CROWN",
        "ENABLE_NSE_MID_GATE",
        "OVERLAY_ACC_MIN",
        "OVERLAY_NOTIFY",
        "ENABLE_15M_CLASSIC",
        "ENABLE_DAILY_FILL",
        "ENABLE_MOVE_CAPTURE",
    }

    def _load_env_file(
        path: str,
        *,
        skip_empty: bool = False,
        skip_keys: set | None = None,
    ) -> None:
        if not os.path.isfile(path):
            return
        blocked = skip_keys or set()
        with open(path, encoding="utf-8") as fh:
            for raw in fh:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key, val = key.strip(), _strip_env_quotes(val.strip())
                if key in blocked:
                    continue
                if skip_empty and not val:
                    continue
                if skip_empty and not val and key in os.environ:
                    continue
                if val or not skip_empty:
                    if skip_empty and not val:
                        continue
                    os.environ[key] = val

    _example = os.path.join(_ROOT, ".env.example")
    _env = os.path.join(_ROOT, ".env")
    _load_env_file(_example, skip_empty=True, skip_keys=_DESK_ENV_KEYS)
    _load_env_file(_env, skip_empty=True)
    # Prefer Windows DPAPI vault over plaintext .env for Kite/Groww secrets.
    try:
        import secrets_store

        secrets_store.apply_to_environ()
    except Exception:
        pass
except ImportError:
    pass

try:
    import pyotp
except ImportError:
    pyotp = None  # type: ignore

try:
    import requests
except ImportError:
    requests = None  # type: ignore

try:
    from growwapi import GrowwAPI as _GrowwAPI
except ImportError:
    _GrowwAPI = None

GROWW_API_BASE = "https://api.groww.in"
API_VERSION = "1.0"

GROWW_INDEX_SYMBOLS = {"NIFTY", "BANKNIFTY", "SENSEX"}

GROWW_SYMBOL_OVERRIDES = {
    "BANKNIFTY": "NIFTY BANK",
    "NIFTY": "NIFTY",
}

_client: Any = None
_token_cached: Optional[str] = None
_token_obtained_at: float = 0.0
_last_error: Optional[str] = None
_auth_mode: Optional[str] = None


def _ist_now() -> datetime:
    if ZoneInfo:
        return datetime.now(ZoneInfo("Asia/Kolkata"))
    return datetime.now()


def stock_key_from_input(stock_input: str) -> str:
    return stock_input.strip().upper()


import market_symbols

is_groww_eligible = market_symbols.is_groww_eligible
groww_trading_symbol = market_symbols.groww_trading_symbol
apply_live_quote_to_daily_df = market_symbols.apply_live_quote_to_daily_df


def groww_ltp_key(stock_key: str) -> str:
    return f"NSE_{groww_trading_symbol(stock_key)}"


def _read_env(name: str) -> Optional[str]:
    val = os.environ.get(name, "").strip()
    return val or None


def _parse_token_response(data: Any) -> Optional[str]:
    if not isinstance(data, dict):
        return None
    if data.get("access_token"):
        return data["access_token"]
    if data.get("token"):
        return data["token"]
    payload = data.get("payload")
    if isinstance(payload, dict):
        if payload.get("access_token"):
            return payload["access_token"]
        if payload.get("token"):
            return payload["token"]
    return None


def _approval_checksum(api_secret: str, timestamp: str) -> str:
    return hashlib.sha256(f"{api_secret}{timestamp}".encode("utf-8")).hexdigest()


def _mint_via_approval(api_key: str, api_secret: str) -> Tuple[Optional[str], Optional[str]]:
    global _auth_mode
    _auth_mode = "approval"

    if _GrowwAPI is not None:
        try:
            token = _GrowwAPI.get_access_token(api_key=api_key, secret=api_secret)
            if token:
                return token, None
        except Exception as exc:
            sdk_err = str(exc)
        else:
            sdk_err = None
    else:
        sdk_err = None

    if requests is None:
        return None, sdk_err or "Install requests for Groww auth"

    timestamp = str(int(time.time()))
    checksum = _approval_checksum(api_secret, timestamp)
    try:
        resp = requests.post(
            f"{GROWW_API_BASE}/v1/token/api/access",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "X-API-VERSION": API_VERSION,
            },
            json={
                "key_type": "approval",
                "checksum": checksum,
                "timestamp": timestamp,
            },
            timeout=30,
        )
        if resp.status_code != 200:
            hint = ""
            if resp.status_code == 401:
                hint = " Approve today's API key on Groww → Settings → Trading APIs."
            return None, f"Groww approval token error ({resp.status_code}): {resp.text[:220]}.{hint}"
        token = _parse_token_response(resp.json())
        if not token:
            return None, f"Groww token response missing access_token: {resp.text[:220]}"
        return token, None
    except Exception as exc:
        return None, str(exc)


def _mint_via_totp(totp_key: str, totp_secret: str) -> Tuple[Optional[str], Optional[str]]:
    global _auth_mode
    _auth_mode = "totp"

    if pyotp is None:
        return None, "Install pyotp for TOTP auth: pip install pyotp"

    totp_code = pyotp.TOTP(totp_secret).now()

    if _GrowwAPI is not None:
        try:
            token = _GrowwAPI.get_access_token(api_key=totp_key, totp=totp_code)
            if token:
                return token, None
        except Exception:
            pass

    if requests is None:
        return None, "requests is required for Groww auth"

    try:
        resp = requests.post(
            f"{GROWW_API_BASE}/v1/token/api/access",
            headers={
                "Authorization": f"Bearer {totp_key}",
                "Content-Type": "application/json",
                "X-API-VERSION": API_VERSION,
            },
            json={"key_type": "totp", "totp": totp_code},
            timeout=30,
        )
        if resp.status_code != 200:
            return None, f"Groww TOTP token error ({resp.status_code}): {resp.text[:220]}"
        token = _parse_token_response(resp.json())
        if not token:
            return None, f"Groww token response missing access_token: {resp.text[:220]}"
        return token, None
    except Exception as exc:
        return None, str(exc)


def _mint_access_token() -> Tuple[Optional[str], Optional[str]]:
    direct = _read_env("GROWW_ACCESS_TOKEN")
    if direct:
        return direct, None

    api_key = _read_env("GROWW_API_KEY")
    api_secret = _read_env("GROWW_API_SECRET")
    if api_key and api_secret:
        token, err = _mint_via_approval(api_key, api_secret)
        if token:
            return token, None
        if err and len(api_key) > 400 and "inactive" in (err or "").lower():
            return None, (
                f"{err} Your GROWW_API_KEY looks like a TOTP JWT (~{len(api_key)} chars). "
                "Use a fresh pair from Generate API key → paste both into GROWW_API_KEY and "
                "GROWW_API_SECRET, or use GROWW_TOTP_KEY + GROWW_TOTP_SECRET, or "
                "GROWW_ACCESS_TOKEN from Generate Access Token."
            )
        return None, err

    totp_key = _read_env("GROWW_TOTP_KEY")
    totp_secret = _read_env("GROWW_TOTP_SECRET")
    if totp_key and totp_secret:
        return _mint_via_totp(totp_key, totp_secret)

    return None, (
        "Groww not configured. Set GROWW_API_KEY + GROWW_API_SECRET, "
        "GROWW_TOTP_KEY + GROWW_TOTP_SECRET, or GROWW_ACCESS_TOKEN in .env."
    )


def get_access_token(force_refresh: bool = False) -> Tuple[Optional[str], Optional[str]]:
    global _token_cached, _token_obtained_at, _last_error
    if _token_cached and not force_refresh and (time.time() - _token_obtained_at) < 3600:
        return _token_cached, None
    token, err = _mint_access_token()
    _last_error = err
    if token:
        _token_cached = token
        _token_obtained_at = time.time()
    else:
        _token_cached = None
    return token, err


def _get_groww_sdk(force_refresh: bool = False) -> Tuple[Any, Optional[str]]:
    global _client
    token, err = get_access_token(force_refresh=force_refresh)
    if err or not token:
        return None, err
    if _GrowwAPI is None:
        return None, "Install growwapi: pip install growwapi"
    if _client is None or force_refresh:
        _client = _GrowwAPI(token)
    return _client, None


def _quote_via_rest(trading_symbol: str, token: str) -> Dict[str, Any]:
    if requests is None:
        raise RuntimeError("requests not installed")
    resp = requests.get(
        f"{GROWW_API_BASE}/v1/live-data/quote",
        params={
            "exchange": "NSE",
            "segment": "CASH",
            "trading_symbol": trading_symbol,
        },
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "X-API-VERSION": API_VERSION,
        },
        timeout=20,
    )
    if resp.status_code == 401:
        raise PermissionError("Groww access token invalid or expired")
    if resp.status_code == 403:
        raise PermissionError("Groww live data forbidden — check Trading API subscription")
    if resp.status_code != 200:
        raise RuntimeError(f"Groww quote HTTP {resp.status_code}: {resp.text[:300]}")
    return resp.json()


def _normalize_quote(raw: Dict[str, Any], stock_key: str, received_at: datetime) -> Dict[str, Any]:
    ohlc = raw.get("ohlc") or {}
    last_trade_ms = raw.get("last_trade_time")
    exchange_ts = None
    staleness_ms = None
    if last_trade_ms:
        try:
            exchange_ts = datetime.fromtimestamp(int(last_trade_ms) / 1000, tz=timezone.utc)
            staleness_ms = max(0, int((received_at.astimezone(timezone.utc) - exchange_ts).total_seconds() * 1000))
        except (TypeError, ValueError, OSError):
            pass

    last_price = float(raw.get("last_price") or raw.get("ltp") or 0)
    return {
        "stock": stock_key_from_input(stock_key),
        "trading_symbol": groww_trading_symbol(stock_key),
        "exchange": "NSE",
        "segment": "CASH",
        "last_price": round(last_price, 2),
        "open": round(float(ohlc.get("open") or raw.get("open") or 0), 2),
        "high": round(float(ohlc.get("high") or raw.get("high") or 0), 2),
        "low": round(float(ohlc.get("low") or raw.get("low") or 0), 2),
        "close": round(float(ohlc.get("close") or raw.get("close") or last_price), 2),
        "volume": int(raw.get("volume") or 0),
        "day_change": raw.get("day_change"),
        "day_change_perc": raw.get("day_change_perc"),
        "bid_price": raw.get("bid_price"),
        "offer_price": raw.get("offer_price"),
        "upper_circuit_limit": raw.get("upper_circuit_limit"),
        "lower_circuit_limit": raw.get("lower_circuit_limit"),
        "last_trade_time_ms": last_trade_ms,
        "exchange_timestamp_utc": exchange_ts.isoformat() if exchange_ts else None,
        "received_at_ist": received_at.isoformat(),
        "staleness_ms": staleness_ms,
        "source": "groww",
        "feed_type": "live_quote",
    }


def fetch_live_quote(stock_key: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    trading = groww_trading_symbol(stock_key)
    received = _ist_now()

    groww, err = _get_groww_sdk()
    if groww is not None:
        try:
            raw = groww.get_quote(
                exchange=groww.EXCHANGE_NSE,
                segment=groww.SEGMENT_CASH,
                trading_symbol=trading,
            )
            if isinstance(raw, dict):
                return _normalize_quote(raw, stock_key, received), None
        except Exception as exc:
            err = str(exc)
            if "401" in err or "403" in err or "token" in err.lower():
                groww, _err2 = _get_groww_sdk(force_refresh=True)
                if groww is not None:
                    try:
                        raw = groww.get_quote(
                            exchange=groww.EXCHANGE_NSE,
                            segment=groww.SEGMENT_CASH,
                            trading_symbol=trading,
                        )
                        return _normalize_quote(raw, stock_key, received), None
                    except Exception as exc2:
                        err = str(exc2)

    token, terr = get_access_token(force_refresh=True)
    if terr or not token:
        return None, terr or err
    try:
        raw = _quote_via_rest(trading, token)
        return _normalize_quote(raw, stock_key, received), None
    except Exception as exc:
        return None, str(exc)


def fetch_live_ltp(stock_keys: List[str]) -> Tuple[Dict[str, float], Optional[str]]:
    keys = [stock_key_from_input(k) for k in stock_keys][:50]
    if not keys:
        return {}, None

    groww, err = _get_groww_sdk()
    symbols = tuple(groww_ltp_key(k) for k in keys)
    if groww is not None:
        try:
            resp = groww.get_ltp(segment=groww.SEGMENT_CASH, exchange_trading_symbols=symbols)
            out = {}
            for k in keys:
                ltp_key = groww_ltp_key(k)
                val = resp.get(ltp_key) if isinstance(resp, dict) else None
                if val is not None:
                    out[k] = float(val)
            if out:
                return out, None
        except Exception as exc:
            err = str(exc)

    token, terr = get_access_token()
    if terr or not token or requests is None:
        return {}, terr or err

    try:
        resp = requests.get(
            f"{GROWW_API_BASE}/v1/live-data/ltp",
            params={"segment": "CASH", "exchange_symbols": ",".join(symbols)},
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "X-API-VERSION": API_VERSION,
            },
            timeout=20,
        )
        if resp.status_code != 200:
            return {}, f"Groww LTP HTTP {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        out = {}
        for k in keys:
            ltp_key = groww_ltp_key(k)
            if ltp_key in data:
                out[k] = float(data[ltp_key])
        return out, None
    except Exception as exc:
        return {}, str(exc)


def _detect_auth_mode() -> Optional[str]:
    if _read_env("GROWW_ACCESS_TOKEN"):
        return "access_token"
    if _read_env("GROWW_API_KEY") and _read_env("GROWW_API_SECRET"):
        return "api_key_secret"
    if _read_env("GROWW_TOTP_KEY") and _read_env("GROWW_TOTP_SECRET"):
        return "totp"
    return None


def get_provider_status() -> Dict[str, Any]:
    mode = _detect_auth_mode()
    configured = mode is not None
    token, err = get_access_token()
    return {
        "provider": "groww",
        "configured": configured,
        "auth_mode": mode,
        "sdk_installed": _GrowwAPI is not None,
        "token_available": token is not None,
        "last_error": err or _last_error,
        "daily_approval_required": mode == "api_key_secret",
        "note": (
            "API key+secret: approve key each day on Groww Trading APIs page. "
            "Access token expires ~6:00 AM IST. Subscription required for live data."
        ),
    }
