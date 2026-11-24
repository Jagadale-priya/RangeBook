"""Format NIFTY_SENSEX_LIVE_30D.json into per-day date/time sorted markdown."""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "prod_live" / "reports" / "1y" / "NIFTY_SENSEX_LIVE_30D.json"
OUT = ROOT / "prod_live" / "reports" / "1y" / "NIFTY_SENSEX_LIVE_30D_BY_DAY.md"


def main() -> int:
    d = json.loads(SRC.read_text(encoding="utf-8"))
    rows = []
    for r in d["nifty"]["calls"]:
        rows.append({**r, "symbol": "NIFTY"})
    for r in d["sensex"]["calls"]:
        rows.append({**r, "symbol": "SENSEX"})
    rows.sort(key=lambda x: (x.get("day") or "", x.get("hm") or "", x.get("symbol") or ""))
    by = defaultdict(list)
    for r in rows:
        by[r["day"]].append(r)
    all_days = sorted(set(list(d["nifty"]["by_day"]) + list(d["sensex"]["by_day"])))
    start, end = d["window"]["start"], d["window"]["end"]

    lines = [
        "# NIFTY + SENSEX · live 30d · each day · date/time sorted",
        "",
        f"**Window:** `{start}` → `{end}`",
        f"**NIFTY:** {d['nifty']['overall']['n']} @ {d['nifty']['overall']['hit_pct']}% · "
        f"**SENSEX:** {d['sensex']['overall']['n']} @ {d['sensex']['overall']['hit_pct']}%",
        "",
    ]
    for day in all_days:
        rs = by.get(day) or []
        lines.append(f"## {day}")
        lines.append("")
        if not rs:
            lines.append("_No calls_")
            lines.append("")
            continue
        lines.append("| Time | Symbol | Side | Source | Track | Win | Pts |")
        lines.append("|---|---|---|---|---|---|---:|")
        for r in rs:
            w = "W" if r.get("win") is True else ("L" if r.get("win") is False else "?")
            lines.append(
                f"| {r.get('hm')} | **{r.get('symbol')}** | {r.get('decision')} | "
                f"{r.get('source')} | {r.get('track')} | {w} | {r.get('points')} |"
            )
        lines.append("")

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUT} · days={len(all_days)} calls={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
