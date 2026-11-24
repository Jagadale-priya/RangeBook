"""Build complete held desks registry + DESKS.md (P1→P2F) with multi-tags.

Each desk stamps:
  accurate_tag          — desk identity
  accuracy_tag          — ACC_RANGE_lo_hi (hit% range across research windows)
  accuracy_range_tag    — same as accuracy_tag (alias)
  accuracy_band         — A_PERFECT… / B_HIGH_90 / …
  tags[]                — all of the above as a multi-tag list
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

HOLD = Path(__file__).resolve().parent
ROOT = HOLD.parent
sys.path.insert(0, str(ROOT.parent))

from prod_live.logic.accurate_desks import DESK_REGISTRY  # noqa: E402

FLOOR = {
    "PROVEN15_PLUS_CONFIRM_T30": 100.0,
    "ACC100_MULTI_V1": 100.0,
    "ACC100_MULTI_V2": 100.0,
    "ACC100_MULTI_V3": 100.0,
    "ACC100_MULTI_V4": 100.0,
    "ACC100_MULTI_V5": 100.0,
    "ACC_WIDE_P92": 99.24,
    "ACC_WIDE_P90": 95.4,
    "ACC_WIDE_P85": 89.69,
    "ACC_WIDE_P85B": 88.4,
    "ACC_WIDE_P80": 84.72,
    "ACC_WIDE_P75": 82.71,
    "ACC_WIDE_P80_CAP2": 84.72,
    "ACC_WIDE_P75_CAP2": 82.71,
}

P1_LOGIC = {
    "PROVEN15_PLUS_CONFIRM_T30": "Proven15 ∪ dual-TF confirm T30 only · day-dedupe",
    "ACC100_MULTI_V1": "Crown BUY AM≤11:30 T20 + Good BUY latemid gap≥0.45 T30 · 100% nested core",
    "ACC100_MULTI_V2": "V1 ∪ more path-true 100% streams (good/crown expansions)",
    "ACC100_MULTI_V3": "V2 ∪ deeper 100% streams",
    "ACC100_MULTI_V4": "V3 ∪ deeper 100% streams",
    "ACC100_MULTI_V5": "V4 ∪ dual15 + more good/crown 100% streams · Phase-1 lock core",
    "ACC_WIDE_P92": "Wide day-dedupe ladder @ floor ≥99.24% 3y · contains V5 family streams",
    "ACC_WIDE_P90": "Wide day-dedupe @ floor ≥95.4% · contains P92",
    "ACC_WIDE_P85": "Wide day-dedupe @ floor ≥89.69% · contains P90",
    "ACC_WIDE_P85B": "Wide day-dedupe @ floor ≥88.4% · contains P85",
    "ACC_WIDE_P80": "Wide day-dedupe @ floor ≥84.72% · contains P85B",
    "ACC_WIDE_P75": "Widest day-dedupe @ floor ≥82.71% · contains P80",
    "ACC_WIDE_P80_CAP2": "P80 family with day-cap2 (≤2 same-side/day)",
    "ACC_WIDE_P75_CAP2": "P75 family with day-cap2 (≤2 same-side/day)",
}

PHASE_NOTE = {
    "P2C": "Phase-1 base ∪ greedily added path-true stream tags (P2/P2b/P2c) keeping floor",
    "P2D": "P2C seed ∪ denser mine · same floor · more calls",
    "P2E": "P2D seed ∪ last/second picks · cross-CF · day_side · same floor",
    "P2F": "P2E seed ∪ micro-bands · weekday · mid pick · triple-CF · same floor (latest)",
}

BAND_TAG = {
    "A_PERFECT_3Y5Y": "ACC_BAND_A_PERFECT_3Y5Y",
    "B_HIGH_90": "ACC_BAND_B_HIGH_90",
    "C_MID_85": "ACC_BAND_C_MID_85",
    "D_VOL_80": "ACC_BAND_D_VOL_80",
    "E_VOL_75": "ACC_BAND_E_VOL_75",
}

LEVEL_FILES = [
    ("P2C", HOLD / "recipes.json", "stream_tags_held", "held_3y"),
    ("P2D", HOLD / "phase2d" / "recipes_research.json", "stream_tags_research", "research_3y"),
    ("P2E", HOLD / "phase2e" / "recipes_research.json", "stream_tags_research", "research_3y"),
    ("P2F", HOLD / "phase2f" / "recipes_research.json", "stream_tags_research", "research_3y"),
]


def meta_for_base(base_key: str) -> dict:
    if base_key in DESK_REGISTRY:
        return DESK_REGISTRY[base_key]
    day = base_key.replace("_CAP2", "")
    if day + "_CAP2" in DESK_REGISTRY:
        return DESK_REGISTRY[day + "_CAP2"]
    if day in DESK_REGISTRY:
        return DESK_REGISTRY[day]
    return {
        "accuracy_range": "ACC_RANGE_98_100",
        "accuracy_lo": 98.17,
        "accuracy_hi": 100.0,
        "band": "A_PERFECT_3Y5Y",
    }


def floor_tag(floor: float | None) -> str | None:
    if floor is None:
        return None
    # integer-ish → ACC_FLOOR_100; else ACC_FLOOR_82p71
    if abs(floor - round(floor)) < 0.05:
        return f"ACC_FLOOR_{int(round(floor))}"
    return "ACC_FLOOR_" + f"{floor:g}".replace(".", "p")


def build_tags(
    *,
    accurate_tag: str,
    accuracy_tag: str,
    accuracy_band: str,
    floor: float | None,
    logic_level: str,
) -> list[str]:
    """Multi-tag list stamped on every row (order stable)."""
    out = [accurate_tag, accuracy_tag]
    band_t = BAND_TAG.get(accuracy_band)
    if band_t:
        out.append(band_t)
    ft = floor_tag(floor)
    if ft:
        out.append(ft)
    out.append(f"LOGIC_{logic_level}")
    # de-dupe preserve order
    seen = set()
    uniq = []
    for t in out:
        if t and t not in seen:
            seen.add(t)
            uniq.append(t)
    return uniq


def load_candidates(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8")).get("candidates") or {}


def enrich(desk: dict) -> dict:
    ar = desk["accuracy_range_tag"]
    desk["accuracy_tag"] = ar  # primary accuracy-range tag name
    desk["accuracy_range_tag"] = ar
    tags = build_tags(
        accurate_tag=desk["accurate_tag"],
        accuracy_tag=ar,
        accuracy_band=desk.get("accuracy_band") or "",
        floor=desk.get("floor"),
        logic_level=desk["logic_level"],
    )
    desk["tags"] = tags
    desk["accuracy_note"] = (
        f"Hit-target accuracy range {desk.get('accuracy_lo')}–{desk.get('accuracy_hi')}% "
        f"(min/max across 3y/5y/10y research windows for this desk family)"
    )
    return desk


desks: dict = {}

# Phase-1
for tag, meta in DESK_REGISTRY.items():
    ar = meta["accuracy_range"]
    band = meta.get("band") or ""
    desks[tag] = enrich(
        {
            "accurate_tag": tag,
            "desk_tag": tag,
            "logic_level": "P1",
            "status": "LOCKED",
            "mode": "cap2" if "CAP2" in tag else "day",
            "accuracy_range_tag": ar,
            "accuracy_band": band,
            "accuracy_lo": meta.get("accuracy_lo"),
            "accuracy_hi": meta.get("accuracy_hi"),
            "floor": FLOOR.get(tag),
            "research_3y": dict(meta.get("research_3y") or {}),
            "base_desk": tag,
            "base_key": tag,
            "stream_count": None,
            "logic": P1_LOGIC.get(tag, "Phase-1 locked accurate desk"),
            "lane": "HOLDING",
            "not_live": True,
            "kind": "phase1_locked",
            "recipes": "prod_live/logic/acc100_streams.py",
        }
    )

# Phase expansions
for level, path, tag_key, n_key in LEVEL_FILES:
    for base, meta in load_candidates(path).items():
        cand = meta.get("candidate_tag") or f"{base}_{level}"
        p1m = meta_for_base(base)
        ar = p1m["accuracy_range"]
        band = p1m.get("band") or ""
        held = meta.get(n_key) or meta.get("held_3y") or meta.get("research_3y") or {}
        tags_s = meta.get(tag_key) or meta.get("stream_tags_held") or meta.get("stream_tags_research") or []
        mode = meta.get("mode") or ("cap2" if "CAP2" in base else "day")
        floor = meta.get("floor") or FLOOR.get(base) or FLOOR.get(base.replace("_CAP2", ""))
        base_desk = meta.get("base_desk") or base.replace("_CAP2", "")
        # P2F day + Cap2 desks are promoted to LIVE accurate book
        p2f_live = level == "P2F" and mode in ("day", "cap2")
        kind = (
            "live_p2f_day"
            if (level == "P2F" and mode == "day")
            else ("live_p2f_cap2" if (level == "P2F" and mode == "cap2") else f"holding_{level.lower()}")
        )
        desks[cand] = enrich(
            {
                "accurate_tag": cand,
                "desk_tag": cand,
                "logic_level": level,
                "status": "PROMOTED" if p2f_live else "HELD",
                "mode": mode,
                "accuracy_range_tag": ar,
                "accuracy_band": band,
                "accuracy_lo": p1m.get("accuracy_lo"),
                "accuracy_hi": p1m.get("accuracy_hi"),
                "floor": floor,
                "research_3y": {"n": held.get("n"), "hit_pct": held.get("hit_pct")},
                "base_desk": base_desk,
                "base_key": base,
                "stream_count": len(tags_s),
                "logic": (
                    f"{PHASE_NOTE[level]} · base=`{base}` · mode={mode} · "
                    f"merge={'cap2≤2 same-side' if mode == 'cap2' else '1 call/day'}"
                ),
                "lane": "LIVE" if p2f_live else "HOLDING",
                "not_live": (not p2f_live),
                "promoted": bool(p2f_live),
                "kind": kind,
                "recipes": str(path.relative_to(HOLD.parent.parent)).replace("\\", "/"),
            }
        )

payload = {
    "status": "HELD_COMPLETE",
    "latest_level": "P2F",
    "lane": "HOLDING",
    "not_live": True,
    "keep_all_levels": True,
    "multi_tag": True,
    "stamp_fields": [
        "lane",
        "logic_level",
        "desk_tag",
        "accurate_tag",
        "accuracy_tag",
        "accuracy_range_tag",
        "accuracy_lo",
        "accuracy_hi",
        "accuracy_band",
        "tags",
    ],
    "tag_roles": {
        "accurate_tag": "Desk / channel identity",
        "accuracy_tag": "Hit-target accuracy range (ACC_RANGE_lo_hi)",
        "accuracy_range_tag": "Alias of accuracy_tag",
        "accuracy_band": "Band group A–E",
        "ACC_FLOOR_*": "Desk 3y hit floor",
        "LOGIC_*": "Logic level P1/P2C/…/P2F",
        "tags": "All of the above as a list (multi-tag OK)",
    },
    "desks": desks,
}
(HOLD / "desks_held.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

# --- DESKS.md ---
lines = [
    "# Held accurate desks — complete logic + multi-tags",
    "",
    "**Status:** `HELD_COMPLETE` · **Latest:** Phase-2f · **Lane:** `HOLDING` (not live)",
    "",
    "Keep **every** level (P1 → P2F). Live stays on `FINAL_LOGIC.md`.",
    "",
    "## Multi-tag stamp (every row)",
    "",
    "Each call carries **multiple tags** — desk identity **and** hit-accuracy range:",
    "",
    "```",
    "lane=HOLDING",
    "logic_level=P2F",
    "desk_tag=ACC100_MULTI_V11",
    "accurate_tag=ACC100_MULTI_V11          # desk / channel",
    "accuracy_tag=ACC_RANGE_98_100          # hit-target accuracy range",
    "accuracy_range_tag=ACC_RANGE_98_100    # same (alias)",
    "accuracy_lo=98.17",
    "accuracy_hi=100.0",
    "accuracy_band=A_PERFECT_3Y5Y",
    "tags=[ACC100_MULTI_V11, ACC_RANGE_98_100, ACC_BAND_A_PERFECT_3Y5Y, ACC_FLOOR_100, LOGIC_P2F]",
    "```",
    "",
    "| Tag field | Meaning |",
    "|---|---|",
    "| `accurate_tag` | Which desk / channel fired |",
    "| `accuracy_tag` / `ACC_RANGE_*` | Research hit% range (lo–hi across 3y/5y/10y) for that desk family |",
    "| `ACC_BAND_*` | Band group (perfect / high-90 / mid-85 / vol-80 / vol-75) |",
    "| `ACC_FLOOR_*` | 3y hit floor used when building the desk |",
    "| `LOGIC_*` | Logic level |",
    "",
    "Machine registry: `desks_held.json`",
    "",
    "## How a desk is built",
    "",
    "1. **Phase-1** — fixed stream recipes in `logic/acc100_streams.py` (LOCKED).",
    "2. **Phase-2c…2f** — start from Phase-1 desk, **greedily union** mined path-true",
    "   stream tags that keep the desk’s **3y hit floor**.",
    "3. **Day mode** = 1 call/day. **Cap2 mode** = ≤2 same-side calls/day.",
    "4. Nested priorities share calendar days across desks; **no within-desk day dups**.",
    "",
    "## Accuracy-range tags (hit target %)",
    "",
    "| accuracy_tag | Lo–Hi % | Band | Example desks |",
    "|---|---|---|---|",
    "| `ACC_RANGE_100_100` | 100–100 | A | `PROVEN15_PLUS_CONFIRM_T30` |",
    "| `ACC_RANGE_96_100` | 96.62–100 | A | `ACC100_MULTI_V1` |",
    "| `ACC_RANGE_97_100` | 97.8–100 | A | V2, V3, V4 |",
    "| `ACC_RANGE_98_100` | 98.17–100 | A | V5, V8–V11, Cap2_P2F |",
    "| `ACC_RANGE_91_100` | 91.1–99.24 | B | P92 ladder |",
    "| `ACC_RANGE_89_96` | 89.88–95.4 | B | P90 ladder |",
    "| `ACC_RANGE_84_90` | 84–89.88 | C | P85 ladder |",
    "| `ACC_RANGE_81_89` | 81.1–88.4 | C | P85B ladder |",
    "| `ACC_RANGE_76_85` | 76.63–84.72 | D | P80 day |",
    "| `ACC_RANGE_77_87` | 77.7–86.29 | D | P80 Cap2 |",
    "| `ACC_RANGE_75_83` | 75.15–82.71 | E | P75 day |",
    "| `ACC_RANGE_75_84` | 75.5–83.39 | E | P75 Cap2 |",
    "",
    "## Latest recommended stamps (P2F)",
    "",
    "| Priority | accurate_tag | accuracy_tag | Lo–Hi | Floor | Mode | 3y N @ hit |",
    "|---:|---|---|---|---:|---|---|",
]

p2f_order = [
    "ACC100_MULTI_V11",
    "ACC100_MULTI_V5_CAP2_P2F",
    "ACC_WIDE_P92_P2F",
    "ACC_WIDE_P90_P2F",
    "ACC_WIDE_P85_P2F",
    "ACC_WIDE_P85B_P2F",
    "ACC_WIDE_P80_P2F",
    "ACC_WIDE_P75_P2F",
    "ACC_WIDE_P92_CAP2_P2F",
    "ACC_WIDE_P90_CAP2_P2F",
    "ACC_WIDE_P85_CAP2_P2F",
]
pri = 1
for tag in p2f_order:
    m = desks[tag]
    r = m["research_3y"]
    lines.append(
        f"| {pri} | `{tag}` | `{m['accuracy_tag']}` | "
        f"{m.get('accuracy_lo')}–{m.get('accuracy_hi')} | {m.get('floor')} | {m['mode']} | "
        f"{r.get('n')} @ {r.get('hit_pct')}% |"
    )
    pri += 1

lines += ["", "## All desks by logic level", ""]

by = defaultdict(list)
for tag, m in desks.items():
    by[m["logic_level"]].append((tag, m))

level_titles = {
    "P1": "Phase-1 LOCKED",
    "P2C": "Phase-2c HELD",
    "P2D": "Phase-2d HELD",
    "P2E": "Phase-2e HELD",
    "P2F": "Phase-2f HELD (latest)",
}


def sort_key(item):
    tag, m = item
    order = [
        "PROVEN",
        "ACC100_MULTI_V1",
        "ACC100_MULTI_V2",
        "ACC100_MULTI_V3",
        "ACC100_MULTI_V4",
        "ACC100_MULTI_V5",
        "ACC100_MULTI_V8",
        "ACC100_MULTI_V9",
        "ACC100_MULTI_V10",
        "ACC100_MULTI_V11",
        "ACC100_MULTI_V5_CAP2",
        "ACC_WIDE_P92",
        "ACC_WIDE_P90",
        "ACC_WIDE_P85",
        "ACC_WIDE_P85B",
        "ACC_WIDE_P80",
        "ACC_WIDE_P75",
    ]
    for i, pref in enumerate(order):
        if tag.startswith(pref):
            return (i, 0 if "CAP2" not in tag else 1, tag)
    return (99, 0, tag)


for lv in ["P1", "P2C", "P2D", "P2E", "P2F"]:
    lines += [f"### {level_titles[lv]}", ""]
    if lv != "P1":
        lines += [f"_{PHASE_NOTE[lv]}_", ""]
    lines += [
        "| accurate_tag | accuracy_tag | Lo–Hi | Floor | Mode | 3y N | Hit% | tags |",
        "|---|---|---|---:|---|---:|---:|---|",
    ]
    for tag, m in sorted(by[lv], key=sort_key):
        r = m["research_3y"]
        tags_s = ", ".join(f"`{t}`" for t in m.get("tags") or [])
        lines.append(
            f"| `{tag}` | `{m['accuracy_tag']}` | {m.get('accuracy_lo')}–{m.get('accuracy_hi')} | "
            f"{m.get('floor')} | {m['mode']} | {r.get('n')} | {r.get('hit_pct')} | {tags_s} |"
        )
    lines.append("")

lines += [
    "## Logic detail — Phase-2f desks (latest)",
    "",
]
for tag, _ in sorted(by["P2F"], key=sort_key):
    m = desks[tag]
    r = m["research_3y"]
    lines += [
        f"### `{tag}`",
        "",
        f"- **accurate_tag:** `{tag}`",
        f"- **accuracy_tag:** `{m['accuracy_tag']}` ({m.get('accuracy_lo')}–{m.get('accuracy_hi')}%)",
        f"- **tags:** {', '.join('`'+t+'`' for t in m.get('tags') or [])}",
        f"- **logic_level:** `P2F` · base=`{m.get('base_key')}` · mode={m['mode']} · floor={m.get('floor')}",
        f"- **3y:** {r.get('n')} @ {r.get('hit_pct')}% · streams={m.get('stream_count')}",
        f"- **logic:** {m['logic']}",
        "",
    ]

(HOLD / "DESKS.md").write_text("\n".join(lines), encoding="utf-8")
print("Wrote desks_held.json + DESKS.md · desks=", len(desks), "multi_tag=True")
for lv in ["P1", "P2C", "P2D", "P2E", "P2F"]:
    print(f"  {lv}: {len(by[lv])}")
# sample
s = desks["ACC100_MULTI_V11"]
print("sample V11 tags:", s["tags"], "accuracy_tag:", s["accuracy_tag"], f"{s['accuracy_lo']}-{s['accuracy_hi']}")
