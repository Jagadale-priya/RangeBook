import json
import sqlite3

con = sqlite3.connect(r"c:\Users\Priyanka\Agent\stock_signal_data\knowledge.db")
con.row_factory = sqlite3.Row
rows = con.execute(
    "SELECT * FROM session_calls WHERE stock='NIFTY' AND session_date='2026-11-18' ORDER BY id"
).fetchall()
print("n", len(rows))
for r in rows:
    d = dict(r)
    payload = json.loads(d["payload_json"] or "{}")
    readings = payload.get("readings") or {}
    print("==== ticket", d["ticket_n"], d["decision"], d["status"], d["status_plain"])
    print("taken", d["taken_at"], "closed", d["closed_at"])
    print("entry", d["entry"], "SL", d["stop_loss"], "T1", d["target_1"], "p_t1", d["p_t1"], "regime", d["regime"])
    for k in (
        "source",
        "track",
        "dual_track",
        "accuracy_label",
        "channel",
        "book",
        "list_priority",
        "clean",
        "headline",
        "candle_patterns",
    ):
        if k in payload:
            print(" payload.", k, "=", payload.get(k))
        if k in readings:
            print(" readings.", k, "=", readings.get(k))
    print(" readings keys", list(readings.keys())[:40])
    for k in (
        "accuracy_label",
        "track",
        "source",
        "dual_track",
        "proven_100",
        "champion",
        "baseline",
        "stack",
        "headline",
        "tags",
        "accuracy_tags",
        "model_view",
    ):
        if k in readings:
            print(" readings.", k, "=", readings.get(k))
    # dump small payload fields
    for k, v in payload.items():
        if k in ("readings", "history", "option", "contracts"):
            continue
        if isinstance(v, (str, int, float, bool)) or v is None:
            print(" payload.", k, "=", v)
