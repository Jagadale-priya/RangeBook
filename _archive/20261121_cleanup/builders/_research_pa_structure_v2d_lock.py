"""Combo-tune winning knobs (body55, or_align, flip_cd) and lock best.

  python -u prod_live/tests/builders/_research_pa_structure_v2d_lock.py
"""
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
    str(ROOT / "prod_live" / "tests" / "builders"),
]
import path_setup  # noqa: F401,E402
import kite_data  # noqa: E402

from prod_live.logic import pa_structure_live as pa  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"


def main() -> int:
    print("Pulling 1m…", flush=True)
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
    base = pa.CFG_V1

    cands = {
        "v1": base,
        "body55": replace(base, name="body55", body_min=0.55),
        "or_align": replace(base, name="or_align", or_side_align=True),
        "flip_cd": replace(base, name="flip_cd", side_flip_cooldown=20),
        "body55_or": replace(base, name="body55_or", body_min=0.55, or_side_align=True),
        "body55_flip": replace(
            base, name="body55_flip", body_min=0.55, side_flip_cooldown=20
        ),
        "or_flip": replace(
            base, name="or_flip", or_side_align=True, side_flip_cooldown=20
        ),
        "body55_or_flip": replace(
            base,
            name="body55_or_flip",
            body_min=0.55,
            or_side_align=True,
            side_flip_cooldown=20,
        ),
        "v2d": replace(
            base,
            name="v2d",
            body_min=0.55,
            or_side_align=True,
            side_flip_cooldown=20,
            min_risk=7.0,
            loss_extra_cooldown=10,
        ),
        "v2e": replace(
            base,
            name="v2e",
            body_min=0.52,
            or_side_align=True,
            side_flip_cooldown=18,
            sweep_depth_atr=0.15,
            sweep_wick_frac=0.20,
            reclaim_beyond=0.05,
            min_risk=6.0,
        ),
        "v2f": replace(
            base,
            name="v2f",
            body_min=0.55,
            or_side_align=True,
            side_flip_cooldown=20,
            max_calls_day=3,
        ),
    }

    rows = []
    for n, cfg in cands.items():
        allc = pa.scan_session(bars, settle=True, cfg=cfg)
        c10 = [c for c in allc if c.day in last10]
        ct = pa.scan_session(tb, settle=True, cfg=cfg)
        s, s10, st = pa.summarize(allc), pa.summarize(c10), pa.summarize(ct)
        print(
            f"{n:16} full {s['n']:3} {s['hit_pct']}% R={s['avg_R']} sum={s['sum_pts']} | "
            f"L10 {s10['n']} {s10['hit_pct']}% R={s10['avg_R']} | "
            f"TD {st['n']} {st['hit_pct']}% {st['sum_pts']}",
            flush=True,
        )
        rows.append((n, cfg, s, s10, st, ct))

    def key(r):
        _n, _cfg, s, s10, _st, _ct = r
        if (s.get("n") or 0) < 50:
            return (-1.0, -1.0, -1.0, -1.0)
        return (
            float(s10.get("hit_pct") or 0),
            float(s.get("avg_R") or 0),
            float(s.get("hit_pct") or 0),
            float(s.get("sum_pts") or 0),
        )

    best = max(rows, key=key)
    best_name, locked, s, s10, st, ct = best
    print(f"BEST={best_name}", flush=True)
    pa.save_locked_cfg(locked)
    pa.CFG = locked
    pa.save_ledger(
        {"desk": pa.DESK, "logic_ver": "v2d", "cfg_name": best_name, "calls": []}
    )
    meta = pa.append_live_calls(ct, mark_fire=True)

    v1 = rows[0]
    payload = {
        "today": today,
        "best": best_name,
        "full": s,
        "last10": s10,
        "today_summary": st,
        "today_calls": [c.to_dict() for c in ct],
        "ledger": meta,
        "v1": {"full": v1[2], "last10": v1[3], "today": v1[4]},
        "compare": [
            {"name": n, "full": sf, "last10": sl, "today": stt}
            for n, _c, sf, sl, stt, _ct in rows
        ],
        "improvements_locked": [
            "body_min 0.55 (stronger closes)" if "body" in best_name or best_name.startswith("v2") else None,
            "OR-side align" if "or" in best_name or best_name.startswith("v2") else None,
            "side-flip cooldown" if "flip" in best_name or best_name.startswith("v2") else None,
        ],
    }
    payload["improvements_locked"] = [x for x in payload["improvements_locked"] if x]

    lines = [
        f"# PA Structure locked · {today} · `{best_name}`",
        "",
        "| Scope | N | Hit% | AvgR | Sum |",
        "|---|---:|---:|---:|---:|",
        f"| Full | {s['n']} | {s['hit_pct']} | {s['avg_R']} | {s['sum_pts']} |",
        f"| Last10 | {s10['n']} | {s10['hit_pct']} | {s10['avg_R']} | {s10['sum_pts']} |",
        f"| Today | {st['n']} | {st['hit_pct']} | {st['avg_R']} | {st['sum_pts']} |",
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
        "## vs v1",
        "",
        f"| | v1 | **{best_name}** |",
        "|---|---|---|",
        f"| Full Hit | {v1[2]['hit_pct']} | **{s['hit_pct']}** |",
        f"| Full AvgR | {v1[2]['avg_R']} | **{s['avg_R']}** |",
        f"| Full Sum | {v1[2]['sum_pts']} | **{s['sum_pts']}** |",
        f"| L10 Hit | {v1[3]['hit_pct']} | **{s10['hit_pct']}** |",
        f"| Today Hit | {v1[4]['hit_pct']} | **{st['hit_pct']}** |",
        f"| Today Sum | {v1[4]['sum_pts']} | **{st['sum_pts']}** |",
        "",
        "## All combos",
        "",
        "| Profile | Full N/Hit/R/Sum | L10 Hit | Today Hit/Sum |",
        "|---|---|---:|---|",
    ]
    for n, _c, sf, sl, stt, _ct in rows:
        mark = "**" if n == best_name else ""
        lines.append(
            f"| {mark}{n}{mark} | {sf['n']}/{sf['hit_pct']}/{sf['avg_R']}/{sf['sum_pts']} | "
            f"{sl['hit_pct']} | {stt['n']}/{stt['hit_pct']}/{stt['sum_pts']} |"
        )

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "PA_STRUCTURE_V2D_LOCK.md").write_text("\n".join(lines), encoding="utf-8")
    (OUT / "PA_STRUCTURE_V2D_LOCK.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )
    (OUT / "PA_STRUCTURE_TODAY_LIVE.md").write_text("\n".join(lines), encoding="utf-8")
    (OUT / "PA_STRUCTURE_TODAY_LIVE.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )
    print(f"ledger {meta}", flush=True)
    print(f"Wrote {OUT / 'PA_STRUCTURE_V2D_LOCK.md'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
