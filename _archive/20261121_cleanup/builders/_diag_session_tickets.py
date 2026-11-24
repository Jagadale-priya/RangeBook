"""Dump recent fno_session.sqlite tickets for NIFTY/BN/SENSEX."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

p = Path(r"c:\Users\Priyanka\Agent\stock_signal_data\fno_session.sqlite")
con = sqlite3.connect(p)
con.row_factory = sqlite3.Row
cur = con.cursor()
print("tables:", [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")])
for t in [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")]:
    cols = [c[1] for c in cur.execute(f"PRAGMA table_info({t})")]
    n = cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    print(f"\n== {t} cols={cols} n={n}")
    try:
        rows = cur.execute(f"SELECT * FROM {t} ORDER BY rowid DESC LIMIT 30").fetchall()
    except Exception as e:
        print("err", e)
        continue
    for r in rows:
        d = dict(r)
        # truncate bulky fields
        for k, v in list(d.items()):
            if isinstance(v, str) and len(v) > 400:
                d[k] = v[:400] + "…"
        print(json.dumps(d, default=str)[:1200])
        print("---")
