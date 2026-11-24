"""PA + morning FRVP S/R quality · uncapped density (no hard 3/day).

Uses the FRVP module added for chart (POC/VAH/VAL/HVN) as causal filters
on top of PA setups. Cooldown still prevents spam; max_calls raised.

  python -u prod_live/tests/builders/_research_pa_frvp_more_calls.py
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
    str(ROOT / "app" / "fno"),
    str(ROOT / "app" / "market"),
]
import kite_data  # noqa: E402
from prod_live.logic import pa_structure_live as pa  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
MD = OUT / "PA_FRVP_MORE_CALLS.md"
JS = OUT / "PA_FRVP_MORE_CALLS.json"
TODAY_MD = OUT / "PA_STRUCTURE_TODAY_LIVE.md"


def score(s: dict, *, min_n: int = 15) -> float:
    if not s or (s.get("n") or 0) < min_n:
        return -999.0
    hit = float(s.get("hit_pct") or 0)
    ar = float(s.get("avg_R") or 0)
    n = int(s["n"])
    sp = float(s.get("sum_pts") or 0)
    # more calls rewarded lightly if accuracy holds
    return hit * 2.5 + ar * 35.0 + min(n, 80) * 0.25 + (sp / 80.0)


def main() -> int:
    print("Pulling NIFTY 1m…", flush=True)
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

    base = replace(
        pa.CFG_V1,
        name="pa_uncap",
        body_min=0.55,
        or_side_align=True,
        side_flip_cooldown=12,
        max_calls_day=12,
        cooldown_bars=10,
        use_frvp=False,
    )

    cands = {
        "v2f_cap3": replace(
            pa.CFG_V1,
            name="v2f_cap3",
            body_min=0.55,
            or_side_align=True,
            side_flip_cooldown=20,
            max_calls_day=3,
            use_frvp=False,
        ),
        "pa_uncap": base,
        "frvp_near_or": replace(
            base,
            name="frvp_near_or",
            use_frvp=True,
            frvp_mode="near_level",
            frvp_anchor="or30",
            max_calls_day=12,
        ),
        "frvp_near_expand": replace(
            base,
            name="frvp_near_expand",
            use_frvp=True,
            frvp_mode="near_level",
            frvp_anchor="session_expand",
            frvp_refresh_every=12,
            max_calls_day=12,
        ),
        "frvp_bounce": replace(
            base,
            name="frvp_bounce",
            use_frvp=True,
            frvp_mode="bounce_sr",
            frvp_anchor="or30",
            max_calls_day=12,
        ),
        "frvp_vah_break": replace(
            base,
            name="frvp_vah_break",
            use_frvp=True,
            frvp_mode="vah_break",
            frvp_anchor="or30",
            max_calls_day=12,
        ),
        "frvp_near_dense": replace(
            base,
            name="frvp_near_dense",
            use_frvp=True,
            frvp_mode="near_level",
            frvp_anchor="session_expand",
            frvp_zone_atr=0.55,
            cooldown_bars=8,
            side_flip_cooldown=8,
            max_calls_day=16,
        ),
        "frvp_bounce_expand": replace(
            base,
            name="frvp_bounce_expand",
            use_frvp=True,
            frvp_mode="bounce_sr",
            frvp_anchor="session_expand",
            frvp_refresh_every=10,
            max_calls_day=12,
        ),
    }

    rows = []
    for name, cfg in cands.items():
        print(f"  {name}…", flush=True)
        allc = pa.scan_session(bars, settle=True, cfg=cfg)
        c10 = [c for c in allc if c.day in last10]
        ct = pa.scan_session(tb, settle=True, cfg=cfg)
        s, s10, st = pa.summarize(allc), pa.summarize(c10), pa.summarize(ct)
        # calls per day
        from collections import Counter

        cpd = Counter(c.day for c in allc)
        avg_cpd = round(sum(cpd.values()) / max(1, len(cpd)), 2) if cpd else 0
        row = {
            "name": name,
            "full": s,
            "last10": s10,
            "today": st,
            "today_calls": [c.to_dict() for c in ct],
            "avg_calls_per_day": avg_cpd,
            "score": round(score(s), 3),
            "score_l10": round(score(s10, min_n=8), 3),
            "cfg": cfg,
        }
        rows.append(row)
        print(
            f"    n={s.get('n')} hit={s.get('hit_pct')} R={s.get('avg_R')} "
            f"sum={s.get('sum_pts')} cpd={avg_cpd} | "
            f"L10 {s10.get('n')} {s10.get('hit_pct')}% | "
            f"TD {st.get('n')} {st.get('hit_pct')}% {st.get('sum_pts')}",
            flush=True,
        )

    ranked = sorted(rows, key=lambda r: (r["score_l10"], r["score"]), reverse=True)
    # prefer FRVP or uncap that beats/holds vs v2f on hit while more calls
    v2f = next(r for r in rows if r["name"] == "v2f_cap3")
    prefer = [
        r
        for r in ranked
        if r["name"] != "v2f_cap3"
        and (r["full"].get("n") or 0) >= (v2f["full"].get("n") or 0)
        and (r["full"].get("hit_pct") or 0) >= (v2f["full"].get("hit_pct") or 0) - 3.0
        and (r["full"].get("avg_R") or -9) > 0
    ]
    if not prefer:
        prefer = [
            r
            for r in ranked
            if (r["full"].get("n") or 0) > (v2f["full"].get("n") or 0)
            and (r["last10"].get("hit_pct") or 0) >= 60
            and (r["full"].get("avg_R") or -9) > 0
        ]
    best = prefer[0] if prefer else ranked[0]
    best_name = best["name"]
    print(f"BEST={best_name}", flush=True)

    pa.save_locked_cfg(best["cfg"])
    (pa.HOLD / "locked_engine.json").write_text(
        json.dumps(
            {
                "engine": "structure_frvp",
                "name": best_name,
                "use_frvp": bool(best["cfg"].use_frvp),
                "frvp_mode": best["cfg"].frvp_mode if best["cfg"].use_frvp else None,
                "max_calls_day": best["cfg"].max_calls_day,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    ct = pa.scan_session(tb, settle=True, cfg=best["cfg"])
    pa.save_ledger(
        {
            "desk": pa.DESK,
            "logic_ver": "pa_frvp",
            "cfg_name": best_name,
            "calls": [],
        }
    )
    ledger = pa.append_live_calls(ct, mark_fire=True)

    lines = [
        f"# PA + FRVP more calls · {today}",
        "",
        f"**Locked:** `{best_name}` · max_calls/day={best['cfg'].max_calls_day} · "
        f"FRVP=`{best['cfg'].use_frvp}` mode=`{best['cfg'].frvp_mode if best['cfg'].use_frvp else '—'}`",
        "",
        "FRVP uses morning module (`fno_fixed_range_vp`) → **POC / VAH / VAL / HVN** as S/R quality.",
        "No hard 3-call cap — cooldown + optional FRVP proximity gate density.",
        "",
        "## Comparison",
        "",
        "| Book | Full N/Hit/R/Sum | Avg calls/day | L10 Hit | Today N/Hit/Sum | Score |",
        "|---|---|---:|---:|---|---:|",
    ]
    for r in ranked:
        f, l, t = r["full"], r["last10"], r["today"]
        mark = "**" if r["name"] == best_name else ""
        lines.append(
            f"| {mark}{r['name']}{mark} | {f.get('n')}/{f.get('hit_pct')}/{f.get('avg_R')}/{f.get('sum_pts')} | "
            f"{r['avg_calls_per_day']} | {l.get('hit_pct')} | "
            f"{t.get('n')}/{t.get('hit_pct')}/{t.get('sum_pts')} | {r['score_l10']} |"
        )

    st = best["today"]
    lines += [
        "",
        f"## Today `{best_name}`",
        "",
        f"n={st.get('n')} hit={st.get('hit_pct')} avgR={st.get('avg_R')} sum={st.get('sum_pts')}",
        "",
        "| HM | Side | Setup | Entry | SL | Risk | Exit | Pts | R |",
        "|---|---|---|---:|---:|---:|---|---:|---:|",
    ]
    for c in ct:
        lines.append(
            f"| {c.hm} | {c.side} | {c.setup} | {c.entry} | {c.stop_loss} | {c.risk} | "
            f"{c.exit_why} | {c.pts} | {c.R} |"
        )
    if not ct:
        lines.append("| — | — | no fires | — | — | — | — | — | — |")

    lines += [
        "",
        "## vs old cap3",
        "",
        f"| | v2f_cap3 | **{best_name}** |",
        "|---|---|---|",
        f"| N | {v2f['full'].get('n')} | **{best['full'].get('n')}** |",
        f"| Hit% | {v2f['full'].get('hit_pct')} | **{best['full'].get('hit_pct')}** |",
        f"| AvgR | {v2f['full'].get('avg_R')} | **{best['full'].get('avg_R')}** |",
        f"| Calls/day | {v2f['avg_calls_per_day']} | **{best['avg_calls_per_day']}** |",
        f"| Today N/Sum | {v2f['today'].get('n')}/{v2f['today'].get('sum_pts')} | "
        f"**{st.get('n')}/{st.get('sum_pts')}** |",
        "",
    ]
    OUT.mkdir(parents=True, exist_ok=True)
    MD.write_text("\n".join(lines), encoding="utf-8")
    TODAY_MD.write_text("\n".join(lines), encoding="utf-8")
    payload = {
        "best": best_name,
        "today": today,
        "ranked": [
            {
                "name": r["name"],
                "full": r["full"],
                "last10": r["last10"],
                "today": r["today"],
                "avg_calls_per_day": r["avg_calls_per_day"],
                "score_l10": r["score_l10"],
            }
            for r in ranked
        ],
        "today_calls": [c.to_dict() for c in ct],
        "ledger": ledger,
    }
    JS.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {MD}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
