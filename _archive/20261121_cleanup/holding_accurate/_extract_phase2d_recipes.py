"""Build phase2d research recipe snapshot from ACC_PHASE2D report + held P2c tags."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REP = ROOT / "prod_live" / "reports" / "1y"
OUT = Path(__file__).resolve().parent


def tags_from(items) -> list[str]:
    out, seen = [], set()
    for a in items or []:
        t = a["tag"] if isinstance(a, dict) else str(a)
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return out


def main() -> None:
    held = json.loads((OUT / "recipes.json").read_text(encoding="utf-8"))
    p2d = json.loads((REP / "ACC_PHASE2D_KEEP_GOING.json").read_text(encoding="utf-8"))
    cands = {}
    for key, v in (p2d.get("results") or {}).items():
        base_held = (held.get("candidates") or {}).get(key) or {}
        combined, seen = [], set()
        for t in (base_held.get("stream_tags_held") or []) + tags_from(v.get("added_streams_new")):
            if t not in seen:
                seen.add(t)
                combined.append(t)
        r3 = (v.get("result") or {}).get("3y") or {}
        cands[key] = {
            "base_desk": key.replace("_CAP2", ""),
            "mode": v.get("mode") or ("cap2" if key.endswith("_CAP2") else "day"),
            "candidate_tag": v.get("candidate_tag"),
            "floor": v.get("floor"),
            "phase1_3y": v.get("phase1_3y") or v.get("baseline", {}).get("3y"),
            "phase2c_3y_n": v.get("phase2c_3y_n"),
            "research_3y": r3,
            "delta_vs_phase1_3y": v.get("delta_vs_phase1_3y"),
            "delta_vs_phase2c_3y": v.get("delta_vs_phase2c_3y"),
            "stream_tags_from_p2c_held": list(base_held.get("stream_tags_held") or []),
            "stream_tags_p2d_new": tags_from(v.get("added_streams_new")),
            "stream_tags_research": combined,
            "status": "RESEARCH",
        }
    payload = {
        "status": "RESEARCH",
        "not_live": True,
        "phase": "2d",
        "note": "Research snapshot — Phase-1 locked, Phase-2c held; P2d not promoted",
        "window_end": p2d.get("window_end"),
        "report": "reports/1y/ACC_PHASE2D_KEEP_GOING.md",
        "candidates": cands,
        "elapsed_s": p2d.get("elapsed_s"),
    }
    path = OUT / "phase2d" / "recipes_research.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print("Wrote", path)
    for k, v in cands.items():
        r = v["research_3y"]
        print(f"  {k}: n={r.get('n')}@{r.get('hit_pct')} streams={len(v['stream_tags_research'])}")


if __name__ == "__main__":
    main()
