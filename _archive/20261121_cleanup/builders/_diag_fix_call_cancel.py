"""Verify same-side LTP drift no longer cancels; FIXED clips for 3 indices."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "app"))
sys.path.insert(0, str(ROOT / "app" / "fno"))
sys.path.insert(0, str(ROOT))

import fno_session_rules as fsrules
import fno_risk_engine as fre
import fno_live_config as cfg

# Simulate env after .env change (may already be loaded by process)
print(
    "flags",
    {
        "use_dual": cfg.use_dual_track(),
        "pre_dual": cfg.enable_pre_dual_single(),
        "stacked": cfg.enable_stacked_calls(),
    },
)

for sym, expect in (("NIFTY", 30.0), ("BANKNIFTY", 75.0), ("SENSEX", 100.0)):
    sl, t1, t2, _ = fre.clip_points(sym, 10000.0, atr=200.0)
    assert sl == expect and t1 == expect, (sym, sl, t1)
    print("clip_ok", sym, sl, t1)

ticket = fsrules.persist_new_ticket(
    None,
    decision="BUY",
    stop_loss=62000.0,
    target_1=62200.0,
    taken_at="2026-11-17T10:00:00+05:30",
    session_date_value="2026-11-17",
    entry=62100.0,
    readings={"track": "pre_dual_single", "good": True, "soft_gates": True, "source": "pre_dual_single"},
    symbol="BANKNIFTY",
)
assert ticket and ticket["status"] == "open"
# LTP drift same side — must keep
ticket2 = fsrules.persist_new_ticket(
    ticket,
    decision="BUY",
    stop_loss=62100.0,
    target_1=62300.0,
    taken_at="2026-11-17T10:01:00+05:30",
    session_date_value="2026-11-17",
    entry=62200.0,  # >0.51 drift
    readings={"track": "pre_dual_single", "good": True, "soft_gates": True, "source": "pre_dual_single"},
    symbol="BANKNIFTY",
)
assert ticket2 is ticket or (
    ticket2.get("entry") == 62100.0 and ticket2.get("status") == "open"
), ticket2
assert not any(
    str(h.get("status")) == "cancelled" for h in (ticket2.get("history") or [])
), ticket2.get("history")
print("no_cancel_on_drift_ok", ticket2.get("entry"), ticket2.get("tickets"))

# BN FINAL levels
from prod_live.logic import bn_final_live as bn
from prod_live.logic import sensex_final_live as sx

lv = bn.levels(62319.7, "BUY")
assert abs(lv["stop_loss"] - (62319.7 - 75)) < 0.01
assert abs(lv["target_1"] - (62319.7 + 75)) < 0.01
lv2 = sx.levels(82406.49, "BUY")
assert abs(lv2["stop_loss"] - (82406.49 - 100)) < 0.01
print("final_brackets_ok", lv, lv2)
print("PASS")
