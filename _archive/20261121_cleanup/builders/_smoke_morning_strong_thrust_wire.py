"""Offline smoke: morning strong OR+5 thrust live wire (no Kite).

  python -u prod_live/tests/builders/_smoke_morning_strong_thrust_wire.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [
    str(ROOT),
    str(ROOT / "app"),
    str(ROOT / "app" / "fno"),
    str(ROOT / "prod_live"),
]


def main() -> int:
    import fno_live_config
    import nifty_morning_strong_thrust as nmst
    import fno_dual_modal_list as modal
    from prod_live.logic.champ_plus_engine import session_candidate_from_dual

    fails = 0

    def ok(name: str, cond: bool, detail: str = "") -> None:
        nonlocal fails
        if not cond:
            fails += 1
        print(("PASS" if cond else "FAIL"), name, detail)

    ok("flag default ON", fno_live_config.enable_nifty_morning_strong_thrust())
    ok(
        "suppress dual does not block",
        nmst.dual_blocks(
            {"decision": "BUY", "track": "champion"}, suppress_dual_list=True
        )
        is False,
    )
    ok(
        "listing dual blocks",
        nmst.dual_blocks(
            {"decision": "BUY", "track": "champion"}, suppress_dual_list=False
        )
        is True,
    )

    # Synthetic 15m thrust + 5m fill tape
    idx15 = pd.date_range("2026-10-26 09:15", periods=6, freq="15min", tz="Asia/Kolkata")
    # OR bar, then thrust green with uplift>=50 body>=55% breaking prior highs
    rows15 = [
        # 09:15 OR
        dict(Open=22400.0, High=22450.0, Low=22380.0, Close=22410.0),
        # 09:30
        dict(Open=22412.0, High=22440.0, Low=22405.0, Close=22430.0),
        # 09:45 thrust: uplift from open 22400 → close 22480 = 80; body big; > prior highs
        dict(Open=22430.0, High=22485.0, Low=22428.0, Close=22480.0),
        dict(Open=22480.0, High=22500.0, Low=22460.0, Close=22470.0),
        dict(Open=22470.0, High=22520.0, Low=22465.0, Close=22510.0),
        dict(Open=22510.0, High=22540.0, Low=22500.0, Close=22530.0),
    ]
    bars15 = pd.DataFrame(rows15, index=idx15)
    # 5m after 09:45 dips to OR+5=22455
    idx5 = pd.date_range("2026-10-26 09:15", periods=20, freq="5min", tz="Asia/Kolkata")
    rows5 = []
    for ts in idx5:
        rows5.append(dict(Open=22440.0, High=22490.0, Low=22460.0, Close=22470.0))
    bars5 = pd.DataFrame(rows5, index=idx5)
    # Force a fill bar at 09:50: low touches 22455, green close > OR
    bars5.loc[idx5[7], :] = dict(Open=22460.0, High=22475.0, Low=22452.0, Close=22470.0)

    asof = pd.Timestamp("2026-10-26 10:00", tz="Asia/Kolkata")
    payload = nmst.evaluate(bars15, bars5, asof=asof, price=22470.0)
    ok("evaluate fires BUY", isinstance(payload, dict) and payload.get("decision") == "BUY", str(payload))
    if payload:
        ok("entry near OR+5", abs(float(payload["entry"]) - 22455.0) < 0.1, str(payload.get("entry")))
        ok("morning flag", payload.get("morning_strong_thrust") is True)
        ok("±30", float(payload["sl_pts"]) == 30 and float(payload["t1_pts"]) == 30)

    readings: dict = {}
    if payload:
        nmst.stamp_readings(readings, payload)
    ok("readings track confident", readings.get("track") == "confident")
    ok("readings morning flag", readings.get("morning_strong_thrust") is True)
    ok("readings listable", readings.get("listable") is True)

    if payload:
        sug = nmst.as_suggestion(payload)
        ok("suggestion listable", sug.get("listable") is True)
        cand = session_candidate_from_dual(
            payload, day="2026-10-26", hm=payload.get("hm") or "09:50", entry=payload["entry"]
        )
        ok(
            "champ cand",
            isinstance(cand, dict) and cand.get("morning_strong_thrust") is True,
            str(cand),
        )

        result = {
            "fno_analysis": {"dual_track_call": payload, "champ_plus_live": {"added": []}},
        }
        ticket = modal._from_morning_strong_thrust(
            result,
            None,
            symbol="NIFTY",
            bars=None,
            live_quote=None,
            db_path=None,
            asof="2026-10-26T09:50:00+05:30",
        )
        ok("modal morning path no crash", True, str(type(ticket)))

    print("FAILS", fails)
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
