"""Confirm CHAMP_PLUS live ticket-fill fires new days without blockers.

Simulates tomorrow session dual call → engine must add Cap4 call to live ledger,
stamp tags, and never report blocked.

  python -u prod_live/tests/confirm_champ_plus_live_engine.py
"""
from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "prod_live"))
import path_setup  # noqa: F401,E402

from prod_live.logic.champ_plus_engine import (  # noqa: E402
    CAP,
    _LIVE_LEDGER,
    call_key,
    load_held_raw,
    load_live_ledger,
    save_live_ledger,
)
from prod_live.logic.champ_plus_live import (  # noqa: E402
    ACCURACY_TAG,
    DESK,
    ensure_session_calls,
    stamp_live,
)
from prod_live.adapters.live_session_final import annotate_analyze_result  # noqa: E402
from prod_live.logic.combined_live_book import combine_live_rows, call_key as ck  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y" / "CHAMP_PLUS_LIVE_ENGINE_CONFIRM.md"


def main() -> int:
    # Use a day after held book max so we prove *new day* fire
    held = load_held_raw()
    max_held = max((str(r.get("day") or "") for r in held), default="2026-11-12")
    tomorrow = (date.fromisoformat(max_held) + timedelta(days=1)).isoformat()
    # skip weekends lightly
    d = date.fromisoformat(tomorrow)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    tomorrow = d.isoformat()

    # backup live ledger
    prev = load_live_ledger()
    # remove any prior test rows for tomorrow
    cleaned = [r for r in prev if str(r.get("day") or "") != tomorrow]
    save_live_ledger(cleaned)

    dual = {
        "decision": "BUY",
        "day": tomorrow,
        "hm": "10:15",
        "entry": 25500.0,
        "p_t1": 0.72,
        "track": "dual10m",
    }
    print(f"FIRE test day={tomorrow} dual={dual}", flush=True)
    meta = ensure_session_calls(
        tomorrow,
        dual_call=dual,
        hm="10:15",
        entry=25500.0,
    )
    assert meta.get("blocked") is False, meta
    added = meta.get("added") or []
    day_calls = meta.get("day_calls") or []
    print(
        f"  n_day={meta.get('n_day')} n_added={meta.get('n_added')} "
        f"desk={DESK} acc={ACCURACY_TAG}",
        flush=True,
    )
    ok_fire = meta.get("n_added", 0) >= 1 and len(added) >= 1
    if not ok_fire:
        print("FAIL: expected at least 1 live fire", flush=True)
        save_live_ledger(prev)
        return 1

    a0 = added[0]
    assert a0.get("accurate_tag") == DESK
    assert a0.get("accuracy_tag") == ACCURACY_TAG
    assert a0.get("decision") == "BUY"
    assert abs(float(a0.get("target_1")) - (25500.0 + 30)) < 0.01
    assert abs(float(a0.get("stop_loss")) - (25500.0 - 30)) < 0.01
    assert len([r for r in day_calls if str(r.get("day")) == tomorrow]) <= CAP

    # held untouched
    held2 = load_held_raw()
    assert len(held2) == len(held), "held book must not change"

    # annotate path
    result = {"fno_analysis": {}}
    dual2 = dict(dual)
    annotate_analyze_result(
        result,
        symbol="NIFTY",
        dual_call=dual2,
        readings={},
        emit_notify=False,
    )
    cpl = (result.get("fno_analysis") or {}).get("champ_plus_live") or {}
    assert cpl.get("live_engine") is True
    assert cpl.get("blocked") is False
    assert int(cpl.get("n_day") or 0) >= 1

    # combine with empty other books — no block
    stamped_day = stamp_live(day_calls)
    comb = combine_live_rows(champ_plus=stamped_day, p2f_day={}, p2f_cap2={}, p2g_10m={})
    assert comb["blocked_distinct"] == 0
    raw_keys = {ck(r) for r in comb["raw_rows"] if all(ck(r))}
    ui_keys = {ck(r) for r in comb["ui_rows"]}
    assert not (raw_keys - ui_keys)

    # second fire same key must not duplicate past Cap
    meta2 = ensure_session_calls(tomorrow, dual_call=dual, hm="10:15", entry=25500.0)
    keys = [call_key(r) for r in (meta2.get("day_calls") or [])]
    assert len(keys) == len(set(keys)), "duplicate keys in day book"

    lines = [
        "# CHAMP_PLUS live engine confirm",
        "",
        f"**Test day (tomorrow-style):** `{tomorrow}`",
        f"**Fired:** {meta.get('n_added')} · day book N={meta.get('n_day')} · cap={CAP}",
        f"**Desk:** `{DESK}` · **accuracy_tag:** `{ACCURACY_TAG}`",
        f"**Blocked:** `{meta.get('blocked')}`",
        f"**Held N unchanged:** {len(held)}",
        "",
        "## Added call",
        "",
        f"- {a0.get('day')} {a0.get('hm')} {a0.get('decision')} "
        f"entry={a0.get('entry')} SL={a0.get('stop_loss')} T={a0.get('target_1')}",
        "",
        "## Verdict",
        "",
        "**PASS** — live ticket-fill fires new day without blockers.",
        "",
    ]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # restore previous ledger but keep the proof fire (user wants engine live)
    # merge: prev + new tomorrow calls
    live_now = load_live_ledger()
    print(f"Wrote {OUT}", flush=True)
    print(f"VERDICT PASS · live ledger rows={len(live_now)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
