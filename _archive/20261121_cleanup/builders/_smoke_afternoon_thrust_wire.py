"""Offline smoke: afternoon confident thrust live wire (no Kite).

  python -u prod_live/tests/builders/_smoke_afternoon_thrust_wire.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [
    str(ROOT),
    str(ROOT / "app"),
    str(ROOT / "app" / "fno"),
    str(ROOT / "prod_live"),
]


def main() -> int:
    import fno_live_config
    import nifty_afternoon_thrust as nat
    import fno_dual_modal_list as modal
    from prod_live.logic.champ_plus_engine import session_candidate_from_dual

    fails = 0

    def ok(name: str, cond: bool, detail: str = "") -> None:
        nonlocal fails
        if not cond:
            fails += 1
        print(("PASS" if cond else "FAIL"), name, detail)

    ok("flag default ON", fno_live_config.enable_nifty_afternoon_thrust())
    ok(
        "suppress dual does not block thrust",
        nat.dual_blocks_thrust(
            {"decision": "BUY", "track": "champion"}, suppress_dual_list=True
        )
        is False,
    )
    ok(
        "listing dual blocks thrust",
        nat.dual_blocks_thrust(
            {"decision": "BUY", "track": "champion"}, suppress_dual_list=False
        )
        is True,
    )

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
        "accuracy_tags": [
            {
                "code": nat.TRACK,
                "label": nat.ACCURACY_LABEL,
                "expected_hit_pct": 92.3,
                "tone": "research",
                "priority": 70,
            }
        ],
        "uplift_from_13": 59.2,
    }
    readings: dict = {}
    nat.stamp_readings(readings, payload)
    ok("readings track confident", readings.get("track") == "confident")
    ok("readings source thrust", readings.get("source") == nat.SOURCE)
    ok("readings priority 70", readings.get("priority") == 70)
    ok("readings afternoon flag", readings.get("afternoon_thrust") is True)

    sug = nat.as_suggestion(payload)
    ok("suggestion tag confident", "afternoon thrust" in str(sug.get("suggestion_tag")))
    ok("suggestion listable", sug.get("listable") is True)

    cand = session_candidate_from_dual(payload, day="2026-11-19", hm="14:00", entry=25436.55)
    ok("champ cand", isinstance(cand, dict) and cand.get("afternoon_thrust") is True, str(cand))
    ok("champ cand entry live", cand and abs(float(cand["entry"]) - 25436.55) < 0.01, str((cand or {}).get("entry")))

    result = {
        "fno_analysis": {"dual_track_call": payload, "champ_plus_live": {"added": []}},
    }
    ticket = modal._from_afternoon_thrust(
        result,
        None,
        symbol="NIFTY",
        bars=None,
        live_quote=None,
        db_path=None,
        asof="2026-11-19T14:00:00+05:30",
    )
    # Without session_calls DB, persist may return None/ticket — just ensure no crash
    ok("modal thrust path no crash", True, str(type(ticket)))

    # Sensex / BN untouched by flag
    ok("Sensex suppress bypass still off dual-suppress", not fno_live_config.suppress_dual_list_for("SENSEX"))

    print("fails", fails)
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
