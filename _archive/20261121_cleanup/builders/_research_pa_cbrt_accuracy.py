"""Research CBRT (consol→break→retest→pullback) for accuracy vs locked PA.

  python -u prod_live/tests/builders/_research_pa_cbrt_accuracy.py
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict, replace
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
from prod_live.logic.pa_cbrt_live import CbrtConfig, cbrt_profiles, scan_cbrt  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
MD = OUT / "PA_CBRT_ACCURACY.md"
JS = OUT / "PA_CBRT_ACCURACY.json"
TODAY_MD = OUT / "PA_STRUCTURE_TODAY_LIVE.md"
TODAY_JS = OUT / "PA_STRUCTURE_TODAY_LIVE.json"


def fetch():
    print("Pulling Kite NIFTY 1m · 25d …", flush=True)
    raw, err = kite_data.fetch_historical_candles(
        "NIFTY", "minute", days=25, keep_partial=False
    )
    if err or raw is None:
        raise RuntimeError(err)
    bars = pa.norm_1m(raw)
    print(f"  bars={len(bars)}", flush=True)
    return bars


def acc_score(s: dict, *, min_n: int = 10) -> float:
    """Prioritize hit% then avg_R; require enough trades."""
    if not s or (s.get("n") or 0) < min_n:
        return -999.0
    hit = float(s.get("hit_pct") or 0)
    ar = float(s.get("avg_R") or 0)
    n = int(s["n"])
    sp = float(s.get("sum_pts") or 0)
    # accuracy first; mild reward for R and not collapsing n
    return hit * 3.0 + ar * 25.0 + min(n, 40) * 0.2 + (1.0 if sp > 0 else -5.0)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    bars = fetch()
    days = sorted({str(ts.date()) for ts in bars.index})
    today = days[-1]
    last10 = set(days[-10:])
    tb = bars[bars.index.strftime("%Y-%m-%d") == today]

    rows = []

    # baselines from structure desk
    baselines = {
        "v1": pa.CFG_V1,
        "body55_or": pa.load_locked_cfg()
        if pa.LOCKED_CFG_PATH.exists()
        else replace(pa.CFG_V1, name="body55_or", body_min=0.55, or_side_align=True),
        "v2f_cap3": replace(
            pa.CFG_V1,
            name="v2f_cap3",
            body_min=0.55,
            or_side_align=True,
            side_flip_cooldown=20,
            max_calls_day=3,
        ),
    }
    for name, cfg in baselines.items():
        if cfg.name != name:
            cfg = replace(cfg, name=name)
        allc = pa.scan_session(bars, settle=True, cfg=cfg)
        c10 = [c for c in allc if c.day in last10]
        ct = pa.scan_session(tb, settle=True, cfg=cfg)
        s, s10, st = pa.summarize(allc), pa.summarize(c10), pa.summarize(ct)
        rows.append(
            {
                "name": name,
                "kind": "structure",
                "full": s,
                "last10": s10,
                "today": st,
                "today_calls": [c.to_dict() for c in ct],
                "score_full": round(acc_score(s, min_n=12), 3),
                "score_last10": round(acc_score(s10, min_n=8), 3),
                "cfg": cfg,
                "engine": "structure",
            }
        )
        print(
            f"{name:18} STRUCT full {s.get('n')} {s.get('hit_pct')}% R={s.get('avg_R')} "
            f"| L10 {s10.get('n')} {s10.get('hit_pct')}% | TD {st.get('n')} {st.get('hit_pct')}%",
            flush=True,
        )

    for name, cfg in cbrt_profiles().items():
        allc = scan_cbrt(bars, settle=True, cfg=cfg)
        c10 = [c for c in allc if c.day in last10]
        ct = scan_cbrt(tb, settle=True, cfg=cfg)
        s, s10, st = pa.summarize(allc), pa.summarize(c10), pa.summarize(ct)
        rows.append(
            {
                "name": name,
                "kind": "cbrt",
                "full": s,
                "last10": s10,
                "today": st,
                "today_calls": [c.to_dict() for c in ct],
                "score_full": round(acc_score(s, min_n=8), 3),
                "score_last10": round(acc_score(s10, min_n=5), 3),
                "cfg": cfg,
                "engine": "cbrt",
            }
        )
        print(
            f"{name:18} CBRT   full {s.get('n')} {s.get('hit_pct')}% R={s.get('avg_R')} "
            f"| L10 {s10.get('n')} {s10.get('hit_pct')}% | TD {st.get('n')} {st.get('hit_pct')}%",
            flush=True,
        )

    ranked = sorted(
        rows, key=lambda r: (r["score_last10"], r["score_full"]), reverse=True
    )
    # Prefer accuracy: among top, pick highest last10 hit with full hit >= body55_or - 3
    b55 = next(r for r in rows if r["name"] == "body55_or")
    floor_hit = (b55["last10"].get("hit_pct") or 0) - 0.5
    accurate = [
        r
        for r in ranked
        if (r["last10"].get("hit_pct") or 0) >= floor_hit
        and (r["full"].get("n") or 0) >= 8
        and (r["full"].get("avg_R") or -9) > 0
    ]
    best = accurate[0] if accurate else ranked[0]
    best_name = best["name"]
    print(f"BEST={best_name} engine={best['engine']}", flush=True)

    # lock for live
    if best["engine"] == "structure":
        pa.save_locked_cfg(best["cfg"])
        pa.CFG = best["cfg"]
        ct_best = pa.scan_session(tb, settle=True, cfg=best["cfg"])
        engine_tag = "structure"
    else:
        # store CBRT as sidecar + mark locked_cfg with flag
        cbrt_path = pa.HOLD / "locked_cbrt.json"
        pa.HOLD.mkdir(parents=True, exist_ok=True)
        cbrt_path.write_text(json.dumps(asdict(best["cfg"]), indent=2), encoding="utf-8")
        # also keep structure cfg pointing to body55_or as fallback notify path
        # primary live engine stamp
        meta_lock = {
            "engine": "cbrt",
            "name": best_name,
            "cbrt": asdict(best["cfg"]),
        }
        (pa.HOLD / "locked_engine.json").write_text(
            json.dumps(meta_lock, indent=2), encoding="utf-8"
        )
        ct_best = scan_cbrt(tb, settle=True, cfg=best["cfg"])
        engine_tag = "cbrt"

    # always stamp engine file
    (pa.HOLD / "locked_engine.json").write_text(
        json.dumps(
            {
                "engine": engine_tag,
                "name": best_name,
                "cbrt": asdict(best["cfg"]) if engine_tag == "cbrt" else None,
                "structure": asdict(best["cfg"]) if engine_tag == "structure" else None,
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )

    pa.save_ledger(
        {
            "desk": pa.DESK,
            "logic_ver": "cbrt" if engine_tag == "cbrt" else "v2d",
            "cfg_name": best_name,
            "engine": engine_tag,
            "calls": [],
        }
    )
    ledger = pa.append_live_calls(ct_best, mark_fire=True)

    payload = {
        "today": today,
        "best": best_name,
        "engine": engine_tag,
        "ranked": [
            {
                "name": r["name"],
                "kind": r["kind"],
                "score_last10": r["score_last10"],
                "score_full": r["score_full"],
                "full": r["full"],
                "last10": r["last10"],
                "today": r["today"],
            }
            for r in ranked
        ],
        "best_today_calls": [c.to_dict() for c in ct_best],
        "ledger": ledger,
        "vs_body55_or": {
            "body55_or": {
                "full": b55["full"],
                "last10": b55["last10"],
                "today": b55["today"],
            },
            "best": {
                "full": best["full"],
                "last10": best["last10"],
                "today": best["today"],
            },
        },
    }
    JS.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    st = best["today"]
    lines = [
        f"# PA CBRT accuracy research · {today}",
        "",
        f"**Locked:** `{best_name}` · engine=`{engine_tag}`",
        "",
        "State machine: **Consolidation → Breakout → Retest → Pullback** (1m Kite, causal).",
        "",
        "## Ranked (accuracy-first)",
        "",
        "| Profile | Kind | Full N/Hit/R/Sum | L10 N/Hit/R | Today N/Hit/Sum | Score L10 |",
        "|---|---|---|---|---|---:|",
    ]
    for r in ranked:
        f, l, t = r["full"], r["last10"], r["today"]
        mark = "**" if r["name"] == best_name else ""
        lines.append(
            f"| {mark}{r['name']}{mark} | {r['kind']} | "
            f"{f.get('n')}/{f.get('hit_pct')}/{f.get('avg_R')}/{f.get('sum_pts')} | "
            f"{l.get('n')}/{l.get('hit_pct')}/{l.get('avg_R')} | "
            f"{t.get('n')}/{t.get('hit_pct')}/{t.get('sum_pts')} | {r['score_last10']} |"
        )

    lines += [
        "",
        f"## Today `{best_name}`",
        "",
        f"n={st.get('n')} hit={st.get('hit_pct')} avgR={st.get('avg_R')} sum={st.get('sum_pts')}",
        "",
        "| HM | Side | Setup | Entry | SL | Risk | Exit | Pts | R | MFE |",
        "|---|---|---|---:|---:|---:|---|---:|---:|---:|",
    ]
    for c in ct_best:
        lines.append(
            f"| {c.hm} | {c.side} | {c.setup} | {c.entry} | {c.stop_loss} | {c.risk} | "
            f"{c.exit_why} | {c.pts} | {c.R} | {c.mfe} |"
        )
    if not ct_best:
        lines.append("| — | — | no CBRT setup today | — | — | — | — | — | — | — |")

    lines += [
        "",
        "## vs body55_or",
        "",
        f"| | body55_or | **{best_name}** |",
        "|---|---|---|",
        f"| Full Hit | {b55['full'].get('hit_pct')} | **{best['full'].get('hit_pct')}** |",
        f"| Full AvgR | {b55['full'].get('avg_R')} | **{best['full'].get('avg_R')}** |",
        f"| L10 Hit | {b55['last10'].get('hit_pct')} | **{best['last10'].get('hit_pct')}** |",
        f"| Today Hit | {b55['today'].get('hit_pct')} | **{st.get('hit_pct')}** |",
        f"| Today Sum | {b55['today'].get('sum_pts')} | **{st.get('sum_pts')}** |",
        "",
    ]
    MD.write_text("\n".join(lines), encoding="utf-8")
    TODAY_MD.write_text("\n".join(lines), encoding="utf-8")
    TODAY_JS.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {MD}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
