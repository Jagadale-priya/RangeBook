"""One-shot: build recipes.json from Phase-2 / 2b / 2c reports."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REP = ROOT / "prod_live" / "reports" / "1y"
OUT = Path(__file__).resolve().parent


def tags_from(result: dict, *keys: str) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for key in keys:
        for a in result.get(key) or []:
            t = a["tag"] if isinstance(a, dict) else str(a)
            if t and t not in seen:
                seen.add(t)
                out.append(t)
    return out


def main() -> None:
    p2 = json.loads((REP / "ACC_PHASE2_SAME_ACC_MORE.json").read_text(encoding="utf-8"))
    p2b = json.loads((REP / "ACC_PHASE2B_DEEPER_MORE.json").read_text(encoding="utf-8"))
    p2c = json.loads((REP / "ACC_PHASE2C_EVEN_MORE.json").read_text(encoding="utf-8"))

    p2_tags = {
        k: tags_from(v, "added_streams")
        for k, v in (p2.get("results") or {}).items()
        if not k.endswith("_SIDES")
    }
    p2b_tags = {
        k: tags_from(v, "added_streams")
        for k, v in (p2b.get("results") or {}).items()
        if not k.endswith("_SIDES")
    }
    p2c_new = {
        k: tags_from(v, "added_streams_new")
        for k, v in (p2c.get("results") or {}).items()
        if not k.endswith("_SIDES")
    }

    # Combined day-mode recipes: P2 → P2b → P2c-new (order matters for replay)
    day_desks = [
        "ACC100_MULTI_V5",
        "ACC_WIDE_P92",
        "ACC_WIDE_P90",
        "ACC_WIDE_P85",
        "ACC_WIDE_P85B",
        "ACC_WIDE_P80",
        "ACC_WIDE_P75",
    ]
    candidates = {}
    for desk in day_desks:
        combined: list[str] = []
        seen: set[str] = set()
        for src in (p2_tags.get(desk) or [], p2b_tags.get(desk) or [], p2c_new.get(desk) or []):
            for t in src:
                if t not in seen:
                    seen.add(t)
                    combined.append(t)
        r = (p2c.get("results") or {}).get(desk) or {}
        candidates[desk] = {
            "base_desk": desk,
            "mode": "day",
            "candidate_tag": r.get("candidate_tag"),
            "floor": r.get("floor"),
            "phase1_3y": r.get("phase1_3y"),
            "held_3y": (r.get("result") or {}).get("3y"),
            "delta_vs_phase1_3y": r.get("delta_vs_phase1_3y"),
            "stream_tags_p2": p2_tags.get(desk) or [],
            "stream_tags_p2b": p2b_tags.get(desk) or [],
            "stream_tags_p2c_new": p2c_new.get(desk) or [],
            "stream_tags_held": combined,
        }

    for key in ("ACC100_MULTI_V5_CAP2", "ACC_WIDE_P92_CAP2", "ACC_WIDE_P90_CAP2"):
        r = (p2c.get("results") or {}).get(key) or {}
        base = key.replace("_CAP2", "")
        candidates[key] = {
            "base_desk": base,
            "mode": "cap2",
            "candidate_tag": r.get("candidate_tag"),
            "floor": r.get("floor"),
            "phase1_3y": ((p2c.get("results") or {}).get(base) or {}).get("phase1_3y"),
            "held_3y": (r.get("result") or {}).get("3y"),
            "delta_vs_phase1_3y": r.get("delta_vs_phase1_3y"),
            "stream_tags_p2": [],
            "stream_tags_p2b": [],
            "stream_tags_p2c_new": p2c_new.get(key) or [],
            "stream_tags_held": p2c_new.get(key) or [],
        }

    payload = {
        "status": "HOLDING",
        "not_live": True,
        "phase1": {
            "status": "LOCKED",
            "logic": "prod_live/logic/accurate_desks.py",
            "streams": "prod_live/logic/acc100_streams.py",
            "confirm": "prod_live/tests/confirm_accurate_desks_3y_match.py",
            "doc": "phase1/PHASE1_LOGIC.md",
        },
        "phase2c": {
            "status": "HELD",
            "note": "Candidates held as stream-tag recipes on top of Phase-1 desks",
            "reports": [
                "reports/1y/ACC_PHASE2_SAME_ACC_MORE.md",
                "reports/1y/ACC_PHASE2B_DEEPER_MORE.md",
                "reports/1y/ACC_PHASE2C_EVEN_MORE.md",
            ],
            "doc": "phase2c/PHASE2C_LOGIC.md",
        },
        "window_end": p2c.get("window_end"),
        "candidates": candidates,
    }
    out_path = OUT / "recipes.json"
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print("Wrote", out_path)
    for k, v in candidates.items():
        h = v.get("held_3y") or {}
        print(
            f"  {k}: streams={len(v['stream_tags_held'])} "
            f"3y={h.get('n')}@{h.get('hit_pct')} cand={v.get('candidate_tag')}"
        )


if __name__ == "__main__":
    main()
