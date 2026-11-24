"""Compare Kite token sources: .env vs DPAPI vault vs environ."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "app" / "market"))
sys.path.insert(0, str(ROOT / "tools" / "research"))
try:
    import path_setup  # noqa: F401
except Exception:
    pass

import groww_data  # noqa: F401 — loads .env then vault into environ


def fp(t: str) -> str:
    t = str(t or "")
    if len(t) > 8:
        return f"len={len(t)} {t[:4]}…{t[-4:]}"
    return f"len={len(t)} {t!r}"


def main() -> int:
    env_tok = os.environ.get("KITE_ACCESS_TOKEN", "")
    file_tok = ""
    env_path = ROOT / ".env"
    if env_path.is_file():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("KITE_ACCESS_TOKEN="):
                file_tok = line.split("=", 1)[1].strip().strip('"').strip("'")
                break
    vault_tok = ""
    try:
        import secrets_store

        vault_tok = secrets_store.get("KITE_ACCESS_TOKEN") or ""
    except Exception as exc:
        vault_tok = f"ERR:{exc}"

    print("environ", fp(env_tok), "same_file", env_tok == file_tok, "same_vault", env_tok == vault_tok)
    print("file   ", fp(file_tok))
    print("vault  ", fp(vault_tok))
    print("file==vault", file_tok == vault_tok)

    import kite_auth

    read = kite_auth._read_env("KITE_ACCESS_TOKEN") or ""
    print("_read_env", fp(read), "same_vault", read == vault_tok)

    kite_auth.reload_access_token_from_env_file()
    after = os.environ.get("KITE_ACCESS_TOKEN", "")
    print(
        "after reload_env_file",
        fp(after),
        "stomped_to_file",
        after == file_tok and after != vault_tok,
        "same_vault",
        after == vault_tok,
    )

    tok, err = kite_auth.get_access_token()
    print("get_access_token ok", bool(tok), "err", err)
    if tok:
        print("returned same_vault", tok == vault_tok, "same_file", tok == file_tok)

    import kite_data

    df, herr = kite_data.fetch_historical_candles(
        "NIFTY", interval="minute", days=1, keep_partial=True
    )
    print("hist ok", df is not None and len(df) > 0, "n", 0 if df is None else len(df), "err", herr)
    if df is not None and len(df):
        print("last_bar", df.index[-1], float(df["close"].iloc[-1]) if "close" in df.columns else float(df["Close"].iloc[-1]))

    # scalper path
    from app.fno import fno_scalper_1m as s

    s._KITE_DEAD_UNTIL = 0.0
    s._BAR_CACHE.clear()
    tick = s.scalper_tick("NIFTY")
    print(
        "scalper_tick feed",
        tick.get("feed"),
        "kite_dead",
        tick.get("kite_dead"),
        "live",
        tick.get("live"),
        "note",
        (tick.get("note") or "")[:80],
        "bar",
        tick.get("bar_time"),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
