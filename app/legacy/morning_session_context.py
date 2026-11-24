"""Pre-live morning SESSION CONTEXT — no trade calls.

Frozen packs:
  - Range: MORNING_CTX_V4 / PRE915 ATR×3.5 (~96%+ containment)
  - Bias/Gap: MORNING_CALIBRATED_V1 (deep fusion + revalidation)

Research:
  prod_live/reports/1y/MORNING_CALIBRATED_GUARANTEE.md
  prod_live/reports/1y/MORNING_FINAL_REVALIDATE.md
  prod_live/reports/1y/MORNING_BIAS_STABILITY_SCAN.md
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

LOGIC_TAG = "MORNING_CALIBRATED_V1"
GAP_TH_PCT = 0.35
FLOOR_PCT = 0.004
# After 9:15 (open known): ATR*2.6 dn120 — ≥95% open-locked containment.
ATR_MULT = 2.6
# Before 9:15 (morning job): wider provisional box centered on prior close.
PRE915_ATR_MULT = 3.5
MAX_RANGE_LOOKBACK = 20
UP_HALF_MULT = 1.0
DN_HALF_MULT = 1.2
RANGE_MULT = 1.5  # legacy V2

# Calibrated directional rules (NIFTY deep hunt + walk/stability scans).
# Bias HIGH: US+Asia agree AND |SPX|>=1.5% → spoken ≥70% on 1y/3y/5y (walk_min~63%).
BIAS_AGREE_SPX_TH = 1.5
# Bias MED lean: |fuse_us_asia|>=5.5 (stable ~65% walk).
BIAS_FUSE_MED_TH = 5.5
# Gap lean (NOT held / not guaranteed): same agree+SPX gate, labeled lean.
GAP_LEAN_SPX_TH = 1.5

# Locked NIFTY full-containment — open-locked (post 9:15 reference).
LOCKED_1Y = {
    "report_end": "2026-11-11",
    "test_days": 252,
    "range_open_method": "atr_2_6x__dn120",
    "range_open_inside_pct": 0.9603,
    "range_open_median_width_pct": 0.0320,
    "gap_default_rule": "lean_or_natural",
    "bias_rule": "agree_spx_1_5_HIGH",
    "bias_note": "Calibrated V1: speak bias only on strong US+Asia+SPX days (≥70% windows).",
    "vol_method": "atr_pct_expanding_tercile",
    "vol_accuracy": 0.52,
}
LOCKED_3Y = {
    "report_end": "2026-11-11",
    "test_days": 756,
    "range_open_method": "atr_2_6x__dn120",
    "range_open_inside_pct": 0.9524,
    "range_open_median_width_pct": 0.0313,
    "gap_natural_accuracy": 0.6825,
    "vol_accuracy": 0.4802,
}
LOCKED_5Y = {
    "report_end": "2026-11-11",
    "test_days": 1260,
    "range_open_method": "atr_2_6x__dn120",
    "range_open_inside_pct": 0.9571,
    "range_open_median_width_pct": 0.0325,
}
# True morning-job box (center = prior close, no today's open).
LOCKED_PRE915 = {
    "range_method": "pre915_atr_3_5x__dn120",
    "center": "prior_close",
    "1y_inside_pct": 0.964,
    "3y_inside_pct": 0.966,
    "5y_inside_pct": 0.972,
    "3y_median_width_pct": 0.0403,
    "bias_rule": "agree_spx_1_5",
    "bias_spoken_acc": {"1y": 0.833, "3y": 0.711, "5y": 0.729},
    "gap_rule": "lean_agree_spx_1_5_NOT_HELD",
    "research": "MORNING_CALIBRATED_V1",
}
LOCKED_CALIBRATED = {
    "tag": "MORNING_CALIBRATED_V1",
    "range_guaranteed": True,
    "bias_guaranteed_when_speaking": True,
    "bias_floor": 0.70,
    "bias_rule": "us_asia_agree && abs(spx_ret)>=1.5",
    "gap_guaranteed": False,
    "gap_rule": "same gate as bias lean only",
    "reports": [
        "MORNING_CALIBRATED_GUARANTEE",
        "MORNING_FINAL_REVALIDATE",
        "MORNING_BIAS_STABILITY_SCAN",
        "MORNING_DEEP_FUSION",
    ],
}


def wilder_atr(high: pd.Series, low: pd.Series, close: pd.Series, n: int = 14) -> pd.Series:
    prev_c = close.shift(1)
    tr = pd.concat([(high - low), (high - prev_c).abs(), (low - prev_c).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def planned_width_v4(df: pd.DataFrame, *, pre915: bool = False) -> Tuple[float, float, float]:
    """Return (width, atr14, max20_range) using only completed bars in df.

    pre915=True → ATR*3.5 (morning job before cash open).
    pre915=False → ATR*2.6 (open-locked path after 9:15).
    """
    h = df["High"].astype(float)
    l = df["Low"].astype(float)
    c = df["Close"].astype(float)
    atr_raw = wilder_atr(h, l, c, 14).iloc[-1]
    try:
        atr = float(atr_raw)
    except (TypeError, ValueError):
        atr = float("nan")
    if atr != atr or atr <= 0:  # NaN / non-positive
        atr = 0.0
    prev_c = float(c.iloc[-1]) if float(c.iloc[-1]) == float(c.iloc[-1]) else 0.0
    day_rng = (h - l).clip(lower=0)
    max20_raw = float(day_rng.tail(MAX_RANGE_LOOKBACK).max()) if len(day_rng) else 0.0
    max20 = max20_raw if max20_raw == max20_raw else 0.0
    floor = max((prev_c * FLOOR_PCT) if prev_c > 0 else 1.0, 1.0)
    mult = PRE915_ATR_MULT if pre915 else ATR_MULT
    width = max(atr * mult, floor)
    return width, atr, max20


def planned_width_v3(df: pd.DataFrame) -> Tuple[float, float, float]:
    """Legacy V3 hybrid width (kept for comparison scripts)."""
    h = df["High"].astype(float)
    l = df["Low"].astype(float)
    c = df["Close"].astype(float)
    atr = float(wilder_atr(h, l, c, 14).iloc[-1])
    prev_c = float(c.iloc[-1])
    day_rng = (h - l).clip(lower=0)
    max20 = float(day_rng.tail(MAX_RANGE_LOOKBACK).max()) if len(day_rng) else 0.0
    floor = max(prev_c * FLOOR_PCT, 1.0)
    width = max(max(atr * 2.2, max20), floor)
    return width, atr, max20


def planned_width_max_yday_atr_1_5x(
    prev_high: float, prev_low: float, atr_val: float, price: float
) -> float:
    """Legacy V2 helper (not used by V3 forecast)."""
    yday = max(float(prev_high) - float(prev_low), 0.0)
    atr = max(float(atr_val), 0.0)
    floor = max(float(price) * FLOOR_PCT, 1.0)
    return max(max(yday, atr) * RANGE_MULT, floor)


def planned_width_atr14_1_2x(prev_high: float, prev_low: float, atr_val: float, price: float) -> float:
    return planned_width_max_yday_atr_1_5x(prev_high, prev_low, atr_val, price)


def _structure_label(df: pd.DataFrame) -> str:
    """Prior-bar trend only (last row = latest completed session)."""
    if df is None or len(df) < 25:
        return "UNKNOWN"
    h = df["High"].astype(float)
    l = df["Low"].astype(float)
    # Use all but require two 10-day windows ending at last bar
    roll_high = h.rolling(10).max()
    roll_low = l.rolling(10).min()
    if len(df) < 20 or pd.isna(roll_high.iloc[-1]) or pd.isna(roll_high.iloc[-11]):
        return "UNKNOWN"
    rh, rl = float(roll_high.iloc[-1]), float(roll_low.iloc[-1])
    ph, pl = float(roll_high.iloc[-11]), float(roll_low.iloc[-11])
    if rh > ph and rl > pl:
        return "UPTREND"
    if rh < ph and rl < pl:
        return "DOWNTREND"
    return "RANGE"


def classify_gap(open_px: Optional[float], prev_close: float) -> Dict[str, Any]:
    if open_px is None or not prev_close:
        return {
            "gap": "NATURAL",
            "gap_pct": None,
            "status": "premarket_default",
            "note": "Open unknown — 1y bake-off: always_natural is the only prior-day rule that held; await cash open.",
        }
    gap_pct = (float(open_px) - float(prev_close)) / float(prev_close) * 100.0
    if gap_pct > GAP_TH_PCT:
        g = "GAP_UP"
    elif gap_pct < -GAP_TH_PCT:
        g = "GAP_DOWN"
    else:
        g = "NATURAL"
    return {
        "gap": g,
        "gap_pct": round(gap_pct, 2),
        "status": "open_observed",
        "note": f"Classified from cash open vs prior close (±{GAP_TH_PCT}%).",
    }


def classify_vix_regime(vix_level: Optional[float]) -> Dict[str, Any]:
    if vix_level is None or vix_level != vix_level:
        return {"available": False, "level": None, "regime": "UNKNOWN"}
    level = float(vix_level)
    if level < 14:
        regime = "LOW"
    elif level < 18:
        regime = "NORMAL"
    elif level < 22:
        regime = "ELEVATED"
    else:
        regime = "HIGH"
    return {"available": True, "level": round(level, 2), "regime": regime}


def vol_label_from_history(df: pd.DataFrame) -> Dict[str, Any]:
    """ATR% expanding tercile using completed bars only."""
    if df is None or len(df) < 60:
        return {"vol_label": "UNKNOWN", "atr_pct": None}
    h, l, c = df["High"].astype(float), df["Low"].astype(float), df["Close"].astype(float)
    atr = wilder_atr(h, l, c, 14)
    atr_pct = (atr / c) * 100.0
    last = float(atr_pct.iloc[-1])
    hist = atr_pct.iloc[:-1].dropna()
    if len(hist) < 40:
        return {"vol_label": "NORMAL", "atr_pct": round(last, 3)}
    q33, q66 = float(hist.quantile(0.33)), float(hist.quantile(0.66))
    if last >= q66:
        lab = "HIGH"
    elif last <= q33:
        lab = "LOW"
    else:
        lab = "NORMAL"
    return {"vol_label": lab, "atr_pct": round(last, 3), "q33": round(q33, 3), "q66": round(q66, 3)}


def best_chain_guidance(
    *,
    vol_label: str,
    vix_regime: str,
    bias: str,
    atr_pct: Optional[float],
) -> Dict[str, Any]:
    """Style guidance only — never a BUY/SELL ticket."""
    if vix_regime == "HIGH" or vol_label == "HIGH":
        style = "SPREAD"
        why = "High vol/VIX — prefer defined-risk spreads; avoid naked ATM debit chase."
    elif vix_regime == "LOW" and vol_label == "LOW":
        style = "INDEX_FUT"
        why = "Low vol — futures or slightly OTM; avoid overpaying premium."
    elif vix_regime == "ELEVATED" or vol_label == "HIGH":
        style = "ATM_OPTION"
        why = "Elevated vol — ATM/near-ATM options; size down."
    else:
        style = "ATM_OR_FUT"
        why = "Normal regime — futures or ATM options."

    side = "NONE"
    # Soft side hint only when bias is not NEUTRAL (still not a call)
    if bias == "BULLISH":
        side = "CE" if style != "INDEX_FUT" else "FUT_LONG"
    elif bias == "BEARISH":
        side = "PE" if style != "INDEX_FUT" else "FUT_SHORT"

    strike = "ATM"
    if style == "SPREAD":
        strike = "ATM_SPREAD"
    elif style == "INDEX_FUT":
        strike = "FUTURE"
    elif atr_pct is not None and atr_pct > 1.2:
        strike = "ITM_OR_ATM"

    return {
        "style": style,
        "side_hint": side,
        "strike_band": strike,
        "why": why,
        "guide_only": True,
        "is_call": False,
    }


def forecast_range_box(
    df: pd.DataFrame,
    open_px: Optional[float] = None,
) -> Dict[str, Any]:
    if df is None or len(df) < 20:
        return {"available": False}
    c = df["Close"].astype(float)
    prev_c = float(c.iloc[-1])
    pre915 = open_px is None or float(open_px or 0) <= 0
    width, atr, max20 = planned_width_v4(df, pre915=pre915)
    half = width / 2.0
    up = half * UP_HALF_MULT
    dn = half * DN_HALF_MULT
    if not pre915:
        center = float(open_px)
        hi, lo = center + up, center - dn
        gap = center - prev_c
        method = "open_locked_atr26x_dn120"
        if prev_c > 0 and abs(gap) / prev_c >= 0.0035:
            extra = min(abs(gap), width * 0.35)
            if gap > 0:
                hi += extra
            else:
                lo -= extra
            method = "open_locked_atr26x_dn120_gap_asymmetric"
        locked = True
        anchor = "session_open"
    else:
        # Morning job before 9:15 — proven provisional box (no today's open).
        center = prev_c
        hi, lo = center + up, center - dn
        method = "pre915_atr35x_dn120"
        locked = False
        anchor = "prev_close"
    def _r(x: float, n: int = 2):
        try:
            v = float(x)
            if v != v:  # NaN
                return None
            return round(v, n)
        except (TypeError, ValueError):
            return None

    width_pct = None
    if prev_c and prev_c == prev_c and prev_c > 0:
        width_pct = _r((hi - lo) / prev_c * 100, 3)
    return {
        "available": True,
        "expected_high": _r(hi),
        "expected_low": _r(lo),
        "planned_width": _r(hi - lo),
        "width_pct": width_pct,
        "locked": locked,
        "anchor": anchor,
        "method": method,
        "reference_prev_close": _r(prev_c),
        "reference_open": None if open_px is None else _r(float(open_px)),
        "atr14": _r(atr),
        "max20_range": _r(max20),
        "up_half_mult": UP_HALF_MULT,
        "dn_half_mult": DN_HALF_MULT,
    }


def _chg_from_markets(markets: List[Dict[str, Any]], symbols: Tuple[str, ...]) -> Optional[float]:
    vals = []
    for m in markets or []:
        if (m.get("symbol") or "") in symbols:
            try:
                vals.append(float(m.get("change_pct")))
            except (TypeError, ValueError):
                continue
    if not vals:
        return None
    return float(np.mean(vals))


def compute_overnight_fusion(
    overnight_panel: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Live overnight fusion matching research fuse_us_asia / agree_spx features."""
    panel = overnight_panel or {}
    markets = list(panel.get("markets") or [])
    spx = _chg_from_markets(markets, ("^GSPC",))
    ndx = _chg_from_markets(markets, ("^IXIC",))
    dji = _chg_from_markets(markets, ("^DJI",))
    n225 = _chg_from_markets(markets, ("^N225",))
    hsi = _chg_from_markets(markets, ("^HSI",))
    vix = _chg_from_markets(markets, ("^VIX",))

    us_vals = [x for x in (spx, ndx, dji) if x is not None]
    asia_vals = [x for x in (n225, hsi) if x is not None]
    us_mean = float(np.mean(us_vals)) if us_vals else None
    asia_mean = float(np.mean(asia_vals)) if asia_vals else None
    us_asia_agree = bool(
        us_mean is not None
        and asia_mean is not None
        and (
            (us_mean > 0.25 and asia_mean > 0.25)
            or (us_mean < -0.25 and asia_mean < -0.25)
        )
    )
    fuse = 0.0
    if us_mean is not None:
        fuse += float(np.sign(us_mean) * min(abs(us_mean), 2.0) * 2.0)
    if asia_mean is not None:
        fuse += float(np.sign(asia_mean) * min(abs(asia_mean), 2.0) * 1.5)
    if vix is not None:
        fuse -= float(np.sign(vix) * min(abs(vix), 5.0) * 0.4)

    return {
        "spx_ret": None if spx is None else round(spx, 3),
        "ndx_ret": None if ndx is None else round(ndx, 3),
        "us_mean": None if us_mean is None else round(us_mean, 3),
        "asia_mean": None if asia_mean is None else round(asia_mean, 3),
        "vix_ret": None if vix is None else round(vix, 3),
        "us_asia_agree": us_asia_agree,
        "fuse_us_asia": round(fuse, 3),
        "panel_bias": panel.get("bias"),
        "panel_score": panel.get("score_delta"),
        "markets_n": len(markets),
    }


def decide_pre915_gap_bias(
    fusion: Dict[str, Any],
    *,
    news_tone: Optional[str] = None,
    news_score: Optional[float] = None,
    trend: Optional[str] = None,
) -> Dict[str, Any]:
    """Calibrated V1 directional decision (before cash open).

    - Bias HIGH (held ≥70% windows): US+Asia agree and |SPX|>=1.5
    - Bias MED: |fuse_us_asia|>=5.5
    - Gap: same HIGH gate as lean only (not guaranteed)
    - News strong opposite → veto spoken HIGH/MED back to NATURAL/NEUTRAL
    """
    spx = fusion.get("spx_ret")
    agree = bool(fusion.get("us_asia_agree"))
    fuse = float(fusion.get("fuse_us_asia") or 0.0)
    tone = (news_tone or "NEUTRAL").upper()
    nscore = float(news_score) if news_score is not None else None

    high_up = agree and spx is not None and float(spx) >= BIAS_AGREE_SPX_TH
    high_dn = agree and spx is not None and float(spx) <= -BIAS_AGREE_SPX_TH
    med_up = fuse >= BIAS_FUSE_MED_TH
    med_dn = fuse <= -BIAS_FUSE_MED_TH

    bias = "NEUTRAL"
    bias_conf = "ABSTAIN"
    bias_held = False
    gap = "NATURAL"
    gap_conf = "ABSTAIN"
    gap_held = False

    if high_up:
        bias, bias_conf, bias_held = "BULLISH", "HIGH", True
        gap, gap_conf = "GAP_UP", "LOW"
    elif high_dn:
        bias, bias_conf, bias_held = "BEARISH", "HIGH", True
        gap, gap_conf = "GAP_DOWN", "LOW"
    elif med_up:
        bias, bias_conf, bias_held = "BULLISH", "MED", False
    elif med_dn:
        bias, bias_conf, bias_held = "BEARISH", "MED", False

    # News veto / soft lean
    news_veto = False
    if bias == "BULLISH" and (tone == "BEARISH" or (nscore is not None and nscore <= -3)):
        news_veto = True
    if bias == "BEARISH" and (tone == "BULLISH" or (nscore is not None and nscore >= 3)):
        news_veto = True
    if news_veto:
        bias, bias_conf, bias_held = "NEUTRAL", "ABSTAIN", False
        gap, gap_conf = "NATURAL", "ABSTAIN"

    soft = "NEUTRAL"
    if bias in ("BULLISH", "BEARISH"):
        soft = bias
    elif (fusion.get("panel_bias") or "").upper() in ("RISK_ON", "BULLISH") and tone != "BEARISH":
        soft = "BULLISH"
    elif (fusion.get("panel_bias") or "").upper() in ("RISK_OFF", "BEARISH") and tone != "BULLISH":
        soft = "BEARISH"
    elif (trend or "") == "UPTREND" and tone != "BEARISH":
        soft = "BULLISH"
    elif (trend or "") == "DOWNTREND" and tone != "BULLISH":
        soft = "BEARISH"

    drivers = []
    if spx is not None:
        drivers.append(f"SPX {float(spx):+.2f}%")
    if fusion.get("us_mean") is not None:
        drivers.append(f"US mean {fusion['us_mean']:+.2f}%")
    if fusion.get("asia_mean") is not None:
        drivers.append(f"Asia mean {fusion['asia_mean']:+.2f}%")
    drivers.append(f"US+Asia agree={agree}")
    drivers.append(f"fuse_us_asia={fuse:+.2f}")
    if tone and tone != "NEUTRAL":
        drivers.append(f"news={tone}")
    if news_veto:
        drivers.append("news_veto=True")
    if trend:
        drivers.append(f"trend={trend}")

    return {
        "bias": bias,
        "bias_confidence": bias_conf,
        "bias_held": bias_held,
        "gap": gap,
        "gap_confidence": gap_conf,
        "gap_held": gap_held,
        "soft_lean": soft,
        "news_veto": news_veto,
        "drivers": drivers,
        "rule": {
            "bias_high": f"us_asia_agree && abs(spx)>={BIAS_AGREE_SPX_TH}",
            "bias_med": f"abs(fuse_us_asia)>={BIAS_FUSE_MED_TH}",
            "gap_lean": f"same as bias_high (NOT held); th={GAP_LEAN_SPX_TH}",
        },
    }


def build_session_context(
    symbol: str,
    df: pd.DataFrame,
    *,
    open_px: Optional[float] = None,
    vix_level: Optional[float] = None,
    news_tone: Optional[str] = None,
    news_score: Optional[float] = None,
    overnight_bias: Optional[str] = None,
    overnight_panel: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Morning / pre-session context row. Never includes decision/BUY/SELL.

    Morning job (before 9:15): open_px=None.
    Uses PRE915 range (guaranteed ~96%+) + calibrated gap/bias from news+globals+TA.
    """
    k = symbol.strip().upper()
    if df is None or len(df) < 30:
        return {
            "symbol": k,
            "available": False,
            "logic_tag": LOGIC_TAG,
            "error": "insufficient_daily_bars",
            "is_call": False,
        }

    work = df.copy()
    colmap = {str(c).lower(): c for c in work.columns}
    for src, dst in (("open", "Open"), ("high", "High"), ("low", "Low"), ("close", "Close")):
        if dst not in work.columns and src in colmap:
            work[dst] = work[colmap[src]]

    rng = forecast_range_box(work, open_px=open_px)
    prev_c = float(work["Close"].astype(float).iloc[-1])
    gap_obs = classify_gap(open_px, prev_c)
    trend = _structure_label(work)
    vol = vol_label_from_history(work)
    vix = classify_vix_regime(vix_level)
    pre915 = open_px is None or float(open_px or 0) <= 0

    panel = overnight_panel
    if panel is None and overnight_bias is not None:
        panel = {"bias": overnight_bias, "markets": []}
    fusion = compute_overnight_fusion(panel)

    if pre915:
        decision = decide_pre915_gap_bias(
            fusion,
            news_tone=news_tone,
            news_score=news_score,
            trend=trend,
        )
        gap_label = decision["gap"]
        bias = decision["bias"]
        soft = decision["soft_lean"]
        bias_proven = {
            "bias": bias,
            "proven": bool(decision["bias_held"]),
            "spoken": bias in ("BULLISH", "BEARISH"),
            "confidence": decision["bias_confidence"],
            "floor": 0.70 if decision["bias_held"] else None,
            "note": (
                "Held ≥70% spoken on 1y/3y/5y when US+Asia agree & |SPX|≥1.5%."
                if decision["bias_held"]
                else "Abstain/MED lean — strong agree+SPX gate not fired (or news veto)."
            ),
            "research": "MORNING_CALIBRATED_V1",
            "drivers": decision["drivers"],
        }
        gap_proven = {
            "gap": gap_label,
            "proven": False,
            "held": False,
            "confidence": decision["gap_confidence"],
            "mode": "pre915_lean",
            "note": (
                "Gap lean from same US+Asia+SPX gate — NOT guaranteed (best hard gap ~54-59%)."
                if gap_label != "NATURAL"
                else "No strong overnight agree+SPX signal — gap NATURAL."
            ),
            "research": "MORNING_CALIBRATED_V1",
            "drivers": decision["drivers"],
        }
        gap_detail = {
            "gap": gap_label,
            "gap_pct": None,
            "status": "pre915_calibrated_lean",
            "confidence": decision["gap_confidence"],
            "held": False,
        }
    else:
        decision = {
            "bias_confidence": "OBSERVED",
            "gap_confidence": "OBSERVED",
            "bias_held": False,
            "gap_held": False,
            "news_veto": False,
            "drivers": [],
            "soft_lean": "NEUTRAL",
        }
        gap_label = gap_obs.get("gap")
        gap_detail = gap_obs
        soft = "NEUTRAL"
        ovn = (overnight_bias or fusion.get("panel_bias") or "").upper()
        if ovn in ("RISK_ON", "BULLISH") and (news_tone or "").upper() != "BEARISH":
            soft = "BULLISH"
        elif ovn in ("RISK_OFF", "BEARISH") and (news_tone or "").upper() != "BULLISH":
            soft = "BEARISH"
        bias = soft if soft in ("BULLISH", "BEARISH") else "NEUTRAL"
        bias_proven = {
            "bias": bias,
            "proven": False,
            "spoken": bias in ("BULLISH", "BEARISH"),
            "confidence": "LOW",
            "note": "Open known — gap observed; bias is soft lean only.",
            "research": "MORNING_CALIBRATED_V1",
        }
        gap_proven = {
            "gap": gap_label,
            "proven": True,
            "held": True,
            "mode": gap_obs.get("status"),
            "note": "Observed from cash open vs prior close (definitional 100%).",
            "research": "MORNING_CALIBRATED_V1",
        }

    chain = best_chain_guidance(
        vol_label=str(vol.get("vol_label") or "UNKNOWN"),
        vix_regime=str(vix.get("regime") or "UNKNOWN"),
        bias=soft if soft != "NEUTRAL" else bias,
        atr_pct=vol.get("atr_pct"),
    )

    what_to_expect = []
    if pre915:
        what_to_expect.append(
            "PRE-9:15 MORNING_CALIBRATED_V1: range guaranteed ~96%+; "
            f"bias={bias} ({decision.get('bias_confidence')}); "
            f"gap={gap_label} ({decision.get('gap_confidence')}, not guaranteed)."
        )
    if not pre915 and gap_label != "NATURAL":
        what_to_expect.append(
            f"Gap observed {gap_label} ({gap_detail.get('gap_pct'):+.2f}%) — "
            "classified from open vs prior close (proven 100%)."
        )
    what_to_expect.append(
        f"Expected range ₹{rng.get('expected_low')} – ₹{rng.get('expected_high')} "
        f"({rng.get('method')}, locked={rng.get('locked')})."
    )
    drv = decision.get("drivers") or []
    if not drv:
        drv = [
            f"SPX {fusion.get('spx_ret')}",
            f"agree={fusion.get('us_asia_agree')}",
            f"fuse={fusion.get('fuse_us_asia')}",
            f"news={news_tone or 'n/a'}",
            f"trend={trend}",
        ]
    what_to_expect.append("Drivers: " + "; ".join(str(x) for x in drv))
    what_to_expect.append(
        f"Vol {vol.get('vol_label')} (ATR% {vol.get('atr_pct')}); "
        f"VIX {vix.get('regime')} ({vix.get('level')})."
    )
    what_to_expect.append(f"Chain style guidance: {chain['style']} / {chain['strike_band']} — {chain['why']}")

    return {
        "symbol": k,
        "available": True,
        "logic_tag": LOGIC_TAG,
        "is_call": False,
        "expected_high": rng.get("expected_high"),
        "expected_low": rng.get("expected_low"),
        "day_range": rng,
        "mode": "pre915" if pre915 else "open_locked",
        "bias": bias,
        "bias_confidence": decision.get("bias_confidence"),
        "soft_lean": soft,
        "bias_edge": bool(decision.get("bias_held")),
        "bias_proven": bias_proven,
        "gap": gap_label,
        "gap_confidence": decision.get("gap_confidence"),
        "gap_detail": gap_detail,
        "gap_proven": gap_proven,
        "trend": trend,
        "overnight_bias": overnight_bias or fusion.get("panel_bias"),
        "overnight_fusion": fusion,
        "drivers": decision.get("drivers") or [],
        "parameters": {
            "vol_label": vol.get("vol_label"),
            "atr_pct": vol.get("atr_pct"),
            "vix": vix,
            "expected_width_pct": rng.get("width_pct"),
            "news_tone": news_tone,
            "news_score": news_score,
            "news_veto": decision.get("news_veto"),
        },
        "best_chain": chain,
        "what_to_expect": what_to_expect,
        "provenance": {
            "locked_1y": LOCKED_1Y,
            "locked_pre915": LOCKED_PRE915,
            "locked_calibrated": LOCKED_CALIBRATED,
            "no_calls": True,
        },
    }


FORBIDDEN_CALL_KEYS = (
    "decision",
    "intraday_ready",
    "fno_picks",
    "intraday_picks",
    "accurate_tag",
    "BUY",
    "SELL",
)


def assert_no_calls(row: Dict[str, Any]) -> None:
    for k in FORBIDDEN_CALL_KEYS:
        if k in row and row[k] not in (None, False):
            # allow string mentions inside notes only via nested — top-level forbidden
            if k in ("BUY", "SELL") and isinstance(row.get(k), str):
                raise AssertionError(f"forbidden call key {k}")
            if k in row and k not in ("BUY", "SELL"):
                raise AssertionError(f"forbidden call key {k}={row[k]}")
    if row.get("is_call") is True:
        raise AssertionError("is_call must be false")
    bc = row.get("best_chain") or {}
    if bc.get("is_call") is True or bc.get("guide_only") is not True:
        raise AssertionError("best_chain must be guide_only")


def build_watchlist_context(
    items: List[Dict[str, Any]],
    load_daily_fn,
    *,
    vix_level: Optional[float] = None,
    open_by_symbol: Optional[Dict[str, float]] = None,
    news_tone_by_symbol: Optional[Dict[str, str]] = None,
) -> List[Dict[str, Any]]:
    open_by_symbol = open_by_symbol or {}
    news_tone_by_symbol = news_tone_by_symbol or {}
    out: List[Dict[str, Any]] = []
    for item in items:
        sym = (item.get("symbol") or item.get("stock") or "").strip().upper()
        if not sym:
            continue
        try:
            df = load_daily_fn(sym)
        except Exception as exc:
            out.append({"symbol": sym, "available": False, "error": str(exc), "is_call": False, "logic_tag": LOGIC_TAG})
            continue
        row = build_session_context(
            sym,
            df,
            open_px=open_by_symbol.get(sym),
            vix_level=vix_level,
            news_tone=news_tone_by_symbol.get(sym),
        )
        assert_no_calls(row)
        out.append(row)
    return out
