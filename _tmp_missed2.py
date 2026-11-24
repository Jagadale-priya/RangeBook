import json
import sqlite3
from pathlib import Path

DB = Path(r"c:\Users\Priyanka\Agent\stock_signal_data\knowledge.db")
TODAY = "2026-11-16"
con = sqlite3.connect(str(DB))
con.row_factory = sqlite3.Row

print("=== desk_notifications cols ===")
cols = [r[1] for r in con.execute("PRAGMA table_info(desk_notifications)")]
print(cols)
rows = con.execute("SELECT * FROM desk_notifications ORDER BY rowid DESC LIMIT 30").fetchall()
for r in rows:
    d = dict(r)
    s = json.dumps(d, default=str)
    if TODAY not in s:
        continue
    slim = {k: d.get(k) for k in d if k not in ("payload_json", "body", "detail_json")}
    print(slim)
    for k in ("payload_json", "body", "message", "detail_json", "title"):
        if d.get(k):
            try:
                p = json.loads(d[k]) if isinstance(d[k], str) and str(d[k]).startswith("{") else d[k]
            except Exception:
                p = d[k]
            print(" ", k, str(p)[:300])

print("\n=== session_calls BN full ===")
cols = [r[1] for r in con.execute("PRAGMA table_info(session_calls)")]
print("cols", cols)
for r in con.execute(
    "SELECT * FROM session_calls WHERE session_date=? AND stock='BANKNIFTY'",
    (TODAY,),
):
    d = dict(r)
    print({k: d[k] for k in d if k != "payload_json"})
    pj = d.get("payload_json")
    if pj:
        p = json.loads(pj)
        print(" keys", list(p.keys())[:40])
        for k in (
            "decision",
            "status",
            "taken_at",
            "closed_at",
            "cancel_reason",
            "closed_reason",
            "note",
            "source",
            "track",
            "readings",
        ):
            if k in p:
                v = p[k]
                if k == "readings" and isinstance(v, dict):
                    print(" readings", {kk: v.get(kk) for kk in list(v)[:25]})
                else:
                    print(" ", k, v)
        hist = p.get("history") or []
        print(" history n", len(hist))
        for h in hist[-3:]:
            if isinstance(h, dict):
                print("  hist", {k: h.get(k) for k in ("decision", "status", "entry", "taken_at", "closed_at", "note")})

print("\n=== fno_live_archive today ===")
cols = [r[1] for r in con.execute("PRAGMA table_info(fno_live_archive)")]
print(cols)
for r in con.execute(
    """SELECT stock, bar_bucket, ticket_n, decision, call_status, price, entry, favor_pts
       FROM fno_live_archive WHERE session_date=? AND stock IN ('NIFTY','BANKNIFTY','SENSEX')
       ORDER BY bar_bucket""",
    (TODAY,),
):
    print(dict(r))

print("\n=== fno_point_journal today ===")
try:
    for r in con.execute(
        """SELECT stock, bar_ts, decision, entry, status, favor_points, p_t1
           FROM fno_point_journal WHERE session_date=? AND stock IN ('NIFTY','BANKNIFTY','SENSEX')
           ORDER BY bar_ts""",
        (TODAY,),
    ):
        print(dict(r))
except Exception as e:
    print(e)
