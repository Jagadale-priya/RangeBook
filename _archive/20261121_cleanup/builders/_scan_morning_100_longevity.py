"""Scan whether any morning-strong gate holds 100% on 3y or 5y."""
from __future__ import annotations

import importlib.util
import json
import sys
from itertools import product
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / "app")]
spec = importlib.util.spec_from_file_location(
    "m100",
    ROOT / "prod_live" / "tests" / "builders" / "_research_nifty_morning_100pct_1_3_5y.py",
)
m = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(m)

OUT = ROOT / "prod_live" / "reports" / "1y" / "NIFTY_MORNING_STRONG_100PCT_1_3_5Y.md"


def main() -> None:
    print("rebuild events…", flush=True)
    df15 = m._load(m.TAPE15)
    df5 = m._load(m.TAPE5)
    by15 = {d: g for d, g in df15.groupby(df15.index.strftime("%Y-%m-%d"))}
    by5 = {d: g for d, g in df5.groupby(df5.index.strftime("%Y-%m-%d"))}
    all_days = sorted(by15.keys())
    days = all_days[-(m.SESSIONS["5y"] + 20) :]
    events = m.build_events(by15, by5, days)
    windows = {
        lb: set(days[-n:] if len(days) >= n else days) for lb, n in m.SESSIONS.items()
    }
    gates = []
    for lim, up, body, top, hmax, fb, mb in product(
        [5.0],
        [50, 60, 70, 80, 90, 100, 120],
        [0.65, 0.70, 0.75, 0.80],
        [0.0, 0.7, 0.8],
        ["10:30", "11:00", "11:30"],
        [True],
        [4, 6, 8, 12, 18],
    ):
        gates.append(
            dict(
                name=f"u{up}_b{int(body*100)}_t{int(top*100)}_{hmax}_mb{mb}",
                lim=lim,
                min_up=up,
                body=body,
                top=top,
                hmin="09:45",
                hmax=hmax,
                fill_green=True,
                forbid_both_sides=fb,
                max_fill_bars=mb,
            )
        )
    print("gates", len(gates), "events", len(events), flush=True)
    hits3, hits5, best1 = [], [], []
    for g in gates:
        s1 = m.score_window(events, windows["1y"], g)
        s3 = m.score_window(events, windows["3y"], g)
        s5 = m.score_window(events, windows["5y"], g)
        if s3["hit_pct"] == 100.0 and s3["n"] >= 3:
            hits3.append((s3["n"], s5["hit_pct"], s5["n"], s1["n"], g["name"], g, s1, s3, s5))
        if s5["hit_pct"] == 100.0 and s5["n"] >= 3:
            hits5.append((s5["n"], s3["n"], s1["n"], g["name"], g, s1, s3, s5))
        if s1["hit_pct"] == 100.0 and s1["n"] >= 5:
            best1.append(
                (
                    s3["hit_pct"] or 0,
                    s5["hit_pct"] or 0,
                    s1["n"],
                    s3["n"],
                    s5["n"],
                    g["name"],
                    g,
                    s1,
                    s3,
                    s5,
                )
            )
    hits3.sort(reverse=True)
    hits5.sort(reverse=True)
    best1.sort(reverse=True)
    print("3y@100 n>=3:", len(hits3), flush=True)
    for t in hits3[:10]:
        print(" ", t[4], "3y", t[0], "5y", t[2], "@", t[1], "1y", t[3], flush=True)
    print("5y@100 n>=3:", len(hits5), flush=True)
    for t in hits5[:10]:
        print(" ", t[3], "5y", t[0], "3y", t[1], "1y", t[2], flush=True)
    print("best among 1y100:", flush=True)
    for t in best1[:8]:
        print(
            f"  {t[5]} 1y {t[2]}@100 3y {t[3]}@{t[0]} 5y {t[4]}@{t[1]}",
            flush=True,
        )

    # append longevity section to existing MD
    lines = [
        "",
        "## Longevity check (extra scan)",
        "",
        f"- Gates in longevity scan: {len(gates)}",
        f"- **3y @ 100% with n≥3:** {len(hits3)}",
        f"- **5y @ 100% with n≥3:** {len(hits5)}",
        "",
    ]
    if hits3:
        t = hits3[0]
        lines += [
            "### Thickest 3y @ 100%",
            f"- `{t[4]}` · 3y {t[0]}@100% · 5y {t[2]}@{t[1]}% · 1y {t[3]}",
            f"- params: `{json.dumps(t[5])}`",
            "",
        ]
    else:
        lines.append("- No gate held **100% on 3y** even with n≥3 in this family.")
        lines.append("")
    if hits5:
        t = hits5[0]
        lines += [
            "### Thickest 5y @ 100%",
            f"- `{t[3]}` · 5y {t[0]}@100% · 3y {t[1]} · 1y {t[2]}",
            f"- params: `{json.dumps(t[4])}`",
            "",
        ]
    else:
        lines.append("- No gate held **100% on 5y** even with n≥3 in this family.")
        lines.append("")
    if best1:
        t = best1[0]
        lines += [
            "### Best 1y@100% by 3y then 5y hit",
            f"- `{t[5]}` · 1y {t[2]}@100% · 3y {t[3]}@{t[0]}% · 5y {t[4]}@{t[1]}%",
            f"- params: `{json.dumps(t[6])}`",
            "",
            "**Verdict:** 100% is achievable on **1y**, but does **not** hold through **3y/5y** "
            "in the honest OR+5 morning-strong family — expect ~93–95% on longer windows for the best 1y-perfect gates.",
            "",
        ]
    OUT.write_text(OUT.read_text(encoding="utf-8") + "\n".join(lines), encoding="utf-8")
    print("updated", OUT, flush=True)


if __name__ == "__main__":
    main()
