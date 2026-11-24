"""Append / refresh holding accurate_tag entries in config/tags.json from desks_held.json."""
from __future__ import annotations

import json
from pathlib import Path

HOLD = Path(__file__).resolve().parent
TAGS = HOLD.parent / "config" / "tags.json"

held = json.loads((HOLD / "desks_held.json").read_text(encoding="utf-8"))
tags = json.loads(TAGS.read_text(encoding="utf-8"))

# Update ACC_RANGE_* desk lists with held expand tags
range_members: dict[str, list[str]] = {}
for tag, m in held["desks"].items():
    ar = m["accuracy_range_tag"]
    range_members.setdefault(ar, []).append(tag)

for ar, members in range_members.items():
    if ar not in tags:
        continue
    existing = list(tags[ar].get("desks") or [])
    merged = sorted(set(existing) | set(members))
    tags[ar]["desks"] = merged

# Band members
band_key = {
    "A_PERFECT_3Y5Y": "ACC_BAND_A_PERFECT_3Y5Y",
    "B_HIGH_90": "ACC_BAND_B_HIGH_90",
    "C_MID_85": "ACC_BAND_C_MID_85",
    "D_VOL_80": "ACC_BAND_D_VOL_80",
    "E_VOL_75": "ACC_BAND_E_VOL_75",
}
band_members: dict[str, list[str]] = {}
for tag, m in held["desks"].items():
    b = m.get("accuracy_band") or ""
    if b:
        band_members.setdefault(b, []).append(tag)
for band, members in band_members.items():
    key = band_key.get(band)
    if not key or key not in tags:
        continue
    existing = list(tags[key].get("desks") or [])
    tags[key]["desks"] = sorted(set(existing) | set(members))

# Desk accurate_tag entries (skip overwriting rich P1 entries; only fill missing / refresh expand)
added = 0
updated = 0
for tag, m in held["desks"].items():
    entry = {
        "status": m["status"],
        "keep": True,
        "kind": "holding_accurate_tag",
        "accurate_tag": tag,
        "desk_tag": tag,
        "logic_level": m["logic_level"],
        "base_desk": m.get("base_key") or m.get("base_desk"),
        "mode": m["mode"],
        "floor_pct": m.get("floor"),
        "research_3y": m.get("research_3y"),
        "stream_count": m.get("stream_count"),
        "logic": m.get("logic"),
        "not_live": True,
        "lane": "HOLDING",
        "accuracy_tag": m.get("accuracy_tag") or m["accuracy_range_tag"],
        "accuracy_range": m["accuracy_range_tag"],
        "accuracy_lo": m.get("accuracy_lo"),
        "accuracy_hi": m.get("accuracy_hi"),
        "accuracy_band": m["accuracy_band"],
        "tags": list(m.get("tags") or []),
        "recipes": m.get("recipes"),
    }
    if tag in tags and tags[tag].get("kind") in (
        "holding_accurate_desk",
        "holding_wide_desk",
        "accurate_tag",
    ) and m["logic_level"] == "P1":
        # Keep P1 rich entries; only ensure accurate_tag + range/band present
        tags[tag].setdefault("accurate_tag", tag)
        tags[tag]["accuracy_range"] = m["accuracy_range_tag"]
        tags[tag]["accuracy_band"] = m["accuracy_band"]
        tags[tag]["keep"] = True
        tags[tag]["lane"] = "HOLDING"
        tags[tag]["not_live"] = True
        updated += 1
        continue
    if tag not in tags:
        added += 1
    else:
        updated += 1
    tags[tag] = entry

TAGS.write_text(json.dumps(tags, indent=2) + "\n", encoding="utf-8")
print(f"tags.json: added={added} updated={updated} total_keys={len(tags)}")
