"""Generate measured ACC_RANGE_* stamps for P2G 10m desks from 5y confirm.

Uses min/max hit% across 1y · 3y · 5y · extra_2y so the range tag actually
covers every measured window (not the copied P2F ranges).

  python -u prod_live/tests/builders/stamp_p2g_10m_accuracy_tags.py
"""
from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
import path_setup  # noqa: F401,E402

REP5 = ROOT / "prod_live" / "reports" / "5y" / "ACC_PHASE2G_10M_5Y.json"
OUT_MD = ROOT / "prod_live" / "reports" / "5y" / "ACC_PHASE2G_10M_ACCURACY_TAGS.md"
OUT_JS = ROOT / "prod_live" / "holding_accurate" / "phase2g" / "accuracy_tags.json"
LOGIC = ROOT / "prod_live" / "logic" / "p2g_10m.py"
RECIPES = ROOT / "prod_live" / "holding_accurate" / "phase2g" / "recipes_research.json"
DESKS_MD = ROOT / "prod_live" / "holding_accurate" / "DESKS.md"
DESKS_JS = ROOT / "prod_live" / "holding_accurate" / "desks_held.json"

WINDOWS = ("extra_2y", "3y", "5y", "1y")


def floor_tag(floor: float) -> str:
    if float(floor) == int(floor):
        return f"ACC_FLOOR_{int(floor)}"
    return f"ACC_FLOOR_{str(floor).replace('.', 'p')}"


def band_for(lo: float) -> str:
    if lo >= 98.0:
        return "A_PERFECT_3Y5Y"
    if lo >= 90.0:
        return "B_HIGH_90"
    if lo >= 85.0:
        return "C_MID_85"
    if lo >= 80.0:
        return "D_VOL_80"
    return "E_VOL_75"


def range_tag(lo: float, hi: float) -> str:
    return f"ACC_RANGE_{int(math.floor(lo))}_{int(math.ceil(hi))}"


def hits_of(block: Dict[str, Any]) -> List[Tuple[str, float, int]]:
    out = []
    for w in WINDOWS:
        st = block.get(w) or {}
        hp = st.get("hit_pct")
        n = int(st.get("n") or 0)
        if hp is None or n <= 0:
            continue
        out.append((w, float(hp), n))
    return out


def build_stamps(results: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    stamps: Dict[str, Dict[str, Any]] = {}
    for desk, block in results.items():
        measured = hits_of(block)
        if not measured:
            continue
        lo = min(h for _, h, _ in measured)
        hi = max(h for _, h, _ in measured)
        # also 3y+5y only (legacy DESKS wording) — documented, not used as stamp if wider
        y35 = [h for w, h, _ in measured if w in ("3y", "5y")]
        lo35 = min(y35) if y35 else lo
        hi35 = max(y35) if y35 else hi
        ar = range_tag(lo, hi)
        band = band_for(lo)
        floor = float(block.get("floor") or 0)
        ft = floor_tag(floor)
        tags = [
            desk,
            ar,
            f"ACC_BAND_{band}",
            ft,
            "LOGIC_P2G",
            "LANE_RESEARCH",
        ]
        # verify every measured hit sits inside [lo, hi] and inside tag ints
        tag_lo = int(math.floor(lo))
        tag_hi = int(math.ceil(hi))
        ok_cover = all(tag_lo <= h <= tag_hi for _, h, _ in measured)
        stamps[desk] = {
            "accurate_tag": desk,
            "desk_tag": desk,
            "accuracy_tag": ar,
            "accuracy_range_tag": ar,
            "accuracy_lo": round(lo, 2),
            "accuracy_hi": round(hi, 2),
            "accuracy_band": band,
            "floor": floor,
            "floor_tag": ft,
            "logic_level": "P2G",
            "mode": "day",
            "lane": "RESEARCH",
            "not_live": True,
            "dual_model": "10m_train",
            "brackets": {"target": 30.0, "sl": 30.0, "risk": 30.0},
            "ok_5y": bool(block.get("ok_5y")),
            "base": block.get("base"),
            "measured": {
                w: {"n": n, "hit_pct": hp} for w, hp, n in measured
            },
            "range_3y5y_only": {"lo": round(lo35, 2), "hi": round(hi35, 2)},
            "prev_accuracy_tag_copied_from_p2f": None,  # filled below
            "range_covers_all_windows": ok_cover,
            "tags": tags,
            "accuracy_note": (
                f"Hit-target accuracy range {lo:.2f}–{hi:.2f}% "
                f"(min/max across 1y/3y/5y/extra_2y for this P2G 10m desk)"
            ),
        }
    return stamps


PREV_COPIED = {
    "ACC100_MULTI_V12_P2G_10M": "ACC_RANGE_98_100",
    "ACC_WIDE_P92_P2G_10M": "ACC_RANGE_91_100",
    "ACC_WIDE_P90_P2G_10M": "ACC_RANGE_89_96",
    "ACC_WIDE_P85_P2G_10M": "ACC_RANGE_84_90",
    "ACC_WIDE_P85B_P2G_10M": "ACC_RANGE_81_89",
    "ACC_WIDE_P80_P2G_10M": "ACC_RANGE_76_85",
    "ACC_WIDE_P75_P2G_10M": "ACC_RANGE_75_83",
}


def patch_logic(stamps: Dict[str, Dict[str, Any]]) -> None:
    text = LOGIC.read_text(encoding="utf-8")
    # ACCURACY_TAG_BY_DESK block
    lines = ["ACCURACY_TAG_BY_DESK: Dict[str, str] = {"]
    for desk, st in stamps.items():
        lines.append(f'    "{desk}": "{st["accuracy_tag"]}",')
    lines.append("}")
    new_map = "\n".join(lines)

    text2, n = re.subn(
        r"ACCURACY_TAG_BY_DESK: Dict\[str, str\] = \{.*?\n\}",
        new_map,
        text,
        count=1,
        flags=re.S,
    )
    if n != 1:
        raise SystemExit("failed to patch ACCURACY_TAG_BY_DESK")

    meta_lines = [
        "",
        "# Measured lo/hi from 1y·3y·5y·extra_2y (ACC_PHASE2G_10M_5Y.json)",
        "ACCURACY_META_BY_DESK: Dict[str, Dict[str, object]] = {",
    ]
    for desk, st in stamps.items():
        meta_lines.append(
            f'    "{desk}": {{'
            f'"accuracy_tag": "{st["accuracy_tag"]}", '
            f'"accuracy_lo": {st["accuracy_lo"]}, '
            f'"accuracy_hi": {st["accuracy_hi"]}, '
            f'"accuracy_band": "{st["accuracy_band"]}", '
            f'"floor_tag": "{st["floor_tag"]}"'
            f"}},"
        )
    meta_lines.append("}")
    meta_block = "\n".join(meta_lines)

    if "ACCURACY_META_BY_DESK" in text2:
        text2 = re.sub(
            r"\n# Measured lo/hi.*?ACCURACY_META_BY_DESK: Dict\[str, Dict\[str, object\]\] = \{.*?\n\}",
            meta_block,
            text2,
            count=1,
            flags=re.S,
        )
    else:
        text2 = text2.replace(new_map, new_map + "\n" + meta_block)

    # stamp helper if missing
    if "def stamp_research" not in text2:
        helper = '''

def stamp_research(rows, desk_tag: str):
    """Stamp RESEARCH P2G 10m multi-tags with measured ACC_RANGE."""
    meta = ACCURACY_META_BY_DESK.get(desk_tag) or {}
    ar = str(meta.get("accuracy_tag") or ACCURACY_TAG_BY_DESK.get(desk_tag) or "")
    band = str(meta.get("accuracy_band") or "")
    ft = str(meta.get("floor_tag") or "")
    lo = meta.get("accuracy_lo")
    hi = meta.get("accuracy_hi")
    tags = [desk_tag]
    if ar:
        tags.append(ar)
    if band:
        tags.append(f"ACC_BAND_{band}")
    if ft:
        tags.append(ft)
    tags.extend([f"LOGIC_{LOGIC_LEVEL}", "LANE_RESEARCH"])
    out = []
    for r in rows:
        rr = dict(r)
        rr["lane"] = LANE
        rr["status"] = STATUS
        rr["not_live"] = True
        rr["logic_level"] = LOGIC_LEVEL
        rr["desk_tag"] = desk_tag
        rr["accurate_tag"] = desk_tag
        rr["accuracy_tag"] = ar
        rr["accuracy_range_tag"] = ar
        rr["accuracy_lo"] = lo
        rr["accuracy_hi"] = hi
        rr["accuracy_band"] = band
        rr["mode"] = MODE
        rr["hard_gate"] = HARD_GATES.get(desk_tag)
        existing = list(rr.get("tags") or [])
        seen = set(existing)
        for t in tags:
            if t and t not in seen:
                existing.append(t)
                seen.add(t)
        rr["tags"] = existing
        out.append(rr)
    return out
'''
        text2 = text2.rstrip() + "\n" + helper + "\n"

    LOGIC.write_text(text2, encoding="utf-8")


def patch_recipes(stamps: Dict[str, Dict[str, Any]]) -> None:
    rec = json.loads(RECIPES.read_text(encoding="utf-8"))
    cands = rec.get("candidates") or {}
    by_tag = {st["accurate_tag"]: st for st in stamps.values()}
    for _base, block in cands.items():
        tag = block.get("candidate_tag")
        st = by_tag.get(tag)
        if not st:
            continue
        block["accuracy_tag"] = st["accuracy_tag"]
        block["accuracy_range_tag"] = st["accuracy_tag"]
        block["accuracy_lo"] = st["accuracy_lo"]
        block["accuracy_hi"] = st["accuracy_hi"]
        block["accuracy_band"] = st["accuracy_band"]
        block["floor_tag"] = st["floor_tag"]
        block["tags"] = st["tags"]
        block["accuracy_note"] = st["accuracy_note"]
        block["brackets"] = st["brackets"]
    rec["accuracy_tags_source"] = "ACC_PHASE2G_10M_5Y.json · measured 1y/3y/5y/extra_2y"
    RECIPES.write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")


def patch_desks_held(stamps: Dict[str, Dict[str, Any]]) -> None:
    data = json.loads(DESKS_JS.read_text(encoding="utf-8"))
    desks = data.setdefault("desks", {})
    for desk, st in stamps.items():
        desks[desk] = {
            "accurate_tag": desk,
            "desk_tag": desk,
            "logic_level": "P2G",
            "status": "RESEARCH",
            "mode": "day",
            "accuracy_range_tag": st["accuracy_tag"],
            "accuracy_tag": st["accuracy_tag"],
            "accuracy_band": st["accuracy_band"],
            "accuracy_lo": st["accuracy_lo"],
            "accuracy_hi": st["accuracy_hi"],
            "floor": st["floor"],
            "research_1y": st["measured"].get("1y"),
            "research_3y": st["measured"].get("3y"),
            "research_5y": st["measured"].get("5y"),
            "research_extra_2y": st["measured"].get("extra_2y"),
            "ok_5y": st["ok_5y"],
            "base_desk": st.get("base"),
            "dual_model": "10m_train",
            "lane": "RESEARCH",
            "not_live": True,
            "kind": "phase2g_10m",
            "brackets": st["brackets"],
            "tags": st["tags"],
            "accuracy_note": st["accuracy_note"],
            "prev_accuracy_tag_copied_from_p2f": st["prev_accuracy_tag_copied_from_p2f"],
        }
    data["latest_level"] = "P2G"
    data["p2g_10m_accuracy_tags"] = str(OUT_JS.relative_to(ROOT)).replace("\\", "/")
    DESKS_JS.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def patch_desks_md(stamps: Dict[str, Dict[str, Any]]) -> None:
    text = DESKS_MD.read_text(encoding="utf-8")
    # refresh range table rows for new tags (append if missing)
    section_lines = [
        "",
        "## Phase-2G RESEARCH — 10m dual (measured ranges)",
        "",
        "_Source: `reports/5y/ACC_PHASE2G_10M_5Y.json` · lo/hi = min/max of 1y·3y·5y·extra_2y · brackets ±30._",
        "",
        "| Priority | accurate_tag | accuracy_tag | Lo–Hi | Floor | 5y OK | 5y N@hit | tags |",
        "|---:|---|---|---|---:|---|---|---|",
    ]
    for i, (desk, st) in enumerate(stamps.items(), 1):
        m5 = st["measured"].get("5y") or {}
        section_lines.append(
            f"| {i} | `{desk}` | `{st['accuracy_tag']}` | "
            f"{st['accuracy_lo']}–{st['accuracy_hi']} | {st['floor']} | "
            f"{'Y' if st['ok_5y'] else 'N'} | "
            f"{m5.get('n')}@{m5.get('hit_pct')} | "
            + ", ".join(f"`{t}`" for t in st["tags"])
            + " |"
        )
    section_lines.append("")
    section_lines.append("### New ACC_RANGE tags (P2G 10m only)")
    section_lines.append("")
    section_lines.append("| accuracy_tag | Lo–Hi % | Band | Desk |")
    section_lines.append("|---|---|---|---|")
    seen = set()
    for st in stamps.values():
        ar = st["accuracy_tag"]
        if ar in seen:
            continue
        seen.add(ar)
        section_lines.append(
            f"| `{ar}` | {st['accuracy_lo']}–{st['accuracy_hi']} | "
            f"{st['accuracy_band']} | `{st['accurate_tag']}` |"
        )
    section_lines.append("")

    marker = "## Phase-2G RESEARCH — 10m dual (measured ranges)"
    if marker in text:
        # replace from marker to EOF or next ## at end — keep prior content, replace section
        pre = text.split(marker)[0].rstrip()
        text = pre + "\n" + "\n".join(section_lines)
    else:
        text = text.rstrip() + "\n" + "\n".join(section_lines)
    DESKS_MD.write_text(text + "\n", encoding="utf-8")


def write_report(stamps: Dict[str, Dict[str, Any]]) -> None:
    lines = [
        "# P2G 10m — measured accuracy tags",
        "",
        "**Source:** `ACC_PHASE2G_10M_5Y.json`",
        "**Rule:** `accuracy_lo/hi` = min/max hit% across **1y · 3y · 5y · extra_2y**",
        "**Brackets:** Target **+30** · SL **−30** (same as P2F/P2G path risk)",
        "**Lane:** RESEARCH · not live",
        "",
        "## Stamp table",
        "",
        "| accurate_tag | OLD (copied P2F) | NEW accuracy_tag | Lo–Hi | Band | Floor | Covers? | 5y OK |",
        "|---|---|---|---|---|---:|---|---|",
    ]
    for desk, st in stamps.items():
        lines.append(
            f"| `{desk}` | `{st['prev_accuracy_tag_copied_from_p2f']}` | "
            f"`{st['accuracy_tag']}` | {st['accuracy_lo']}–{st['accuracy_hi']} | "
            f"`ACC_BAND_{st['accuracy_band']}` | {st['floor']} | "
            f"{'Y' if st['range_covers_all_windows'] else 'N'} | "
            f"{'Y' if st['ok_5y'] else 'N'} |"
        )

    lines.extend(
        [
            "",
            "## Per-desk measured hits",
            "",
        ]
    )
    for desk, st in stamps.items():
        lines.append(f"### `{desk}`")
        lines.append("")
        lines.append(
            f"- **accuracy_tag:** `{st['accuracy_tag']}` · "
            f"**lo/hi:** {st['accuracy_lo']}–{st['accuracy_hi']}"
        )
        lines.append(
            f"- **3y+5y only:** {st['range_3y5y_only']['lo']}–{st['range_3y5y_only']['hi']}"
        )
        lines.append(f"- **tags:** " + ", ".join(f"`{t}`" for t in st["tags"]))
        lines.append("")
        lines.append("| Window | N | Hit% |")
        lines.append("|---|---:|---:|")
        for w, stw in st["measured"].items():
            lines.append(f"| {w} | {stw['n']} | {stw['hit_pct']} |")
        lines.append("")

    lines.extend(
        [
            "## Example row stamp",
            "",
            "```",
            "lane=RESEARCH",
            "logic_level=P2G",
            "accurate_tag=ACC_WIDE_P85B_P2G_10M",
            "accuracy_tag=ACC_RANGE_88_95",
            "accuracy_lo=88.41",
            "accuracy_hi=94.23",
            "accuracy_band=C_MID_85",
            "tags=[ACC_WIDE_P85B_P2G_10M, ACC_RANGE_88_95, ACC_BAND_C_MID_85, ACC_FLOOR_88p4, LOGIC_P2G, LANE_RESEARCH]",
            "```",
            "",
        ]
    )
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    raw = json.loads(REP5.read_text(encoding="utf-8"))
    stamps = build_stamps(raw.get("results") or {})
    for desk, st in stamps.items():
        st["prev_accuracy_tag_copied_from_p2f"] = PREV_COPIED.get(desk)
        # safety: every measured hit must sit in tag integer bounds
        assert st["range_covers_all_windows"], desk

    OUT_JS.parent.mkdir(parents=True, exist_ok=True)
    OUT_JS.write_text(json.dumps({"status": "RESEARCH", "desks": stamps}, indent=2) + "\n", encoding="utf-8")
    write_report(stamps)
    patch_logic(stamps)
    patch_recipes(stamps)
    patch_desks_held(stamps)
    patch_desks_md(stamps)

    print(f"Wrote {OUT_MD}")
    print(f"Wrote {OUT_JS}")
    print(f"Patched {LOGIC}")
    print(f"Patched {RECIPES}")
    print(f"Patched {DESKS_JS}")
    print(f"Patched {DESKS_MD}")
    for desk, st in stamps.items():
        print(
            f"  {desk}: {st['prev_accuracy_tag_copied_from_p2f']} → "
            f"{st['accuracy_tag']} ({st['accuracy_lo']}–{st['accuracy_hi']})"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
