"""Retrain the 5m dual heads with a matched isotonic map and compare to the saved pack.

  python -u prod_live/tests/builders/research_dual5m_retrain.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
BUILDERS = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BUILDERS))
import path_setup  # noqa: F401,E402

import research_dual5m_6m_and_nov10m as m  # noqa: E402

PACK = m.PACK_DIR / "dual5m_packs.joblib"
FREEZE = m.FREEZE
TEST_A, TEST_B = "2025-11-15", "2026-11-15"


def _rank_report(name: str, packs, tickets) -> None:
    print(f"\n{name}")
    for side in ("BUY", "SELL"):
        pack = packs.get(side) or {}
        if not pack.get("available"):
            print(f"  {side} unavailable")
            continue
        rows = [r for r in tickets if r["decision"] == side and str(r["day"]) > FREEZE]
        X = np.asarray([r["x"] for r in rows], dtype=float)
        y = np.asarray([r["y"] for r in rows], dtype=int)
        raw = pack["base"].predict_proba(X)[:, 1]
        cal = np.clip(pack["iso"].transform(raw), 0.05, 0.95)
        print(
            f"  {side} oos n={len(rows)} y={100*y.mean():.1f}% "
            f"raw_auc={m._auc(y, raw):.3f} cal_auc={m._auc(y, cal):.3f} "
            f"cal p10/50/90={np.quantile(cal, [0.1, 0.5, 0.9]).round(3).tolist()} "
            f"unique_cal={len(np.unique(np.round(cal, 3)))}"
        )
        year = [r for r in rows if TEST_A <= str(r["day"]) <= TEST_B]
        if not year:
            continue
        Xy = np.asarray([r["x"] for r in year], dtype=float)
        yy = np.asarray([r["y"] for r in year], dtype=int)
        cy = np.clip(pack["iso"].transform(pack["base"].predict_proba(Xy)[:, 1]), 0.05, 0.95)
        order = np.argsort(cy)
        # top fifth vs bottom fifth of the last year
        k = max(1, len(year) // 5)
        top = yy[order[-k:]]
        bot = yy[order[:k]]
        print(
            f"    last year n={len(year)} hit={100*yy.mean():.1f}% "
            f"top fifth n={k} hit={100*top.mean():.1f}% "
            f"bottom fifth hit={100*bot.mean():.1f}%"
        )


def main() -> int:
    import joblib

    tickets = json.loads(m.CACHE_XY5.read_text(encoding="utf-8"))["tickets"]
    old = joblib.load(PACK)
    _rank_report("OLD pack (isotonic from a different tree)", old, tickets)
    new = m.train_heads_calibrated(tickets)
    _rank_report("NEW pack (isotonic on the deployed tree)", new, tickets)
    joblib.dump(new, PACK)
    print(f"\nsaved {PACK}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
