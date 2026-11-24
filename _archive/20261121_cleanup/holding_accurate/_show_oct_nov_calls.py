import json
from pathlib import Path

p = Path(__file__).resolve().parents[1] / "reports" / "1y" / "ACC_PRIORITY_LEVELS_6M_1Y.json"
d = json.loads(p.read_text(encoding="utf-8"))
pris = ["P100", "P92", "P90", "P85", "P85B", "P80", "P75"]

lines = [
    "# P2F latest — each call Oct + Nov 2026",
    "",
    "**Level:** Phase-2f (latest held) · day-dedupe · no within-desk duplicates",
    "",
]

for pri in pris:
    key = f"P2F|{pri}"
    r = d["results"][key]
    calls = [
        c
        for c in r["calls_1y"]
        if str(c.get("day") or "").startswith(("2026-10", "2026-11"))
    ]
    lines += [
        f"## {pri} — `{r['candidate_tag']}` ({len(calls)} calls)",
        "",
        "| Day | HM | Side | Win | p_t1 | Pts | Tag |",
        "|---|---|---|---|---:|---:|---|",
    ]
    for c in calls:
        win = "W" if c.get("win") else "L"
        lines.append(
            f"| {c.get('day')} | {c.get('hm')} | {c.get('side')} | {win} | "
            f"{c.get('p_t1')} | {c.get('points')} | `{c.get('tag')}` |"
        )
    lines.append("")

# Cross-priority same-day map for Oct-Nov
lines += [
    "## Same calendar day across priorities (nested, not duplicates)",
    "",
    "| Day | Priorities that fired |",
    "|---|---|",
]
by_day = {}
for pri in pris:
    r = d["results"][f"P2F|{pri}"]
    for c in r["calls_1y"]:
        day = str(c.get("day") or "")
        if day.startswith(("2026-10", "2026-11")):
            by_day.setdefault(day, []).append(pri)
for day in sorted(by_day):
    lines.append(f"| {day} | {', '.join(by_day[day])} |")
lines.append("")

out = Path(__file__).resolve().parents[1] / "reports" / "1y" / "ACC_P2F_OCT_NOV_2026_CALLS.md"
out.write_text("\n".join(lines), encoding="utf-8")
print("Wrote", out)
for pri in pris:
    n = sum(
        1
        for c in d["results"][f"P2F|{pri}"]["calls_1y"]
        if str(c.get("day") or "").startswith(("2026-10", "2026-11"))
    )
    print(pri, n)
