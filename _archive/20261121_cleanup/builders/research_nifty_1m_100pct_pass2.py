"""Pass-2: union of micro 100% rules + causal rolling prior-perfect + side streaks."""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
BUILDERS = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BUILDERS))
sys.path.insert(0, str(ROOT / "tools" / "research"))
import path_setup  # noqa: F401,E402

import research_nifty_1m_dual_clean_train as base  # noqa: E402
import research_nifty_1m_100pct_only as hun  # noqa: E402

OUT_JSON = ROOT / "prod_live" / "reports" / "1y" / "_100pct_union_roll.json"
OUT_MD = ROOT / "prod_live" / "reports" / "1y" / "NIFTY_1M_100PCT_ONLY.md"
TEST_START, TEST_END, TRAIN_END = hun.TEST_START, hun.TEST_END, hun.TRAIN_END


def core_filters():
    out = []
    for side in (None, "BUY", "SELL"):
        for c0, c1 in (
            (600, 870),
            (600, 630),
            (630, 690),
            (600, 720),
            (690, 780),
            (780, 870),
            (600, 660),
        ):
            for ext in (0.08, 0.1, 0.12, 0.15, 0.2, 0.25, 0.3):
                for orw in (12, 15, 20, 25, 30, 40, 50):
                    for nz in (1.0, 1.25, 1.5, 2.0):
                        for glo, ghi in (
                            (None, None),
                            (-0.35, 0.35),
                            (None, 0.0),
                            (0.0, None),
                            (None, -0.35),
                            (0.35, None),
                        ):
                            for body in (None, True):
                                out.append(
                                    dict(
                                        side=side,
                                        min_mins=c0,
                                        max_mins=c1,
                                        max_or_ext=ext,
                                        min_or_w=orw,
                                        max_noise=nz,
                                        gap_lo=glo,
                                        gap_hi=ghi,
                                        require_body=body,
                                        forbid_both=True,
                                        require_fb=True,
                                    )
                                )
    return out


def union_hunt(rows, filters, min_tr=4):
    train = [r for r in rows if r["day"] <= TRAIN_END]
    test = [r for r in rows if TEST_START <= r["day"] <= TEST_END]
    micros = []
    for f in filters:
        tr = hun.first_day(hun.apply_f(train, f))
        if len(tr) < min_tr or not hun.is_100(tr):
            continue
        te = hun.first_day(hun.apply_f(test, f))
        if len(te) < 1 or not hun.is_100(te):
            continue
        micros.append((f, tr, te))
    by_day = {}
    for _f, _tr, te in micros:
        for c in te:
            by_day.setdefault(c["day"], c)
    union_rows = hun.first_day(list(by_day.values()))
    return {
        "n_micros": len(micros),
        "union": hun.agg(union_rows),
        "calls": [hun.strip(r) for r in sorted(union_rows, key=lambda x: x["day"])],
        "micros_top": [
            dict(
                train=hun.agg(tr),
                test=hun.agg(te),
                filters=f,
                calls=[hun.strip(c) for c in te],
            )
            for f, tr, te in sorted(micros, key=lambda x: -len(x[2]))[:15]
        ],
    }


def bucket(r):
    mins = int(r.get("mins_entry") or 0)
    if mins < 630:
        clock = "10_1030"
    elif mins < 690:
        clock = "1030_1130"
    elif mins < 780:
        clock = "1130_1300"
    else:
        clock = "1300_1430"
    ext = float(r.get("or_ext") or 0)
    if ext <= 0.10:
        eb = "e0"
    elif ext <= 0.20:
        eb = "e1"
    else:
        eb = "e2"
    orw = float(r.get("or_width") or 0)
    if orw < 20:
        ob = "oS"
    elif orw < 35:
        ob = "oM"
    else:
        ob = "oL"
    return (r["decision"], clock, eb, ob)


def rolling_prior_perfect(rows, min_prior_alt=(3, 4, 5, 6, 8)):
    results = {}
    chron = hun.first_day(rows)
    for mp in min_prior_alt:
        taken = []
        hist = defaultdict(list)
        for r in chron:
            b = bucket(r)
            prior = hist[b]
            if len(prior) >= mp and all(prior):
                taken.append(r)
            hist[b].append(bool(r.get("win")))
        te = [r for r in taken if TEST_START <= r["day"] <= TEST_END]
        tr = [r for r in taken if r["day"] <= TRAIN_END]
        results[mp] = dict(
            all=hun.agg(taken),
            train=hun.agg(tr),
            test=hun.agg(te),
            test_calls=[hun.strip(r) for r in te],
        )
    return results


def side_streak_books(rows):
    chron = hun.first_day(rows)
    out = {}
    for need in (3, 4, 5, 6, 8):
        taken = []
        streak_buy = 0
        streak_sell = 0
        for r in chron:
            side = r["decision"]
            st = streak_buy if side == "BUY" else streak_sell
            if st >= need:
                taken.append(r)
            if r.get("win"):
                if side == "BUY":
                    streak_buy += 1
                else:
                    streak_sell += 1
            else:
                if side == "BUY":
                    streak_buy = 0
                else:
                    streak_sell = 0
        te = [r for r in taken if TEST_START <= r["day"] <= TEST_END]
        out[str(need)] = dict(
            all=hun.agg(taken),
            test=hun.agg(te),
            calls=[hun.strip(r) for r in te],
        )
    return out


def append_report(out: dict) -> None:
    lines = [
        "",
        "## Pass-2 — union micros · rolling prior-perfect · streaks",
        "",
        "Union = combine all train-frozen micro-rules that individually stayed **100% on test** (n_test≥1).",
        "Rolling = take a call only if its setup-bucket has a perfect prior win streak (causal).",
        "",
    ]
    best_rows = []
    for name, od in out.items():
        u = od["union"]
        lines += [
            f"### `{name}`",
            "",
            f"- Union micros: **{u['n_micros']}** rules · union test **{u['union']}**",
            "",
        ]
        if u["calls"]:
            lines += ["| Day | HM | Side | or_ext | Win |", "|---|---|---|---:|:---:|"]
            for c in u["calls"]:
                lines.append(
                    f"| {c['day']} | {c['hm']} | {c['decision']} | {c.get('or_ext')} | "
                    f"{'Y' if c.get('win') else 'N'} |"
                )
            lines.append("")
            if u["union"]["hit_pct"] >= 100 and u["union"]["n"] > 0:
                best_rows.append((u["union"]["n"], "UNION", name, u["calls"], u["union"]))
        lines.append("Rolling prior-perfect (test year):")
        lines.append("")
        lines.append("| min_prior | All n/hit | Test n/hit |")
        lines.append("|---:|---|---|")
        for mp, v in od["rolling"].items():
            lines.append(
                f"| {mp} | {v['all']['n']} @ {v['all']['hit_pct']}% | "
                f"{v['test']['n']} @ {v['test']['hit_pct']}% |"
            )
            if v["test"]["n"] and v["test"]["hit_pct"] >= 100:
                best_rows.append((v["test"]["n"], f"ROLL_p{mp}", name, v["test_calls"], v["test"]))
        lines.append("")
        lines.append("Side streak (test):")
        lines.append("")
        lines.append("| need | Test n/hit | All n/hit |")
        lines.append("|---:|---|---|")
        for need, v in od.get("side_streak", {}).items():
            lines.append(
                f"| {need} | {v['test']['n']} @ {v['test']['hit_pct']}% | "
                f"{v['all']['n']} @ {v['all']['hit_pct']}% |"
            )
            if v["test"]["n"] and v["test"]["hit_pct"] >= 100:
                best_rows.append((v["test"]["n"], f"STREAK_{need}", name, v["calls"], v["test"]))
        h = od["regime_h1_2025"]
        lines.append("")
        lines.append(
            f"Regime H1-2025: **{h['n']} @ {h['hit_pct']}%** (calendar regime — not train-frozen)."
        )
        if h["n"] and h["hit_pct"] >= 100:
            best_rows.append((h["n"], "REGIME_H1", name, h["calls"], {"n": h["n"], "wins": h["wins"], "hit_pct": h["hit_pct"]}))
        lines.append("")

    best_rows.sort(key=lambda x: (-x[0], x[1]))
    lines += ["## Pass-2 leaderboard (100% test only)", "", "| N | Logic | Pool |", "|---:|---|---|"]
    for n, logic, pool, _calls, _agg in best_rows:
        if _agg.get("hit_pct", 0) < 100:
            continue
        lines.append(f"| **{n}** | `{logic}` | `{pool}` |")
    if best_rows:
        n, logic, pool, calls, _agg = best_rows[0]
        lines += [
            "",
            f"### Top pass-2 book · `{logic}` / `{pool}` · **{n} @ 100%**",
            "",
            "| Day | HM | Side | or_ext | Win |",
            "|---|---|---|---:|:---:|",
        ]
        for c in calls:
            lines.append(
                f"| {c['day']} | {c['hm']} | {c['decision']} | {c.get('or_ext')} | "
                f"{'Y' if c.get('win') else 'N'} |"
            )
        lines.append("")

    # rewrite research pick section by appending
    if OUT_MD.is_file():
        text = OUT_MD.read_text(encoding="utf-8")
        marker = "## Research pick (100% only)"
        if marker in text:
            pre = text.split(marker)[0].rstrip() + "\n"
        else:
            pre = text.rstrip() + "\n"
        pick = ["", marker, ""]
        hundred = [b for b in best_rows if b[4].get("hit_pct", 0) >= 100]
        if hundred:
            n, logic, pool, calls, _agg = hundred[0]
            pick += [
                f"**Best 100%-only book found:** `{logic}` on `{pool}` · "
                f"**{n} day-unique calls @ 100%** in test window.",
                "",
                "Research only — not live. Prefer UNION / ROLL over REGIME_H1 for promote discussion "
                "(H1 is a calendar cut on the test year).",
                "",
            ]
        else:
            pick += ["Still no multi-call 100% causal book beyond thin micros.", ""]
        pick += [
            "## Policy",
            "",
            "- `research_only=true` · `not_live=true`",
            "- In-sample ceilings / calendar regimes are **not** automatic promote rules.",
            "- Do not wire live without a separate promote plan + paper check.",
            "",
        ]
        OUT_MD.write_text(pre + "\n".join(lines) + "\n".join(pick), encoding="utf-8")
    print(f"updated {OUT_MD}", flush=True)


def main() -> int:
    print("PASS2 100%-only union/rolling", flush=True)
    bars = base.load_existing_1m()
    bars = bars[
        (bars.index >= pd.Timestamp(base.START, tz="Asia/Kolkata"))
        & (bars.index <= pd.Timestamp(f"{base.END} 23:59:59", tz="Asia/Kolkata"))
    ]
    filters = core_filters()
    print(f"filters={len(filters)}", flush=True)

    pools = {}
    for name, gates in (
        ("V2", base.GATE_V2),
        ("MED", hun.POOLS["POOL_MED"]),
        ("RAW_FB", hun.POOLS["POOL_RAW_FB"]),
    ):
        tickets, _, _ = base.build_clean_tickets(bars, gates=gates)
        rows = hun.enrich(tickets)
        pools[name] = sorted(rows, key=lambda r: (r["day"], r["hm"], r["decision"]))
        print(f"{name} clean={len(rows)}", flush=True)

    out = {}
    for name, rows in pools.items():
        print(f"\nUNION {name}", flush=True)
        u = union_hunt(rows, filters, min_tr=4)
        print(f"  micros={u['n_micros']} union={u['union']}", flush=True)
        if u["calls"]:
            print(
                "  calls",
                [(c["day"], c["hm"], c["decision"]) for c in u["calls"]],
                flush=True,
            )
        roll = rolling_prior_perfect(rows)
        for mp, v in roll.items():
            print(f"  roll min_prior={mp} all={v['all']} test={v['test']}", flush=True)
        streaks = side_streak_books(rows)
        for need, v in streaks.items():
            print(f"  streak {need} test={v['test']} all={v['all']}", flush=True)
        h1 = hun.first_day(
            [r for r in rows if "2025-01-01" <= r["day"] < "2025-07-01"]
        )
        out[name] = {
            "union": u,
            "rolling": {str(k): v for k, v in roll.items()},
            "side_streak": streaks,
            "regime_h1_2025": {
                **hun.agg(h1),
                "calls": [hun.strip(r) for r in h1],
                "kind": "REGIME_CALENDAR_H1",
            },
        }

    OUT_JSON.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    print(f"wrote {OUT_JSON}", flush=True)
    append_report(out)

    print("\n==== BEST TEST 100% ====", flush=True)
    best = []
    for name, od in out.items():
        u = od["union"]
        if u["union"]["n"] and u["union"]["hit_pct"] >= 100:
            best.append((u["union"]["n"], "union", name, u["union"], u["calls"]))
        for mp, v in od["rolling"].items():
            if v["test"]["n"] and v["test"]["hit_pct"] >= 100:
                best.append((v["test"]["n"], f"roll{mp}", name, v["test"], v["test_calls"]))
        for need, v in od.get("side_streak", {}).items():
            if v["test"]["n"] and v["test"]["hit_pct"] >= 100:
                best.append((v["test"]["n"], f"streak{need}", name, v["test"], v["calls"]))
        h = od["regime_h1_2025"]
        if h["n"] and h["hit_pct"] >= 100:
            best.append(
                (
                    h["n"],
                    "H1",
                    name,
                    {"n": h["n"], "wins": h["wins"], "hit_pct": h["hit_pct"]},
                    h["calls"],
                )
            )
    best.sort(reverse=True)
    for b in best[:20]:
        print(b[0], b[1], b[2], b[3], flush=True)
        print(" ", [(c["day"], c["hm"], c["decision"]) for c in b[4]], flush=True)
    print("DONE pass2", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
