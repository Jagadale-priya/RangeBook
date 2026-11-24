"""Union of PROVEN T20 fingerprint keys → check combined cover still 100% hold."""
from __future__ import annotations

import json
import pickle
import sys
from ast import literal_eval
from collections import defaultdict
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
BUILDERS = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BUILDERS))
sys.path.insert(0, str(ROOT / "tools" / "research"))
import path_setup  # noqa: F401

import research_nifty_1m_dual_clean_train as base  # noqa: E402
import research_nifty_1m_candle_textbook_deep as tb  # noqa: E402
import research_nifty_1m_pattern_behavior_then_100 as beh  # noqa: E402
import research_nifty_1m_vix_candle_adaptive as vixmod  # noqa: E402
import research_nifty_1m_scalp_fwd_nov9_hold as fwdmod  # noqa: E402
from _diag_scalp_structure_vix_analyze import enrich_structure  # noqa: E402
from _diag_scalp_fail3_t20_sl10 import enrich_prior3  # noqa: E402
from _diag_scalp_deep_1cpd_100_hold26 import enrich_deep  # noqa: E402
from _diag_scalp_ma_lastyear_init import WIN_LO, HOLD_LO, PACK, add_ma_layers, enrich_ma_layers, summarize  # noqa: E402
from _diag_scalp_ma_hold100 import keys_hold  # noqa: E402
from _diag_scalp_ma_hold_approaches import path_ma_trail_strict  # noqa: E402
from _diag_scalp_ma_hold100_indicators import add_indicators, enrich_ind  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
BLOB = OUT / "NIFTY_1M_HELD_T20_PROVEN100.json"
REPORT = OUT / "NIFTY_1M_HELD_T20_PROVEN100.md"


def main() -> int:
    blob = json.loads(BLOB.read_text(encoding="utf-8"))
    proven_keys = defaultdict(set)
    for r in blob["proven"]:
        if r.get("key"):
            try:
                proven_keys[float(r["t1"])].add(literal_eval(r["key"]))
            except Exception:
                pass
    print("keys", {t: len(ks) for t, ks in proven_keys.items()}, flush=True)

    raw = base.load_existing_1m()
    raw = raw[raw.index >= pd.Timestamp(WIN_LO, tz="Asia/Kolkata")]
    data_hi = str(raw.index.max().date())
    df = tb.detect_textbook(raw)
    df = beh.add_rsi(df)
    df = add_ma_layers(df)
    df = add_indicators(df)
    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values
    o = df["Open"].astype(float).values
    ema34 = df["ema34"].astype(float).values
    vix = vixmod.load_vix()
    xs = pickle.load(next(PACK.glob("events_2025-11-17_*.pkl")).open("rb"))
    fwdmod.enrich_evt(xs, h, l, c, o)
    enrich_structure(xs, h, l, c, o, vix)
    enrich_prior3(xs, h, l, c, o)
    enrich_deep(xs, h, l, c, o, df)
    enrich_ma_layers(xs, df)
    enrich_ind(xs, df)

    lines = [
        "",
        "## UNION of all single-key PROVEN fingerprints",
        "",
        "| T1 | #keys | Train n@hit cover | Hold n@hit cover | still 100%? |",
        "|---:|---:|---|---|:---:|",
    ]

    for t1 in (20.0, 25.0, 30.0):
        keys = proven_keys.get(t1, set())
        for e in xs:
            ok, reason, sl, t1v = path_ma_trail_strict(h, l, c, ema34, int(e["full_i"]), e["decision"], t1)
            e["_win"] = bool(ok)
            e["_keys"] = set(keys_hold(e))
            e["_t1"] = float(t1)
            e["_sl"] = float(sl or 0)
        train = [e for e in xs if e["day"] < HOLD_LO]
        hold = [e for e in xs if e["day"] >= HOLD_LO]
        tr_days = sorted({e["day"] for e in train})
        ho_days = sorted({e["day"] for e in hold})

        def pick(rows, ks=keys):
            for e in sorted(rows, key=lambda x: x["mins"]):
                if e["_keys"] & ks:
                    return e
            return None

        def run(events, days):
            by = defaultdict(list)
            for e in events:
                by[e["day"]].append(e)
            calls = [pick(by[d]) for d in days]
            calls = [e for e in calls if e]
            return summarize(calls, len(days))

        st_tr = run(train, tr_days)
        st_ho = run(hold, ho_days)
        ok = st_tr["all_win"] and st_ho["all_win"] and st_ho["n"] >= 1
        print(f"UNION T{t1:.0f} keys={len(keys)} train={st_tr} hold={st_ho} ok={ok}", flush=True)
        lines.append(
            f"| **{t1:.0f}** | {len(keys)} | {st_tr['n']}@{st_tr['hit']}%/{st_tr['cover']}% | "
            f"{st_ho['n']}@{st_ho['hit']}%/{st_ho['cover']}% | {'YES' if ok else 'NO'} |"
        )

        # list hold calls for T20 union
        if t1 == 20.0:
            by = defaultdict(list)
            for e in hold:
                by[e["day"]].append(e)
            lines += ["", "### Hold calls · UNION T20", "", "| Day | HM | Side | Pattern | Win |", "|---|---|---|---|---|"]
            for d in ho_days:
                e = pick(by.get(d, []))
                if e:
                    lines.append(f"| {d} | {e['hm']} | {e['decision']} | {e['primary']} | {e['_win']} |")

    text = REPORT.read_text(encoding="utf-8")
    if "## UNION of all single-key" in text:
        text = text.split("## UNION of all single-key")[0].rstrip() + "\n"
    REPORT.write_text(text + "\n".join(lines) + "\n", encoding="utf-8")
    print(f"Updated {REPORT}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
