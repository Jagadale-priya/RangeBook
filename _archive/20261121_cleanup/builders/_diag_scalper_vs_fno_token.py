"""Compare F&O quote path vs scalper hist/token handling. Masked only."""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / "app" / "market"), str(ROOT / "app" / "fno")]

import path_setup  # noqa: F401
import secrets_store  # noqa: E402
import kite_auth  # noqa: E402
import kite_data  # noqa: E402


def mask(t: str) -> str:
    t = str(t or "")
    if not t:
        return "EMPTY"
    return f"{t[:4]}…{t[-4:]} len={len(t)}"


def main() -> None:
    vault = str(secrets_store.get("KITE_ACCESS_TOKEN") or "").strip()
    env = str(os.environ.get("KITE_ACCESS_TOKEN") or "").strip()
    file_tok = ""
    env_path = Path(ROOT) / ".env"
    if env_path.is_file():
        for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.startswith("KITE_ACCESS_TOKEN="):
                file_tok = line.split("=", 1)[1].strip().strip('"').strip("'")
                break

    print("=== token sources ===")
    print("vault  ", mask(vault))
    print("environ", mask(env), "eq_vault", env == vault)
    print("dotenv ", mask(file_tok), "eq_vault", file_tok == vault, "eq_env", file_tok == env)

    for label, tok in (("vault", vault), ("environ", env), ("dotenv", file_tok)):
        if not tok:
            print(f"validate {label}: EMPTY")
            continue
        ok = kite_auth.validate_access_token(tok)
        print(f"validate {label}: {ok}")

    tok, err = kite_auth.get_access_token()
    print("get_access_token", mask(tok or ""), "err", err)

    q, e = kite_data.fetch_live_quote("NIFTY")
    print(
        "fetch_live_quote",
        "ok" if q and q.get("last_price") is not None else "FAIL",
        "ltp",
        (q or {}).get("last_price"),
        "src",
        (q or {}).get("source"),
        "err",
        e,
    )

    df, he = kite_data.fetch_historical_candles(
        "NIFTY", interval="minute", days=2, keep_partial=True
    )
    print(
        "hist",
        "ok" if df is not None and len(df) else "FAIL",
        "n",
        0 if df is None else len(df),
        "err",
        he,
        "max",
        None if df is None or not len(df) else str(df.index.max()),
    )

    # How does ticker / WS see token?
    try:
        import kite_ticker

        st = kite_ticker.status() if hasattr(kite_ticker, "status") else None
        print("ticker_status", st)
    except Exception as exc:
        print("ticker_status err", exc)

    for path in (
        "http://127.0.0.1:5000/fno/live-watch",
        "http://127.0.0.1:5000/fno/scalper/tick?stock=NIFTY",
        "http://127.0.0.1:5000/fno/scalper/live?stock=NIFTY&notify=0&mode=oracle_t15",
        "http://127.0.0.1:5000/health",
    ):
        try:
            d = json.load(urllib.request.urlopen(path, timeout=90))
            if "live-watch" in path:
                print("api live-watch last_error", d.get("last_error"))
                print("api NIFTY", d.get("last_results", {}).get("NIFTY"))
            elif "tick" in path:
                print(
                    "api tick feed",
                    d.get("feed"),
                    "live",
                    d.get("live"),
                    "ltp",
                    (d.get("quote") or {}).get("last_price"),
                    "note",
                    d.get("note"),
                    "kite_dead",
                    d.get("kite_dead"),
                )
            elif "live?" in path:
                live = d.get("live") or {}
                print(
                    "api scalper live",
                    "ok",
                    d.get("ok"),
                    "fast",
                    d.get("fast"),
                    "note",
                    d.get("note"),
                    "entry",
                    {k: live.get(k) for k in ("hm", "decision", "primary", "entry")}
                    if live
                    else None,
                    "notified_flag_field",
                    d.get("notified"),
                )
            else:
                print("health kite", {k: d.get(k) for k in d if "kite" in k.lower()})
        except Exception as exc:
            print("api fail", path, exc)


if __name__ == "__main__":
    main()
