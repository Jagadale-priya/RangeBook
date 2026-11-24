"""NIFTY F&O Cap6-relevant DB tickets/notifies last 1m (exclude scalper)."""
from __future__ import annotations

import json
import sqlite3
from collections import Counter
from pathlib import Path

DB = Path(__file__).resolve().parents[3] / "stock_signal_data" / "knowledge.db"
START = "2026-10-20"


def main() -> int:
    con = sqlite3.connect(str(DB))
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    tickets = []
    for r in cur.execute(
        "SELECT * FROM session_calls WHERE stock='NIFTY' AND product='fno' "
        "AND session_date >= ? ORDER BY session_date, taken_at",
        (START,),
    ):
        tickets.append(dict(r))
    print(f"NIFTY fno session_calls since {START}: {len(tickets)}")
    by_status = Counter(str(t.get("status") or "") for t in tickets)
    print("status", dict(by_status))
    for t in tickets:
        pay = {}
        try:
            pay = json.loads(t.get("payload_json") or "{}")
        except Exception:
            pass
        readings = (pay.get("readings") or {}) if isinstance(pay, dict) else {}
        tags = readings.get("accuracy_tags") or readings.get("tags") or pay.get("tags") or []
        print(
            {
                "day": t.get("session_date"),
                "decision": t.get("decision"),
                "status": t.get("status"),
                "entry": t.get("entry"),
                "taken_at": str(t.get("taken_at") or "")[:19],
                "tags": tags[:6] if isinstance(tags, list) else tags,
                "champ": bool(readings.get("champ_plus")) if isinstance(readings, dict) else False,
            }
        )

    notifs = []
    for r in cur.execute(
        "SELECT * FROM desk_notifications WHERE stock='NIFTY' AND created_at >= ? "
        "ORDER BY created_at",
        (START,),
    ):
        d = dict(r)
        kind = str(d.get("kind") or "")
        if kind.startswith("scalper"):
            continue
        notifs.append(d)
    print(f"\nNIFTY non-scalper notifies since {START}: {len(notifs)}")
    print("kinds", dict(Counter(str(n.get("kind") or "") for n in notifs)))
    for n in notifs[:40]:
        print(
            {
                "at": str(n.get("created_at") or "")[:19],
                "kind": n.get("kind"),
                "decision": n.get("decision"),
                "title": (n.get("title") or "")[:70],
                "entry": n.get("entry"),
            }
        )
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
