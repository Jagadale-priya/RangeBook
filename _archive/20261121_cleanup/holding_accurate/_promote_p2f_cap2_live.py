"""Flip P2F Cap2 desks HOLDING → LIVE in desks_held.json + tags.json.

  python -u prod_live/holding_accurate/_promote_p2f_cap2_live.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HOLD = Path(__file__).resolve().parent
ROOT = HOLD.parent
REPO = ROOT.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(ROOT))
import path_setup  # noqa: F401,E402

from prod_live.logic.p2f_cap2_live import LIVE_CAP2_DESKS  # noqa: E402

HELD = HOLD / "desks_held.json"
TAGS = ROOT / "config" / "tags.json"


def main() -> None:
    held = json.loads(HELD.read_text(encoding="utf-8"))
    desks = held.get("desks") or {}
    promoted = []
    for tag in LIVE_CAP2_DESKS:
        m = desks.get(tag)
        if not m:
            print(f"MISSING desk {tag}")
            continue
        m["lane"] = "LIVE"
        m["not_live"] = False
        m["status"] = "PROMOTED"
        m["kind"] = "live_p2f_cap2"
        m["promoted"] = True
        m["mode"] = "cap2"
        promoted.append(tag)
    held["live_cap2_promoted"] = promoted
    held["live_cap2_note"] = (
        "P2F Cap2 desks promoted to LIVE accurate book. "
        "Volume stack unchanged. Day desks already LIVE."
    )
    HELD.write_text(json.dumps(held, indent=2) + "\n", encoding="utf-8")
    print(f"desks_held: promoted {len(promoted)} Cap2 desks")

    tags = json.loads(TAGS.read_text(encoding="utf-8"))
    n = 0
    for tag in LIVE_CAP2_DESKS:
        if tag not in tags:
            print(f"MISSING tags.json {tag}")
            continue
        tags[tag]["lane"] = "LIVE"
        tags[tag]["not_live"] = False
        tags[tag]["status"] = "PROMOTED"
        tags[tag]["promoted"] = True
        tags[tag]["mode"] = "cap2"
        n += 1
    TAGS.write_text(json.dumps(tags, indent=2) + "\n", encoding="utf-8")
    print(f"tags.json: promoted {n} Cap2 entries")


if __name__ == "__main__":
    main()
