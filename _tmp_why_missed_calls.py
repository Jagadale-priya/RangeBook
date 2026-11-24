"""Why missed BUY/SELL today — inspect dual, tickets, indications."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = ROOT / "stock_signal_data" / "knowledge.db"
TODAY = datetime.now().strftime("%Y-%m-%d")
con = sqlite3.connect(str(DB))
con.row_factory = sqlite3.Row

print("now", datetime.now().isoformat(), "today", TODAY)

print("\n=== session_calls today ===")
for r in con.execute(
    """SELECT stock, decision, status, entry, p_t1, ticket_n, stop_loss, target_1
       FROM session_calls WHERE session_date=? ORDER BY stock, ticket_n""",
    (TODAY,),
):
    print(dict(r))
n = con.execute("SELECT COUNT(*) FROM session_calls WHERE session_date=?", (TODAY,)).fetchone()[0]
print("n=", n)

print("\n=== latest analysis_snapshots today ===")
for sym in ("NIFTY", "BANKNIFTY", "SENSEX"):
    rows = con.execute(
        """SELECT id, analysis_mode, decision, confidence, created_at
           FROM analysis_snapshots WHERE stock=? AND as_of_date=? AND product='fno'
           ORDER BY created_at DESC LIMIT 3""",
        (sym, TODAY),
    ).fetchall()
    print(sym, [dict(x) for x in rows])

print("\n=== latest full payload dual/call bits ===")
for sym in ("NIFTY", "BANKNIFTY", "SENSEX"):
    row = con.execute(
        """SELECT id, created_at, payload_json FROM analysis_snapshots
           WHERE stock=? AND as_of_date=? AND product='fno'
           ORDER BY created_at DESC LIMIT 1""",
        (sym, TODAY),
    ).fetchone()
    if not row:
        print(sym, "none")
        continue
    p = json.loads(row["payload_json"] or "{}")
    fa = p.get("fno_analysis") or {}
    print(f"\n## {sym} snap {row['id']} @ {row['created_at']}")
    print("  decision", p.get("decision"), "summary:", str(p.get("summary") or fa.get("headline") or "")[:180])
    print("  session_tickets", len(p.get("session_tickets") or []), "active", p.get("active_call"))
    # desk alerts
    print("  desk_alerts", (fa.get("desk_alerts") or [])[:6])
    # look for dual anywhere
    blob = json.dumps(fa)
    for key in ("dual_call", "live_dual", "call_live", "bn_final_live", "sensex_final_live", "champ_plus_live", "final_sensex_fno", "final_bn_fno", "final_nifty_fno"):
        v = fa.get(key)
        if isinstance(v, dict):
            print(f"  {key}:", {k: v.get(k) for k in list(v)[:18]})
    lc = fa.get("live_context") or {}
    sm = lc.get("session_model") or {}
    if sm:
        print("  session_model:", {k: sm.get(k) for k in ("decision", "p_t1", "buy_p", "should_trade", "side", "first_clip")})
        al = sm.get("alignment") or {}
        print("  alignment:", al.get("note"), "feats first_break", (sm.get("features") or {}).get("first_break"), "or_ext", (sm.get("features") or {}).get("or_ext"))
    # search dual_track in whole payload textually
    if "dual" in blob.lower() or "champion" in blob.lower() or "proven" in blob.lower():
        # find nested
        def walk(obj, path=""):
            if isinstance(obj, dict):
                if any(k in obj for k in ("track", "dual_track", "first_break")) and ("decision" in obj or "p_t1" in obj):
                    print("  nest", path, {k: obj.get(k) for k in ("decision", "track", "p_t1", "hm", "first_break", "or_ext", "hold_reason", "reason") if k in obj})
                for k, v in obj.items():
                    if k in ("features", "bars_5m", "bars_15m"):
                        continue
                    walk(v, path + "/" + k)
            elif isinstance(obj, list) and len(obj) < 20:
                for i, v in enumerate(obj[:10]):
                    walk(v, path + f"[{i}]")
        walk(fa, "fa")

print("\n=== fno_indications latest ===")
for sym in ("NIFTY", "BANKNIFTY", "SENSEX"):
    r = con.execute(
        "SELECT bar_ts, updated_at, payload_json FROM fno_indications WHERE stock=? AND session_date=? ORDER BY updated_at DESC LIMIT 1",
        (sym, TODAY),
    ).fetchone()
    if not r:
        print(sym, "no ind")
        continue
    p = json.loads(r["payload_json"] or "{}")
    print(sym, "bar", r["bar_ts"], "upd", r["updated_at"], "keys", list(p.keys())[:20])

print("\n=== FINAL live ledgers ===")
for path in (
    ROOT / "prod_live/holding_accurate/champion_plus/live_session_calls.json",
    ROOT / "prod_live/holding_accurate/banknifty_final/live_session_calls.json",
    ROOT / "prod_live/holding_accurate/sensex_final/live_session_calls.json",
):
    if not path.is_file():
        continue
    raw = json.loads(path.read_text(encoding="utf-8"))
    calls = raw.get("calls") or []
    today = [c for c in calls if str(c.get("day") or "")[:10] == TODAY]
    print(path.parent.name, "today", today)

print("\n=== overlay / classic / daily_fill today ===")
for table in ("overlay_indication_calls", "classic_15m_calls", "daily_fill_calls", "crown_5m_calls", "move_capture_calls"):
    try:
        rows = con.execute(
            f"SELECT stock, decision, status, entry, bar_time FROM {table} WHERE session_date=? AND stock IN ('NIFTY','BANKNIFTY','SENSEX')",
            (TODAY,),
        ).fetchall()
        print(table, [dict(x) for x in rows])
    except Exception as e:
        print(table, e)
