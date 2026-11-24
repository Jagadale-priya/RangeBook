"""NIFTY morning RUNAWAY BUY — catch no-OR-retest trend days at 100% (1y/3y/5y).

Target miss shape (2026-11-20): strong day-up, OR break early, bodies <80%,
price never revisits OR+5 → locked L5_u70_b80 limit lane silent.

Honest entries only (no synth look-ahead):
  A) close of qualifying thrust bar (chase)
  B) next 15m open after thrust
  C) break of thrust-bar high on later 15m (continuation)
  D) 5m close break of thrust high after signal

  python -u prod_live/tests/builders/_research_nifty_morning_runaway_100.py
"""
from __future__ import annotations

import json
import sys
from itertools import product
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / "app")]
import path_setup  # noqa: F401,E402

OUT_DIR = ROOT / "prod_live" / "reports" / "1y"
OUT_MD = OUT_DIR / "NIFTY_MORNING_RUNAWAY_100PCT.md"
OUT_JSON = OUT_DIR / "NIFTY_MORNING_RUNAWAY_100PCT.json"
TAPE15 = ROOT / "stock_signal_data" / "fno_validate" / "NIFTY_15m_kite.csv"
TAPE5 = ROOT / "stock_signal_data" / "fno_validate" / "NIFTY_5m_kite.csv"
SL = T1 = 30.0
SESSIONS = {"1y": 252, "3y": 756, "5y": 1260}
MIN_N = {"1y": 5, "3y": 8, "5y": 10}


def _load(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    df.columns = [str(c).strip().title() for c in df.columns]
    if df.index.tz is None:
        df.index = df.index.tz_localize("Asia/Kolkata")
    else:
        df.index = df.index.tz_convert("Asia/Kolkata")
    return df.sort_index()


def _hm(ts: Any) -> str:
    t = pd.Timestamp(ts).tz_convert("Asia/Kolkata")
    return f"{int(t.hour):02d}:{int(t.minute):02d}"


def _outcome(entry: float, after: pd.DataFrame) -> str:
    if after is None or after.empty:
        return "open"
    stop, tgt = entry - SL, entry + T1
    for _, r in after.iterrows():
        lo, hi = float(r["Low"]), float(r["High"])
        if lo <= stop and hi >= tgt:
            return "loss"
        if hi >= tgt:
            return "win"
        if lo <= stop:
            return "loss"
    return "open"


def build_day_features(
    sess: pd.DataFrame, s5: pd.DataFrame
) -> Optional[Dict[str, Any]]:
    if len(sess) < 6:
        return None
    or_hi = float(sess["High"].iloc[0])
    or_lo = float(sess["Low"].iloc[0])
    w = or_hi - or_lo
    if w <= 0:
        return None
    day_open = float(sess["Open"].iloc[0])
    first_up = first_dn = None
    for i in range(len(sess)):
        c = float(sess["Close"].iloc[i])
        if first_up is None and c > or_hi:
            first_up = i
        if first_dn is None and c < or_lo:
            first_dn = i
    down_first = first_up is not None and first_dn is not None and first_dn < first_up
    day_hi = float(sess["High"].max())
    # Did price revisit OR+5 after first up break?
    revisited = False
    if first_up is not None:
        lim = or_hi + 5.0
        after = (
            s5[s5.index > sess.index[first_up]]
            if s5 is not None and len(s5)
            else sess.iloc[first_up + 1 :]
        )
        for thr, r in after.iterrows():
            if _hm(thr) > "13:00":
                break
            if float(r["Low"]) <= lim:
                revisited = True
                break
    return {
        "or_hi": or_hi,
        "or_lo": or_lo,
        "w": w,
        "day_open": day_open,
        "day_hi": day_hi,
        "day_up": day_hi - day_open,
        "down_first": down_first,
        "first_up": first_up,
        "revisited_or5": revisited,
        "strong": (day_hi - day_open) >= 150,
    }


def try_entries(sess: pd.DataFrame, s5: pd.DataFrame, meta: dict) -> List[dict]:
    """Emit candidate entries for several modes with rich features (filter later)."""
    or_hi = meta["or_hi"]
    day_open = meta["day_open"]
    out: List[dict] = []
    if meta["down_first"]:
        return out

    for i, ts in enumerate(sess.index):
        h = _hm(ts)
        if h < "09:45" or h > "12:00" or i < 2:
            continue
        row = sess.iloc[i]
        c = float(row["Close"])
        o = float(row["Open"])
        hi = float(row["High"])
        lo = float(row["Low"])
        if c <= or_hi or c <= o:
            continue
        uplift = c - day_open
        if uplift < 40:
            continue
        prior1 = float(sess["High"].iloc[i - 1])
        prior2 = max(float(sess["High"].iloc[j]) for j in range(i - 2, i))
        rng = max(hi - lo, 1e-9)
        body = abs(c - o) / rng
        top = (c - lo) / rng
        bf = (c - or_hi) / meta["w"]
        day_hi_so_far = float(sess["High"].iloc[: i + 1].max())
        # Mode A: close chase
        after_a = s5[s5.index > ts] if s5 is not None and len(s5) else sess.iloc[i + 1 :]
        out.append(
            {
                "mode": "close",
                "sig_hm": h,
                "entry_hm": h,
                "entry": round(c, 2),
                "uplift": round(uplift, 1),
                "body": round(body, 4),
                "top": round(top, 4),
                "bf": round(bf, 4),
                "bar_rng": round(rng, 1),
                "prior1_break": c > prior1,
                "prior2_break": c > prior2,
                "day_hi_up": round(day_hi_so_far - day_open, 1),
                "ext_pts": round(c - or_hi, 1),
                "out": _outcome(c, after_a),
            }
        )
        # Mode B: next 15m open
        if i + 1 < len(sess):
            nts = sess.index[i + 1]
            entry_b = float(sess["Open"].iloc[i + 1])
            after_b = s5[s5.index > nts] if s5 is not None and len(s5) else sess.iloc[i + 2 :]
            out.append(
                {
                    "mode": "next_open",
                    "sig_hm": h,
                    "entry_hm": _hm(nts),
                    "entry": round(entry_b, 2),
                    "uplift": round(uplift, 1),
                    "body": round(body, 4),
                    "top": round(top, 4),
                    "bf": round(bf, 4),
                    "bar_rng": round(rng, 1),
                    "prior1_break": c > prior1,
                    "prior2_break": c > prior2,
                    "day_hi_up": round(day_hi_so_far - day_open, 1),
                    "ext_pts": round(c - or_hi, 1),
                    "out": _outcome(entry_b, after_b),
                }
            )
        # Mode C: later 15m close breaks signal high
        sig_high = hi
        for j in range(i + 1, len(sess)):
            h2 = _hm(sess.index[j])
            if h2 > "13:00":
                break
            row2 = sess.iloc[j]
            c2 = float(row2["Close"])
            o2 = float(row2["Open"])
            if c2 <= sig_high or c2 <= o2:
                continue
            after_c = (
                s5[s5.index > sess.index[j]]
                if s5 is not None and len(s5)
                else sess.iloc[j + 1 :]
            )
            out.append(
                {
                    "mode": "brk_sig_high_15",
                    "sig_hm": h,
                    "entry_hm": h2,
                    "entry": round(c2, 2),
                    "uplift": round(uplift, 1),
                    "body": round(body, 4),
                    "top": round(top, 4),
                    "bf": round(bf, 4),
                    "bar_rng": round(rng, 1),
                    "prior1_break": c > prior1,
                    "prior2_break": c > prior2,
                    "day_hi_up": round(day_hi_so_far - day_open, 1),
                    "ext_pts": round(c - or_hi, 1),
                    "cont_body": round(
                        abs(c2 - o2) / max(float(row2["High"]) - float(row2["Low"]), 1e-9),
                        4,
                    ),
                    "out": _outcome(c2, after_c),
                }
            )
            break
        # Mode D: 5m close breaks signal high
        if s5 is not None and len(s5):
            after5 = s5[s5.index > ts]
            for thr, r2 in after5.iterrows():
                h2 = _hm(thr)
                if h2 > "13:00":
                    break
                c2 = float(r2["Close"])
                o2 = float(r2["Open"])
                if c2 <= sig_high or c2 <= o2:
                    continue
                after_d = after5[after5.index > thr]
                out.append(
                    {
                        "mode": "brk_sig_high_5",
                        "sig_hm": h,
                        "entry_hm": h2,
                        "entry": round(c2, 2),
                        "uplift": round(uplift, 1),
                        "body": round(body, 4),
                        "top": round(top, 4),
                        "bf": round(bf, 4),
                        "bar_rng": round(rng, 1),
                        "prior1_break": c > prior1,
                        "prior2_break": c > prior2,
                        "day_hi_up": round(day_hi_so_far - day_open, 1),
                        "ext_pts": round(c - or_hi, 1),
                        "out": _outcome(c2, after_d),
                    }
                )
                break
    return out


def gate_ok(ev: dict, g: Dict[str, Any]) -> bool:
    if ev["mode"] != g["mode"]:
        return False
    if ev["sig_hm"] < g["hmin"] or ev["sig_hm"] > g["hmax"]:
        return False
    if ev["uplift"] < float(g["min_up"]):
        return False
    if ev["body"] < float(g["min_body"]):
        return False
    if ev["body"] > float(g.get("max_body", 9)):
        return False
    top = float(g.get("top") or 0)
    if top and ev["top"] < top:
        return False
    if g.get("prior2") and not ev["prior2_break"]:
        return False
    if g.get("prior1") and not ev["prior1_break"]:
        return False
    if ev["day_hi_up"] < float(g.get("min_day_hi_up", 0)):
        return False
    if ev["ext_pts"] < float(g.get("min_ext", 0)):
        return False
    if ev["ext_pts"] > float(g.get("max_ext", 9999)):
        return False
    if ev["bar_rng"] < float(g.get("min_rng", 0)):
        return False
    if g.get("min_cont_body") and ev.get("cont_body", 1) < float(g["min_cont_body"]):
        return False
    if g.get("entry_hm_max") and ev["entry_hm"] > g["entry_hm_max"]:
        return False
    return True


def score(events: List[dict], days: Set[str], g: Dict[str, Any]) -> Dict[str, Any]:
    picked = []
    seen = set()
    for ev in events:
        if ev["d"] not in days or ev["d"] in seen:
            continue
        if not gate_ok(ev, g):
            continue
        if ev["out"] not in ("win", "loss"):
            continue
        seen.add(ev["d"])
        picked.append(ev)
    n = len(picked)
    wins = sum(1 for e in picked if e["out"] == "win")
    return {
        "n": n,
        "wins": wins,
        "losses": n - wins,
        "hit_pct": round(100.0 * wins / n, 2) if n else None,
        "strong_n": sum(1 for e in picked if e.get("strong")),
        "no_retest_n": sum(1 for e in picked if not e.get("revisited_or5")),
        "calls": [
            {
                "d": e["d"],
                "sig": e["sig_hm"],
                "entry_hm": e["entry_hm"],
                "entry": e["entry"],
                "out": e["out"],
                "uplift": e["uplift"],
                "body": e["body"],
                "mode": e["mode"],
                "revisited": e.get("revisited_or5"),
            }
            for e in picked
        ],
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print("load…", flush=True)
    df15 = _load(TAPE15)
    df5 = _load(TAPE5)
    by15 = {d: g for d, g in df15.groupby(df15.index.strftime("%Y-%m-%d"))}
    by5 = {d: g for d, g in df5.groupby(df5.index.strftime("%Y-%m-%d"))}
    all_days = sorted(by15.keys())
    days = all_days[-(SESSIONS["5y"] + 20) :]
    print(f"days={len(days)} {days[0]}→{days[-1]}", flush=True)

    events: List[dict] = []
    for di, d in enumerate(days):
        if di % 200 == 0:
            print(f"  build {di}/{len(days)}", flush=True)
        sess = by15[d]
        s5 = by5.get(d, sess.iloc[0:0])
        meta = build_day_features(sess, s5)
        if not meta:
            continue
        cands = try_entries(sess, s5, meta)
        # keep first candidate per mode only (order is time order)
        seen_m = set()
        for ev in cands:
            key = ev["mode"]
            if key in seen_m:
                continue
            # For close/next_open we want first qualifying bar under loose floors;
            # gate filter tightens later. Still first-in-time per mode.
            seen_m.add(key)
            ev = dict(ev)
            ev["d"] = d
            ev["strong"] = meta["strong"]
            ev["revisited_or5"] = meta["revisited_or5"]
            ev["day_up"] = round(meta["day_up"], 1)
            ev["decided"] = ev["out"] in ("win", "loss")
            if ev["decided"]:
                events.append(ev)
            # also allow brk modes to keep first only — already
        # Actually for close mode we need ALL candidate bars available for filter,
        # not just first loose. Rebuild: store all close/next candidates.
    # Rebuild properly — store all modes' candidates (cap 3 close signals / day)
    events = []
    for di, d in enumerate(days):
        if di % 200 == 0:
            print(f"  events {di}/{len(days)}", flush=True)
        sess = by15[d]
        s5 = by5.get(d, sess.iloc[0:0])
        meta = build_day_features(sess, s5)
        if not meta:
            continue
        cands = try_entries(sess, s5, meta)
        per_mode_count = {"close": 0, "next_open": 0, "brk_sig_high_15": 0, "brk_sig_high_5": 0}
        for ev in cands:
            m = ev["mode"]
            if per_mode_count[m] >= 1:
                continue  # first signal only per mode (gate picks params)
            per_mode_count[m] += 1
            ev = dict(ev)
            ev["d"] = d
            ev["strong"] = meta["strong"]
            ev["revisited_or5"] = meta["revisited_or5"]
            ev["day_up"] = round(meta["day_up"], 1)
            if ev["out"] in ("win", "loss"):
                events.append(ev)
    print(f"events={len(events)}", flush=True)

    windows = {
        lb: set(days[-n:] if len(days) >= n else days) for lb, n in SESSIONS.items()
    }

    gates: List[Dict[str, Any]] = []
    # Compact grid — chase / continuation (soft bodies allowed for Nov20-like)
    for mode in ("close", "next_open", "brk_sig_high_15", "brk_sig_high_5"):
        for up, body, max_body, hmax, min_hi, max_ext in product(
            (80, 100, 120, 150, 180),
            (0.45, 0.55, 0.65),
            (0.75, 0.85, 9.0),
            ("11:00", "11:30", "12:00"),
            (0, 120, 150),
            (9999, 150),
        ):
            if max_body < body:
                continue
            name = (
                f"{mode}_u{up}_b{int(body*100)}-{int(max_body*100) if max_body < 9 else 99}"
                f"_{hmax}_hi{min_hi}_xe{max_ext}"
            )
            gates.append(
                dict(
                    name=name,
                    mode=mode,
                    min_up=up,
                    min_body=body,
                    max_body=max_body,
                    top=0.0,
                    hmin="09:45",
                    hmax=hmax,
                    prior2=True,
                    min_ext=0,
                    max_ext=max_ext,
                    min_day_hi_up=min_hi,
                )
            )
    # curated for Nov20-like: soft body, high uplift, continuation break
    curated = [
        dict(name="nov20_close_u150_b45-75_p2_hi150", mode="close", min_up=150, min_body=0.45, max_body=0.75, top=0, hmin="09:45", hmax="11:30", prior2=True, min_day_hi_up=150, min_ext=20, max_ext=9999),
        dict(name="nov20_close_u120_b40-75_p2", mode="close", min_up=120, min_body=0.40, max_body=0.75, top=0, hmin="09:45", hmax="11:00", prior2=True, min_day_hi_up=120, min_ext=15, max_ext=9999),
        dict(name="nov20_brk15_u100_b45_p2", mode="brk_sig_high_15", min_up=100, min_body=0.45, max_body=0.85, top=0, hmin="09:45", hmax="11:30", prior2=True, min_day_hi_up=100, min_ext=10, max_ext=9999, min_cont_body=0.5),
        dict(name="nov20_brk5_u100_b45_p2", mode="brk_sig_high_5", min_up=100, min_body=0.45, max_body=0.85, top=0, hmin="09:45", hmax="11:30", prior2=True, min_day_hi_up=100, min_ext=10, max_ext=9999),
        dict(name="nov20_next_u150_b45_p2", mode="next_open", min_up=150, min_body=0.45, max_body=0.80, top=0, hmin="09:45", hmax="11:00", prior2=True, min_day_hi_up=150),
        dict(name="run_close_u180_b50_p2_e40", mode="close", min_up=180, min_body=0.50, max_body=0.85, top=0.7, hmin="10:00", hmax="12:00", prior2=True, min_ext=40, max_ext=9999, min_day_hi_up=180),
        dict(name="run_brk15_u120_b50_cont60", mode="brk_sig_high_15", min_up=120, min_body=0.50, max_body=0.90, top=0, hmin="09:45", hmax="11:30", prior2=True, min_cont_body=0.60, min_day_hi_up=120, entry_hm_max="12:30"),
        dict(name="run_brk5_u150_b45_hi150", mode="brk_sig_high_5", min_up=150, min_body=0.45, max_body=0.85, top=0, hmin="09:45", hmax="11:30", prior2=True, min_day_hi_up=150),
    ]
    gates.extend(curated)
    seen = set()
    uniq = []
    for g in gates:
        if g["name"] in seen:
            continue
        seen.add(g["name"])
        uniq.append(g)
    gates = uniq
    print(f"gates={len(gates)}", flush=True)

    results = []
    for g in gates:
        row: Dict[str, Any] = {"gate": g["name"], "params": {k: v for k, v in g.items() if k != "name"}}
        for lb in ("1y", "3y", "5y"):
            sc = score(events, windows[lb], g)
            slim = {k: sc[k] for k in ("n", "wins", "losses", "hit_pct", "strong_n", "no_retest_n")}
            if lb == "1y":
                slim["calls"] = sc["calls"]
            row[lb] = slim
        row["hold_100_all"] = all(
            row[lb]["hit_pct"] == 100.0 and row[lb]["n"] >= MIN_N[lb] for lb in ("1y", "3y", "5y")
        )
        row["hold_100_1y"] = row["1y"]["hit_pct"] == 100.0 and row["1y"]["n"] >= MIN_N["1y"]
        results.append(row)
        if row["hold_100_all"] or (row["hold_100_1y"] and row["3y"].get("hit_pct") == 100):
            print(
                f"{g['name'][:70]:70s} 1y {row['1y']['n']}@{row['1y']['hit_pct']} "
                f"3y {row['3y']['n']}@{row['3y']['hit_pct']} "
                f"5y {row['5y']['n']}@{row['5y']['hit_pct']} ALL={row['hold_100_all']}",
                flush=True,
            )

    results.sort(
        key=lambda r: (
            int(r["hold_100_all"]),
            int(r["hold_100_1y"]),
            (r["5y"]["hit_pct"] or 0) if r["hold_100_all"] else 0,
            r["5y"]["n"] if r["hold_100_all"] else 0,
            (r["1y"]["hit_pct"] or 0),
            r["1y"]["n"],
            (r["3y"]["hit_pct"] or 0),
            (r["5y"]["hit_pct"] or 0),
        ),
        reverse=True,
    )
    all100 = [r for r in results if r["hold_100_all"]]
    y1 = [r for r in results if r["hold_100_1y"]]
    best = None
    if all100:
        best = max(all100, key=lambda r: (r["5y"]["n"], r["3y"]["n"], r["1y"]["n"]))
    elif y1:
        best = max(
            y1,
            key=lambda r: (
                (r["3y"]["hit_pct"] or 0),
                (r["5y"]["hit_pct"] or 0),
                r["1y"]["n"],
            ),
        )

    payload = {
        "note": "Runaway / no-OR-retest morning BUY complementary to L5_u70_b80 limit lane",
        "min_n": MIN_N,
        "hold_100_all_n": len(all100),
        "hold_100_1y_n": len(y1),
        "best": best,
        "top": [
            {
                "gate": r["gate"],
                "1y": r["1y"],
                "3y": {k: r["3y"][k] for k in ("n", "wins", "hit_pct")},
                "5y": {k: r["5y"][k] for k in ("n", "wins", "hit_pct")},
                "all100": r["hold_100_all"],
                "params": r["params"],
            }
            for r in results[:40]
        ],
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        "# NIFTY morning RUNAWAY BUY · 100% research (complement to OR+5 limit)",
        "",
        "For Nov20-style days: strong up, soft bodies, **no revisit of OR+5**.",
        "Locked limit lane (`L5_u70_b80`) correctly stays silent — need a 2nd lane.",
        "",
        f"Gates: {len(results)} · hold 100% on 1y+3y+5y: **{len(all100)}** · 1y-only 100%: **{len(y1)}**",
        "",
        "## Best",
        "",
    ]
    if best and best["hold_100_all"]:
        lines += [
            f"- **`{best['gate']}`** holds **100%** on 1y/3y/5y",
            f"- 1y {best['1y']['n']}@{best['1y']['hit_pct']}% · "
            f"3y {best['3y']['n']}@{best['3y']['hit_pct']}% · "
            f"5y {best['5y']['n']}@{best['5y']['hit_pct']}%",
            f"- params: `{json.dumps(best['params'])}`",
            "",
            "### 1y calls",
            "",
        ]
        for c in best["1y"].get("calls") or []:
            lines.append(
                f"- {c['d']} {c['mode']} sig {c['sig']} entry {c['entry_hm']} @ {c['entry']} · "
                f"{c['out']} · uplift {c['uplift']} body {c['body']} retest={c['revisited']}"
            )
    elif best:
        lines += [
            f"- No all-window 100%. Best 1y@100: **`{best['gate']}`**",
            f"- 1y {best['1y']['n']}@{best['1y']['hit_pct']}% · "
            f"3y {best['3y']['n']}@{best['3y']['hit_pct']}% · "
            f"5y {best['5y']['n']}@{best['5y']['hit_pct']}%",
            f"- params: `{json.dumps(best['params'])}`",
            "",
            "### Verdict",
            "",
            "- Pure chase/continuation entries that catch Nov20-style runaways "
            "**do not** hold 100% across 3y/5y in this sweep.",
            "- Practical path: keep OR+5 **100%** lane + accept a second lane at ~90%+ "
            "or use afternoon thrust for continuation after 13:00.",
        ]
    else:
        lines.append("- No gate reached 1y 100% with n floors.")

    lines += [
        "",
        "## Ranking",
        "",
        "| gate | 1y | 3y | 5y | all100 |",
        "|---|---:|---:|---:|---|",
    ]
    for r in results[:25]:
        lines.append(
            f"| `{r['gate']}` | {r['1y']['n']}@{r['1y']['hit_pct']} | "
            f"{r['3y']['n']}@{r['3y']['hit_pct']} | {r['5y']['n']}@{r['5y']['hit_pct']} | "
            f"{r['hold_100_all']} |"
        )
    lines += ["", f"JSON: `{OUT_JSON}`", ""]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print("wrote", OUT_MD, flush=True)
    print("ALL100", len(all100), "Y1", len(y1), flush=True)
    if best:
        print("BEST", best["gate"], best["1y"]["n"], best["1y"]["hit_pct"], best["3y"]["hit_pct"], best["5y"]["hit_pct"], flush=True)


if __name__ == "__main__":
    main()
