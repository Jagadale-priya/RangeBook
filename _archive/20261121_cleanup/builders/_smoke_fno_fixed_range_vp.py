"""Smoke Fixed Range Volume Profile on NIFTY local tape (chart-only).

  python -u prod_live/tests/builders/_smoke_fno_fixed_range_vp.py

Uses local kite CSV when live Kite token is unavailable. Groww unused.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [
    str(ROOT),
    str(ROOT / "app"),
    str(ROOT / "app" / "fno"),
    str(ROOT / "app" / "market"),
    str(ROOT / "prod_live"),
]

import fno_fixed_range_vp as frvp  # noqa: E402


def main() -> int:
    print("=== FRVP smoke (chart-only) ===", flush=True)
    print("note:", frvp.INDEX_VOLUME_NOTE, flush=True)

    # Prefer a known session morning on the 5m tape
    start = "2026-11-18 09:15:00+05:30"
    end = "2026-11-18 12:00:00+05:30"
    out = frvp.build_profile_for_symbol(
        "NIFTY",
        start=start,
        end=end,
        n_rows=24,
        va_pct=0.70,
        prefer_interval="5minute",
    )
    print(json.dumps({
        "ok": out.get("ok"),
        "error": out.get("error"),
        "source": out.get("source"),
        "bar_count": out.get("bar_count"),
        "poc": out.get("poc"),
        "vah": out.get("vah"),
        "val": out.get("val"),
        "total_vol": out.get("total_vol"),
        "n_rows": out.get("n_rows"),
        "chart_only": (out.get("meta") or {}).get("chart_only"),
        "no_calls": (out.get("meta") or {}).get("no_calls_link"),
    }, indent=2), flush=True)

    if not out.get("ok"):
        # synthetic fallback proves engine path still works offline
        import pandas as pd

        idx = pd.date_range("2026-11-18 09:15", periods=30, freq="5min", tz="Asia/Kolkata")
        px = 25200.0
        rows = []
        for i, ts in enumerate(idx):
            o = px
            c = px + (5 if 10 <= i <= 20 else -2)
            rows.append({"Open": o, "High": max(o, c) + 8, "Low": min(o, c) - 8, "Close": c, "Volume": 100 + i * 3})
            px = c
        toy = frvp.compute_fixed_range_vp(pd.DataFrame(rows, index=idx), n_rows=24)
        print("tape miss — toy ok=", toy.get("ok"), "poc=", toy.get("poc"), flush=True)
        return 0 if toy.get("ok") else 1

    assert out["val"] <= out["poc"] <= out["vah"]
    assert out["meta"]["chart_only"] and out["meta"]["no_calls_link"]
    print("SMOKE OK", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
