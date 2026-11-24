"""Fine-tune on top of v1 — keep edge, cut only weak-sweep / tight-SL noise.

  python -u prod_live/tests/builders/_research_pa_structure_v2b_tune.py
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
MD = OUT / "PA_STRUCTURE_V2B_TUNE.md"
JS = OUT / "PA_STRUCTURE_V2B_TUNE.json"
TODAY_MD = OUT / "PA_STRUCTURE_TODAY_LIVE.md"
TODAY_JS = OUT / "PA_STRUCTURE_TODAY_LIVE.json"


def fetch():
    raw, err = kite_data.fetch_historical_candles(
        "NIFTY", "minute", days=25, keep_partial=False
    )
    if err or raw is None:
        raise RuntimeError(err)
    return pa.norm_1m(raw)


def score(s: dict, *, min_n: int = 12) -> float:
    if not s or not s.get("n") or s["n"] < min_n:
        return -999.0
    hit = float(s.get("hit_pct") or 0)
    ar = float(s.get("avg_R") or 0)
    sp = float(s.get("sum_pts") or 0)
    # reward accuracy + expectancy + absolute edge; soft penalty if n collapses hard
    return hit * 1.5 + ar * 50.0 + sp / 50.0 + min(s["n"], 60) * 0.15


def main() -> int:
    print("Pulling 1m…", flush=True)
    bars = fetch()
    days = sorted({str(ts.date()) for ts in bars.index})
    today = days[-1]
    last10 = set(days[-10:])
    today_bars = bars[bars.index.strftime("%Y-%m-%d") == today]
    base = pa.CFG_V1

    candidates = {
        "v1": base,
        # single knobs
        "minrisk7": replace(base, name="minrisk7", min_risk=7.0),
        "minrisk8": replace(base, name="minrisk8", min_risk=8.0),
        "minrisk9": replace(base, name="minrisk9", min_risk=9.0),
        "minrisk10": replace(base, name="minrisk10", min_risk=10.0),
        "body55": replace(base, name="body55", body_min=0.55),
        "break25": replace(base, name="break25", break_atr_frac=0.25),
        "sweep_q": replace(
            base,
            name="sweep_q",
            sweep_depth_atr=0.20,
            sweep_wick_frac=0.25,
            reclaim_beyond=0.10,
        ),
        "or_align": replace(base, name="or_align", or_side_align=True),
        "strict_htf": replace(base, name="strict_htf", strict_htf=True),
        "mom": replace(base, name="mom", require_break_mom=True),
        "late_open": replace(base, name="late_open", trade_lo=9 * 60 + 50),
        "loss_cd": replace(base, name="loss_cd", loss_extra_cooldown=12),
        "flip_cd": replace(base, name="flip_cd", side_flip_cooldown=20),
        "cap3": replace(base, name="cap3", max_calls_day=3),
        "cd15": replace(base, name="cd15", cooldown_bars=15),
        # combos aimed at loss autopsy
        "v2b": replace(
            base,
            name="v2b",
            min_risk=8.0,
            body_min=0.50,
            sweep_depth_atr=0.20,
            sweep_wick_frac=0.25,
            reclaim_beyond=0.10,
            loss_extra_cooldown=12,
            side_flip_cooldown=15,
            cooldown_bars=14,
            max_calls_day=3,
        ),
        "v2b_oralign": replace(
            base,
            name="v2b_oralign",
            min_risk=8.0,
            body_min=0.50,
            sweep_depth_atr=0.20,
            sweep_wick_frac=0.25,
            reclaim_beyond=0.10,
            or_side_align=True,
            loss_extra_cooldown=12,
            side_flip_cooldown=15,
            cooldown_bars=14,
            max_calls_day=3,
        ),
        "v2b_plus": replace(
            base,
            name="v2b_plus",
            min_risk=8.0,
            body_min=0.52,
            break_atr_frac=0.20,
            sweep_depth_atr=0.22,
            sweep_wick_frac=0.28,
            reclaim_beyond=0.12,
            or_side_align=True,
            require_break_mom=True,
            loss_extra_cooldown=12,
            side_flip_cooldown=18,
            cooldown_bars=14,
            max_calls_day=3,
            trade_lo=9 * 60 + 45,
        ),
        "v2c": replace(
            base,
            name="v2c",
            min_risk=9.0,
            sweep_depth_atr=0.22,
            sweep_wick_frac=0.28,
            reclaim_beyond=0.12,
            loss_extra_cooldown=15,
            side_flip_cooldown=20,
            cooldown_bars=15,
            max_calls_day=3,
        ),
        "v2c_oralign": replace(
            base,
            name="v2c_oralign",
            min_risk=9.0,
            sweep_depth_atr=0.22,
            sweep_wick_frac=0.28,
            reclaim_beyond=0.12,
            or_side_align=True,
            loss_extra_cooldown=15,
            side_flip_cooldown=20,
            cooldown_bars=15,
            max_calls_day=3,
        ),
    }

    rows = []
    for name, cfg in candidates.items():
        allc = pa.scan_session(bars, settle=True, cfg=cfg)
        c10 = [c for c in allc if c.day in last10]
        ct = pa.scan_session(today_bars, settle=True, cfg=cfg)
        s_all, s10, st = pa.summarize(allc), pa.summarize(c10), pa.summarize(ct)
        row = {
            "name": name,
            "full": s_all,
            "last10": s10,
            "today": st,
            "today_calls": [c.to_dict() for c in ct],
            "score_full": round(score(s_all), 3),
            "score_last10": round(score(s10, min_n=8), 3),
            "cfg": cfg,
        }
        rows.append(row)
        print(
            f"{name:14} full {s_all.get('n'):3} {s_all.get('hit_pct')}% "
            f"R={s_all.get('avg_R')} sum={s_all.get('sum_pts')} | "
            f"L10 {s10.get('n')} {s10.get('hit_pct')}% | "
            f"TD {st.get('n')} {st.get('hit_pct')}% {st.get('sum_pts')}",
            flush=True,
        )

    # Prefer improves vs v1 on last10 hit OR full avg_R/sum without collapsing n too hard
    v1 = next(r for r in rows if r["name"] == "v1")
    ranked = sorted(
        rows, key=lambda r: (r["score_last10"], r["score_full"]), reverse=True
    )
    # among top, prefer ones that beat v1 full sum_pts OR hit% with n>=0.5*v1
    def beats_v1(r):
        f, v = r["full"], v1["full"]
        if not f.get("n") or f["n"] < max(12, int(0.45 * (v.get("n") or 1))):
            return False
        return (f.get("hit_pct") or 0) >= (v.get("hit_pct") or 0) - 1.0 and (
            (f.get("avg_R") or -9) >= (v.get("avg_R") or 0) - 0.02
            or (f.get("sum_pts") or -9) >= (v.get("sum_pts") or 0) * 0.85
        )

    improvers = [r for r in ranked if r["name"] != "v1" and beats_v1(r)]
    if improvers:
        best = improvers[0]
    else:
        # next: best that improves last10 hit vs v1 with decent n
        alt = [
            r
            for r in ranked
            if r["name"] != "v1"
            and (r["last10"].get("n") or 0) >= 8
            and (r["last10"].get("hit_pct") or 0) >= (v1["last10"].get("hit_pct") or 0)
            and (r["full"].get("avg_R") or -9) >= (v1["full"].get("avg_R") or 0) - 0.05
        ]
        best = alt[0] if alt else ranked[0]

    best_name = best["name"]
    locked = best["cfg"]
    print(f"\nLOCKED={best_name}", flush=True)
    pa.save_locked_cfg(locked)
    pa.CFG = locked

    ct_best = pa.scan_session(today_bars, settle=True, cfg=locked)
    pa.save_ledger(
        {
            "desk": pa.DESK,
            "logic_ver": "v2b",
            "cfg_name": best_name,
            "calls": [],
        }
    )
    ledger = pa.append_live_calls(ct_best, mark_fire=True)

    payload = {
        "today": today,
        "best": best_name,
        "v1": {"full": v1["full"], "last10": v1["last10"], "today": v1["today"]},
        "ranked": [
            {
                "name": r["name"],
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
    }
    JS.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        f"# PA Structure v2b tune · {today}",
        "",
        f"**Locked:** `{best_name}` (vs v1 baseline)",
        "",
        "## Ranked",
        "",
        "| Profile | Full N/Hit/R/Sum | L10 N/Hit/R | Today N/Hit/Sum | Score L10 |",
        "|---|---|---|---|---:|",
    ]
    for r in ranked:
        f, l, t = r["full"], r["last10"], r["today"]
        mark = "**" if r["name"] == best_name else ""
        lines.append(
            f"| {mark}{r['name']}{mark} | {f.get('n')}/{f.get('hit_pct')}/{f.get('avg_R')}/{f.get('sum_pts')} | "
            f"{l.get('n')}/{l.get('hit_pct')}/{l.get('avg_R')} | "
            f"{t.get('n')}/{t.get('hit_pct')}/{t.get('sum_pts')} | {r['score_last10']} |"
        )

    st = best["today"]
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
    lines += [
        "",
        "## vs v1 today",
        "",
        f"| | v1 | {best_name} |",
        f"|---|---|---|",
        f"| N | {v1['today'].get('n')} | {st.get('n')} |",
        f"| Hit% | {v1['today'].get('hit_pct')} | {st.get('hit_pct')} |",
        f"| Sum | {v1['today'].get('sum_pts')} | {st.get('sum_pts')} |",
        f"| AvgR | {v1['today'].get('avg_R')} | {st.get('avg_R')} |",
        "",
        f"Full: v1 {v1['full']} → {best_name} {best['full']}",
        "",
    ]
    MD.write_text("\n".join(lines), encoding="utf-8")

    TODAY_JS.write_text(
        json.dumps(
            {
                "desk": pa.DESK,
                "cfg_name": best_name,
                "today": today,
                "today_summary": st,
                "today_calls": [c.to_dict() for c in ct_best],
                "window_summary": best["full"],
                "last10_summary": best["last10"],
                "v1_today": v1["today"],
                "tune_report": str(MD).replace("\\", "/"),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    TODAY_MD.write_text(
        "\n".join(
            [
                f"# PA Structure Live · {today} · `{best_name}`",
                "",
                f"Tuned vs v1 — see `{MD.name}`",
                "",
                f"| | v1 | **{best_name}** |",
                f"|---|---|---|",
                f"| Today N | {v1['today'].get('n')} | **{st.get('n')}** |",
                f"| Today Hit% | {v1['today'].get('hit_pct')} | **{st.get('hit_pct')}** |",
                f"| Today Sum | {v1['today'].get('sum_pts')} | **{st.get('sum_pts')}** |",
                f"| Window Hit% | {v1['full'].get('hit_pct')} | **{best['full'].get('hit_pct')}** |",
                f"| Window Sum | {v1['full'].get('sum_pts')} | **{best['full'].get('sum_pts')}** |",
                "",
                "| HM | Side | Setup | Entry | SL | Risk | Exit | Pts | R |",
                "|---|---|---|---:|---:|---:|---|---:|---:|",
            ]
            + [
                f"| {c.hm} | {c.side} | {c.setup} | {c.entry} | {c.stop_loss} | {c.risk} | "
                f"{c.exit_why} | {c.pts} | {c.R} |"
                for c in ct_best
            ]
            + ["", f"Locked cfg → `prod_live/holding_accurate/pa_structure/locked_cfg.json`", ""]
        ),
        encoding="utf-8",
    )
    print(f"Wrote {MD}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
