"""Dump all held desks P1→P2F with accurate tags."""
from __future__ import annotations

import json
from pathlib import Path

HOLD = Path(__file__).resolve().parent
ROOT = HOLD.parent

# Phase-1 registry
import sys

sys.path.insert(0, str(ROOT.parent))
from prod_live.logic.accurate_desks import DESK_REGISTRY  # noqa: E402

FLOOR = {
    "ACC100_MULTI_V5": 100.0,
    "ACC100_MULTI_V1": 100.0,
    "ACC100_MULTI_V2": 100.0,
    "ACC100_MULTI_V3": 100.0,
    "ACC100_MULTI_V4": 100.0,
    "PROVEN15_PLUS_CONFIRM_T30": 100.0,
    "ACC_WIDE_P92": 99.24,
    "ACC_WIDE_P90": 95.4,
    "ACC_WIDE_P85": 89.69,
    "ACC_WIDE_P85B": 88.4,
    "ACC_WIDE_P80": 84.72,
    "ACC_WIDE_P75": 82.71,
    "ACC_WIDE_P80_CAP2": 84.72,
    "ACC_WIDE_P75_CAP2": 82.71,
}

BAND = {
    "ACC_RANGE_100_100": "A_PERFECT_3Y5Y",
    "ACC_RANGE_96_100": "A_PERFECT_3Y5Y",
    "ACC_RANGE_97_100": "A_PERFECT_3Y5Y",
    "ACC_RANGE_98_100": "A_PERFECT_3Y5Y",
    "ACC_RANGE_91_100": "B_HIGH_90",
    "ACC_RANGE_89_96": "B_HIGH_90",
    "ACC_RANGE_84_90": "C_MID_85",
    "ACC_RANGE_81_89": "C_MID_85",
    "ACC_RANGE_76_85": "D_VOL_80",
    "ACC_RANGE_77_87": "D_VOL_80",
    "ACC_RANGE_75_83": "E_VOL_75",
    "ACC_RANGE_75_84": "E_VOL_75",
}

# Inherit range from base desk for phase expansions
BASE_RANGE = {k: v["accuracy_range"] for k, v in DESK_REGISTRY.items()}


def load_cands(path: Path, key_tags: str = "stream_tags_research"):
    if not path.exists():
        return {}
    d = json.loads(path.read_text(encoding="utf-8"))
    return d.get("candidates") or {}


p1 = {
    k: {
        "accurate_tag": k,
        "desk_tag": k,
        "logic_level": "P1",
        "status": "LOCKED",
        "mode": "cap2" if "CAP2" in k else "day",
        "accuracy_range_tag": meta["accuracy_range"],
        "accuracy_band": meta.get("band") or BAND.get(meta["accuracy_range"], ""),
        "floor": FLOOR.get(k),
        "research_3y": meta.get("research_3y") or {},
        "base_desk": k,
        "stream_count": None,
        "kind": "phase1_locked",
        "lane": "HOLDING",
        "not_live": True,
    }
    for k, meta in DESK_REGISTRY.items()
}

levels = [
    ("P2C", HOLD / "recipes.json", "stream_tags_held", "held_3y", "HELD"),
    ("P2D", HOLD / "phase2d" / "recipes_research.json", "stream_tags_research", "research_3y", "HELD"),
    ("P2E", HOLD / "phase2e" / "recipes_research.json", "stream_tags_research", "research_3y", "HELD"),
    ("P2F", HOLD / "phase2f" / "recipes_research.json", "stream_tags_research", "research_3y", "HELD"),
]

all_desks = dict(p1)
for level, path, tag_key, n_key, status in levels:
    cands = load_cands(path)
    for base, meta in cands.items():
        cand = meta.get("candidate_tag") or f"{base}_{level}"
        base_desk = meta.get("base_desk") or base.replace("_CAP2", "")
        # Cap2 bases often named ACC100_MULTI_V5_CAP2 etc
        range_src = base if base in BASE_RANGE else (base_desk if base_desk in BASE_RANGE else "ACC100_MULTI_V5")
        if "CAP2" in base and base.replace("_CAP2", "") + "_CAP2" in BASE_RANGE:
            range_src = base if base in BASE_RANGE else range_src
        # Prefer P1 wide cap2 range when applicable
        if base.endswith("_CAP2") and base in BASE_RANGE:
            range_src = base
        elif base.endswith("_CAP2"):
            # V5_CAP2 / P92_CAP2 etc — map from day base range for 100/P92/P90; P85 from P85
            day = base.replace("_CAP2", "")
            range_src = BASE_RANGE.get(day, BASE_RANGE.get("ACC100_MULTI_V5"))
            # special: known P1 only has P80/P75 CAP2 with own range
            if day + "_CAP2" in BASE_RANGE:
                range_src = day + "_CAP2"
            else:
                range_src = day if day in BASE_RANGE else "ACC100_MULTI_V5"
        ar = BASE_RANGE.get(range_src) if isinstance(range_src, str) else None
        if ar is None:
            ar = BASE_RANGE.get(str(range_src), "ACC_RANGE_98_100")
        if isinstance(range_src, str) and range_src in BASE_RANGE:
            ar = BASE_RANGE[range_src]
        elif base in BASE_RANGE:
            ar = BASE_RANGE[base]
        else:
            day = base.replace("_CAP2", "")
            ar = BASE_RANGE.get(day, "ACC_RANGE_98_100")

        held = meta.get(n_key) or meta.get("held_3y") or meta.get("research_3y") or {}
        tags = meta.get(tag_key) or meta.get("stream_tags_held") or meta.get("stream_tags_research") or []
        all_desks[cand] = {
            "accurate_tag": cand,
            "desk_tag": cand,
            "logic_level": level,
            "status": status,
            "mode": meta.get("mode") or ("cap2" if "CAP2" in base else "day"),
            "accuracy_range_tag": ar,
            "accuracy_band": BAND.get(ar, ""),
            "floor": meta.get("floor") or FLOOR.get(base) or FLOOR.get(base.replace("_CAP2", "")),
            "research_3y": {
                "n": held.get("n"),
                "hit_pct": held.get("hit_pct"),
            },
            "base_desk": base_desk if not base.endswith("_CAP2") else base,
            "base_key": base,
            "stream_count": len(tags),
            "kind": f"holding_{level.lower()}",
            "lane": "HOLDING",
            "not_live": True,
        }

# Write machine registry
out_json = HOLD / "desks_held.json"
payload = {
    "status": "HELD_COMPLETE",
    "latest_level": "P2F",
    "lane": "HOLDING",
    "not_live": True,
    "stamp_fields": [
        "lane",
        "logic_level",
        "desk_tag",
        "accurate_tag",
        "accuracy_range_tag",
        "accuracy_band",
    ],
    "desks": all_desks,
}
out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
print("Wrote", out_json, "desks=", len(all_desks))

# Brief by level
from collections import defaultdict

by = defaultdict(list)
for tag, m in all_desks.items():
    by[m["logic_level"]].append((tag, m))
for lv in ["P1", "P2C", "P2D", "P2E", "P2F"]:
    print(f"\n=== {lv} ({len(by[lv])}) ===")
    for tag, m in sorted(by[lv], key=lambda x: (0 if "MULTI" in x[0] or "PROVEN" in x[0] else 1, x[0])):
        r = m["research_3y"]
        print(
            f"  {tag:36} range={m['accuracy_range_tag']:18} floor={m.get('floor')} "
            f"3y={r.get('n')}@{r.get('hit_pct')} mode={m['mode']} streams={m.get('stream_count')}"
        )
