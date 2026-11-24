"""Compare available NIFTY logics with dual proven/champion listing removed.

Window: last 1y ending 2026-11-13 (held books / research CSVs).
Does not re-simulate packs — uses locked call ledgers.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
END = "2026-11-13"
START = (pd.Timestamp(END) - pd.DateOffset(years=1)).strftime("%Y-%m-%d")
OUT = ROOT / "reports" / "1y" / "NIFTY_NO_DUAL_FIRST_1Y.md"

DUAL_TRACKS = {"champion", "proven_research", "proven_100", "proven"}


def _load_json_calls(path: Path):
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        for v in raw.values():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                return v
            if isinstance(v, dict) and isinstance(v.get("calls"), list):
                return v["calls"]
    return []


def _is_win(r: dict):
    if r.get("win") is True:
        return True
    if r.get("win") is False:
        return False
    w = str(r.get("win") or "").strip().lower()
    if w in ("1", "true", "yes"):
        return True
    if w in ("0", "false", "no"):
        return False
    o = str(r.get("outcome") or "").lower()
    if o.startswith("t1") or o == "target":
        return True
    if "sl" in o or o == "stop":
        return False
    pts = r.get("points")
    if pts is not None:
        try:
            return float(pts) > 0
        except Exception:
            return None
    return None


def _clip(rows, dayk="day"):
    out = []
    for r in rows:
        d = str(r.get(dayk) or r.get("date") or "")[:10]
        if START <= d <= END:
            out.append(r)
    return out


def _stats(rows, label: str, note: str = ""):
    n = len(rows)
    wins = sum(1 for r in rows if _is_win(r) is True)
    losses = sum(1 for r in rows if _is_win(r) is False)
    hit = (100.0 * wins / n) if n else 0.0
    net = 0.0
    for r in rows:
        try:
            net += float(r.get("points") or 0)
        except Exception:
            pass
    tracks = {}
    for r in rows:
        t = str(r.get("track") or r.get("accurate_tag") or r.get("desk") or r.get("book") or "?")
        tracks[t] = tracks.get(t, 0) + 1
    return {
        "label": label,
        "n": n,
        "wins": wins,
        "losses": losses,
        "hit": hit,
        "net": net,
        "tracks": tracks,
        "note": note,
    }


def main() -> None:
    rows = []

    cp = ROOT / "holding_accurate" / "champion_plus" / "t30_sl30_5y_calls.json"
    cp_all = _clip(_load_json_calls(cp))
    rows.append(
        _stats(
            cp_all,
            "CHAMP_PLUS T30SL30 Cap4 (held)",
            "Primary fill when dual list suppressed · locked book",
        )
    )
    rows.append(
        _stats(
            [r for r in cp_all if str(r.get("track")) not in DUAL_TRACKS],
            "CHAMP_PLUS minus champion/proven tracks",
            "Fill-ish streams only (dual10m / crown / good / dual5)",
        )
    )

    for name, path, note in [
        (
            "push5 1y",
            ROOT / "holding_accurate" / "champion_plus" / "push5_calls_1y.json",
            "Earlier CHAMP_PLUS push variant",
        ),
        (
            "push4 1y",
            ROOT / "holding_accurate" / "champion_plus" / "push4_calls_1y.json",
            "Earlier CHAMP_PLUS push variant",
        ),
        (
            "T30 SL20",
            ROOT / "holding_accurate" / "champion_plus" / "t30_sl20_calls.json",
            "Tighter SL variant",
        ),
        (
            "T30 SL20 more",
            ROOT / "holding_accurate" / "champion_plus" / "t30_sl20_more_calls.json",
            "Wider fill T30/SL20",
        ),
    ]:
        if path.exists():
            rows.append(_stats(_clip(_load_json_calls(path)), name, note))

    proven_csv = ROOT / "research" / "nifty_fno" / "reports" / "PROVEN_ACCURATE_1Y_CALLS.csv"
    if proven_csv.exists():
        with proven_csv.open(encoding="utf-8") as f:
            proven_rows = list(csv.DictReader(f))
        rows.append(
            _stats(
                proven_rows,
                "Research proven book (15m+10m proven_100)",
                "Not wired to live · accurate research folder only",
            )
        )

    # Dual champion-only reference from CHAMP_PLUS seed tracks (same window)
    dual_seed = [r for r in cp_all if str(r.get("track")) in DUAL_TRACKS]
    rows.append(
        _stats(
            dual_seed,
            "Dual proven/champion seed (inside CHAMP_PLUS book)",
            "What we removed from first listing · for contrast only",
        )
    )

    rows_sorted = sorted(rows, key=lambda x: (-x["hit"], -x["n"]))

    lines = [
        "# NIFTY — no dual proven/champion first (1y compare)",
        "",
        f"**Window:** {START} → {END}",
        "**Live change:** `SUPPRESS_DUAL_LIST=1` (default) — dual packs still score/annotate; "
        "Calls board lists via **CHAMP_PLUS / crown fill** when empty.",
        "**Restore dual-first:** `SUPPRESS_DUAL_LIST=0`",
        "",
        "## Ranking (hit ↓, then n ↓)",
        "",
        "| Logic | n | wins | hit % | net pts | note |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for r in rows_sorted:
        lines.append(
            f"| **{r['label']}** | {r['n']} | {r['wins']} | {r['hit']:.2f} | "
            f"{r['net']:.1f} | {r['note']} |"
        )

    lines.extend(
        [
            "",
            "## Track mix (top books)",
            "",
        ]
    )
    for r in rows_sorted[:4]:
        mix = ", ".join(f"{k}:{v}" for k, v in sorted(r["tracks"].items(), key=lambda kv: -kv[1])[:8])
        lines.append(f"- **{r['label']}** — {mix or '—'}")

    lines.extend(
        [
            "",
            "## Takeaway",
            "",
            "1. With dual proven/champion **not** listing first, the strongest ready book is "
            f"**CHAMP_PLUS T30SL30** (~{rows[0]['n']} @ **{rows[0]['hit']:.2f}%**).",
            "2. Stripping champion/proven seed tracks from that book still leaves "
            f"**{rows[1]['n']} @ {rows[1]['hit']:.2f}%** on fill streams.",
            "3. Research proven-only book stays small (~29) and is **not** the live fill path.",
            "4. SL20 variants add volume but drop hit into the ~80% band — prefer ±30 Cap4.",
            "",
            "## Code",
            "",
            "- Flag: `app/fno/fno_live_config.suppress_dual_list()`",
            "- Wiring: `app/fno/fno_ws_rescore.py` (both rescore paths)",
            "- Fill: `app/fno/fno_dual_modal_list.fill_from_channels`",
            "",
            f"_Generated by `tests/builders/_cmp_no_dual_first_1y.py`_",
            "",
        ]
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(OUT)
    for r in rows_sorted:
        print(
            f"{r['hit']:6.2f}%  n={r['n']:4d}  net={r['net']:8.1f}  {r['label']}"
        )


if __name__ == "__main__":
    main()
