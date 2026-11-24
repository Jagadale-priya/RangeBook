"""NIFTY session_calls + dual config snapshot."""
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

con = sqlite3.connect(ROOT / "stock_signal_data" / "knowledge.db")
con.row_factory = sqlite3.Row
rows = con.execute(
    """
    SELECT stock, session_date, ticket_n, decision, status, entry, stop_loss, target_1,
           p_t1, taken_at, closed_at, substr(payload_json,1,400) AS payload
    FROM session_calls
    WHERE session_date >= '2026-11-14'
    ORDER BY id DESC
    """
).fetchall()
print("session_calls since 11-14:", len(rows))
for r in rows:
    print(dict(r))
    print("---")

import fno_live_config as cfg

print(
    "config",
    {
        "use_dual": cfg.use_dual_track(),
        "stacked": cfg.enable_stacked_calls(),
        "pre_dual_soft": getattr(cfg, "pre_dual_soft_gates", lambda: None)(),
    },
)

# pack presence
from pathlib import Path as P
for sym, paths in {
    "NIFTY": [
        "stock_signal_data/fno_validate/research/nifty_side_models",
    ],
    "BANKNIFTY": [
        "stock_signal_data/fno_validate/research/banknifty_side_models",
    ],
    "SENSEX": [
        "stock_signal_data/fno_validate/research/sensex_side_models",
    ],
}.items():
    d = ROOT / paths[0]
    print(sym, "dir", d.is_dir(), "pkls", sorted(p.name for p in d.glob("*.pkl"))[:12] if d.is_dir() else [])
