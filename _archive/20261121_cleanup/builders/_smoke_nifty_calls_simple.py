"""Smoke: NIFTY Calls = thrust-only, merge same-time, never skip later fire.

  python -u prod_live/tests/builders/_smoke_nifty_calls_simple.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / "app"), str(ROOT / "app" / "fno")]
os.environ["SUPPRESS_DUAL_LIST"] = "0"  # even if off, NIFTY dual still never lists
os.environ["ENABLE_NIFTY_AFTERNOON_THRUST"] = "0"  # afternoon must not block
os.environ["ENABLE_NIFTY_MORNING_STRONG_THRUST"] = "1"
os.environ["ENABLE_P2F_LIVE_ACCURATE"] = "1"


def main() -> int:
    import fno_dual_modal_list as modal
    import fno_live_config
    import fno_session_rules as fsrules
    import nifty_afternoon_thrust as nat
    import nifty_calls_live as ncl
    import nifty_morning_strong_thrust as nmst

    fails = 0

    def ok(name: str, cond: bool, detail: str = "") -> None:
        nonlocal fails
        if not cond:
            fails += 1
        print(("PASS" if cond else "FAIL"), name, detail)

    ok("nifty dual never lists", fno_live_config.suppress_dual_list_for("NIFTY") is True)
    ok("sensex not forced", fno_live_config.suppress_dual_list_for("SENSEX") in (True, False))

    morning = {
        "decision": "BUY",
        "track": nmst.TRACK,
        "source": nmst.SOURCE,
        "morning_strong_thrust": True,
        "afternoon_thrust": False,
        "entry": 25500.0,
        "stop_loss": 25470.0,
        "target_1": 25530.0,
        "p_t1": 0.8,
        "hm": "09:50",
        "accuracy_label": nmst.ACCURACY_LABEL,
        "accuracy_tags": [],
    }
    afternoon = {
        "decision": "BUY",
        "track": nat.TRACK,
        "source": nat.SOURCE,
        "afternoon_thrust": True,
        "morning_strong_thrust": False,
        "entry": 25540.0,
        "stop_loss": 25510.0,
        "target_1": 25570.0,
        "p_t1": 0.7,
        "hm": "14:00",
        "accuracy_label": nat.ACCURACY_LABEL,
        "accuracy_tags": [],
    }

    # Afternoon OFF: payloads ignored — must not block morning or CHAMP
    ok("afternoon disabled", ncl._afternoon_enabled() is False)
    only_m = ncl.extract_payloads(
        {
            "nifty_list_payloads": [morning, afternoon],
            "nifty_morning_strong_thrust_payload": morning,
            "nifty_afternoon_thrust_payload": afternoon,
        }
    )
    ok("extract skips afternoon when off", len(only_m) == 1 and only_m[0].get("morning_strong_thrust"), str(only_m))

    morning_only = {
        "fno_analysis": {
            "dual_track_call": morning,
            "nifty_list_payloads": [morning],
            "nifty_morning_strong_thrust_payload": morning,
        },
        "nifty_list_payloads": [morning],
        "nifty_morning_strong_thrust_payload": morning,
    }
    t1 = modal.fill_from_channels(
        morning_only,
        symbol="NIFTY",
        session_ticket=None,
        asof="2026-11-20T09:50:00+05:30",
    )
    live1 = fsrules.open_ticket(t1)
    ok("morning L5 listed", live1 is not None and abs(float(live1["entry"]) - 25500) < 0.01)

    # Distinct CHAMP_PLUS fire must list even while morning is open (no blocker)
    champ_after = {
        "fno_analysis": {
            "champ_plus_live": {
                "added": [
                    {
                        "decision": "BUY",
                        "track": "dual10m",
                        "entry": 25580.0,
                        "stop_loss": 25550.0,
                        "target_1": 25610.0,
                        "hm": "11:00",
                        "day": "2026-11-20",
                        "p_t1": 0.75,
                        "accuracy_label": "CHAMP_PLUS_T30SL30_CAP6",
                        "tags": ["CHAMP_PLUS_T30SL30_CAP6", "ACC_WIDE_P92_P2F", "ACC_RANGE_91_100"],
                    }
                ]
            }
        }
    }
    t2 = modal.fill_from_channels(
        champ_after,
        symbol="NIFTY",
        session_ticket=t1,
        asof="2026-11-20T11:00:00+05:30",
    )
    live2 = fsrules.open_ticket(t2)
    ok("champ not blocked by morning", live2 is not None)
    ok(
        "champ is open now",
        live2 is not None and abs(float(live2["entry"]) - 25580) < 0.01,
        str((live2 or {}).get("entry")),
    )
    hist = (t2 or {}).get("history") or []
    ok("morning archived when champ lists", any(h.get("status") == "cancelled" for h in hist), str(len(hist)))
    tags = (live2.get("readings") or {}).get("accuracy_tags") or [] if live2 else []
    ok("P2F/CHAMP tags combined", any("P2F" in str(t) or "CHAMP" in str(t) for t in tags), str(tags))

    # 15m champion dual still must NOT list; CHAMP_PLUS dual10m SHOULD list
    champ_dual = {
        "fno_analysis": {
            "champ_plus_live": {
                "added": [
                    {
                        "decision": "BUY",
                        "track": "champion",
                        "entry": 25524.35,
                        "stop_loss": 25494.35,
                        "target_1": 25554.35,
                        "hm": "09:45",
                        "day": "2026-11-20",
                        "p_t1": 0.6,
                    }
                ]
            }
        }
    }
    t3 = modal.fill_from_channels(
        champ_dual, symbol="NIFTY", session_ticket=None, asof="2026-11-20T09:45:00+05:30"
    )
    ok("no 15m champion dual on nifty board", fsrules.open_ticket(t3) is None, str(t3))

    champ_plus = {
        "fno_analysis": {
            "champ_plus_live": {
                "added": [
                    {
                        "decision": "BUY",
                        "track": "dual10m",
                        "entry": 25530.0,
                        "stop_loss": 25500.0,
                        "target_1": 25560.0,
                        "hm": "10:00",
                        "day": "2026-11-20",
                        "p_t1": 0.7,
                        "accuracy_label": "CHAMP_PLUS · 10m dual",
                    }
                ]
            }
        }
    }
    t4 = modal.fill_from_channels(
        champ_plus, symbol="NIFTY", session_ticket=None, asof="2026-11-20T10:00:00+05:30"
    )
    live4 = fsrules.open_ticket(t4)
    ok("CHAMP_PLUS dual10m lists", live4 is not None, str((live4 or {}).get("readings")))

    print("FAILS", fails)
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
