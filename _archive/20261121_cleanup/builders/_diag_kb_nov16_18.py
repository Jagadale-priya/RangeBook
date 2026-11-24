import sqlite3
from pathlib import Path

p = Path("stock_signal_data/knowledge.db")
con = sqlite3.connect(p)
cur = con.cursor()
tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print("tables", tables)
for t in tables:
    tl = t.lower()
    if any(x in tl for x in ("session", "call", "ticket", "fno", "live")):
        cols = [r[1] for r in cur.execute(f"PRAGMA table_info({t})").fetchall()]
        print(t, cols)
        try:
            n = cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            print("  n=", n)
            # sample recent
            rows = cur.execute(f"SELECT * FROM {t} ORDER BY rowid DESC LIMIT 3").fetchall()
            for r in rows:
                print("  ", r[:12] if isinstance(r, tuple) else r)
        except Exception as exc:
            print("  err", exc)

# also search any text for 2026-11-16..18
for t in tables:
    cols = [r[1] for r in cur.execute(f"PRAGMA table_info({t})").fetchall()]
    text_cols = [c for c in cols if c.lower() in ("day", "date", "session_date", "taken_at", "symbol", "stock", "payload", "json", "data")]
    if not text_cols:
        continue
    for c in text_cols:
        try:
            q = f"SELECT COUNT(*) FROM {t} WHERE CAST({c} AS TEXT) LIKE '%2026-11-16%' OR CAST({c} AS TEXT) LIKE '%2026-11-17%' OR CAST({c} AS TEXT) LIKE '%2026-11-18%'"
            n = cur.execute(q).fetchone()[0]
            if n:
                print(f"HIT {t}.{c} n={n}")
                rows = cur.execute(
                    f"SELECT * FROM {t} WHERE CAST({c} AS TEXT) LIKE '%2026-11-16%' OR CAST({c} AS TEXT) LIKE '%2026-11-17%' OR CAST({c} AS TEXT) LIKE '%2026-11-18%' LIMIT 10"
                ).fetchall()
                for r in rows:
                    print(" ", r[:8] if isinstance(r, tuple) else r)
        except Exception:
            pass
