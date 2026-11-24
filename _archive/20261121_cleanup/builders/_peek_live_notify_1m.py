"""Peek knowledge.db NIFTY session + desk notifications last 1m."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parents[3] / "stock_signal_data" / "knowledge.db"
START = "2026-10-20"


def main() -> int:
    con = sqlite3.connect(str(DB))
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    cols = [r[1] for r in cur.execute("PRAGMA table_info(session_calls)").fetchall()]
    print("session_calls", cols)
    rows = cur.execute("SELECT * FROM session_calls ORDER BY rowid DESC LIMIT 8").fetchall()
    for r in rows:
        d = dict(r)
        print({k: d.get(k) for k in cols[:12]})

    ncols = [r[1] for r in cur.execute("PRAGMA table_info(desk_notifications)").fetchall()]
    print("desk_notifications", ncols)
    nifty = []
    for r in cur.execute("SELECT * FROM desk_notifications ORDER BY rowid DESC LIMIT 800"):
        d = dict(r)
        blob = json.dumps(d, default=str).upper()
        if "NIFTY" not in blob:
            continue
        ts = str(d.get("created_at") or d.get("ts") or d.get("at") or "")
        day = ts[:10]
        if day and day < START:
            continue
        nifty.append(d)
    print("nifty notifs since", START, "=", len(nifty))
    for d in nifty[:25]:
        print(
            {
                "created_at": d.get("created_at") or d.get("ts"),
                "kind": d.get("kind"),
                "decision": d.get("decision"),
                "title": (d.get("title") or "")[:60],
                "message": (d.get("message") or "")[:80],
                "dedupe_key": d.get("dedupe_key"),
            }
        )

    # session_calls NIFTY in window
    sc = []
    for r in cur.execute("SELECT * FROM session_calls ORDER BY rowid DESC LIMIT 2000"):
        d = dict(r)
        blob = json.dumps(d, default=str).upper()
        if "NIFTY" not in blob:
            continue
        day = str(d.get("session_date") or d.get("day") or d.get("taken_at") or "")[:10]
        if day and day < START:
            continue
        sc.append(d)
    print("nifty session_calls since", START, "=", len(sc))
    for d in sc[:30]:
        print(
            {
                "day": d.get("session_date") or d.get("day") or d.get("taken_at"),
                "stock": d.get("stock") or d.get("symbol"),
                "decision": d.get("decision"),
                "taken_at": d.get("taken_at"),
                "entry": d.get("entry"),
                "source": d.get("source"),
            }
        )
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
