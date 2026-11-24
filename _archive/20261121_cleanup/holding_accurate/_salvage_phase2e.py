"""Salvage Phase-2e partial stream tags from terminal log into recipes."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOLD = Path(__file__).resolve().parent
TERM = Path(r"C:\Users\Priyanka\.cursor\projects\c-Users-Priyanka-Agent\terminals\514381.txt")
P2D = HOLD / "phase2d" / "recipes_research.json"
OUT = HOLD / "phase2e" / "recipes_research.json"

FINALS = {
    "ACC100_MULTI_V5": {"n": 241, "hit_pct": 100.0, "candidate_tag": "ACC100_MULTI_V10"},
    "ACC_WIDE_P92": {"n": 243, "hit_pct": 99.5885, "candidate_tag": "ACC_WIDE_P92_P2E"},
    "ACC_WIDE_P90": {"n": 274, "hit_pct": 96.3504, "candidate_tag": "ACC_WIDE_P90_P2E"},
    "ACC_WIDE_P85": {"n": 317, "hit_pct": 89.9054, "candidate_tag": "ACC_WIDE_P85_P2E"},
    "ACC_WIDE_P85B": {"n": 329, "hit_pct": 88.4498, "candidate_tag": "ACC_WIDE_P85B_P2E"},
    "ACC_WIDE_P80": {"n": 360, "hit_pct": 84.7222, "candidate_tag": "ACC_WIDE_P80_P2E"},
    "ACC_WIDE_P75": {"n": 382, "hit_pct": 82.7225, "candidate_tag": "ACC_WIDE_P75_P2E"},
    "ACC100_MULTI_V5_CAP2": {"n": 325, "hit_pct": 100.0, "candidate_tag": "ACC100_MULTI_V5_CAP2_P2E"},
    "ACC_WIDE_P92_CAP2": {"n": 327, "hit_pct": 99.6942, "candidate_tag": "ACC_WIDE_P92_CAP2_P2E"},
    "ACC_WIDE_P90_CAP2": {"n": 370, "hit_pct": 96.7568, "candidate_tag": "ACC_WIDE_P90_CAP2_P2E"},
    "ACC_WIDE_P85_CAP2": {"n": 447, "hit_pct": 89.7092, "candidate_tag": "ACC_WIDE_P85_CAP2_P2E"},
    "ACC_WIDE_P85B_CAP2": {"n": 459, "hit_pct": 88.4532, "candidate_tag": "ACC_WIDE_P85B_CAP2_P2E"},
    "ACC_WIDE_P80_CAP2": {"n": 521, "hit_pct": 84.8369, "candidate_tag": "ACC_WIDE_P80_CAP2_P2E"},
    # P75 CAP2 incomplete — omit or mark partial
}


def main() -> None:
    p2d = json.loads(P2D.read_text(encoding="utf-8")).get("candidates") or {}
    text = TERM.read_text(encoding="utf-8", errors="replace")
    desk = None
    added: dict[str, list[str]] = {}
    for line in text.splitlines():
        m = re.search(r"  (ACC\S+) CAP2 floor=", line)
        if m:
            desk = m.group(1) + "_CAP2"
            added.setdefault(desk, [])
            continue
        m = re.search(r"  (ACC\S+) floor=", line)
        if m:
            desk = m.group(1)
            if "CAP2" in line or "DAY_SIDE" in line:
                desk = None
                continue
            added.setdefault(desk, [])
            continue
        if desk is None:
            continue
        m = re.search(r"\[(day|cap2)\] \+\d+ (\S+) ", line)
        if m:
            added[desk].append(m.group(2))

    cands = {}
    for key, fin in FINALS.items():
        base = key.replace("_CAP2", "")
        p2d_meta = p2d.get(key) or p2d.get(base) or {}
        prior = list(p2d_meta.get("stream_tags_research") or [])
        new = added.get(key) or []
        combined, seen = [], set()
        for t in prior + new:
            if t not in seen:
                seen.add(t)
                combined.append(t)
        cands[key] = {
            "base_desk": base,
            "mode": "cap2" if key.endswith("_CAP2") else "day",
            "candidate_tag": fin["candidate_tag"],
            "research_3y": {"n": fin["n"], "hit_pct": fin["hit_pct"]},
            "status": "RESEARCH_PARTIAL" if key == "ACC_WIDE_P75_CAP2" else "RESEARCH",
            "stream_tags_from_p2d": prior,
            "stream_tags_p2e_new": new,
            "stream_tags_research": combined,
            "note": "Salvaged from Phase-2e partial terminal; P75_CAP2 omitted (incomplete)",
        }

    payload = {
        "status": "RESEARCH",
        "phase": "2e",
        "partial": True,
        "not_live": True,
        "note": "Salvaged partial Phase-2e — day + completed cap2 only",
        "report": "reports/1y/ACC_PHASE2E_PARTIAL.md",
        "candidates": cands,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print("Wrote", OUT)
    for k, v in cands.items():
        print(f"  {k}: n={v['research_3y']['n']} streams={len(v['stream_tags_research'])}")


if __name__ == "__main__":
    main()
