"""
Kite Connect access_token: auto-refresh on expiry via Zerodha login + TOTP.

Optional .env (enables hands-free daily refresh):
  KITE_USER_ID=your_zerodha_client_id
  KITE_PASSWORD=your_kite_password
  KITE_TOTP_SECRET=base32_secret_from_authenticator_app

Still required:
  KITE_API_KEY, KITE_API_SECRET, KITE_REDIRECT_URL (must match developer app)
"""

from __future__ import annotations

import os
import re
import threading
import time
from typing import Any, List, Optional, Tuple
from urllib.parse import parse_qs, quote, urlparse

import groww_data  # loads .env then DPAPI vault into environ

try:
    import secrets_store
except ImportError:
    secrets_store = None  # type: ignore

try:
    import pyotp
except ImportError:
    pyotp = None  # type: ignore

try:
    import requests
except ImportError:
    requests = None  # type: ignore

try:
    from kiteconnect import KiteConnect
except ImportError:
    KiteConnect = None  # type: ignore

import path_setup
ROOT = str(path_setup.ROOT)
ENV_PATH = os.path.join(ROOT, ".env")

KITE_LOGIN = "https://kite.zerodha.com/api/login"
KITE_TWOFA = "https://kite.zerodha.com/api/twofa"
KITE_CONNECT_LOGIN = "https://kite.zerodha.com/connect/login"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

_refresh_lock = threading.Lock()
_token_cached: Optional[str] = None
_token_validated_at: float = 0.0
_last_error: Optional[str] = None
_last_refresh_mode: Optional[str] = None


def _read_env(name: str) -> Optional[str]:
    if secrets_store is not None:
        val = secrets_store.get(name)
        if val:
            return val
    val = os.environ.get(name, "").strip()
    return val or None


def auto_login_configured() -> bool:
    uid = _read_env("KITE_USER_ID") or _read_env("KITE_ZERODHA_USER_ID")
    pwd = _read_env("KITE_PASSWORD")
    totp = _read_env("KITE_TOTP_SECRET")
    if os.environ.get("KITE_AUTO_LOGIN", "1").strip().lower() in ("0", "false", "no"):
        return False
    return bool(uid and pwd and totp and pyotp is not None)


def api_credentials_ready() -> bool:
    return bool(_read_env("KITE_API_KEY") and _read_env("KITE_API_SECRET"))


def save_access_token(token: str) -> None:
    """Persist today's access token in the DPAPI vault (preferred) and memory.

    Legacy .env writes are skipped when the vault is available so the git tree
    does not keep rotating plaintext tokens.
    """
    global _token_cached, _token_validated_at
    token = str(token).strip()
    if not token:
        return
    saved_vault = False
    if secrets_store is not None:
        try:
            secrets_store.set_secret("KITE_ACCESS_TOKEN", token)
            saved_vault = True
        except Exception:
            saved_vault = False
    if not saved_vault:
        line = f"KITE_ACCESS_TOKEN={token}"
        if os.path.isfile(ENV_PATH):
            with open(ENV_PATH, encoding="utf-8") as fh:
                lines = fh.readlines()
            found = False
            for i, raw in enumerate(lines):
                if raw.strip().startswith("KITE_ACCESS_TOKEN="):
                    lines[i] = line + "\n"
                    found = True
                    break
            if not found:
                if lines and not lines[-1].endswith("\n"):
                    lines[-1] += "\n"
                lines.append(line + "\n")
            with open(ENV_PATH, "w", encoding="utf-8") as fh:
                fh.writelines(lines)
        else:
            with open(ENV_PATH, "w", encoding="utf-8") as fh:
                fh.write(line + "\n")
    os.environ["KITE_ACCESS_TOKEN"] = token
    _token_cached = token
    _token_validated_at = time.time()


def extract_request_token(text: str) -> Optional[str]:
    text = text.strip()
    m = re.search(r"request_token=([^&\s]+)", text)
    if m:
        return m.group(1)
    if len(text) > 10 and " " not in text and "/" not in text:
        return text
    return None


def exchange_request_token(request_token: str) -> Tuple[Optional[str], Optional[str]]:
    global _last_refresh_mode
    if KiteConnect is None:
        return None, "Install kiteconnect: pip install kiteconnect"
    api_key = _read_env("KITE_API_KEY")
    api_secret = _read_env("KITE_API_SECRET")
    if not api_key or not api_secret:
        return None, "Set KITE_API_KEY and KITE_API_SECRET in .env"
    try:
        kite = KiteConnect(api_key=api_key)
        session = kite.generate_session(request_token, api_secret=api_secret)
        access = session.get("access_token")
        if not access:
            return None, "Kite session response missing access_token"
        save_access_token(access)
        _last_refresh_mode = "oauth"
        return access, None
    except Exception as exc:
        return None, str(exc)


def _session_login() -> Tuple[Any, Optional[str]]:
    if requests is None:
        return None, "Install requests"
    uid = _read_env("KITE_USER_ID") or _read_env("KITE_ZERODHA_USER_ID")
    pwd = _read_env("KITE_PASSWORD")
    totp_secret = _read_env("KITE_TOTP_SECRET")
    if not uid or not pwd or not totp_secret:
        return None, "Set KITE_USER_ID, KITE_PASSWORD, KITE_TOTP_SECRET for auto login"
    if pyotp is None:
        return None, "Install pyotp for auto login: pip install pyotp"

    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT})
    try:
        r = s.post(KITE_LOGIN, data={"user_id": uid, "password": pwd}, timeout=30)
        payload = r.json()
        if payload.get("status") != "success":
            msg = payload.get("message") or r.text[:200]
            return None, f"Kite login failed: {msg}"
        data = payload.get("data") or {}
        request_id = data.get("request_id")
        if not request_id:
            return None, "Kite login missing request_id"
        otp = pyotp.TOTP(totp_secret).now()
        r2 = s.post(
            KITE_TWOFA,
            data={
                "user_id": uid,
                "request_id": request_id,
                "twofa_value": otp,
                "twofa_type": "totp",
            },
            timeout=30,
        )
        payload2 = r2.json()
        if payload2.get("status") != "success":
            msg = payload2.get("message") or r2.text[:200]
            return None, f"Kite 2FA failed: {msg}"
        return s, None
    except Exception as exc:
        return None, str(exc)


def _request_token_via_session(session: Any) -> Tuple[Optional[str], Optional[str]]:
    api_key = _read_env("KITE_API_KEY")
    if not api_key:
        return None, "KITE_API_KEY not set"
    url = f"{KITE_CONNECT_LOGIN}?v=3&api_key={quote(api_key)}"
    try:
        r = session.get(url, timeout=30, allow_redirects=True)
        tok = extract_request_token(r.url)
        if tok:
            return tok, None
        if "request_token=" in (r.text or ""):
            m = re.search(r"request_token=([^&\"']+)", r.text)
            if m:
                return m.group(1), None
        return None, f"No request_token in redirect (HTTP {r.status_code}). Check KITE_REDIRECT_URL in developer app."
    except Exception as exc:
        return None, str(exc)


def mint_access_token_auto() -> Tuple[Optional[str], Optional[str]]:
    global _last_refresh_mode, _last_error
    sess, err = _session_login()
    if err or not sess:
        _last_error = err
        return None, err
    req_tok, err2 = _request_token_via_session(sess)
    if err2 or not req_tok:
        _last_error = err2
        return None, err2
    access, err3 = exchange_request_token(req_tok)
    _last_error = err3
    if access:
        _last_refresh_mode = "auto_totp"
    return access, err3


def _token_looks_invalid(exc: BaseException) -> bool:
    msg = str(exc).lower()
    # Connection errors on Windows can say a socket operation was "forbidden by
    # its access permissions".  That is a local network restriction, not a Kite
    # HTTP 403 and must not be reported as an expired access token.
    if "socket" in msg or "failed to establish a new connection" in msg:
        return False
    return any(x in msg for x in ("token", "401", "403", "session", "unauthorized", "forbidden"))


def validate_access_token(access_token: str) -> bool:
    if KiteConnect is None:
        return False
    api_key = _read_env("KITE_API_KEY")
    if not api_key:
        return False
    try:
        kite = KiteConnect(api_key=api_key)
        kite.set_access_token(access_token)
        kite.profile()
        return True
    except Exception as exc:
        return not _token_looks_invalid(exc)


def reload_access_token_from_env_file() -> None:
    """Load KITE_ACCESS_TOKEN into process env without destroying any store.

    Priority for *which* token to use:
      1) in-memory process env (login / UI may have just set a live one)
      2) DPAPI vault
      3) plaintext `.env` (last resort)

    Never writes vault → `.env` (that stomped live tokens when stores drifted).
    Never clears a present token.
    """
    global _token_cached, _token_validated_at

    vault_tok = ""
    if secrets_store is not None:
        try:
            vault_tok = str(secrets_store.get("KITE_ACCESS_TOKEN") or "").strip()
        except Exception:
            vault_tok = ""

    file_tok = ""
    if os.path.isfile(ENV_PATH):
        try:
            with open(ENV_PATH, encoding="utf-8") as fh:
                for raw in fh:
                    line = raw.strip()
                    if not line or line.startswith("#") or not line.startswith("KITE_ACCESS_TOKEN="):
                        continue
                    file_tok = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
        except OSError:
            file_tok = ""

    prev = os.environ.get("KITE_ACCESS_TOKEN", "").strip()
    # Keep a live in-process token. Only fill env when empty.
    if prev:
        chosen = prev
    elif vault_tok:
        chosen = vault_tok
    else:
        chosen = file_tok

    if not chosen:
        return

    if chosen != prev:
        os.environ["KITE_ACCESS_TOKEN"] = chosen
        if chosen != _token_cached:
            _token_cached = None
            _token_validated_at = 0.0


def get_access_token(force_refresh: bool = False) -> Tuple[Optional[str], Optional[str]]:
    """
    Return access_token for Kite Connect / WS.

    Prefer a token that validates. If profile() rejects every candidate but a
    token is still present, return it anyway so KiteTicker/WS can keep running
    (F&O chart uses WS even when REST profile flaps). Never delete stores.
    """
    global _token_cached, _token_validated_at, _last_error

    reload_access_token_from_env_file()

    if not api_credentials_ready():
        return None, "Set KITE_API_KEY and KITE_API_SECRET in .env"

    # Candidates: process env first (live login), then vault, then .env — unique order
    candidates: List[str] = []
    for tok in (
        os.environ.get("KITE_ACCESS_TOKEN", "").strip(),
        str(secrets_store.get("KITE_ACCESS_TOKEN") or "").strip() if secrets_store is not None else "",
        _read_env("KITE_ACCESS_TOKEN") or "",
    ):
        if tok and tok not in candidates:
            candidates.append(tok)

    if _token_cached and _token_cached not in candidates:
        candidates.insert(0, _token_cached)

    if (
        not force_refresh
        and _token_cached
        and (time.time() - _token_validated_at) < 300
    ):
        return _token_cached, None

    with _refresh_lock:
        if (
            not force_refresh
            and _token_cached
            and (time.time() - _token_validated_at) < 300
        ):
            return _token_cached, None

        for tok in candidates:
            if not force_refresh and validate_access_token(tok):
                _token_cached = tok
                _token_validated_at = time.time()
                os.environ["KITE_ACCESS_TOKEN"] = tok
                return tok, None

        if auto_login_configured():
            access, err = mint_access_token_auto()
            if access:
                return access, None
            _last_error = err

        # Soft fallback: keep serving a present token for WS (do not wipe stores)
        soft = candidates[0] if candidates else None
        if soft:
            _token_cached = soft
            # Do not bump validated_at — next cycle may re-check
            os.environ["KITE_ACCESS_TOKEN"] = soft
            return soft, None

        hint = (
            "Kite token expired. Add KITE_USER_ID, KITE_PASSWORD, KITE_TOTP_SECRET for auto refresh, "
            "or run: py kite_login.py"
        )
        return None, _last_error or hint


def kite_connect_login_url(api_key: str) -> str:
    return f"{KITE_CONNECT_LOGIN}?v=3&api_key={quote(api_key)}"


def get_auth_status() -> dict:
    return {
        "api_ready": api_credentials_ready(),
        "access_token_set": bool(_read_env("KITE_ACCESS_TOKEN")),
        "auto_login_configured": auto_login_configured(),
        "last_refresh_mode": _last_refresh_mode,
        "last_error": _last_error,
    }
