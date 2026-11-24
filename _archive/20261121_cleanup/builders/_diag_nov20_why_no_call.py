"""Why Nov20 09:45 champion did not hit Calls / notify."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / "app"), str(ROOT / "app" / "fno")]
os.environ.setdefault("SUPPRESS_DUAL_LIST", "1")

import fno_live_config  # noqa: E402


def main() -> int:
    p = ROOT / "prod_live" / "holding_accurate" / "champion_plus" / "live_session_calls.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    rows = d.get("calls") or d.get("day_calls") or []
    if isinstance(d.get("by_day"), dict):
        rows = list(rows) + list(d["by_day"].get("2026-11-20") or [])
    print("suppress_dual_list", fno_live_config.suppress_dual_list())
    print("suppress_for_NIFTY", fno_live_config.suppress_dual_list_for("NIFTY"))
    print("ledger_updated", d.get("updated_at"))
    for r in rows:
        if str(r.get("day") or "")[:10] != "2026-11-20":
            continue
        print(
            "LEDGER",
            r.get("hm"),
            r.get("decision"),
            r.get("track"),
            r.get("source"),
            r.get("entry"),
            "live_fire=",
            r.get("live_fire"),
            "aft=",
            r.get("afternoon_thrust"),
        )
    # session_calls db if present
    for cand in [
        ROOT / "stock_signal_data" / "session_calls.db",
        ROOT / "app" / "stock_signal_data" / "session_calls.db",
        Path(os.environ.get("SESSION_CALLS_DB", "")),
    ]:
        if cand and cand.exists():
            import sqlite3

            con = sqlite3.connect(str(cand))
            con.row_factory = sqlite3.Row
            try:
                tabs = [r[0] for r in con.execute("select name from sqlite_master where type='table'")]
                print("DB", cand, "tables", tabs)
                for t in tabs:
                    if "call" in t.lower() or "session" in t.lower():
                        q = f"select * from {t} where cast(stock as text) like '%NIFTY%' order by rowid desc limit 8"
                        try:
                            for row in con.execute(q):
                                print("DBROW", dict(row))
                        except Exception as exc:
                            print("DB query skip", t, exc)
            finally:
                con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
