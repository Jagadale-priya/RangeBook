"""Snapshot Phase-2f research recipes from report + P2e seeds."""
from __future__ import annotations

import json
from pathlib import Path

HOLD = Path(__file__).resolve().parent
REP = HOLD.parent / "reports" / "1y"
P2E = HOLD / "phase2e" / "recipes_research.json"
P2F = json.loads((REP / "ACC_PHASE2F_KEEP_PUSHING.json").read_text(encoding="utf-8"))
p2e = json.loads(P2E.read_text(encoding="utf-8")).get("candidates") or {}

cands = {}
for key, v in (P2F.get("results") or {}).items():
    prior = list((p2e.get(key) or {}).get("stream_tags_research") or [])
    new = [a["tag"] for a in (v.get("added_streams_new") or [])]
    combined, seen = [], set()
    for t in prior + new:
        if t not in seen:
            seen.add(t)
            combined.append(t)
    r3 = (v.get("result") or {}).get("3y") or {}
    cands[key] = {
        "base_desk": key.replace("_CAP2", ""),
        "mode": v.get("mode"),
        "candidate_tag": v.get("candidate_tag"),
        "research_3y": r3,
        "phase2e_3y_n": v.get("phase2e_3y_n"),
        "delta_vs_phase2e_3y": v.get("delta_vs_phase2e_3y"),
        "stream_tags_research": combined,
        "status": "RESEARCH",
    }

payload = {
    "status": "RESEARCH",
    "phase": "2f",
    "not_live": True,
    "report": "reports/1y/ACC_PHASE2F_KEEP_PUSHING.md",
    "candidates": cands,
    "elapsed_s": P2F.get("elapsed_s"),
}
out = HOLD / "phase2f" / "recipes_research.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
print("Wrote", out)
for k, v in cands.items():
    print(f"  {k}: n={v['research_3y'].get('n')} streams={len(v['stream_tags_research'])}")
