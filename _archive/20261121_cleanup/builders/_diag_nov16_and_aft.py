"""Diagnose Nov16 champion BUY into red + why no post-13:00 call on latest session."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [
    str(ROOT / "prod_live" / "tests" / "builders"),
    str(ROOT / "app" / "fno"),
    str(ROOT / "prod_live"),
]
import kite_data  # noqa: E402
import nifty_afternoon_thrust as nat  # noqa: E402


def _cols(df: pd.DataFrame) -> pd.DataFrame:
    m = {c: str(c).strip().title() for c in df.columns}
    out = df.rename(columns=m)
    # common kite aliases
    ren = {}
    for c in out.columns:
        cl = c.lower()
        if cl in ("open", "high", "low", "close", "volume"):
            ren[c] = cl.title()
    return out.rename(columns=ren) if ren else out


def main() -> int:
    df, err = kite_data.fetch_historical_candles(
        "NIFTY", interval="15minute", days=10, keep_partial=True
    )
    if err or df is None or df.empty:
        print("pull failed", err)
        return 1
    print("columns", list(df.columns))
    df = _cols(df)
    # normalize OHLC names
    cmap = {c.lower(): c for c in df.columns}
    for need in ("open", "high", "low", "close"):
        if need not in cmap:
            # try exact
            pass
    # force lower
    df = df.rename(columns={c: c.lower() for c in df.columns})
    for need in ("open", "high", "low", "close"):
        if need not in df.columns:
            print("missing", need, "have", list(df.columns))
            return 1
    # title for thrust module
    bars = df.rename(
        columns={"open": "Open", "high": "High", "low": "Low", "close": "Close"}
    )

    days = sorted(set(bars.index.strftime("%Y-%m-%d")))
    print("days", days)

    # --- Nov 16 day path around 10:15 ---
    day = "2026-11-16"
    d = bars[bars.index.strftime("%Y-%m-%d") == day]
    if d.empty:
        print("no bars", day)
    else:
        o0 = float(d.iloc[0]["Open"])
        or_hi = float(d.iloc[0]["High"])
        or_lo = float(d.iloc[0]["Low"])
        print(f"\n=== {day} session ===")
        print(f"OR open={o0:.2f} hi={or_hi:.2f} lo={or_lo:.2f}")
        for ts, row in d.iterrows():
            hm = pd.Timestamp(ts).tz_convert("Asia/Kolkata").strftime("%H:%M")
            if hm > "11:00":
                break
            c = float(row["Close"])
            print(
                f"  {hm} O={float(row['Open']):.2f} H={float(row['High']):.2f} "
                f"L={float(row['Low']):.2f} C={c:.2f} "
                f"vsOR={'ABOVE_HI' if c>or_hi else ('BELOW_LO' if c<or_lo else 'IN_OR')} "
                f"vsOpen={'GREEN_DAY' if c>=o0 else 'RED_DAY'} "
                f"bar={'G' if c>float(row['Open']) else 'R'}"
            )
        # live book row
        book = ROOT / "prod_live" / "holding_accurate" / "champion_plus" / "live_session_calls.json"
        if book.exists():
            raw = json.loads(book.read_text(encoding="utf-8"))
            rows = raw if isinstance(raw, list) else (raw.get("calls") or raw.get("rows") or [])
            hits = [
                r
                for r in rows
                if isinstance(r, dict)
                and str(r.get("day") or "")[:10] == day
                and str(r.get("hm") or "")[:5] == "10:15"
            ]
            print("live_session_calls 10:15:", json.dumps(hits, indent=2)[:2000])

    # --- latest session afternoon thrust ---
    last = days[-1]
    print(f"\n=== afternoon thrust check · {last} ===")
    d = bars[bars.index.strftime("%Y-%m-%d") == last]
    o0 = float(d.iloc[0]["Open"])
    or_hi = float(d.iloc[0]["High"])
    or_lo = float(d.iloc[0]["Low"])
    open13 = None
    for ts, row in d.iterrows():
        hm = pd.Timestamp(ts).tz_convert("Asia/Kolkata").strftime("%H:%M")
        if hm == "13:00":
            open13 = float(row["Open"])
    print(f"OR open={o0:.2f} hi={or_hi:.2f} lo={or_lo:.2f} open13={open13}")
    print(f"day close={float(d.iloc[-1]['Close']):.2f} chg={float(d.iloc[-1]['Close'])-o0:.2f}")

    fired = None
    for ts, row in d.iterrows():
        hm = pd.Timestamp(ts).tz_convert("Asia/Kolkata").strftime("%H:%M")
        if hm < "13:00":
            continue
        window = bars[bars.index <= ts]
        ev = nat.evaluate(window, asof=pd.Timestamp(ts).to_pydatetime(), price=float(row["Close"]))
        c = float(row["Close"])
        reasons = []
        if hm < "13:15" or hm > "14:45":
            reasons.append("outside_13:15-14:45")
        if open13 is None:
            reasons.append("no_13:00_bar")
        else:
            if c <= or_hi:
                reasons.append(f"close<=OR_hi ({c:.1f}<={or_hi:.1f})")
            if c <= float(row["Open"]):
                reasons.append("red_bar")
            if (c - open13) < 30:
                reasons.append(f"uplift_from_13={c-open13:.1f}<30")
            # prior 2 highs
            loc = list(d.index).index(ts)
            if loc >= 2:
                prior = [float(d.iloc[j]["High"]) for j in range(loc - 2, loc)]
                if c <= max(prior):
                    reasons.append(f"no_break_prior2H max={max(prior):.1f}")
        print(
            f"  {hm} C={c:.2f} green={c>float(row['Open'])} "
            f"thrust={'FIRE' if ev else 'no'} "
            f"fail={';'.join(reasons) if reasons and not ev else '-'}"
        )
        if ev and fired is None:
            fired = (hm, ev)

    print("FIRE result:", fired[0] if fired else "NONE")

    # also CHAMP_PLUS afternoon listings that day
    book = ROOT / "prod_live" / "holding_accurate" / "champion_plus" / "live_session_calls.json"
    if book.exists():
        raw = json.loads(book.read_text(encoding="utf-8"))
        rows = raw if isinstance(raw, list) else (raw.get("calls") or raw.get("rows") or [])
        aft = [
            r
            for r in rows
            if isinstance(r, dict)
            and str(r.get("day") or "")[:10] == last
            and str(r.get("hm") or "")[:5] >= "13:00"
        ]
        print(f"CHAMP_PLUS book after 13:00 on {last}:", len(aft))
        for r in aft:
            print(" ", r.get("hm"), r.get("decision"), r.get("track"), r.get("entry"))
        day_rows = [
            r
            for r in rows
            if isinstance(r, dict) and str(r.get("day") or "")[:10] == last
        ]
        print(f"CHAMP_PLUS all calls on {last}:", len(day_rows))
        for r in day_rows:
            print(" ", r.get("hm"), r.get("decision"), r.get("track"), r.get("entry"), r.get("source"))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
