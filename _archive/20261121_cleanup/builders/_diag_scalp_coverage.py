"""Oracle day coverage: can every day path-win T1=10 with SL<=12 structure?"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BUILDERS = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BUILDERS))
sys.path.insert(0, str(ROOT / "tools" / "research"))
import path_setup  # noqa: F401

import research_nifty_1m_dual_clean_train as base  # noqa: E402
import research_nifty_1m_chart_only_100 as co  # noqa: E402

PACK = ROOT / "stock_signal_data" / "fno_validate" / "research" / "nifty_1m_scalp_prevcandle_100"
REPORT_MD = ROOT / "prod_live" / "reports" / "1y" / "NIFTY_1M_SCALP_PREVCANDLE_100.md"


def lesser(e, st):
    p, s = e["sl_prev"], e["sl_sig"]
    return {
        "prev": p,
        "sig": s,
        "min": min(p, s) if s >= 4 else p,
        "cap8": min(p, 8.0),
        "cap10": min(p, 10.0),
        "cap12": min(p, 12.0),
        "p75": max(4.0, 0.75 * p),
    }[st]


def main() -> int:
    blob = pickle.load(next(PACK.glob("scalp_events_*.pkl")).open("rb"))
    cal, test = blob["cal"], blob["test"]
    raw = base.load_existing_1m()
    h = raw["High"].astype(float).values
    l = raw["Low"].astype(float).values
    c = raw["Close"].astype(float).values
    styles = ["prev", "sig", "min", "cap8", "cap10", "cap12", "p75"]
    lines = [
        "",
        "## Oracle coverage (path T1=10 · structure SL in 4–12)",
        "",
        "If some entry that day can win with tight structure stop:",
        "",
        "| Window | Days | Any style | Prev | Cap10 | Cap8 | MFE≥10 & SL≤12 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for name, pool in (("cal", cal), ("l3m", test)):
        days = sorted({e["day"] for e in pool})
        hit = {st: 0 for st in styles}
        hit_any = hit_mfe = hit_mfe_sl = 0
        miss = []
        for d in days:
            es = [e for e in pool if e["day"] == d]
            ok_any = False
            for st in styles:
                found = False
                for e in es:
                    sl = lesser(e, st)
                    if not (4 <= sl <= 12):
                        continue
                    if st == "prev" and e.get("prev_t10") == "win":
                        found = True
                        break
                    if st == "sig" and e.get("sig_t10") == "win":
                        found = True
                        break
                    win, out = co.path_hit(h, l, c, e["full_i"], e["decision"], float(sl), 10.0)
                    if win and out == "t1":
                        found = True
                        break
                if found:
                    hit[st] += 1
                    ok_any = True
            if ok_any:
                hit_any += 1
            else:
                miss.append(d)
            if any(e["mfe"] >= 10 for e in es):
                hit_mfe += 1
            if any(e["mfe"] >= 10 and 4 <= e["sl_prev"] <= 12 for e in es):
                hit_mfe_sl += 1
        n = len(days)
        lines.append(
            f"| {name} | {n} | {hit_any} | {hit['prev']} | {hit['cap10']} | "
            f"{hit['cap8']} | {hit_mfe_sl} |"
        )
        print(
            f"{name} days={n} any={hit_any} prev={hit['prev']} cap10={hit['cap10']} "
            f"cap8={hit['cap8']} mfe_sl12={hit_mfe_sl} miss={len(miss)}",
            flush=True,
        )
        if miss[:8]:
            print(f"  miss sample: {miss[:8]}", flush=True)

    md = REPORT_MD.read_text(encoding="utf-8")
    marker = "## Oracle coverage (path T1=10 · structure SL in 4–12)"
    if marker in md:
        md = md.split(marker)[0].rstrip()
    REPORT_MD.write_text(md + "\n" + "\n".join(lines) + "\n", encoding="utf-8")
    print("DONE coverage", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
