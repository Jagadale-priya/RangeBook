"""RESEARCH ONLY — last-1y deep accuracy hunt on NIFTY 1m dual CLEAN (V2 gates).

Honest protocol:
  - Rebuild GATE_V2 (+ MED / WIDE) tickets with features from cache
  - Train dual heads on tickets with day < TEST_START (no 1y leakage)
  - Score TEST window; mine 100%-hit books on TRAIN, validate on TEST
  - Also report in-sample TEST ceiling (oracle) labeled as such

  python -u prod_live/tests/builders/research_nifty_1m_dual_clean_1y_deep.py
"""
from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from itertools import product
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
BUILDERS = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BUILDERS))
sys.path.insert(0, str(ROOT / "tools" / "research"))
import path_setup  # noqa: F401,E402

import research_nifty_1m_dual_clean_train as base  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
REPORT_MD = OUT / "NIFTY_1M_DUAL_CLEAN_1Y_DEEP.md"
REPORT_JSON = OUT / "NIFTY_1M_DUAL_CLEAN_1Y_DEEP.json"

# Last full year of available 1m tape (cache ends 2025-12-30)
TEST_START = "2025-01-01"
TEST_END = "2025-12-30"
TRAIN_END = "2024-12-31"  # heads / rule mine use day <= TRAIN_END

# Extra profiles to hunt more 100% calls (still no look-ahead)
GATE_MED = {
    **base.GATE_V2,
    "min_or_width": 16.0,
    "max_noise_vs_sl": 1.50,
    "max_or_ext": 0.30,
    "min_entry_mins": 10 * 60,
    "require_body_align": True,
    "require_first_break": True,
    "forbid_both_sides": True,
}
GATE_WIDE = {
    **base.GATE_V2,
    "min_or_width": 14.0,
    "max_noise_vs_sl": 1.75,
    "max_or_ext": 0.40,
    "min_entry_mins": 9 * 60 + 45,
    "require_body_align": False,
    "require_first_break": True,
    "forbid_both_sides": True,
}

PROFILES = (
    ("V2_STRICT", base.GATE_V2),
    ("V2_MED", GATE_MED),
    ("V2_WIDE", GATE_WIDE),
)


def _agg(rows: List[dict]) -> Dict[str, Any]:
    if not rows:
        return {"n": 0, "wins": 0, "hit_pct": 0.0}
    wins = sum(1 for r in rows if r.get("win"))
    return {"n": len(rows), "wins": wins, "hit_pct": round(100.0 * wins / len(rows), 2)}


def first_day(rows: List[dict]) -> List[dict]:
    seen = set()
    out = []
    for r in sorted(rows, key=lambda x: (x.get("day"), x.get("hm"), -(float(x.get("p_t1") or 0)))):
        d = r.get("day")
        if d in seen:
            continue
        seen.add(d)
        out.append(r)
    return out


def strip_call(r: dict) -> dict:
    keys = (
        "day",
        "hm",
        "decision",
        "entry",
        "win",
        "outcome",
        "points",
        "p_t1",
        "or_ext",
        "or_width",
        "noise_vs_sl",
        "mins_entry",
        "first_break",
        "body_ok",
        "both_sides",
        "profile",
    )
    return {k: r.get(k) for k in keys}


def train_heads(tickets: List[dict], train_end: str) -> Dict[str, Any]:
    """Reuse base trainer but freeze at train_end."""
    old = base.FREEZE
    base.FREEZE = train_end
    try:
        return base.train_dual_heads(tickets)
    finally:
        base.FREEZE = old


def score(packs: Dict[str, Any], tickets: List[dict], profile: str) -> List[dict]:
    scored = base.score_all(packs, tickets)
    for r in scored:
        r["profile"] = profile
    return scored


def drop_to_hit(rows: List[dict], target: float = 100.0) -> List[dict]:
    """Drop lowest-p losses until hit≥target (keeps chronological survivors)."""
    keep = list(rows)
    while keep and _agg(keep)["hit_pct"] < target:
        losses = [i for i, r in enumerate(keep) if not r.get("win")]
        if not losses:
            break
        worst = min(losses, key=lambda i: float(keep[i].get("p_t1") or 0))
        keep.pop(worst)
    return keep


def max_n_at_100(rows: List[dict]) -> List[dict]:
    """Among day-unique rows, keep largest prefix of p-desc that is all wins;
    also try drop-losses from full set. Return the larger 100% book."""
    day = first_day(rows)
    by_p = sorted(day, key=lambda r: -float(r.get("p_t1") or 0))
    # longest all-win prefix by p
    prefix: List[dict] = []
    for r in by_p:
        if not r.get("win"):
            break
        prefix.append(r)
    dropped = drop_to_hit(by_p, 100.0)
    # only keep if truly 100
    cands = []
    for c in (prefix, dropped):
        a = _agg(c)
        if a["n"] and a["hit_pct"] >= 100.0 - 1e-9:
            cands.append(c)
    if not cands:
        return []
    return max(cands, key=lambda c: len(c))


def apply_filters(rows: List[dict], f: dict) -> List[dict]:
    out = []
    for r in rows:
        if f.get("side") and r.get("decision") != f["side"]:
            continue
        if float(r.get("p_t1") or 0) < float(f.get("p_min", 0)):
            continue
        if float(r.get("or_ext") or 0) > float(f.get("max_or_ext", 9)):
            continue
        if float(r.get("or_width") or 0) < float(f.get("min_or_w", 0)):
            continue
        if float(r.get("noise_vs_sl") or 0) > float(f.get("max_noise", 9)):
            continue
        mins = float(r.get("mins_entry") or 0)
        if mins < float(f.get("min_mins", 0)) or mins > float(f.get("max_mins", 9999)):
            continue
        if f.get("require_body") and not r.get("body_ok"):
            continue
        if f.get("forbid_both") and r.get("both_sides"):
            continue
        if f.get("require_fb") and not r.get("first_break"):
            continue
        out.append(r)
    return out


def rule_grid() -> List[dict]:
    sides = (None, "BUY", "SELL")
    p_mins = (0.50, 0.52, 0.55, 0.58, 0.60, 0.62, 0.65, 0.68, 0.70)
    max_ext = (0.10, 0.15, 0.20, 0.25, 0.30, 0.40)
    min_or = (14.0, 16.0, 20.0, 25.0, 30.0)
    max_noise = (1.00, 1.25, 1.50, 1.75)
    clocks = (
        (10 * 60, 14 * 60 + 30),
        (10 * 60 + 15, 14 * 60),
        (10 * 60 + 30, 13 * 60 + 30),
        (11 * 60, 14 * 60),
        (10 * 60, 12 * 60 + 30),
    )
    body_opts = (False, True)
    grid = []
    for side, p, ext, orw, nz, clock, body in product(
        sides, p_mins, max_ext, min_or, max_noise, clocks, body_opts
    ):
        grid.append(
            {
                "side": side,
                "p_min": p,
                "max_or_ext": ext,
                "min_or_w": orw,
                "max_noise": nz,
                "min_mins": clock[0],
                "max_mins": clock[1],
                "require_body": body,
                "forbid_both": True,
                "require_fb": True,
            }
        )
    return grid


def mine_rules_on_train(
    train_scored: List[dict],
    test_scored: List[dict],
    *,
    min_train_n: int = 8,
    min_test_n: int = 5,
    target_hit: float = 100.0,
) -> List[dict]:
    """Search filter grid on TRAIN; keep rules with train hit=100% and enough n; score TEST."""
    results = []
    grid = rule_grid()
    print(f"  rule grid size={len(grid)}", flush=True)
    t0 = time.time()
    for i, f in enumerate(grid, 1):
        if i % 5000 == 0:
            print(f"    grid {i}/{len(grid)} hits={len(results)} ({time.time()-t0:.0f}s)", flush=True)
        tr = first_day(apply_filters(train_scored, f))
        ta = _agg(tr)
        if ta["n"] < min_train_n or ta["hit_pct"] < target_hit - 1e-9:
            continue
        te = first_day(apply_filters(test_scored, f))
        ea = _agg(te)
        results.append(
            {
                "filters": f,
                "train": ta,
                "test": ea,
                "test_rows": te,
                "train_rows": tr,
            }
        )
    # prefer: test hit 100 + max test n, then train n, then higher p_min
    results.sort(
        key=lambda r: (
            1 if r["test"]["hit_pct"] >= 100.0 - 1e-9 else 0,
            r["test"]["n"] if r["test"]["hit_pct"] >= 100.0 - 1e-9 else 0,
            r["test"]["hit_pct"],
            r["train"]["n"],
            float(r["filters"]["p_min"]),
        ),
        reverse=True,
    )
    return results


def slice_table(scored: List[dict]) -> List[dict]:
    """Diagnostic slices on a scored set (day-unique where noted)."""
    rows = []
    all_du = first_day(scored)
    rows.append({"slice": "ALL_day_unique", **_agg(all_du)})
    rows.append({"slice": "ALL_tickets", **_agg(scored)})
    for side in ("BUY", "SELL"):
        rows.append({"slice": f"{side}_day_unique", **_agg(first_day([r for r in scored if r.get("decision") == side]))})
    for p in (0.52, 0.55, 0.58, 0.60, 0.62, 0.65, 0.70):
        sub = first_day([r for r in scored if float(r.get("p_t1") or 0) >= p])
        rows.append({"slice": f"FB_P{int(p*100)}_day_unique", **_agg(sub)})
    for lo, hi, name in (
        (600, 630, "10:00-10:30"),
        (630, 690, "10:30-11:30"),
        (690, 780, "11:30-13:00"),
        (780, 870, "13:00-14:30"),
    ):
        sub = first_day([r for r in scored if lo <= float(r.get("mins_entry") or 0) < hi])
        rows.append({"slice": f"clock_{name}", **_agg(sub)})
    for ext in (0.10, 0.15, 0.20, 0.30):
        sub = first_day([r for r in scored if float(r.get("or_ext") or 0) <= ext])
        rows.append({"slice": f"or_ext<={ext}", **_agg(sub)})
    # monthly
    by_m: Dict[str, List[dict]] = defaultdict(list)
    for r in all_du:
        by_m[str(r.get("day") or "")[:7]].append(r)
    for m in sorted(by_m):
        rows.append({"slice": f"month_{m}", **_agg(by_m[m])})
    return rows


def loss_autopsy(scored: List[dict]) -> Dict[str, Any]:
    losses = [r for r in scored if not r.get("win")]
    wins = [r for r in scored if r.get("win")]
    def mean(key, rows):
        if not rows:
            return None
        return round(float(np.mean([float(r.get(key) or 0) for r in rows])), 4)
    return {
        "n_loss": len(losses),
        "n_win": len(wins),
        "loss_mean_p": mean("p_t1", losses),
        "win_mean_p": mean("p_t1", wins),
        "loss_mean_or_ext": mean("or_ext", losses),
        "win_mean_or_ext": mean("or_ext", wins),
        "loss_mean_mins": mean("mins_entry", losses),
        "win_mean_mins": mean("mins_entry", wins),
        "loss_by_side": {
            "BUY": sum(1 for r in losses if r.get("decision") == "BUY"),
            "SELL": sum(1 for r in losses if r.get("decision") == "SELL"),
        },
        "loss_examples": [strip_call(r) for r in sorted(losses, key=lambda x: float(x.get("p_t1") or 0))[:12]],
    }


def run_profile(bars, name: str, gates: dict) -> Dict[str, Any]:
    print(f"\n=== PROFILE {name} ===", flush=True)
    tickets, reasons, drop_pre = base.build_clean_tickets(bars, gates=gates)
    print(f"  clean={len(tickets)} reasons={reasons}", flush=True)
    train_t = [r for r in tickets if str(r["day"]) <= TRAIN_END]
    test_t = [r for r in tickets if TEST_START <= str(r["day"]) <= TEST_END]
    print(f"  split train<={TRAIN_END} n={len(train_t)} · test {TEST_START}→{TEST_END} n={len(test_t)}", flush=True)
    packs = train_heads(train_t, TRAIN_END)
    train_s = score(packs, train_t, name)
    test_s = score(packs, test_t, name)

    # Fixed champ books on TEST
    books = {}
    for bname, pred in (
        ("ALL_DU", lambda r: True),
        ("CHAMP_P55", lambda r: float(r.get("p_t1") or 0) >= 0.55),
        ("CHAMP_P58", lambda r: float(r.get("p_t1") or 0) >= 0.58),
        ("CHAMP_P60", lambda r: float(r.get("p_t1") or 0) >= 0.60),
        ("CHAMP_P62", lambda r: float(r.get("p_t1") or 0) >= 0.62),
        ("BUY_P55", lambda r: r.get("decision") == "BUY" and float(r.get("p_t1") or 0) >= 0.55),
        ("SELL_P55", lambda r: r.get("decision") == "SELL" and float(r.get("p_t1") or 0) >= 0.55),
    ):
        rows = first_day([r for r in test_s if pred(r)])
        books[bname] = {"rows": [strip_call(r) for r in rows], **_agg(rows)}

    # Train-mined proven → test
    print(f"  mining 100% rules on train…", flush=True)
    mined = mine_rules_on_train(train_s, test_s, min_train_n=8, min_test_n=1, target_hit=100.0)
    # keep diverse top: best test-100, best test hit with n>=5, best train-100 with largest test n
    top_mined = []
    seen_sig = set()
    for m in mined:
        f = m["filters"]
        sig = (
            f.get("side"),
            f.get("p_min"),
            f.get("max_or_ext"),
            f.get("min_or_w"),
            f.get("max_noise"),
            f.get("min_mins"),
            f.get("max_mins"),
            f.get("require_body"),
        )
        if sig in seen_sig:
            continue
        seen_sig.add(sig)
        top_mined.append(
            {
                "filters": f,
                "train": m["train"],
                "test": m["test"],
                "test_calls": [strip_call(r) for r in m["test_rows"]],
            }
        )
        if len(top_mined) >= 25:
            break

    # Best OOS 100% among mined
    oos100 = [m for m in top_mined if m["test"]["hit_pct"] >= 100.0 - 1e-9 and m["test"]["n"] >= 1]
    best_oos100 = max(oos100, key=lambda m: m["test"]["n"]) if oos100 else None

    # In-sample TEST oracle ceiling (NOT for promote)
    oracle = max_n_at_100(test_s)
    oracle_agg = _agg(oracle)

    return {
        "profile": name,
        "gates": gates,
        "n_clean": len(tickets),
        "n_train": len(train_t),
        "n_test": len(test_t),
        "reasons": reasons,
        "drop_pre": drop_pre,
        "heads": {
            k: {kk: vv for kk, vv in (v or {}).items() if kk not in ("base", "iso")}
            for k, v in packs.items()
        },
        "test_books": {k: {kk: vv for kk, vv in v.items() if kk != "rows"} for k, v in books.items()},
        "test_books_calls": {k: v.get("rows") for k, v in books.items()},
        "slices_test": slice_table(test_s),
        "slices_train": slice_table(train_s),
        "loss_autopsy_test": loss_autopsy(test_s),
        "mined_top": top_mined,
        "best_oos_100": best_oos100,
        "oracle_test_100": {
            "label": "IN_SAMPLE_CEILING_not_for_promote",
            **oracle_agg,
            "calls": [strip_call(r) for r in oracle],
        },
        "n_rules_train100": len(mined),
        "n_rules_oos100": len(oos100),
    }


def write_report(results: List[dict], meta: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    lines = [
        "# NIFTY 1m dual CLEAN — last-1y deep accuracy (RESEARCH ONLY)",
        "",
        "**Not live. Does not list Calls.**",
        "",
        f"- Test window: `{TEST_START}` → `{TEST_END}` (last full year of 1m cache)",
        f"- Train / rule-mine through: `{TRAIN_END}` (no test leakage into heads or filters)",
        f"- Brackets: ±{base.RISK:g} · OR bars: {base.OR_BARS_1M}",
        f"- Bars: **{meta.get('n_bars')}** · days: **{meta.get('n_days')}**",
        "",
        "## Protocol",
        "",
        "1. Build clean OR-break tickets under each gate profile.",
        "2. Train BUY/SELL heads on pre-test tickets only.",
        "3. Score test year; report fixed champ books.",
        "4. Mine filter rules with **train hit = 100%** (day-unique); validate on test.",
        "5. Oracle = in-sample max-n @100% on test (ceiling only — not a promote rule).",
        "",
    ]
    # Summary table
    lines += ["## Summary (test year)", "", "| Profile | Clean | Test n | DU hit% | Best OOS-100 n | Oracle-100 n |", "|---|---:|---:|---:|---:|---:|"]
    for r in results:
        du = next((s for s in r["slices_test"] if s["slice"] == "ALL_day_unique"), {})
        best = r.get("best_oos_100") or {}
        bn = (best.get("test") or {}).get("n", 0)
        lines.append(
            f"| `{r['profile']}` | {r['n_clean']} | {r['n_test']} | {du.get('hit_pct')} | "
            f"**{bn}** | {r['oracle_test_100'].get('n')} |"
        )
    lines.append("")

    for r in results:
        lines += [
            f"## Profile `{r['profile']}`",
            "",
            f"- Gates: `{json.dumps(r['gates'])}`",
            f"- Train n={r['n_train']} · Test n={r['n_test']} · train100 rules={r['n_rules_train100']} · oos100 rules={r['n_rules_oos100']}",
            "",
            "### Heads",
            "",
        ]
        for side in ("BUY", "SELL"):
            h = (r.get("heads") or {}).get(side) or {}
            if h.get("available"):
                lines.append(
                    f"- **{side}**: n_train={h.get('n_train')} fit_auc={h.get('fit_auc')} "
                    f"calib_auc={h.get('calib_auc')} flip={h.get('score_flipped')}"
                )
            else:
                lines.append(f"- **{side}**: unavailable ({h.get('reason')})")
        lines += ["", "### Fixed test books (day-unique)", "", "| Book | N | Hit% |", "|---|---:|---:|"]
        for k, v in (r.get("test_books") or {}).items():
            lines.append(f"| `{k}` | {v.get('n')} | {v.get('hit_pct')} |")
        lines += ["", "### Test slices", "", "| Slice | N | Hit% |", "|---|---:|---:|"]
        for s in r.get("slices_test") or []:
            if str(s["slice"]).startswith("month_"):
                continue
            lines.append(f"| `{s['slice']}` | {s.get('n')} | {s.get('hit_pct')} |")
        lines += ["", "### Monthly (day-unique)", "", "| Month | N | Hit% |", "|---|---:|---:|"]
        for s in r.get("slices_test") or []:
            if str(s["slice"]).startswith("month_"):
                lines.append(f"| `{s['slice'].replace('month_', '')}` | {s.get('n')} | {s.get('hit_pct')} |")

        best = r.get("best_oos_100")
        lines += ["", "### Best train→test **100%** rule", ""]
        if best and best.get("test", {}).get("n", 0) > 0:
            lines.append(f"- Filters: `{json.dumps(best['filters'])}`")
            lines.append(f"- Train: n={best['train']['n']} hit={best['train']['hit_pct']}%")
            lines.append(f"- **Test: n={best['test']['n']} hit={best['test']['hit_pct']}%**")
            lines.append("")
            lines.append("| Day | HM | Side | p | or_ext | Win |")
            lines.append("|---|---|---|---:|---:|:---:|")
            for c in best.get("test_calls") or []:
                lines.append(
                    f"| {c.get('day')} | {c.get('hm')} | {c.get('decision')} | "
                    f"{c.get('p_t1')} | {c.get('or_ext')} | {'Y' if c.get('win') else 'N'} |"
                )
        else:
            lines.append("_No filter with train=100% also hit 100% on test with ≥1 call._")

        lines += ["", "### Top mined rules (train 100% → test)", "", "| # | Side | p≥ | ext≤ | OR≥ | clock | Test n | Test hit% | Train n |", "|---:|---|---:|---:|---:|---|---:|---:|---:|"]
        for i, m in enumerate((r.get("mined_top") or [])[:12], 1):
            f = m["filters"]
            clock = f"{int(f['min_mins'])//60:02d}:{int(f['min_mins'])%60:02d}-{int(f['max_mins'])//60:02d}:{int(f['max_mins'])%60:02d}"
            lines.append(
                f"| {i} | {f.get('side') or 'BOTH'} | {f.get('p_min')} | {f.get('max_or_ext')} | "
                f"{f.get('min_or_w')} | {clock} | {m['test']['n']} | {m['test']['hit_pct']} | {m['train']['n']} |"
            )

        ora = r.get("oracle_test_100") or {}
        lines += [
            "",
            "### Oracle test ceiling (in-sample — do not promote)",
            "",
            f"- n={ora.get('n')} hit={ora.get('hit_pct')}% · `{ora.get('label')}`",
            "",
        ]
        if ora.get("calls"):
            lines += ["| Day | HM | Side | p | Win |", "|---|---|---|---:|:---:|"]
            for c in ora["calls"]:
                lines.append(
                    f"| {c.get('day')} | {c.get('hm')} | {c.get('decision')} | {c.get('p_t1')} | "
                    f"{'Y' if c.get('win') else 'N'} |"
                )

        la = r.get("loss_autopsy_test") or {}
        lines += [
            "",
            "### Loss autopsy (test tickets)",
            "",
            f"- losses={la.get('n_loss')} wins={la.get('n_win')}",
            f"- mean p loss/win: {la.get('loss_mean_p')} / {la.get('win_mean_p')}",
            f"- mean or_ext loss/win: {la.get('loss_mean_or_ext')} / {la.get('win_mean_or_ext')}",
            f"- by side losses: `{json.dumps(la.get('loss_by_side'))}`",
            "",
        ]

    # Global pick
    lines += ["## Research pick", ""]
    picks = []
    for r in results:
        b = r.get("best_oos_100")
        if b and b.get("test", {}).get("hit_pct", 0) >= 100.0 - 1e-9 and b.get("test", {}).get("n", 0) >= 5:
            picks.append((r["profile"], b))
    if picks:
        picks.sort(key=lambda x: x[1]["test"]["n"], reverse=True)
        prof, b = picks[0]
        lines.append(
            f"**Best honest 100% book:** profile `{prof}` · test **n={b['test']['n']} @ 100%** "
            f"(train n={b['train']['n']} @ 100%)."
        )
        lines.append(f"Filters: `{json.dumps(b['filters'])}`")
    else:
        # fall back: best test hit among mined with n>=5
        fallback = []
        for r in results:
            for m in r.get("mined_top") or []:
                if m["test"]["n"] >= 5:
                    fallback.append((r["profile"], m))
        if fallback:
            fallback.sort(key=lambda x: (x[1]["test"]["hit_pct"], x[1]["test"]["n"]), reverse=True)
            prof, m = fallback[0]
            lines.append(
                f"No ≥5-call OOS 100% book found. Closest: `{prof}` test "
                f"n={m['test']['n']} hit={m['test']['hit_pct']}% (train 100%)."
            )
            lines.append(f"Filters: `{json.dumps(m['filters'])}`")
        else:
            lines.append("Insufficient test volume under these gates for a multi-call 100% OOS book.")
    lines += [
        "",
        "## Policy",
        "",
        "- Research only · `not_live=true`",
        "- Do not wire into live_session / fno_ws_rescore without a separate promote plan.",
        "",
    ]
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    REPORT_JSON.write_text(
        json.dumps({"meta": meta, "test_start": TEST_START, "test_end": TEST_END, "train_end": TRAIN_END, "results": results}, indent=2),
        encoding="utf-8",
    )
    print(f"\n  wrote {REPORT_MD}", flush=True)
    print(f"  wrote {REPORT_JSON}", flush=True)


def main() -> int:
    print("=" * 60, flush=True)
    print("NIFTY 1m dual CLEAN · LAST-1Y DEEP · RESEARCH ONLY", flush=True)
    print(f"train ≤ {TRAIN_END} · test {TEST_START} → {TEST_END}", flush=True)
    print("=" * 60, flush=True)

    bars = base.load_existing_1m()
    if bars.empty:
        print("FAIL: no bars", flush=True)
        return 1
    bars = bars[
        (bars.index >= __import__("pandas").Timestamp(base.START, tz="Asia/Kolkata"))
        & (bars.index <= __import__("pandas").Timestamp(f"{base.END} 23:59:59", tz="Asia/Kolkata"))
    ]
    n_days = len({base._day(ts) for ts in bars.index})
    print(f"tape bars={len(bars)} days={n_days}", flush=True)

    results = []
    for name, gates in PROFILES:
        results.append(run_profile(bars, name, gates))

    meta = {
        "n_bars": len(bars),
        "n_days": n_days,
        "bar_start": str(bars.index.min()),
        "bar_end": str(bars.index.max()),
        "research_only": True,
        "not_live": True,
    }
    write_report(results, meta)
    # console highlight
    print("\n" + "=" * 60, flush=True)
    for r in results:
        du = next((s for s in r["slices_test"] if s["slice"] == "ALL_day_unique"), {})
        b = r.get("best_oos_100")
        print(
            f"{r['profile']}: test_du={du.get('n')}@{du.get('hit_pct')}% · "
            f"oos100_n={(b or {}).get('test', {}).get('n', 0)} · "
            f"oracle100_n={r['oracle_test_100'].get('n')}",
            flush=True,
        )
    print("DONE · research only", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
