"""Offline: afternoon thrust lists even when a suppressed dual ticket is open.

  python -u prod_live/tests/builders/_smoke_afternoon_thrust_board_replace.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [
    str(ROOT),
    str(ROOT / "app"),
    str(ROOT / "app" / "fno"),
    str(ROOT / "prod_live"),
]
os.environ["SUPPRESS_DUAL_LIST"] = "1"
os.environ["ENABLE_NIFTY_AFTERNOON_THRUST"] = "1"


def main() -> int:
    import fno_dual_modal_list as modal
    import fno_session_rules as fsrules
    import nifty_afternoon_thrust as nat

    fails = 0

    def ok(name: str, cond: bool, detail: str = "") -> None:
        nonlocal fails
        if not cond:
            fails += 1
        print(("PASS" if cond else "FAIL"), name, detail)

    open_dual = {
        "session_date": "2026-11-19",
        "decision": "BUY",
        "taken_at": "2026-11-19T09:45:00+05:30",
        "tickets": 1,
        "status": "open",
        "entry": 25400.0,
        "stop_loss": 25370.0,
        "target_1": 25430.0,
        "p_t1": 0.7,
        "readings": {
            "dual_track": True,
            "track": "champion",
            "source": "champion",
            "accuracy_label": "champion dual",
        },
        "history": [],
    }
    ok("open dual blocks board", modal._open(open_dual) is True)
    ok("dual family detect", modal._is_dual_family_ticket(open_dual) is True)

    payload = {
        "decision": "BUY",
        "track": nat.TRACK,
        "source": nat.SOURCE,
        "afternoon_thrust": True,
        "entry": 25436.55,
        "stop_loss": 25406.55,
        "target_1": 25466.55,
        "p_t1": 0.70,
        "hm": "14:00",
        "accuracy_label": nat.ACCURACY_LABEL,
        "accuracy_tags": [],
    }
    result = {"fno_analysis": {"dual_track_call": payload}}

    # Persist path: thrust must replace suppressed dual open ticket
    readings: dict = {}
    nat.stamp_readings(readings, payload)
    replaced = fsrules.persist_new_ticket(
        open_dual,
        decision="BUY",
        stop_loss=payload["stop_loss"],
        target_1=payload["target_1"],
        taken_at="2026-11-19T14:00:00+05:30",
        session_date_value="2026-11-19",
        entry=payload["entry"],
        p_t1=payload["p_t1"],
        readings=readings,
        symbol="NIFTY",
    )
    live = fsrules.open_ticket(replaced)
    ok("persist replaced open dual", live is not None, str((live or {}).get("readings")))
    ok(
        "persist live is thrust",
        bool(live and (live.get("readings") or {}).get("afternoon_thrust")),
        str((live or {}).get("readings")),
    )
    ok(
        "persist entry is thrust",
        live is not None and abs(float(live.get("entry")) - 25436.55) < 0.01,
        str((live or {}).get("entry")),
    )

    # fill_from_channels must not early-return on suppressed dual open
    ticket = modal.fill_from_channels(
        result,
        symbol="NIFTY",
        session_ticket=dict(open_dual),
        bars=None,
        live_quote=None,
        db_path=None,
        asof="2026-11-19T14:00:00+05:30",
    )
    live2 = fsrules.open_ticket(ticket)
    ok("fill_from_channels listed", live2 is not None, str(ticket))
    ok(
        "fill source afternoon thrust",
        bool(
            live2
            and (
                (live2.get("readings") or {}).get("afternoon_thrust")
                or (live2.get("readings") or {}).get("source") == nat.SOURCE
            )
        ),
        str((live2 or {}).get("readings")),
    )

    # Champ must not promote suppressed 15m champion while thrust present
    champ_result = {
        "fno_analysis": {
            "dual_track_call": payload,
            "champ_plus_live": {
                "added": [
                    {
                        "decision": "BUY",
                        "track": "champion",
                        "entry": 25400.0,
                        "stop_loss": 25370.0,
                        "target_1": 25430.0,
                        "hm": "09:45",
                        "day": "2026-11-19",
                        "p_t1": 0.7,
                    }
                ]
            },
        }
    }
    ticket3 = modal.fill_from_channels(
        champ_result,
        symbol="NIFTY",
        session_ticket=None,
        bars=None,
        live_quote=None,
        db_path=None,
        asof="2026-11-19T14:00:00+05:30",
    )
    live3 = fsrules.open_ticket(ticket3)
    ok("thrust preferred over champ dual add", live3 is not None)
    ok(
        "prefer thrust not champion",
        bool(
            live3
            and (
                (live3.get("readings") or {}).get("afternoon_thrust")
                or (live3.get("readings") or {}).get("track") == "confident"
            )
        ),
        str((live3 or {}).get("readings")),
    )

    print("FAILS", fails)
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
