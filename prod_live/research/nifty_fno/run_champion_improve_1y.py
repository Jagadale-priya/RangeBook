"""Research: tighten 5m/10m champion gates on last 1y.

Does not enter the accurate proven book — report only.

  python -u prod_live/research/nifty_fno/run_champion_improve_1y.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / "prod_live" / "research" / "nifty_fno")]

from logic.champion_improve import sweep_gates  # noqa: E402
from logic.proven_book import clip_window, first_per_day, summarize  # noqa: E402

LEDGER = ROOT / "stock_signal_data" / "fno_validate" / "research"
CACHE_15_5 = LEDGER / "_cache_dual15_dual5_10y.json"
CACHE_10 = LEDGER / "_cache_dual_packs_on_10m_1y.json"
OUT = Path(__file__).resolve().parent / "reports"
OUT_MD = OUT / "CHAMPION_IMPROVE_1Y.md"
OUT_JSON = OUT / "CHAMPION_IMPROVE_1Y.json"

END = "2026-11-13"
START_1Y = (pd.Timestamp(END) - pd.DateOffset(years=1)).strftime("%Y-%m-%d")


def _pct(x):
    return "n/a" if x is None else f"{100.0 * x:.1f}%"


def _f(x, nd=2):
    return "n/a" if x is None else f"{x:.{nd}f}"


def main() -> int:
    d = json.loads(CACHE_15_5.read_text(encoding="utf-8"))
    d10 = json.loads(CACHE_10.read_text(encoding="utf-8")) if CACHE_10.is_file() else {"dual10": {}}
    pools = {
        "champ_15m": d["dual15"]["champion"],
        "champ_5m": d["dual5"]["champion"],
        "champ_10m": (d10.get("dual10") or {}).get("champion") or [],
    }

    report = {}
    lines = [
        "# NIFTY F&O champion improve · last 1y",
        "",
        f"**Window:** {START_1Y} → {END}",
        "",
        "Raw champion is kept **out** of the accurate proven book. This sweep only",
        "asks whether tighter gates can rescue 5m/10m champion.",
        "",
    ]
    for name, rows in pools.items():
        raw = first_per_day(clip_window(rows, START_1Y, END))
        raw_s = summarize(raw)
        board = sweep_gates(rows, start=START_1Y, end=END, min_n=5)
        report[name] = {
            "raw": raw_s,
            "gates": [{"gate": b["gate"], "summary": b["summary"]} for b in board],
        }
        lines.append(f"## {name}")
        lines.append("")
        lines.append(
            f"Raw: n={raw_s['n']} hit={_pct(raw_s['hit_rate'])} net={_f(raw_s['net_points'])}"
        )
        lines.append("")
        lines.append("| Gate | N | Hit | Net | OK≥70% |")
        lines.append("|---|---:|---:|---:|---|")
        for b in board:
            s = b["summary"]
            lines.append(
                f"| {b['gate']} | {s['n']} | {_pct(s.get('hit_rate'))} | "
                f"{_f(s.get('net_points'))} | {'Y' if s.get('ok') else ''} |"
            )
        lines.append("")
        best = next((b for b in board if b["summary"].get("ok")), board[0] if board else None)
        if best:
            lines.append(
                f"Best under rules: `{best['gate']}` · "
                f"n={best['summary']['n']} hit={_pct(best['summary'].get('hit_rate'))} "
                f"net={_f(best['summary'].get('net_points'))}"
            )
            lines.append("")

    lines.append("## Verdict")
    lines.append("")
    lines.append(
        "- Accurate live research book stays **proven 15m (+ proven 10m fill)**."
    )
    lines.append(
        "- Promote a champion gate only if 5m/10m hold **hit ≥70%** with usable N."
    )

    OUT.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    OUT_JSON.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(f"wrote {OUT_MD}", flush=True)
    for name, pack in report.items():
        raw = pack["raw"]
        print(
            f"{name}: raw n={raw['n']} hit={_pct(raw.get('hit_rate'))} "
            f"net={_f(raw.get('net_points'))}",
            flush=True,
        )
        ok = [g for g in pack["gates"] if g["summary"].get("ok")]
        if ok:
            g = ok[0]
            print(
                f"  ok gate={g['gate']} n={g['summary']['n']} "
                f"hit={_pct(g['summary'].get('hit_rate'))}",
                flush=True,
            )
        else:
            print("  no gate cleared hit≥70% with n≥5", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
