"""List current live-logic (CHAMP_PLUS) calls for 2026-11-16..18."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "prod_live"))
import path_setup  # noqa: F401,E402

from prod_live.logic.champ_plus_live import load_held_calls, load_live_book, ensure_session_calls  # noqa: E402
from prod_live.logic import champ_plus_engine as eng  # noqa: E402

START, END = "2026-11-16", "2026-11-18"
DAYS = ["2026-11-16", "2026-11-17", "2026-11-18"]


def main() -> None:
    held = load_held_calls()
    full = load_live_book()
    live_raw = eng.load_live_ledger()

    print("=== data coverage ===")
    print(f"held max day: {max((str(r.get('day') or '')[:10] for r in held), default=None)} n={len(held)}")
    print(f"live ledger days: {sorted({str(r.get('day') or '')[:10] for r in live_raw})}")
    print(f"full book max: {max((str(r.get('day') or '')[:10] for r in full), default=None)} n={len(full)}")

    # tape end
    tape = ROOT / "stock_signal_data" / "fno_validate" / "NIFTY_5m_kite.csv"
    if tape.exists():
        import pandas as pd

        df = pd.read_csv(tape, usecols=[0])
        col = df.columns[0]
        print(f"5m tape last: {df[col].iloc[-1]} n={len(df)}")

    print()
    print(f"=== CHAMP_PLUS held∪live · {START} → {END} (before ensure) ===")
    rows = [
        r
        for r in full
        if START <= str(r.get("day") or "")[:10] <= END
    ]
    rows = sorted(rows, key=lambda r: (str(r.get("day")), str(r.get("hm") or "")))
    print(f"n={len(rows)}")
    for r in rows:
        w = r.get("win")
        wstr = "W" if w is True else ("L" if w is False else "?")
        print(
            f"  {r.get('day')} {r.get('hm')} "
            f"{str(r.get('decision') or r.get('side') or '').upper():4} "
            f"track={str(r.get('track') or '—'):16} win={wstr} pts={r.get('points')}"
        )

    print()
    print("=== ensure_session_calls per day (live engine day-open seed) ===")
    for day in DAYS:
        meta = ensure_session_calls(day)
        day_calls = meta.get("day_calls") or []
        added = meta.get("added") or []
        print(
            f"  {day}: n_day={meta.get('n_day')} n_added={meta.get('n_added')} "
            f"blocked={meta.get('blocked')} day_calls={len(day_calls)} added={len(added)}"
        )
        for r in day_calls:
            w = r.get("win")
            wstr = "W" if w is True else ("L" if w is False else "?")
            print(
                f"      {r.get('hm')} {str(r.get('decision') or r.get('side') or '').upper():4} "
                f"track={str(r.get('track') or '—'):16} win={wstr} "
                f"entry={r.get('entry')} SL={r.get('stop_loss')} T={r.get('target_1')}"
            )

    full2 = load_live_book()
    rows2 = [
        r
        for r in full2
        if START <= str(r.get("day") or "")[:10] <= END
    ]
    rows2 = sorted(rows2, key=lambda r: (str(r.get("day")), str(r.get("hm") or "")))
    print()
    print(f"=== AFTER ensure · total board calls {START}→{END}: {len(rows2)} ===")
    by_day = {}
    for r in rows2:
        d = str(r.get("day") or "")[:10]
        by_day.setdefault(d, []).append(r)
    for d in DAYS:
        print(f"  {d}: {len(by_day.get(d) or [])} call(s)")
    for r in rows2:
        w = r.get("win")
        wstr = "W" if w is True else ("L" if w is False else "?")
        print(
            f"  {r.get('day')} {r.get('hm')} "
            f"{str(r.get('decision') or r.get('side') or '').upper():4} "
            f"track={str(r.get('track') or '—'):16} win={wstr} pts={r.get('points')}"
        )


if __name__ == "__main__":
    main()
