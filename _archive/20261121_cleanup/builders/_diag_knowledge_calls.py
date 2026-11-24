"""Dump recent session_calls + overlay indications from knowledge DB."""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "app"))
sys.path.insert(0, str(ROOT / "app" / "legacy"))
sys.path.insert(0, str(ROOT / "app" / "fno"))

import knowledge_db  # noqa: E402

p = knowledge_db.ensure_db_dir()
print("db", p)
# knowledge_db.ensure_db_dir may return dir; find sqlite
cands = []
pp = Path(p)
if pp.is_file():
    cands = [pp]
else:
    cands = list(pp.glob("*.sqlite")) + list(pp.glob("*.db"))
    # also common paths
    for extra in [
        ROOT / "stock_signal_data" / "knowledge.db",
        ROOT / "stock_signal_data" / "knowledge.sqlite",
        Path(knowledge_db.default_db_path()) if hasattr(knowledge_db, "default_db_path") else None,
    ]:
        if extra and Path(extra).is_file():
            cands.append(Path(extra))
print("cands", cands)
db_file = None
for c in cands:
    try:
        con = sqlite3.connect(c)
        tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        if any(t in tables for t in ("session_calls", "overlay_indication_calls")):
            db_file = c
            print("using", c, "tables", tables)
            break
        con.close()
    except Exception as e:
        print("skip", c, e)

if not db_file:
    raise SystemExit("no db")

con = sqlite3.connect(db_file)
con.row_factory = sqlite3.Row
cur = con.cursor()
tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")]
print("tables", tables)

for t in tables:
    if any(x in t for x in ("session", "overlay", "notif", "call")):
        n = cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"\n== {t} n={n}")
        rows = cur.execute(f"SELECT * FROM {t} ORDER BY rowid DESC LIMIT 40").fetchall()
        for r in rows:
            d = dict(r)
            for k, v in list(d.items()):
                if isinstance(v, str) and len(v) > 600:
                    d[k] = v[:600] + "…"
            # filter recent-ish
            day = str(d.get("session_date") or d.get("taken_at") or d.get("created_at") or "")
            if day and day[:10] < "2026-11-10":
                continue
            print(json.dumps(d, default=str)[:1600])
            print("---")
