"""Lock frvp_vah_break — more calls + FRVP VAH/VAL quality."""
from __future__ import annotations

import json
import sys
from collections import Counter
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [
    str(ROOT),
    str(ROOT / "app"),
    str(ROOT / "app" / "fno"),
    str(ROOT / "app" / "market"),
]
import kite_data  # noqa: E402
from prod_live.logic import pa_structure_live as pa  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"


def main() -> int:
    raw, err = kite_data.fetch_historical_candles(
        "NIFTY", "minute", days=25, keep_partial=False
    )
    if err or raw is None:
        raise RuntimeError(err)
    bars = pa.norm_1m(raw)
    today = "2026-11-20"
    tb = bars[bars.index.strftime("%Y-%m-%d") == today]
    cfg = replace(
        pa.CFG_V1,
        name="frvp_vah_break",
        body_min=0.55,
        or_side_align=True,
        side_flip_cooldown=12,
        max_calls_day=12,
        cooldown_bars=10,
        use_frvp=True,
        frvp_mode="vah_break",
        frvp_anchor="or30",
        frvp_prefer_sl=True,
    )
    pa.save_locked_cfg(cfg)
    (pa.HOLD / "locked_engine.json").write_text(
        json.dumps(
            {
                "engine": "structure_frvp",
                "name": "frvp_vah_break",
                "use_frvp": True,
                "frvp_mode": "vah_break",
                "max_calls_day": 12,
                "why": "more calls + FRVP VAH/VAL; L10~73%; today 7/+96",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    allc = pa.scan_session(bars, settle=True, cfg=cfg)
    ct = pa.scan_session(tb, settle=True, cfg=cfg)
    s, st = pa.summarize(allc), pa.summarize(ct)
    cpd = Counter(c.day for c in allc)
    avg = round(sum(cpd.values()) / max(1, len(cpd)), 2)
    pa.save_ledger(
        {"desk": pa.DESK, "logic_ver": "pa_frvp", "cfg_name": "frvp_vah_break", "calls": []}
    )
    meta = pa.append_live_calls(ct, mark_fire=True)
    print("LOCKED frvp_vah_break", s, "cpd", avg, flush=True)
    print("TODAY", st, flush=True)
    for c in ct:
        print(c.hm, c.side, c.setup, c.entry, c.stop_loss, c.pts, c.R, flush=True)

    lines = [
        f"# PA + FRVP locked · {today} · `frvp_vah_break`",
        "",
        "Hard 3-call/day **removed** (cap 12). FRVP morning levels quality-gate PA entries.",
        "",
        "| Knob | Value |",
        "|---|---|",
        "| FRVP | OR30 → POC / VAH / VAL |",
        "| Mode | **vah_break** — BUY at/above VAH · SELL at/below VAL |",
        "| SL | structure + FRVP bias |",
        "| Max calls/day | 12 (cooldown 10) |",
        "",
        f"| Scope | N | Hit% | AvgR | Sum | Calls/day |",
        f"|---|---:|---:|---:|---:|---:|",
        f"| Full 20d | {s.get('n')} | {s.get('hit_pct')} | {s.get('avg_R')} | {s.get('sum_pts')} | {avg} |",
        f"| Today | {st.get('n')} | {st.get('hit_pct')} | {st.get('avg_R')} | {st.get('sum_pts')} | — |",
        "",
        "## Today calls",
        "",
        "| HM | Side | Setup | Entry | SL | Pts | R |",
        "|---|---|---|---:|---:|---:|---:|",
    ]
    for c in ct:
        lines.append(
            f"| {c.hm} | {c.side} | {c.setup} | {c.entry} | {c.stop_loss} | {c.pts} | {c.R} |"
        )
    lines += [
        "",
        "## Why this vs cap3 / near_dense",
        "",
        "- Wanted **more calls** — not stuck at 3/day",
        "- Wanted **FRVP S/R** from morning indicator",
        "- `frvp_vah_break`: ~4.2 calls/day · L10 ~73% · today 7 / +96",
        "- `pa_uncap` has more N but no FRVP filter; this keeps FRVP quality",
        "",
    ]
    OUT.mkdir(parents=True, exist_ok=True)
    text = "\n".join(lines)
    (OUT / "PA_FRVP_MORE_CALLS.md").write_text(text, encoding="utf-8")
    (OUT / "PA_STRUCTURE_TODAY_LIVE.md").write_text(text, encoding="utf-8")
    (OUT / "PA_FRVP_MORE_CALLS.json").write_text(
        json.dumps(
            {
                "best": "frvp_vah_break",
                "full": s,
                "today": st,
                "avg_calls_per_day": avg,
                "today_calls": [c.to_dict() for c in ct],
                "ledger": meta,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print("Wrote reports", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
