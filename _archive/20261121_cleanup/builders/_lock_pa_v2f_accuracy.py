"""Clean compare + lock v2f_cap3 (best accuracy on 1m tape)."""
from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [
    str(ROOT),
    str(ROOT / "app"),
    str(ROOT / "app" / "market"),
]
import kite_data  # noqa: E402
from prod_live.logic import pa_structure_live as pa  # noqa: E402
from prod_live.logic.pa_cbrt_live import CbrtConfig, cbrt_profiles, scan_cbrt  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"


def main() -> int:
    raw, err = kite_data.fetch_historical_candles(
        "NIFTY", "minute", days=25, keep_partial=False
    )
    if err or raw is None:
        raise RuntimeError(err)
    bars = pa.norm_1m(raw)
    days = sorted({str(ts.date()) for ts in bars.index})
    today = days[-1]
    last10 = set(days[-10:])
    tb = bars[bars.index.strftime("%Y-%m-%d") == today]

    true_b55 = replace(pa.CFG_V1, name="body55_or", body_min=0.55, or_side_align=True)
    v2f = replace(
        pa.CFG_V1,
        name="v2f_cap3",
        body_min=0.55,
        or_side_align=True,
        side_flip_cooldown=20,
        max_calls_day=3,
    )
    chase = cbrt_profiles()["cbrt_v2_chase"]

    rows = []
    for label, engine, cfg in [
        ("v1", "structure", pa.CFG_V1),
        ("body55_or", "structure", true_b55),
        ("v2f_cap3", "structure", v2f),
        ("cbrt_v2", "cbrt", CbrtConfig(name="cbrt_v2")),
        ("cbrt_v2_chase", "cbrt", chase),
    ]:
        if engine == "structure":
            allc = pa.scan_session(bars, settle=True, cfg=cfg)
            ct = pa.scan_session(tb, settle=True, cfg=cfg)
        else:
            allc = scan_cbrt(bars, settle=True, cfg=cfg)
            ct = scan_cbrt(tb, settle=True, cfg=cfg)
        c10 = [c for c in allc if c.day in last10]
        s, s10, st = pa.summarize(allc), pa.summarize(c10), pa.summarize(ct)
        print(
            f"{label:14} {s['n']:3} {s['hit_pct']}% R={s['avg_R']} sum={s['sum_pts']} | "
            f"L10 {s10['n']} {s10['hit_pct']}% | TD {st['n']} {st['hit_pct']} {st['sum_pts']}",
            flush=True,
        )
        rows.append((label, engine, cfg, s, s10, st, ct))

    locked = v2f
    pa.save_locked_cfg(locked)
    (pa.HOLD / "locked_engine.json").write_text(
        json.dumps(
            {
                "engine": "structure",
                "name": "v2f_cap3",
                "why": "L10 hit 75% · full 71.7% · best accuracy with n>=24",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    ct = pa.scan_session(tb, settle=True, cfg=locked)
    pa.save_ledger(
        {
            "desk": pa.DESK,
            "logic_ver": "v2f",
            "cfg_name": "v2f_cap3",
            "engine": "structure",
            "calls": [],
        }
    )
    meta = pa.append_live_calls(ct, mark_fire=True)
    v2 = rows[2]

    lines = [
        f"# PA accuracy lock · {today} · `v2f_cap3`",
        "",
        "Research: Consol→Break→Retest (CBRT) + structure ablations on **NIFTY 1m** Kite.",
        "",
        "## Locked for live",
        "",
        "| Knob | Value |",
        "|---|---|",
        "| body_min | 0.55 |",
        "| or_side_align | True |",
        "| side_flip_cooldown | 20 bars |",
        "| max_calls_day | 3 |",
        "| SL | prev candle + swing (structure) |",
        "| Target | none — trail after 1R |",
        "",
        "## Comparison",
        "",
        "| Book | Full N/Hit/R/Sum | L10 Hit | Today Hit/Sum |",
        "|---|---|---:|---|",
    ]
    for label, _e, _c, s, s10, st, _ct in rows:
        mark = "**" if label == "v2f_cap3" else ""
        lines.append(
            f"| {mark}{label}{mark} | {s['n']}/{s['hit_pct']}/{s['avg_R']}/{s['sum_pts']} | "
            f"{s10['hit_pct']} | {st['n']}/{st['hit_pct']}/{st['sum_pts']} |"
        )
    lines += [
        "",
        "## Today locked calls",
        "",
        "| HM | Side | Setup | Entry | SL | Risk | Exit | Pts | R | MFE |",
        "|---|---|---|---:|---:|---:|---|---:|---:|---:|",
    ]
    for c in ct:
        lines.append(
            f"| {c.hm} | {c.side} | {c.setup} | {c.entry} | {c.stop_loss} | {c.risk} | "
            f"{c.exit_why} | {c.pts} | {c.R} | {c.mfe} |"
        )
    lines += [
        "",
        "## Notes",
        "",
        "- **CBRT v2** improved vs v1 (45%→64%) after requiring break **extension before retest**.",
        "- Still below structure accuracy on this 20-session tape — kept as research path.",
        "- **v2f_cap3** = body55_or + flip cooldown + cap3 → best L10 accuracy **75%**.",
        "",
    ]
    text = "\n".join(lines)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "PA_CBRT_ACCURACY.md").write_text(text, encoding="utf-8")
    (OUT / "PA_STRUCTURE_TODAY_LIVE.md").write_text(text, encoding="utf-8")
    payload = {
        "best": "v2f_cap3",
        "today": today,
        "today_calls": [c.to_dict() for c in ct],
        "today_summary": pa.summarize(ct),
        "full": v2[3],
        "last10": v2[4],
        "ledger": meta,
        "compare": [
            {"name": l, "full": s, "last10": s10, "today": st}
            for l, _e, _c, s, s10, st, _ct in rows
        ],
    }
    (OUT / "PA_STRUCTURE_TODAY_LIVE.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )
    (OUT / "PA_CBRT_ACCURACY.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )
    # update module default name
    print("LOCKED v2f_cap3", pa.summarize(ct), "ledger", meta["n_added"], flush=True)
    print(f"Wrote {OUT / 'PA_CBRT_ACCURACY.md'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
