"""Show Sensex dual+fb combine last 19 sessions."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / "prod_live" / "tests" / "builders")]
import path_setup  # noqa: F401,E402

from research_bn_sensex_final_brackets import load_tape  # noqa: E402

HELD = ROOT / "prod_live" / "holding_accurate" / "sensex_final" / "champ_plus_t50_sl50_calls.json"
TAPE = ROOT / "stock_signal_data" / "fno_validate" / "SENSEX_5m_kite.csv"
OUT = ROOT / "prod_live" / "reports" / "1y" / "SENSEX_DUAL_FB_COMBINE_LAST19.md"
N_DAYS = 19


def main() -> int:
    held = json.loads(HELD.read_text(encoding="utf-8"))
    calls = held.get("calls") or []
    meta = held.get("meta") or {}
    policy = meta.get("policy") or {}

    bars, _ = load_tape(TAPE)
    if getattr(bars.index, "tz", None) is not None:
        bars = bars.copy()
        bars.index = bars.index.tz_localize(None)
    days = sorted({str(pd.Timestamp(t).date()) for t in bars.index})
    last = days[-N_DAYS:]

    by = {}
    for r in calls:
        d = str(r.get("day") or "")[:10]
        by.setdefault(d, []).append(r)

    print(f"Desk: {meta.get('desk')} mode={meta.get('mode')}")
    print(f"Logic: dual+fallback combine · no mutual block")
    print(f"LAST {N_DAYS}: {last[0]} → {last[-1]}")
    print()

    hdr = (
        f"{'Day':<12} {'HM':<6} {'Side':<5} {'Src':<14} "
        f"{'Entry':>10} {'Out':<16} {'Pts':>6}"
    )
    print(hdr)
    print("-" * len(hdr))

    tot_w = tot_l = tot_n = 0
    dual_n = fb_n = combo_n = 0
    lines = [
        f"# SENSEX dual+fb combine · last {N_DAYS} sessions",
        "",
        f"**Desk:** `{meta.get('desk')}`",
        f"**Mode:** `{meta.get('mode')}`",
        f"**Dual:** {policy.get('dual')}",
        f"**Fallback:** {policy.get('fallback')}",
        f"**Combine:** {policy.get('combine')}",
        f"**Clip:** ±50/50",
        "",
        f"**Sessions:** {last[0]} → {last[-1]} ({N_DAYS})",
        "",
        "| Day | HM | Side | Source | Entry | SL | T1 | Result | Pts | Tags |",
        "|---|---|---|---|---:|---:|---:|---|---:|---|",
    ]

    for d in last:
        rows = sorted(
            by.get(d) or [],
            key=lambda x: (str(x.get("hm") or ""), str(x.get("decision") or "")),
        )
        if not rows:
            print(f"{d:<12} — NO CALL —")
            lines.append(f"| {d} | — | — | — | — | — | — | NO CALL | — | — |")
            continue
        for i, r in enumerate(rows):
            win = r.get("win")
            pts = float(r.get("points") or 0)
            out = str(r.get("outcome") or "")
            src = str(r.get("source") or "")
            if src == "dual":
                dual_n += 1
            elif src == "fallback":
                fb_n += 1
            elif src == "dual+fallback":
                combo_n += 1
            if win is True:
                tot_w += 1
            elif win is False:
                tot_l += 1
            if win is not None:
                tot_n += 1
            tag = "W" if win is True else ("L" if win is False else "?")
            day_col = d if i == 0 else ""
            tags = ",".join(str(t) for t in (r.get("tags") or [])[:6])
            print(
                f"{day_col:<12} {str(r.get('hm') or '')[:5]:<6} "
                f"{str(r.get('decision') or ''):<5} {src:<14} "
                f"{float(r.get('entry') or 0):10.2f} {(tag + ' ' + out):<16} {pts:6.1f}"
            )
            lines.append(
                f"| {d if i == 0 else ''} | {str(r.get('hm') or '')[:5]} | "
                f"{r.get('decision')} | {src} | "
                f"{float(r.get('entry') or 0):.2f} | {float(r.get('stop_loss') or 0):.2f} | "
                f"{float(r.get('target_1') or 0):.2f} | {tag} {out} | {pts:.0f} | {tags} |"
            )
        known = [r for r in rows if r.get("win") is not None]
        dw = sum(1 for r in known if r.get("win"))
        print(
            f"{'':<12} day: {len(rows)} calls · {dw}/{len(known)} hit · "
            f"dual={sum(1 for r in rows if r.get('source')=='dual')} "
            f"fb={sum(1 for r in rows if r.get('source')=='fallback')} "
            f"combo={sum(1 for r in rows if r.get('source')=='dual+fallback')}"
        )
        print()
        lines.append(
            f"| | | | | | | | **day {len(rows)} · {dw}/{len(known)}** | | |"
        )

    hit = round(100.0 * tot_w / tot_n, 1) if tot_n else None
    print(
        f"TOTAL last{N_DAYS}: {tot_n} settled · W/L {tot_w}/{tot_l} · hit {hit}% · "
        f"dual={dual_n} fb={fb_n} combo={combo_n}"
    )
    lines += [
        "",
        f"**Total:** {tot_n} settled · W/L **{tot_w}/{tot_l}** · hit **{hit}%**",
        f"**Mix:** dual-only {dual_n} · fallback-only {fb_n} · combined {combo_n}",
        "",
    ]
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
