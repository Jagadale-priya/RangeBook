"""Find today's NIFTY modal call in session DBs / snapshots."""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(r"c:\Users\Priyanka\Agent")
sys.path[:0] = [str(ROOT), str(ROOT / "app"), str(ROOT / "app" / "fno"), str(ROOT / "tools" / "research")]
import path_setup  # noqa: F401

TODAY = "2026-11-18"


def dump_db(path: Path) -> None:
    print(f"\n==== {path} exists={path.exists()} ====")
    if not path.exists():
        return
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    print("tables", tables)
    for t in tables:
        cols = [c[1] for c in con.execute(f"PRAGMA table_info({t})")]
        n = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        interesting = any(
            x in t.lower() for x in ("call", "ticket", "session", "fno", "predict", "snap", "alert", "history")
        )
        if not interesting and n > 0:
            # still scan text for NIFTY + today
            pass
        if interesting or n < 5000:
            print(f"  {t}: n={n} cols={cols[:25]}")
        # search rows mentioning today + NIFTY
        text_cols = [c for c in cols if c.lower() in (
            "symbol", "stock", "key", "payload", "json", "data", "body", "decision",
            "day", "date", "session_day", "asof", "created_at", "updated_at", "source",
            "track", "readings", "ticket", "status",
        ) or "json" in c.lower() or "payload" in c.lower() or "data" in c.lower()]
        if not text_cols and cols:
            text_cols = cols[:8]
        try:
            rows = con.execute(f"SELECT * FROM {t} ORDER BY rowid DESC LIMIT 200").fetchall()
        except Exception as e:
            print("  err", e)
            continue
        hits = []
        for r in rows:
            d = dict(r)
            blob = json.dumps(d, default=str)
            if TODAY in blob and ("NIFTY" in blob.upper() or "nifty" in blob):
                hits.append(d)
        if hits:
            print(f"  HITS in {t}: {len(hits)}")
            for d in hits[:8]:
                slim = {}
                for k, v in d.items():
                    s = v if not isinstance(v, str) else (v[:500] + "…" if len(v) > 500 else v)
                    slim[k] = s
                print(json.dumps(slim, default=str)[:1500])
                print("---")


def main() -> int:
    import session_calls as sc

    print("session_calls db", sc.default_db_path())
    dump_db(Path(sc.default_db_path()))
    dump_db(ROOT / "stock_signal_data" / "fno_session.sqlite")
    dump_db(ROOT / "stock_signal_data" / "fno_validate" / "fno_session.sqlite")

    # also search common snapshot folders
    for pat in [
        "**/fno*snap*.json",
        "**/session*nifty*.json",
        "**/nifty*dual*.json",
        "**/live*ticket*.json",
    ]:
        found = list(ROOT.glob(pat))[:20]
        if found:
            print(f"\nglob {pat}: {len(found)}")
            for f in found[:10]:
                try:
                    txt = f.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue
                if TODAY in txt and "NIFTY" in txt.upper():
                    print(" ", f, "bytes", f.stat().st_size)

    # try session_calls API for today
    try:
        rows = sc.list_day_calls(sc.default_db_path(), day=TODAY) if hasattr(sc, "list_day_calls") else None
        print("list_day_calls", rows)
    except Exception as e:
        print("list_day_calls err", e)
    for name in dir(sc):
        if "day" in name.lower() or "today" in name.lower() or "list" in name.lower() or "load" in name.lower():
            print("sc.", name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
