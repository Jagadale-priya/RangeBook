"""NIFTY session_calls 16-18 Nov vs current live CHAMP_PLUS path."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

DB = Path("stock_signal_data/knowledge.db")
DAYS = ("2026-11-16", "2026-11-17", "2026-11-18")


def main() -> None:
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        """
        SELECT id, stock, session_date, ticket_n, decision, status, entry,
               stop_loss, target_1, p_t1, regime, taken_at, closed_at,
               status_plain, payload_json
        FROM session_calls
        WHERE stock='NIFTY' AND product='fno'
          AND session_date BETWEEN '2026-11-16' AND '2026-11-18'
        ORDER BY session_date, ticket_n, id
        """
    ).fetchall()
    print(f"NIFTY session_calls rows: {len(rows)}")
    by_day = {d: [] for d in DAYS}
    for r in rows:
        payload = {}
        try:
            payload = json.loads(r["payload_json"] or "{}")
        except Exception:
            payload = {}
        readings = payload.get("readings") or payload.get("live_readings") or {}
        track = (
            readings.get("track")
            or readings.get("source")
            or r["regime"]
            or payload.get("track")
            or payload.get("source")
            or "—"
        )
        label = readings.get("accuracy_label") or payload.get("accuracy_label") or ""
        accurate = readings.get("accurate_tag") or payload.get("accurate_tag") or ""
        dual_suppressed = bool(
            (payload.get("fno_analysis") or {}).get("dual_list_suppressed")
            or readings.get("dual_list_suppressed")
        )
        champish = any(
            x in str(track).lower() or x in str(label).lower() or x in str(accurate).lower()
            for x in ("champ", "dual10", "crown", "good_prod", "proven_research")
        )
        dualish = str(track).lower() in ("proven_100", "champion", "proven")
        item = {
            "day": r["session_date"],
            "ticket_n": r["ticket_n"],
            "decision": r["decision"],
            "status": r["status"],
            "entry": r["entry"],
            "sl": r["stop_loss"],
            "t1": r["target_1"],
            "p_t1": r["p_t1"],
            "taken_at": r["taken_at"],
            "track": track,
            "label": label,
            "accurate_tag": accurate,
            "dualish": dualish,
            "champish": champish,
            "dual_suppressed_flag": dual_suppressed,
            "sl_pts": abs(float(r["entry"] or 0) - float(r["stop_loss"] or 0))
            if r["entry"] and r["stop_loss"]
            else None,
            "t_pts": abs(float(r["target_1"] or 0) - float(r["entry"] or 0))
            if r["entry"] and r["target_1"]
            else None,
        }
        by_day[r["session_date"]].append(item)
        print(
            f"{item['day']} #{item['ticket_n']} {item['decision']:4} "
            f"status={item['status']:14} track={item['track']!s:18} "
            f"±SL={item['sl_pts']} ±T={item['t_pts']} "
            f"taken={item['taken_at']} label={item['label'][:40]}"
        )

    print()
    print("=== summary by day ===")
    total = 0
    keep_under_new = 0
    for d in DAYS:
        items = by_day.get(d) or []
        # count listed (not cancelled idle)
        listed = [
            x
            for x in items
            if str(x["decision"]).upper() in ("BUY", "SELL")
            and str(x["status"]).lower() not in ("idle",)
        ]
        # under NEW live logic: dual proven/champion would NOT list;
        # CHAMP_PLUS fill (±30) would.
        would_list = []
        for x in listed:
            if x["dualish"] and not x["champish"]:
                # dual-first ticket — suppressed under new logic
                continue
            # Cap4 CHAMP brackets ~30 or champ/fill tracks
            if x["champish"] or (
                x["sl_pts"] is not None
                and abs(x["sl_pts"] - 30) < 0.6
                and abs((x["t_pts"] or 0) - 30) < 0.6
            ):
                would_list.append(x)
            elif not x["dualish"]:
                would_list.append(x)
        print(f"{d}: db_listed={len(listed)} · would_list_under_CHAMP_PLUS≈{len(would_list)}")
        for x in listed:
            flag = "KEEP" if x in would_list else "SUPPRESS(dual)"
            print(
                f"  [{flag}] #{x['ticket_n']} {x['decision']} track={x['track']} "
                f"status={x['status']} SL/T={x['sl_pts']}/{x['t_pts']}"
            )
        total += len(listed)
        keep_under_new += len(would_list)

    # Also CHAMP live ledger
    live_path = Path("prod_live/holding_accurate/champion_plus/live_session_calls.json")
    live = json.loads(live_path.read_text(encoding="utf-8"))
    if isinstance(live, dict):
        live = live.get("calls") or []
    live_hit = [r for r in live if str(r.get("day") or "")[:10] in DAYS]
    print()
    print(f"CHAMP_PLUS live ledger in window: {len(live_hit)}")
    for r in sorted(live_hit, key=lambda x: (str(x.get("day")), str(x.get("hm") or ""))):
        print(
            f"  {r.get('day')} {r.get('hm')} {str(r.get('decision') or r.get('side')).upper()} "
            f"track={r.get('track')} win={r.get('win')}"
        )
    print()
    print(f"DB listed total {total} · under current live logic keep≈{keep_under_new}")
    print(f"CHAMP ledger calls in window: {len(live_hit)}")


if __name__ == "__main__":
    main()
