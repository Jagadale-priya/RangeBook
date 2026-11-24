"""Union MFE-target-reached cells (scalp insight)."""
from __future__ import annotations

import pickle
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BUILDERS = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BUILDERS))
sys.path.insert(0, str(ROOT / "tools" / "research"))
import path_setup  # noqa: F401

PACK = ROOT / "stock_signal_data" / "fno_validate" / "research" / "nifty_1m_scalp_prevcandle_100"
OUT = ROOT / "prod_live" / "reports" / "1y"
REPORT_MD = OUT / "NIFTY_1M_SCALP_PREVCANDLE_100.md"


def cell_key(e):
    return (
        e["primary"],
        e["decision"],
        e["pre_regime"],
        int(e["align_session"]),
        e["clock"],
        "b45+" if e["body_frac"] >= 0.45 else "b<45",
        "sl<=10"
        if e["sl_prev"] <= 10
        else ("sl<=15" if e["sl_prev"] <= 15 else ("sl<=20" if e["sl_prev"] <= 20 else "sl>20")),
        "rsi_lo" if e["rsi_14"] < 40 else ("rsi_mid" if e["rsi_14"] <= 60 else "rsi_hi"),
    )


def main() -> int:
    blob = pickle.load(next(PACK.glob("scalp_events_*.pkl")).open("rb"))
    cal, test = blob["cal"], blob["test"]
    cells = []
    cal_c, test_c = defaultdict(list), defaultdict(list)
    for e in cal:
        if 4 <= e["sl_prev"] <= 20:
            cal_c[cell_key(e)].append(e)
    for e in test:
        if 4 <= e["sl_prev"] <= 20:
            test_c[cell_key(e)].append(e)
    for k, es in cal_c.items():
        by = {}
        for e in sorted(es, key=lambda x: x["mins"]):
            by.setdefault(e["day"], e)
        rows = list(by.values())
        if len(rows) < 3 or any(e["mfe"] < 10 for e in rows):
            continue
        te = test_c.get(k, [])
        by2 = {}
        for e in sorted(te, key=lambda x: x["mins"]):
            by2.setdefault(e["day"], e)
        rows2 = list(by2.values())
        if len(rows2) < 1 or any(e["mfe"] < 10 for e in rows2):
            continue
        pw = sum(1 for e in rows2 if e.get("prev_t10") == "win")
        cells.append(
            {
                "k": k,
                "cal_n": len(rows),
                "l3m_n": len(rows2),
                "avg_sl": sum(e["sl_prev"] for e in rows2) / len(rows2),
                "path_win_l3m": pw / len(rows2),
                "cal_days": [e["day"] for e in rows],
                "l3m_days": [e["day"] for e in rows2],
                "calls": rows2,
            }
        )
    cells.sort(key=lambda r: (-r["l3m_n"], r["avg_sl"], -r["cal_n"]))

    def pack(pool, max_sl=None):
        used_c, used_t = set(), set()
        chosen, calls = [], []
        for r in pool:
            if max_sl is not None and r["avg_sl"] > max_sl:
                continue
            ca, lt = set(r["cal_days"]), set(r["l3m_days"])
            if ca & used_c or lt & used_t:
                continue
            chosen.append(r)
            used_c |= ca
            used_t |= lt
            calls.extend(r["calls"])
        return chosen, used_c, used_t, calls

    c1, uc, ut, calls = pack(cells)
    c2, uc2, ut2, calls2 = pack(cells, max_sl=12)
    print(f"MFE union T1=10: cal {len(uc)} l3m {len(ut)} micros={len(c1)}", flush=True)
    print(f"Tight avgSL<=12: cal {len(uc2)} l3m {len(ut2)} micros={len(c2)}", flush=True)
    for r in c1[:8]:
        print(
            f"  l3m{r['l3m_n']} cal{r['cal_n']} avgSL={r['avg_sl']:.1f} "
            f"pathWin={r['path_win_l3m']*100:.0f}% {r['k']}",
            flush=True,
        )

    # append to report
    lines = [
        "",
        "## Target-reached union (MFE≥10 always · prev-candle structure)",
        "",
        f"- Full union: **{len(uc)} cal days / {len(ut)} last3m days** · {len(c1)} micros",
        f"- Tight avg prev-SL ≤12: **{len(uc2)} / {len(ut2)} days** · {len(c2)} micros",
        "",
        "Best micros (target always prints; SL = prev candle as insurance):",
        "",
        "| Cal | L3m | Avg SL | Path-win% | Cell |",
        "|---:|---:|---:|---:|---|",
    ]
    for r in c1[:12]:
        lines.append(
            f"| {r['cal_n']} | {r['l3m_n']} | {r['avg_sl']:.1f} | "
            f"{r['path_win_l3m']*100:.0f} | `{r['k']}` |"
        )
    lines += [
        "",
        "### Example tight champion cell",
        "",
        "`belt_bear` SELL · continuation · align · late · body≥0.45 · prev-SL≤10 · RSI low",
        "",
        "| Day | HM | Side | PrevSL | MFE | Path T1 before SL |",
        "|---|---|---|---:|---:|---|",
    ]
    # find that cell in c1 or c2
    ex = next((r for r in c1 if r["k"][0] == "belt_bear" and "sl<=10" in r["k"]), c1[0] if c1 else None)
    if ex:
        for e in sorted(ex["calls"], key=lambda x: x["day"])[:15]:
            lines.append(
                f"| {e['day']} | {e['hm']} | {e['decision']} | {e['sl_prev']:.1f} | "
                f"{e['mfe']:.1f} | {e.get('prev_t10')} |"
            )

    md = REPORT_MD.read_text(encoding="utf-8")
    if "## Target-reached union" not in md:
        REPORT_MD.write_text(md.rstrip() + "\n" + "\n".join(lines) + "\n", encoding="utf-8")
    print(f"updated {REPORT_MD}", flush=True)
    print("DONE mfe union", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
