"""Confirm SENSEX FINAL books against locked 5y research golden.

  python -u prod_live/tests/confirm_final_sensex_3books.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import List, Tuple

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import path_setup  # noqa: F401,E402

from prod_live.logic import sensex_final_live as sx  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y" / "FINAL_SENSEX_BOOKS_CONFIRM.md"
REP = ROOT / "prod_live" / "reports" / "5y" / "SENSEX_FINAL_CHAMP_PLUS_5Y.json"


def _hit(rows: List[dict]) -> float:
    if not rows:
        return 0.0
    return round(100.0 * sum(1 for r in rows if r.get("win")) / len(rows), 2)


def clip(rows: List[dict], a: str, b: str) -> List[dict]:
    return [r for r in rows if a <= str(r.get("day") or "") <= b]


def _match(label: str, got_n: int, got_hit: float, exp_n: int, exp_hit: float, tol: float = 0.05) -> Tuple[bool, str]:
    ok = got_n == int(exp_n) and abs(float(got_hit) - float(exp_hit)) <= tol
    return ok, (
        f"{'PASS' if ok else 'FAIL'} {label}: got {got_n}@{got_hit}% · exp {exp_n}@{exp_hit}%"
    )


def main() -> int:
    rep = json.loads(REP.read_text(encoding="utf-8"))
    exp = rep.get("expected") or {}
    held = sx.load_held_calls()
    raw_path = Path(rep.get("calls_path") or "")
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    calls = raw.get("calls") if isinstance(raw, dict) else raw
    passes, fails = [], []
    lines = [
        "# FINAL SENSEX books confirm",
        "",
        f"**Desk:** `{sx.DESK_CHAMP}` · **accuracy_tag:** `{sx.ACCURACY_TAG}`",
        f"**Brackets:** SL {sx.BRACKETS['sl']:g} / T {sx.BRACKETS['target']:g}",
        "",
    ]
    for name, win in (
        ("sx_1y", sx.WINDOW_1Y),
        ("sx_3y", sx.WINDOW_3Y),
        ("sx_5y", sx.WINDOW_5Y),
    ):
        rows = clip(list(calls or []), win["start"], win["end"])
        key = name.split("_")[1]
        e = exp.get(key) or {}
        ok, msg = _match(name, len(rows), _hit(rows), int(e.get("n") or 0), float(e.get("hit_pct") or 0))
        (passes if ok else fails).append(msg)
        lines.append(f"- {msg}")
        print(msg, flush=True)

    from prod_live.adapters import live_session_sensex as ad
    from prod_live.logic.combined_live_book_sensex import combine_live_rows

    dummy = {"fno_analysis": {}}
    out = ad.annotate_analyze_result(dummy, symbol="NIFTY", dual_call={"decision": "BUY"})
    ok_iso = "final_sensex_fno" not in (out.get("fno_analysis") or {})
    msg = f"{'PASS' if ok_iso else 'FAIL'} nifty_isolation"
    (passes if ok_iso else fails).append(msg)
    lines.append(f"- {msg}")
    print(msg, flush=True)

    comb = combine_live_rows()
    ok_c = int(comb.get("blocked") or 0) == 0 and int(comb.get("n") or 0) >= int(
        (exp.get("5y") or {}).get("n") or 0
    )
    msg = f"{'PASS' if ok_c else 'FAIL'} combine_sensex: n={comb.get('n')} blocked={comb.get('blocked')}"
    (passes if ok_c else fails).append(msg)
    lines.append(f"- {msg}")
    print(msg, flush=True)

    lines += ["", f"**PASS {len(passes)} · FAIL {len(fails)}**", ""]
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT} · held_stamped={len(held)}", flush=True)
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(main())
