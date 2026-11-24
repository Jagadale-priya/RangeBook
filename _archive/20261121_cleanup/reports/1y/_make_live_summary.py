"""Build readable LIVE_LOGIC_1Y_SUMMARY.md from JSON."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
d = json.loads((HERE / "LIVE_LOGIC_1Y_MULTITAG.json").read_text(encoding="utf-8"))
c = d["combined"]
lines: list[str] = []
lines.append("# LIVE logic 1y — summary (readable)")
lines.append("")
lines.append(
    f"**Window:** `{d['window']['start']}` → `{d['window']['end']}` · "
    f"**{d['window']['sessions']}** sessions"
)
lines.append(
    f"**Blocked:** **0** · Overlap days: **{c['overlap_days']}** · "
    "Policy: never block / notify"
)
lines.append("")
lines.append("## Headline")
lines.append("")
lines.append("| Slice | N | Hit |")
lines.append("|---|---:|---:|")
for k, label in [
    ("volume_stack", "Volume stack"),
    ("volume_plus_agree", "Volume + AGREE"),
]:
    s = d["components"][k]
    lines.append(f"| {label} | {s['n']} | {s['hit_pct']}% |")
for k, s in d["components"].items():
    if k.startswith("day|"):
        lines.append(f"| P2F day `{k[4:]}` | {s['n']} | {s['hit_pct']}% |")
for k, s in d["components"].items():
    if k.startswith("cap2|"):
        lines.append(f"| P2F Cap2 `{k[5:]}` | {s['n']} | {s['hit_pct']}% |")
lines.append(f"| **Combined all** | **{c['n_all_rows']}** | **{c['hit_all']}%** |")
lines.append(f"| **Primary only** | **{c['n_primary']}** | **{c['hit_primary']}%** |")
lines.append("")
lines.append("## Month summary")
lines.append("")
lines.append(
    "| Month | Sess | All N | All hit | Primary N | Primary hit | "
    "Vol | Day | Cap2 | Notify | Blocked |"
)
lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
for m in d["months"]:
    lines.append(
        f"| {m['month']} | {m['sessions']} | {m['n_all']} | {m['hit_all']}% | "
        f"{m['n_primary']} | {m['hit_primary']}% | {m['volume_n']} | "
        f"{m['p2f_day_n']} | {m['p2f_cap2_n']} | {m['notify_n']} | 0 |"
    )
lines.append("")
lines.append("## Primary calls only (per month)")
lines.append("")
for m in d["months"]:
    prim = [x for x in m["calls"] if x.get("is_primary")]
    lines.append(f"### {m['month']} — {len(prim)} primary")
    lines.append("")
    lines.append(
        "| Day | HM | Side | Book | accurate_tag | accuracy_tag | Win | Multi-tags |"
    )
    lines.append("|---|---|---|---|---|---|---|---|")
    for c0 in prim:
        tags = ", ".join((c0.get("tags") or [])[:6])
        win = "W" if c0.get("win") else "L"
        lines.append(
            f"| {c0['day']} | {c0.get('hm') or ''} | {c0.get('decision') or ''} | "
            f"{c0.get('book') or ''} | `{c0.get('accurate_tag') or ''}` | "
            f"`{c0.get('accuracy_tag') or ''}` | {win} | {tags} |"
        )
    lines.append("")

out = HERE / "LIVE_LOGIC_1Y_SUMMARY.md"
out.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("wrote", out)
