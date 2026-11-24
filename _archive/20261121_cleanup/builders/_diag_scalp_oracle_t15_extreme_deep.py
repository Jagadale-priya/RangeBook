"""Extra research: extreme vs magnet vs AD on Oracle T15 trail (NOT live)."""
from __future__ import annotations

import sys
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
import research_nifty_1m_scalp_prevcandle_100 as scalp  # noqa: E402
from _diag_scalp_ma_lastyear_init import add_ma_layers, enrich_ma_layers  # noqa: E402
from _diag_scalp_ma_hold100_indicators import add_indicators, enrich_ind  # noqa: E402
from _diag_scalp_ma_hold100_large_test import held_gate  # noqa: E402
from _diag_scalp_ma_hold_approaches import path_ma_trail_strict  # noqa: E402
from _diag_scalp_sr_highmove_proven import enrich_sr_archetypes, in_session  # noqa: E402
from _diag_scalp_ad_sr_entry_1m import add_ad_obv_proxy  # noqa: E402

sys.path.insert(0, str(ROOT / "app" / "fno"))
import fno_scalper_setup as setup  # noqa: E402

OUT = ROOT / "prod_live" / "reports" / "1y"
REPORT = OUT / "NIFTY_1M_ORACLE_T15_ACCURACY_BOOST.md"


def main() -> int:
    raw = base.load_existing_1m()
    hi = raw.index.max()
    raw = raw[raw.index >= hi - pd.Timedelta(days=55)]
    df = tb.detect_textbook(raw)
    df = beh.add_rsi(df)
    df = add_ma_layers(df)
    df = add_indicators(df)
    df = add_ad_obv_proxy(df)
    days_all = sorted({str(ts.date()) for ts in df.index})
    keep = set(days_all[-22:])
    events = scalp.collect_scalp_events(
        df, str(df.index.min().date()), str(df.index.max().date())
    )
    enrich_ma_layers(events, df)
    enrich_ind(events, df)
    setup.apply_setup_enrichment(events, df)
    enrich_sr_archetypes(events, df)

    ad_r = df["ad_rising"].astype(bool).values
    ad_f = df["ad_falling"].astype(bool).values
    h = df["High"].astype(float).values
    l = df["Low"].astype(float).values
    c = df["Close"].astype(float).values
    ema34 = df["ema34"].astype(float).values

    for e in events:
        i = int(e["full_i"])
        side = e["decision"]
        e["ad_with"] = (side == "BUY" and bool(ad_r[i])) or (
            side == "SELL" and bool(ad_f[i])
        )
        e["held"] = held_gate(e)
        e["sess"] = in_session(e)
        e["not_extreme"] = not bool(e.get("into_sess_extreme"))
        e["magnet"] = bool(e.get("at_liq_magnet"))
        e["clear"] = bool(e.get("clear_path"))
        e["ctrl"] = bool(e.get("control_with"))
        ok, _, _, _ = path_ma_trail_strict(h, l, c, ema34, i, side, 15.0)
        e["_w15"] = bool(ok)

    pool = [e for e in events if e["day"] in keep and e["sess"]]
    held = [e for e in pool if e["held"]]

    def rate(rows, pred=None):
        sub = [e for e in rows if (pred(e) if pred else True)]
        if not sub:
            return 0, None
        return len(sub), round(100.0 * sum(1 for e in sub if e["_w15"]) / len(sub), 2)

    print("HELD all", rate(held))
    print("HELD into_extreme", rate(held, lambda e: e.get("into_sess_extreme")))
    print("HELD not_extreme", rate(held, lambda e: e.get("not_extreme")))
    print("HELD magnet", rate(held, lambda e: e.get("magnet")))
    print("HELD NOT magnet", rate(held, lambda e: not e.get("magnet")))
    print("HELD AD", rate(held, lambda e: e.get("ad_with")))
    print("HELD AD+magnet", rate(held, lambda e: e.get("ad_with") and e.get("magnet")))
    print(
        "HELD AD+into_extreme",
        rate(held, lambda e: e.get("ad_with") and e.get("into_sess_extreme")),
    )
    print(
        "HELD AD+not_extreme",
        rate(held, lambda e: e.get("ad_with") and e.get("not_extreme")),
    )
    print("HELD clear", rate(held, lambda e: e.get("clear")))
    print("HELD AD+clear", rate(held, lambda e: e.get("ad_with") and e.get("clear")))
    print("HELD AD+ctrl", rate(held, lambda e: e.get("ad_with") and e.get("ctrl")))

    by = defaultdict(list)
    for e in pool:
        by[e["day"]].append(e)
    orac = []
    for d in sorted(by):
        for e in sorted(by[d], key=lambda x: x["mins"]):
            if e["_w15"]:
                orac.append(e)
                break
    print("\nOracle 1/day fingerprint n=", len(orac))
    for k in [
        "held",
        "into_sess_extreme",
        "not_extreme",
        "magnet",
        "ad_with",
        "clear",
        "ctrl",
        "setup_ok",
    ]:
        print(k, round(100.0 * sum(1 for e in orac if e.get(k)) / len(orac), 1))

    def first(pred):
        out = []
        for d in sorted(by):
            for e in sorted(by[d], key=lambda x: x["mins"]):
                if pred(e):
                    out.append(e)
                    break
        return out

    lines = [
        "",
        "## 5) Deeper cut — extreme is NOT always bad for T15 trail",
        "",
        "On **HELD** bars this window, buying/selling **into** the session extreme "
        "(continuation near day high/low) actually **won more** under EMA34 trail than "
        "avoiding it. So a hard `not_extreme` gate is **not** the accuracy booster for Oracle-style T15.",
        "",
        "| Condition on HELD | n | T15 trail hit% |",
        "|---|---:|---:|",
    ]
    for label, pred in [
        ("HELD all", None),
        ("into_sess_extreme", lambda e: e.get("into_sess_extreme")),
        ("not_extreme", lambda e: e.get("not_extreme")),
        ("at_liq_magnet (buy near low / sell near high)", lambda e: e.get("magnet")),
        ("AD_with", lambda e: e.get("ad_with")),
        ("AD + magnet", lambda e: e.get("ad_with") and e.get("magnet")),
        ("AD + into_extreme", lambda e: e.get("ad_with") and e.get("into_sess_extreme")),
        ("AD + not_extreme", lambda e: e.get("ad_with") and e.get("not_extreme")),
        ("AD + clear_path", lambda e: e.get("ad_with") and e.get("clear")),
        ("AD + control", lambda e: e.get("ad_with") and e.get("ctrl")),
    ]:
        n, hit = rate(held, pred)
        lines.append(f"| `{label}` | {n} | {hit} |")
        print(f"table {label}: n={n} hit={hit}")

    lines += [
        "",
        "### Oracle 1/day fingerprint (what winners look like)",
        "",
        f"n={len(orac)} first T15 path-wins/day:",
        "",
    ]
    for k in [
        "held",
        "ad_with",
        "ctrl",
        "clear",
        "magnet",
        "into_sess_extreme",
        "not_extreme",
        "setup_ok",
    ]:
        pct = round(100.0 * sum(1 for e in orac if e.get(k)) / len(orac), 1)
        lines.append(f"- `{k}`: **{pct}%**")

    lines += [
        "",
        "### Blind 1-call/day (same T15 trail exit)",
        "",
        "| Gate | n | Hit% |",
        "|---|---:|---:|",
    ]
    for name, pred in [
        ("HELD", lambda e: e["held"]),
        ("HELD + AD", lambda e: e["held"] and e["ad_with"]),
        ("HELD + magnet", lambda e: e["held"] and e["magnet"]),
        ("HELD + AD + magnet", lambda e: e["held"] and e["ad_with"] and e["magnet"]),
        (
            "HELD + AD + into_extreme",
            lambda e: e["held"] and e["ad_with"] and e.get("into_sess_extreme"),
        ),
        (
            "HELD + AD + !extreme",
            lambda e: e["held"] and e["ad_with"] and e["not_extreme"],
        ),
        ("HELD + AD + clear", lambda e: e["held"] and e["ad_with"] and e["clear"]),
    ]:
        calls = first(pred)
        n = len(calls)
        hit = round(100.0 * sum(1 for e in calls if e["_w15"]) / n, 2) if n else None
        lines.append(f"| `{name}` | {n} | **{hit}** |")
        print(f"1cpd {name}: n={n} hit={hit}")

    lines += [
        "",
        "## 6) Revised takeaway (research only)",
        "",
        "**Oracle T15 + EMA34 trail** = best chart teacher (100% by selecting path-wins).",
        "",
        "**Not into session extreme** = anti-chase rule (don’t BUY already at day high / "
        "SELL already at day low). Useful as *risk hygiene*, but on this 22d HELD sample "
        "it did **not** raise raw T15 hit — continuation into extremes often still trail-wins.",
        "",
        "Closest **blind** way to lean toward Oracle accuracy:",
        "1. Exit: **T15 · EMA34 trail** (keep this)",
        "2. Entry: **HELD + AD_with** (1cpd ~86% here)",
        "3. Optional flavor: **magnet** (buy near session low / sell near high) for mean-revert "
        "OR accept **into_extreme** as breakout continuation — don’t hard-ban extremes yet",
        "",
        "Still research-only — Scalper live Setup A/B unchanged.",
        "",
    ]

    # Append to main report
    text = REPORT.read_text(encoding="utf-8")
    # Replace weak conclusion section 4 advice about not_extreme as primary
    marker = "## 4) Research conclusion"
    if marker in text:
        head = text.split(marker)[0].rstrip()
        # clean messy oracle paragraph
        head = head.replace(
            "Fails still happen on Oracle gap books if a later ‘would-be win’ is taken after a "
            "winner that then… wait — Oracle only selects `_win` events, so **hit is ~100% by construction** "
            "on pure oracle picks. Chart ‘fails’ you see are usually **non-oracle / Setup** calls, or "
            "trail path that looked good then stopped (if mixed modes).",
            "Oracle hit is **100% by construction** (only path-wins are plotted). "
            "When you ‘see fails’, that is usually **Setup / Tier** mode, or mixing modes — "
            "not pure Oracle.",
        )
        new4 = [
            "",
            "## 4) Research conclusion (not live yet)",
            "",
            "**Keep Oracle T15 + EMA34 trail** as the quality ceiling / chart teacher.",
            "",
            "See §5–§6 for the corrected extreme finding and best blind approximation.",
            "",
        ]
        REPORT.write_text(head + "\n".join(new4) + "\n".join(lines), encoding="utf-8")
    else:
        REPORT.write_text(text + "\n".join(lines), encoding="utf-8")
    print(f"updated {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
