"""clean34 + last-10 candle pattern gate BEFORE entry (instant hold/filter logic).

Before any entry: read prior 10 bars → pattern tags.
Lock allow-patterns on TRAIN only → apply blind on HOLD.
"""
from __future__ import annotations

import pickle
import sys
from collections import Counter, defaultdict
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
from _diag_scalp_ma_lastyear_init import (  # noqa: E402
    HOLD_LO,
    WIN_LO,
    PACK,
    add_ma_layers,
    attach_scores,
    enrich_ma_layers,
    hunt_clean_1cpd,
    one_per_day,
    summarize,
    keys_ma_ly,
)
import research_nifty_1m_chart_only_100 as co  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
REPORT = OUT / "NIFTY_1M_SCALP_MA_CLEAN34_PRE10.md"
GAP = 1


def enrich_pre10(events, h, l, c, o):
    """Instant last-10 candle pattern pack (no look-ahead)."""
    for e in events:
        i = int(e["full_i"])
        side = e["decision"]
        if i < 10:
            e["pre10_ok"] = False
            continue
        dirs = []
        bodies = []
        favor = 0
        opp = 0
        his, los, cls = [], [], []
        for k in range(10, 0, -1):  # oldest → newest of prior 10
            j = i - k
            hj, lj, cj, oj = float(h[j]), float(l[j]), float(c[j]), float(o[j])
            rng = max(hj - lj, 0.5)
            body = abs(cj - oj) / rng
            d = "U" if cj > oj else ("D" if cj < oj else "F")
            dirs.append(d)
            bodies.append(body)
            his.append(hj)
            los.append(lj)
            cls.append(cj)
            if side == "BUY":
                if cj > oj:
                    favor += 1
                elif cj < oj:
                    opp += 1
            else:
                if cj < oj:
                    favor += 1
                elif cj > oj:
                    opp += 1

        # last couple (p2,p1) before signal
        couple = "".join(dirs[-2:])
        last3 = "".join(dirs[-3:])
        # compress full 10: count + last5
        nU = dirs.count("U")
        nD = dirs.count("D")
        last5 = "".join(dirs[-5:])
        e["pre10_UD"] = "".join(dirs)
        e["pre10_last5"] = last5
        e["pre10_couple"] = couple
        e["pre10_last3"] = last3
        e["pre10_nU"] = nU
        e["pre10_nD"] = nD
        e["pre10_favor"] = favor
        e["pre10_opp"] = opp
        e["pre10_favor_bin"] = (
            "f7+" if favor >= 7 else ("f5+" if favor >= 5 else ("f3+" if favor >= 3 else "f<3"))
        )
        e["pre10_opp_bin"] = "o5+" if opp >= 5 else ("o3+" if opp >= 3 else "o<3")

        # structure over 10: HH/HL vs LH/LL
        higher_lows = int(los[-1] > los[-5] > los[0])
        lower_highs = int(his[-1] < his[-5] < his[0])
        higher_highs = int(his[-1] > his[-5] > his[0])
        lower_lows = int(los[-1] < los[-5] < los[0])
        if side == "BUY":
            stair = "up" if (higher_lows and higher_highs) else ("chop" if not higher_lows else "hl_only")
        else:
            stair = "dn" if (lower_highs and lower_lows) else ("chop" if not lower_highs else "lh_only")
        e["pre10_stair"] = stair

        # net drift in ATR
        atr = max(float(e.get("atr") or 8.0), 3.0)
        drift = (cls[-1] - cls[0]) / atr
        if side == "SELL":
            drift = -drift
        e["pre10_drift"] = round(drift, 2)
        e["pre10_drift_bin"] = "with" if drift >= 0.4 else ("against" if drift <= -0.4 else "flat")

        # avg body
        ab = sum(bodies) / 10
        e["pre10_body_bin"] = "strong" if ab >= 0.55 else ("soft" if ab < 0.35 else "mid")

        # last-couple continuation vs fight
        if side == "BUY":
            couple_ok = couple in ("UU", "FU", "UF")
            last3_ok = last3.count("U") >= 2
        else:
            couple_ok = couple in ("DD", "FD", "DF")
            last3_ok = last3.count("D") >= 2
        e["pre10_couple_ok"] = int(couple_ok)
        e["pre10_last3_ok"] = int(last3_ok)

        # composite instant hold/entry gates
        e["pre10_hold_soft"] = bool(favor >= 5 and e["pre10_drift_bin"] != "against" and couple_ok)
        e["pre10_hold_mid"] = bool(
            favor >= 6 and stair in ("up", "dn", "hl_only", "lh_only") and couple_ok and e["pre10_drift_bin"] == "with"
        )
        e["pre10_hold_hard"] = bool(
            favor >= 7
            and stair in ("up", "dn")
            and couple_ok
            and last3_ok
            and e["pre10_drift_bin"] == "with"
            and opp <= 2
        )
        # fingerprint for allow-list lock
        e["pre10_fp"] = (
            e["pre10_couple"],
            e["pre10_last3"],
            e["pre10_favor_bin"],
            e["pre10_stair"],
            e["pre10_drift_bin"],
            e["pre10_body_bin"],
        )
        e["pre10_fp2"] = (e["pre10_couple"], e["pre10_favor_bin"], e["pre10_stair"], e["pre10_drift_bin"])
        e["pre10_fp3"] = (e["pre10_last5"], e["pre10_stair"], e["decision"])
        e["pre10_ok"] = True


def score_set(calls, n_days):
    return summarize(calls, n_days)


def apply_1day(events, pred):
    """First chronological adaptive-scored event per day passing pred."""
    by = defaultdict(list)
    for e in events:
        if pred is not None and not pred(e):
            continue
        sc = e.get("_sc_adapt")
        if not sc:
            continue
        by[e["day"]].append({**e, **sc})
    out = []
    for d, xs in sorted(by.items()):
        out.append(sorted(xs, key=lambda x: x["mins"])[0])
    return out


def lock_allow_fps(train_calls, key="pre10_fp2", min_n=2, min_hit=100.0):
    """Patterns that were path-clean on train 1/day (or high purity)."""
    bucket = defaultdict(list)
    for e in train_calls:
        bucket[e.get(key)].append(bool(e["_win"]))
    allow = set()
    stats = {}
    for k, rows in bucket.items():
        if k is None:
            continue
        hit = 100.0 * sum(rows) / len(rows)
        stats[k] = {"n": len(rows), "hit": round(hit, 2)}
        if len(rows) >= min_n and hit >= min_hit:
            allow.add(k)
    return allow, stats


def micro_hold_with_pre10(train, hold, h, l, c, gate_pred, pre10_pred, min_train=2):
    """Same clean34 micro hunt but entry also needs pre10_pred."""

    def both(e):
        return bool(gate_pred(e)) and bool(pre10_pred(e))

    return hunt_clean_1cpd(train, hold, h, l, c, both, min_train=min_train)


def main() -> int:
    print("clean34 + last-10 candle HOLD/entry filter…", flush=True)
    raw = base.load_existing_1m()
    raw = raw[raw.index >= pd.Timestamp(WIN_LO, tz="Asia/Kolkata")]
    df = tb.detect_textbook(raw)
    df = beh.add_rsi(df)
    df = add_ma_layers(df)
    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values
    o = df["Open"].astype(float).values
    vix = vixmod.load_vix()

    data_hi = str(raw.index.max().date())
    xs = pickle.load((PACK / f"events_{WIN_LO}_{data_hi}.pkl").open("rb"))
    fwdmod.enrich_evt(xs, h, l, c, o)
    enrich_structure(xs, h, l, c, o, vix)
    enrich_prior3(xs, h, l, c, o)
    enrich_deep(xs, h, l, c, o, df)
    enrich_ma_layers(xs, df)
    enrich_pre10(xs, h, l, c, o)
    attach_scores(xs, h, l, c)

    train = [e for e in xs if e["day"] < HOLD_LO]
    hold = [e for e in xs if e["day"] >= HOLD_LO]
    td, hd = len({e["day"] for e in train}), len({e["day"] for e in hold})
    clean = lambda e: e.get("gate_clean34")

    # baseline clean34 1/day
    base_tr = apply_1day(train, clean)
    base_ho = apply_1day(hold, clean)
    print(f"baseline clean34 1d train={score_set(base_tr, td)} hold={score_set(base_ho, hd)}", flush=True)

    variants = [
        ("pre10_soft", lambda e: clean(e) and e.get("pre10_hold_soft")),
        ("pre10_mid", lambda e: clean(e) and e.get("pre10_hold_mid")),
        ("pre10_hard", lambda e: clean(e) and e.get("pre10_hold_hard")),
        ("couple_ok", lambda e: clean(e) and e.get("pre10_couple_ok") == 1),
        ("last3_ok", lambda e: clean(e) and e.get("pre10_last3_ok") == 1),
        ("favor7_stair", lambda e: clean(e) and e.get("pre10_favor", 0) >= 7 and e.get("pre10_stair") in ("up", "dn")),
        ("couple+drift", lambda e: clean(e) and e.get("pre10_couple_ok") == 1 and e.get("pre10_drift_bin") == "with"),
        ("couple+favor6", lambda e: clean(e) and e.get("pre10_couple_ok") == 1 and e.get("pre10_favor", 0) >= 6),
    ]

    lines = [
        "# clean34 + **last-10 candle** entry/hold filter",
        "",
        "Before entry: inspect prior **10** 1m candles (dirs, favor count, stair, drift, last-couple/last-3).",
        "Only then allow clean34 signal. Train locks rules; HOLD is unknown.",
        "",
        f"Hold `{HOLD_LO}` → `{data_hi}` · train days {td} · hold days {hd}",
        "",
        "## Instant rule gates (1 call/day)",
        "",
        "| Gate | Train n@hit cover | Hold n@hit cover | vs base hold |",
        "|---|---|---|---|",
    ]

    base_h = score_set(base_ho, hd)
    lines.append(
        f"| `clean34` (base) | {score_set(base_tr, td)['n']}@{score_set(base_tr, td)['hit']}% "
        f"{score_set(base_tr, td)['cover']}% | {base_h['n']}@{base_h['hit']}% {base_h['cover']}% | — |"
    )

    best = ("base", base_h, None)
    results = {}
    for name, pred in variants:
        tr = apply_1day(train, pred)
        ho = apply_1day(hold, pred)
        st_tr, st_ho = score_set(tr, td), score_set(ho, hd)
        delta = round(st_ho["hit"] - base_h["hit"], 2)
        results[name] = {"train": st_tr, "hold": st_ho, "delta": delta}
        print(f"  {name:16s} tr {st_tr['n']}@{st_tr['hit']}%/{st_tr['cover']}% ho {st_ho['n']}@{st_ho['hit']}%/{st_ho['cover']}% Δ{delta}", flush=True)
        lines.append(
            f"| `{name}` | {st_tr['n']}@{st_tr['hit']}% {st_tr['cover']}% | "
            f"{st_ho['n']}@{st_ho['hit']}% {st_ho['cover']}% | {delta:+.2f}pp |"
        )
        if st_ho["hit"] > best[1]["hit"] or (st_ho["hit"] == best[1]["hit"] and st_ho["cover"] > best[1]["cover"]):
            best = (name, st_ho, ho)

    # Allow-list: last-10 fingerprints 100% on train clean34 1d wins/losses
    print("[allow-list fps from train]…", flush=True)
    # use ALL clean34 adaptive calls on train (gap'd) to learn fps — but purity on outcomes
    train_clean_rows = []
    by = defaultdict(list)
    for e in train:
        if not clean(e) or not e.get("_sc_adapt"):
            continue
        by[e["day"]].append({**e, **e["_sc_adapt"]})
    # better: use all gated gap calls for stats richness
    all_tr = []
    last = {}
    for e in sorted((x for x in train if clean(x) and x.get("_sc_adapt")), key=lambda z: (z["day"], z["mins"])):
        prev = last.get(e["day"])
        if prev is not None and e["mins"] - prev < GAP:
            continue
        row = {**e, **e["_sc_adapt"]}
        all_tr.append(row)
        last[e["day"]] = e["mins"]

    lines += ["", "## Allow-list last-10 fingerprints (100% train purity)", "", "| FP key | #allow | Train 1d | Hold 1d |", "|---|---:|---|---|"]

    for fp_key, min_n in (("pre10_fp2", 2), ("pre10_fp2", 3), ("pre10_fp", 2), ("pre10_couple", 5)):
        # purity from all_tr
        bucket = defaultdict(list)
        for e in all_tr:
            bucket[e.get(fp_key)].append(bool(e["_win"]))
        allow = {k for k, rows in bucket.items() if k is not None and len(rows) >= min_n and all(rows)}
        # also build from 1d only for tighter
        allow_1 = set()
        b1 = defaultdict(list)
        for e in base_tr:
            b1[e.get(fp_key)].append(bool(e["_win"]))
        for k, rows in b1.items():
            if k is not None and len(rows) >= max(2, min_n - 1) and all(rows):
                allow_1.add(k)

        for tag, aset in ((f"{fp_key}_all_n{min_n}", allow), (f"{fp_key}_1d", allow_1)):
            if not aset:
                continue

            def pred_factory(allowed, key):
                return lambda e, a=allowed, k=key: clean(e) and e.get(k) in a

            pred = pred_factory(aset, fp_key)
            tr = apply_1day(train, pred)
            ho = apply_1day(hold, pred)
            st_tr, st_ho = score_set(tr, td), score_set(ho, hd)
            print(f"  allow {tag}: n_fp={len(aset)} tr {st_tr['n']}@{st_tr['hit']}% ho {st_ho['n']}@{st_ho['hit']}%/{st_ho['cover']}%", flush=True)
            lines.append(
                f"| `{tag}` ({len(aset)}) | {len(aset)} | {st_tr['n']}@{st_tr['hit']}% {st_tr['cover']}% | "
                f"{st_ho['n']}@{st_ho['hit']}% {st_ho['cover']}% |"
            )
            if st_ho["n"] >= 10 and st_ho["hit"] > best[1]["hit"]:
                best = (tag, st_ho, ho)

    # Micro books with pre10 hard/mid/soft
    lines += ["", "## clean34 micros + pre10 gate", "", "| Book | Micros | Train 1d | Hold 1d |", "|---|---:|---|---|"]
    for name, p10 in (
        ("micro+soft", lambda e: e.get("pre10_hold_soft")),
        ("micro+mid", lambda e: e.get("pre10_hold_mid")),
        ("micro+hard", lambda e: e.get("pre10_hold_hard")),
        ("micro+couple", lambda e: e.get("pre10_couple_ok") == 1),
        ("micro+couple+favor6", lambda e: e.get("pre10_couple_ok") == 1 and e.get("pre10_favor", 0) >= 6),
    ):
        chosen, tr1, ho_full, ho1 = micro_hold_with_pre10(train, hold, h, l, c, clean, p10, min_train=2)
        st_tr1, st_ho1 = score_set(tr1, td), score_set(ho1, hd)
        print(f"  {name}: micros={len(chosen)} tr {st_tr1['n']}@{st_tr1['hit']}% ho {st_ho1['n']}@{st_ho1['hit']}%/{st_ho1['cover']}%", flush=True)
        lines.append(
            f"| **{name}** | {len(chosen)} | {st_tr1['n']}@{st_tr1['hit']}% {st_tr1['cover']}% | "
            f"{st_ho1['n']}@{st_ho1['hit']}% {st_ho1['cover']}% |"
        )
        if st_ho1["n"] >= 10 and (st_ho1["hit"] > best[1]["hit"] or (st_ho1["hit"] == best[1]["hit"] and st_ho1["cover"] > best[1].get("cover", 0))):
            best = (name, st_ho1, ho1)

    # Day log for best
    bname, bst, bcalls = best
    lines += [
        "",
        f"### Best hold lift: `{bname}` → **{bst['hit']}%** on {bst['n']} days (cover {bst['cover']}%)",
        "",
    ]
    if bcalls:
        lines += [
            "| Day | Y/N | HM | Side | Pattern | couple | last3 | favor | stair | drift | T1 | SL | MFE |",
            "|---|---|---|---|---|---|---|---:|---|---|---:|---:|---:|",
        ]
        by1 = {e["day"]: e for e in bcalls}
        hold_days = sorted({e["day"] for e in hold})
        for d in hold_days:
            e = by1.get(d)
            if not e:
                lines.append(f"| {d} | NO_CALL | | | | | | | | | | | |")
                continue
            mark = "Y" if e["_win"] else "N"
            lines.append(
                f"| {d} | {mark} | {e['hm']} | {e['decision']} | {e['primary']} | "
                f"{e.get('pre10_couple')} | {e.get('pre10_last3')} | {e.get('pre10_favor')} | "
                f"{e.get('pre10_stair')} | {e.get('pre10_drift_bin')} | {e.get('_t1',0):.0f} | "
                f"{e.get('_sl',0):.1f} | {e.get('mfe',0):.1f} |"
            )

    # Loss vs win pre10 profile on baseline hold
    loss = [e for e in base_ho if not e["_win"]]
    wins = [e for e in base_ho if e["_win"]]
    lines += [
        "",
        "## What last-10 looks like on base clean34 hold losses vs wins",
        "",
        f"- Loss couple: {Counter(e.get('pre10_couple') for e in loss).most_common(6)}",
        f"- Win couple: {Counter(e.get('pre10_couple') for e in wins).most_common(6)}",
        f"- Loss stair: {Counter(e.get('pre10_stair') for e in loss).most_common()}",
        f"- Win stair: {Counter(e.get('pre10_stair') for e in wins).most_common()}",
        f"- Loss drift: {Counter(e.get('pre10_drift_bin') for e in loss).most_common()}",
        f"- Win drift: {Counter(e.get('pre10_drift_bin') for e in wins).most_common()}",
        f"- Loss favor_bin: {Counter(e.get('pre10_favor_bin') for e in loss).most_common()}",
        f"- Win favor_bin: {Counter(e.get('pre10_favor_bin') for e in wins).most_common()}",
        "",
        "## Exact instant entry check",
        "",
        "1. Signal candle fires (clean34 MA ok).",
        "2. Read bars `i-10 … i-1`: build couple / last3 / favor / stair / drift.",
        "3. **Hold/entry allow** only if chosen pre10 rule passes (else skip — wait next signal).",
        "4. Then place adaptive T1/SL path trade.",
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"BEST {bname} hold={bst}", flush=True)
    print(f"Wrote {REPORT}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
