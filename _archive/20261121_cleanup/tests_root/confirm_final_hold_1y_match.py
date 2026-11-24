"""Confirm final hold 1y matches the locked screenshot / LIVE_FINAL baseline EXACTLY.

Golden book = STACK_PLUS_CROWN_HTF_CAP2 + AGREE_15M_ANY5 stamps
(same builder as FINAL LOGIC/live_final_1y_months_accurate.py).

This is the desk that replaces old live listing — month calls must match golden.

  python -u prod_live/tests/confirm_final_hold_1y_match.py
  python -u prod_live/tests/confirm_final_hold_1y_match.py --notify
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUILDERS = Path(__file__).resolve().parent / "builders"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BUILDERS))
sys.path.insert(0, str(ROOT / "prod_live"))
import path_setup  # noqa: F401,E402

# Reuse the exact final-hold builder (vendored under builders/)
import live_final_1y_months_accurate as hold  # noqa: E402

PROD = ROOT / "prod_live"
OUT = PROD / "reports" / "1y_final_hold_match"
GOLDEN = {
    "window": {"start": "2025-10-24", "end": "2026-10-23", "sessions": 217},
    "live_stack": {"n": 229, "hit_pct": 75.11, "wins": 172, "losses": 57},
    "accurate": {"n": 54, "hit_pct": 90.74, "wins": 49, "losses": 5},
    "other": {"n": 175, "hit_pct": 70.29},
    "monthly": [
        {"month": "2025-10", "n": 9, "hit_pct": 66.67, "accurate_n": 3, "accurate_hit_pct": 100.0, "days_no_call": 1},
        {"month": "2025-11", "n": 17, "hit_pct": 76.47, "accurate_n": 1, "accurate_hit_pct": 100.0, "days_no_call": 6},
        {"month": "2025-12", "n": 21, "hit_pct": 80.95, "accurate_n": 4, "accurate_hit_pct": 100.0, "days_no_call": 7},
        {"month": "2026-01", "n": 19, "hit_pct": 73.68, "accurate_n": 6, "accurate_hit_pct": 100.0, "days_no_call": 5},
        {"month": "2026-02", "n": 22, "hit_pct": 63.64, "accurate_n": 5, "accurate_hit_pct": 80.0, "days_no_call": 5},
        {"month": "2026-03", "n": 11, "hit_pct": 72.73, "accurate_n": 3, "accurate_hit_pct": 66.67, "days_no_call": 11},
        {"month": "2026-04", "n": 14, "hit_pct": 57.14, "accurate_n": 2, "accurate_hit_pct": 100.0, "days_no_call": 6},
        {"month": "2026-05", "n": 15, "hit_pct": 80.0, "accurate_n": 6, "accurate_hit_pct": 83.33, "days_no_call": 8},
        {"month": "2026-06", "n": 22, "hit_pct": 72.73, "accurate_n": 6, "accurate_hit_pct": 66.67, "days_no_call": 8},
        {"month": "2026-07", "n": 18, "hit_pct": 72.22, "accurate_n": 4, "accurate_hit_pct": 100.0, "days_no_call": 6},
        {"month": "2026-08", "n": 18, "hit_pct": 77.78, "accurate_n": 4, "accurate_hit_pct": 100.0, "days_no_call": 4},
        {"month": "2026-09", "n": 21, "hit_pct": 71.43, "accurate_n": 5, "accurate_hit_pct": 100.0, "days_no_call": 5},
        {"month": "2026-10", "n": 22, "hit_pct": 100.0, "accurate_n": 5, "accurate_hit_pct": 100.0, "days_no_call": 1},
    ],
}


def _near(a, b, tol=0.011):
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    return abs(float(a) - float(b)) <= tol


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--notify", action="store_true")
    args = ap.parse_args()

    print("Rebuilding final hold stack (same as screenshot / LIVE_FINAL)…", flush=True)
    # Run hold builder by invoking its main pieces
    live = hold._build_live_stack(hold.START, hold.END)
    sess, stack = live["sess"], live["stack"]
    books = hold.d.build_books(
        {
            "sess": sess,
            "stack": stack,
            "good": live["good"],
            "proven": live["proven"],
            "champ": live["champ"],
            "champ_raw": live["champ"],
            "crown": live["crown_htf"],
            "crown_htf": live["crown_htf"],
            "active": live["active"],
        }
    )
    agree_rows = hold._clean(books["agree_any5_5mentry"])
    agree_exact = {hold._key(r) for r in agree_rows}
    stamped = hold._stamp(stack, agree_exact)
    months = hold._month_block(stamped, sess)

    from accuracy_max_6m import _agg

    a_live = _agg(stamped)
    a_acc = _agg([r for r in stamped if r.get("accurate")])
    a_oth = _agg([r for r in stamped if not r.get("accurate")])

    got = {
        "window": {"start": hold.START, "end": hold.END, "sessions": len(sess)},
        "live_stack": {
            "n": a_live["n"],
            "hit_pct": a_live["hit_pct"],
            "wins": a_live["wins"],
            "losses": a_live["losses"],
        },
        "accurate": {
            "n": a_acc["n"],
            "hit_pct": a_acc["hit_pct"],
            "wins": a_acc["wins"],
            "losses": a_acc["losses"],
        },
        "other": {"n": a_oth["n"], "hit_pct": a_oth["hit_pct"]},
        "monthly": [
            {
                "month": m["month"],
                "n": m["n"],
                "hit_pct": m["hit_pct"],
                "accurate_n": m["accurate_n"],
                "accurate_hit_pct": m["accurate_hit_pct"],
                "days_no_call": m["days_no_call"],
            }
            for m in months
        ],
    }

    mismatches = []
    # totals
    for key in ("n", "hit_pct", "wins", "losses"):
        if got["live_stack"].get(key) != GOLDEN["live_stack"].get(key) and not (
            key == "hit_pct" and _near(got["live_stack"].get(key), GOLDEN["live_stack"].get(key))
        ):
            mismatches.append(
                f"live_stack.{key}: got {got['live_stack'].get(key)} expected {GOLDEN['live_stack'].get(key)}"
            )
    for key in ("n", "hit_pct"):
        g, e = got["accurate"].get(key), GOLDEN["accurate"].get(key)
        if g != e and not (key == "hit_pct" and _near(g, e)):
            mismatches.append(f"accurate.{key}: got {g} expected {e}")
    if got["window"]["sessions"] != GOLDEN["window"]["sessions"]:
        mismatches.append(
            f"sessions: got {got['window']['sessions']} expected {GOLDEN['window']['sessions']}"
        )

    # monthly
    g_by = {m["month"]: m for m in GOLDEN["monthly"]}
    for m in got["monthly"]:
        exp = g_by.get(m["month"])
        if not exp:
            mismatches.append(f"month {m['month']}: unexpected")
            continue
        for key in ("n", "accurate_n", "days_no_call"):
            if m.get(key) != exp.get(key):
                mismatches.append(
                    f"{m['month']}.{key}: got {m.get(key)} expected {exp.get(key)}"
                )
        for key in ("hit_pct", "accurate_hit_pct"):
            if not _near(m.get(key), exp.get(key)):
                mismatches.append(
                    f"{m['month']}.{key}: got {m.get(key)} expected {exp.get(key)}"
                )

    # missing months
    for ym in g_by:
        if ym not in {m["month"] for m in got["monthly"]}:
            mismatches.append(f"month {ym}: missing")

    passed = len(mismatches) == 0
    OUT.mkdir(parents=True, exist_ok=True)
    payload = {
        "passed": passed,
        "golden": GOLDEN,
        "got": got,
        "mismatches": mismatches,
        "note": (
            "Final hold = STACK_PLUS_CROWN_HTF_CAP2 + AGREE stamps from live pool/prod2. "
            "OR-break UI reconstruction (177@67%) is NOT this book — do not use it for match."
        ),
    }
    (OUT / "final_hold_1y_match.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8"
    )

    # Also refresh canonical copy under prod_live/reports/1y
    hold.main()  # regenerates FINAL LOGIC report
    src_md = ROOT / "FINAL LOGIC" / "LIVE_FINAL_1Y_MONTHS_ACCURATE.md"
    if src_md.is_file():
        (PROD / "reports" / "1y" / "LIVE_FINAL_1Y_MONTHS_ACCURATE.md").write_text(
            src_md.read_text(encoding="utf-8"), encoding="utf-8"
        )

    lines = [
        "# Final hold 1y — EXACT match confirmation",
        "",
        f"**Result: `{'PASS — matches screenshot / golden baseline' if passed else 'FAIL'}`**",
        "",
        f"Window `{GOLDEN['window']['start']}` → `{GOLDEN['window']['end']}` · "
        f"**{GOLDEN['window']['sessions']}** sessions",
        "",
        "## Totals",
        "",
        "| Slice | Golden N | Golden Hit | Got N | Got Hit | Match |",
        "|---|---:|---:|---:|---:|---|",
        f"| All live stack | {GOLDEN['live_stack']['n']} | {GOLDEN['live_stack']['hit_pct']}% | "
        f"{got['live_stack']['n']} | {got['live_stack']['hit_pct']}% | "
        f"{'OK' if got['live_stack']['n']==GOLDEN['live_stack']['n'] and _near(got['live_stack']['hit_pct'], GOLDEN['live_stack']['hit_pct']) else 'FAIL'} |",
        f"| Accurate tagged | {GOLDEN['accurate']['n']} | {GOLDEN['accurate']['hit_pct']}% | "
        f"{got['accurate']['n']} | {got['accurate']['hit_pct']}% | "
        f"{'OK' if got['accurate']['n']==GOLDEN['accurate']['n'] and _near(got['accurate']['hit_pct'], GOLDEN['accurate']['hit_pct']) else 'FAIL'} |",
        "",
        "## Per month",
        "",
        "| Month | G Calls | G Hit | G AccN | G AccHit | Got Calls | Got Hit | Got AccN | Got AccHit | Match |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    got_by = {m["month"]: m for m in got["monthly"]}
    for exp in GOLDEN["monthly"]:
        g = got_by.get(exp["month"], {})
        ok = (
            g.get("n") == exp["n"]
            and g.get("accurate_n") == exp["accurate_n"]
            and g.get("days_no_call") == exp["days_no_call"]
            and _near(g.get("hit_pct"), exp["hit_pct"])
            and _near(g.get("accurate_hit_pct"), exp["accurate_hit_pct"])
        )
        lines.append(
            f"| {exp['month']} | {exp['n']} | {exp['hit_pct']}% | {exp['accurate_n']} | "
            f"{exp['accurate_hit_pct']}% | {g.get('n')} | {g.get('hit_pct')}% | "
            f"{g.get('accurate_n')} | {g.get('accurate_hit_pct')}% | {'OK' if ok else 'FAIL'} |"
        )

    if mismatches:
        lines += ["", "## Mismatches", ""]
        for m in mismatches:
            lines.append(f"- {m}")
    else:
        lines += [
            "",
            "## Verdict",
            "",
            "Every month matches the locked final-hold baseline (your screenshot). "
            "This is the book that replaces old live listing.",
            "",
        ]
    md = OUT / "FINAL_HOLD_1Y_MATCH.md"
    md.write_text("\n".join(lines), encoding="utf-8")

    if args.notify:
        try:
            from dotenv import load_dotenv

            load_dotenv(ROOT / ".env")
        except Exception:
            pass
        try:
            import desktop_notify

            desktop_notify.notify(
                "Final hold 1y match " + ("PASS" if passed else "FAIL"),
                f"Stack {got['live_stack']['n']}@{got['live_stack']['hit_pct']}% · "
                f"Acc {got['accurate']['n']}@{got['accurate']['hit_pct']}% · "
                f"mismatches={len(mismatches)}",
                stock="NIFTY",
                kind="alert",
                dedupe_key="final_hold_1y_match",
                product="fno",
            )
        except Exception as exc:
            print("notify failed", exc, flush=True)

    print(json.dumps({"passed": passed, "mismatches": mismatches[:20], "wrote": str(md)}, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
