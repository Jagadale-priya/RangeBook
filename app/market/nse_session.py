"""NSE India website session (news/announcements only — not used for live quotes).

NSE often answers a reused connection with WinError 10054 (connection reset).
One client is shared, requests run one at a time, and a reset opens a new session.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Optional, Tuple

try:
    import requests
except ImportError:
    requests = None  # type: ignore

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

_session: Any = None
_client: Any = None
_lock = threading.Lock()


def reset_session() -> None:
    """Drop the cookie jar and close its sockets so the next call dials a new one."""
    global _session
    old = _session
    _session = None
    if old is not None:
        try:
            old.close()
        except Exception:
            pass


def friendly_error(exc: BaseException) -> str:
    text = str(exc)
    if "10054" in text or "Connection aborted" in text or "Connection reset" in text:
        return "NSE closed the connection"
    if requests is not None and isinstance(exc, requests.exceptions.Timeout):
        return "NSE did not answer in time"
    return "NSE request failed"


def _open_session() -> Optional[Any]:
    if requests is None:
        return None
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": "application/json,text/plain,*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.nseindia.com/",
            # A kept-alive socket is what NSE resets. Each call opens its own.
            "Connection": "close",
        }
    )
    try:
        # Warm cookies. The homepage can answer 403 while the JSON APIs still serve.
        response = session.get("https://www.nseindia.com", timeout=12)
        if response.status_code < 500:
            return session
    except Exception:
        pass
    try:
        session.close()
    except Exception:
        pass
    return None


class _NseClient:
    """Session stand-in. `.get` retries a reset instead of raising WinError 10054."""

    def get(self, url: str, **kwargs: Any) -> Any:
        timeout = kwargs.pop("timeout", 8)
        params = kwargs.pop("params", None)
        headers = kwargs.pop("headers", None)
        attempts = int(kwargs.pop("attempts", 3))
        response, err = _request(
            url, params=params, timeout=timeout, headers=headers, attempts=attempts
        )
        if response is None:
            raise requests.exceptions.ConnectionError(err or "NSE request failed")
        return response


def nse_session() -> Optional[Any]:
    global _client
    if requests is None:
        return None
    if _client is None:
        _client = _NseClient()
    return _client


def _request(
    url: str,
    *,
    params: Any = None,
    timeout: float = 8,
    headers: Any = None,
    attempts: int = 3,
) -> Tuple[Optional[Any], Optional[str]]:
    """One NSE GET. Connection resets and 401/403/429/5xx open a fresh session."""
    global _session
    last = "NSE session unavailable"
    attempts = max(1, attempts)
    for attempt in range(attempts):
        with _lock:
            if _session is None:
                _session = _open_session()
            session = _session
            response = None
            if session is None:
                last = "NSE session unavailable"
            else:
                try:
                    response = session.get(url, params=params, headers=headers, timeout=timeout)
                except Exception as exc:
                    reset_session()
                    last = friendly_error(exc)
                    response = None
                else:
                    code = int(response.status_code)
                    if code in (401, 403, 429) or code >= 500:
                        reset_session()
                        last = f"HTTP {code}"
                        if code == 403 and attempt + 1 == attempts:
                            return response, None
                        response = None
                    else:
                        return response, None
        if attempt + 1 < attempts:
            time.sleep(0.4 * (attempt + 1))
    return None, last
