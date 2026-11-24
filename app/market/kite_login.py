"""
Obtain today's Kite access_token and save it to .env.

Auto mode: if KITE_USER_ID + KITE_PASSWORD + KITE_TOTP_SECRET are set, refreshes without browser.

Manual:
  py kite_login.py              # opens browser + local callback server
  py kite_login.py <request_token>
  py kite_login.py --paste
"""

from __future__ import annotations

import os
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Optional
from urllib.parse import parse_qs, urlparse

import groww_data  # loads .env
import kite_auth

try:
    from kiteconnect import KiteConnect
except ImportError:
    print("Install: pip install kiteconnect")
    raise SystemExit(1)


def _env(name: str) -> str:
    val = os.environ.get(name, "").strip()
    if not val:
        print(f"Missing {name} in .env")
        raise SystemExit(1)
    return val


def _redirect_url() -> str:
    return os.environ.get("KITE_REDIRECT_URL", "http://127.0.0.1/").strip()


def _redirect_host_port(url: str) -> tuple[str, int]:
    parsed = urlparse(url)
    host = parsed.hostname or "127.0.0.1"
    if parsed.port:
        return host, parsed.port
    return host, 443 if parsed.scheme == "https" else 80


def _run_callback_server(api_key: str, redirect: str) -> str:
    host, port = _redirect_host_port(redirect)
    result: dict[str, Optional[str]] = {"token": None, "error": None}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            qs = parse_qs(urlparse(self.path).query)
            if qs.get("status", [""])[0] == "error":
                result["error"] = qs.get("message", ["login failed"])[0]
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"Login failed. Close this tab and check the terminal.")
                return
            tok = qs.get("request_token", [None])[0]
            result["token"] = tok
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Kite login OK. You can close this tab and return to the terminal.")

        def log_message(self, *_args):
            return

    login_url = kite_auth.kite_connect_login_url(api_key)
    print(f"Redirect URL (must match Kite app): {redirect}")
    print(f"Opening: {login_url}")
    if port == 80:
        print("Listening on 127.0.0.1:80 — run terminal as Administrator if bind fails.")
    webbrowser.open(login_url)
    try:
        server = HTTPServer((host, port), Handler)
    except OSError as exc:
        print(f"Could not bind {host}:{port} — {exc}")
        print("Fix: set KITE_REDIRECT_URL=http://127.0.0.1:8765/ in .env and the same URL in My Apps,")
        print("     or add KITE_USER_ID / KITE_PASSWORD / KITE_TOTP_SECRET for auto login.")
        raise SystemExit(1) from exc
    print(f"Waiting for login callback on {host}:{port} ...")
    server.handle_request()
    if result["error"]:
        print(result["error"])
        raise SystemExit(1)
    if not result["token"]:
        print("No request_token received.")
        raise SystemExit(1)
    return result["token"]


def main() -> None:
    if kite_auth.auto_login_configured():
        print("Auto login (TOTP)...")
        access, err = kite_auth.mint_access_token_auto()
        if access:
            print("KITE_ACCESS_TOKEN saved to secure vault (DPAPI) when available.")
            return
        print(f"Auto login failed: {err}")
        print("Falling back to browser login...")

    api_key = _env("KITE_API_KEY")
    _env("KITE_API_SECRET")

    if len(sys.argv) > 1 and sys.argv[1] not in ("--paste", "-p"):
        tok = kite_auth.extract_request_token(sys.argv[1])
        if not tok:
            print("Could not parse request_token from argument.")
            raise SystemExit(1)
        access, err = kite_auth.exchange_request_token(tok)
        if err:
            print(err)
            raise SystemExit(1)
        print("KITE_ACCESS_TOKEN saved.")
        return

    if len(sys.argv) > 1 and sys.argv[1] in ("--paste", "-p"):
        print("Paste the full redirect URL from the browser address bar, then Enter:")
        pasted = input().strip()
        tok = kite_auth.extract_request_token(pasted)
        if not tok:
            print("No request_token found in pasted text.")
            raise SystemExit(1)
        access, err = kite_auth.exchange_request_token(tok)
        if err:
            print(err)
            raise SystemExit(1)
        print("KITE_ACCESS_TOKEN saved.")
        return

    redirect = _redirect_url()
    request_token = _run_callback_server(api_key, redirect)
    access, err = kite_auth.exchange_request_token(request_token)
    if err:
        print(err)
        raise SystemExit(1)
    try:
        kite = KiteConnect(api_key=api_key)
        kite.set_access_token(access)
        profile = kite.profile()
        print(f"Logged in as: {profile.get('user_name')} ({profile.get('user_id')})")
    except Exception:
        print("Access token saved.")


if __name__ == "__main__":
    main()
