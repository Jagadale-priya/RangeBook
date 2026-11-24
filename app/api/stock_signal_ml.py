import path_setup
#!/usr/bin/env python3
""" ==================================================================== STOCK SIGNAL ML ENGINE v1.0 ML-Powered Trading Decision System ====================================================================

  A self-contained script that:
    1. Auto-installs required packages (yfinance, scikit-learn, flask)
    2. Downloads historical stock data (Yahoo Finance, free, no API key)
    3. Computes 30+ technical indicators
    4. Trains ensemble ML models (RandomForest + GradientBoosting + AdaBoost)
    5. Runs a REST API: pass stock name, get BUY/SELL/HOLD decision

  USAGE:
    Quick prediction (no server):
      py stock_signal_ml.py --predict RELIANCE

    Start API server:
      py stock_signal_ml.py

    Then call:
      curl -X POST http://localhost:5000/predict ^
           -H "Content-Type: application/json" ^
           -d "{\"stock\": \"RELIANCE\"}"

  SUPPORTED:
    Indian: RELIANCE, HDFCBANK, INFY, TCS, SBIN, ICICIBANK, etc.
    US:     AAPL, MSFT, GOOGL, AMZN, TSLA, etc.
    Crypto: BTC, ETH, SOL

  DATA SOURCE: Yahoo Finance (historical EOD) + Groww API (live NSE quotes when .env configured)

  DISCLAIMER: Educational / POC only. ML predictions are probabilistic
  (typically 52-60% directional accuracy). Never trade real money
  based solely on automated signals.
====================================================================
"""

import subprocess
import sys
import os
import json
import math
import time
import sqlite3
import hashlib
import warnings
import argparse
import threading
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from pathlib import Path

warnings.filterwarnings("ignore")

# ================================================================
# SECTION 1: AUTO-INSTALL PACKAGES
# ================================================================

def install_packages():
    """Install required packages automatically, handling corporate SSL. """
    required = { "yfinance": "yfinance" , "sklearn": "scikit-learn" , "flask": "flask" , "joblib": "joblib" , }

    print("\n[1/3] Checking dependencies... ")
    all_ok = True

    for import_name, pip_name in required.items():
        try:
            __import__(import_name)
            print(f"  {pip_name}: OK")
            continue
        except ImportError:
            pass

        print(f"  {pip_name}: Installing... ", end=" ", flush=True)
        installed = False

        trust_args = [ "--trusted-host", "pypi.org" , "--trusted-host", "pypi.python.org" , "--trusted-host", "files.pythonhosted.org" , ]

        for extra in [trust_args, []]:
            try:
                subprocess.check_call( [sys.executable, "-m", "pip", "install", pip_name]
                    + extra
                    + ["--quiet"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, )
                print("OK")
                installed = True
                break
            except subprocess.CalledProcessError:
                continue

        if not installed:
            print("FAILED")
            all_ok = False

    if not all_ok:
        print("\nSome packages failed to install. Run manually:")
        print("  pip install yfinance scikit-learn flask")
        sys.exit(1)

    # Optional: matplotlib for charts
    try:
        __import__("matplotlib")
    except ImportError:
        try:
            subprocess.check_call( [sys.executable, "-m", "pip", "install", "matplotlib"]
                + trust_args
                + ["--quiet"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, )
        except Exception:
            pass


install_packages()

# ================================================================
# SECTION 2: IMPORTS (after install)
# ================================================================

import numpy as np
import pandas as pd
import yfinance as yf
import joblib
from sklearn.ensemble import (
    RandomForestClassifier,
    GradientBoostingClassifier,
    AdaBoostClassifier,
    VotingClassifier,
    HistGradientBoostingClassifier,
)
from sklearn.base import clone
from sklearn.calibration import CalibratedClassifierCV
from sklearn.model_selection import TimeSeriesSplit
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from flask import Flask, redirect, request, jsonify, send_from_directory

import groww_data  # .env loader
import live_market
import market_symbols
import regime_features
import ui_provenance
import backtest
import news_data
import analysis_engine
import kite_data
import morning_job
import morning_session_context
import pattern_memory
import structural_analysis
import fundamentals
import india_market_context
import full_market_analysis
import product_analysis
import intraday_engine
import fno_instruments
import fno_live_engine
import fno_ws_rescore
import analysis_store
import audit_report
import historical_audit
import data_inventory

try:
    from xgboost import XGBClassifier
    HAS_XGBOOST = True
except ImportError:
    HAS_XGBOOST = False

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

# ================================================================
# SECTION 3: CONFIGURATION
# ================================================================

SCRIPT_DIR = str(path_setup.ROOT)
BASE_DIR = os.path.join(SCRIPT_DIR, "stock_signal_data")
MODEL_DIR = os.path.join(BASE_DIR, "models")
CACHE_DIR = os.path.join(BASE_DIR, "cache")
CHART_DIR = os.path.join(BASE_DIR, "charts")
DB_PATH = os.path.join(BASE_DIR, "predictions.db")
NEWS_DB_PATH = os.path.join(BASE_DIR, "news.db")
KNOWLEDGE_DB_PATH = os.path.join(BASE_DIR, "knowledge.db")
MORNING_REPORT_DIR = os.path.join(BASE_DIR, "morning_reports")
DASHBOARD_DIR = os.path.join(SCRIPT_DIR, "dashboard")

WATCHLIST = [
    {"symbol": "RELIANCE", "name": "Reliance Industries", "sector": "Energy"},
    {"symbol": "HDFCBANK", "name": "HDFC Bank", "sector": "Banking"},
    {"symbol": "INFY", "name": "Infosys", "sector": "IT"},
    {"symbol": "TCS", "name": "Tata Consultancy", "sector": "IT"},
    {"symbol": "SBIN", "name": "State Bank of India", "sector": "Banking"},
    {"symbol": "ICICIBANK", "name": "ICICI Bank", "sector": "Banking"},
    {"symbol": "BAJFINANCE", "name": "Bajaj Finance", "sector": "NBFC"},
    {"symbol": "BHARTIARTL", "name": "Bharti Airtel", "sector": "Telecom"},
    {"symbol": "AXISBANK", "name": "Axis Bank", "sector": "Banking"},
    {"symbol": "ITC", "name": "ITC Limited", "sector": "FMCG"},
    {"symbol": "LT", "name": "Larsen & Toubro", "sector": "Infra"},
    {"symbol": "TATASTEEL", "name": "Tata Steel", "sector": "Metals"},
    {"symbol": "SUNPHARMA", "name": "Sun Pharma", "sector": "Pharma"},
    {"symbol": "HINDALCO", "name": "Hindalco", "sector": "Metals"},
    {"symbol": "MARUTI", "name": "Maruti Suzuki", "sector": "Auto"},
    {"symbol": "TATAPOWER", "name": "Tata Power", "sector": "Energy"},
    {"symbol": "NIFTY", "name": "NIFTY 50 Index", "sector": "Index"},
    {"symbol": "SENSEX", "name": "SENSEX Index", "sector": "Index"},
]

DATA_YEARS = 5
TRAIN_RATIO = 0.80
MODEL_CACHE_HOURS = 24
API_PORT = 5000
MODEL_VERSION = "3.0"
# 0.3% next-day moves are mostly noise after costs. 0.6% is a real session move
# on NIFTY/large caps without starving the classifier of positive labels.
TARGET_MIN_RETURN = float(os.environ.get("TARGET_MIN_RETURN", "0.006"))
WF_SPLITS = 5
HIGH_CONF_PROBA = 0.62
# Minimum |log odds ratio vs base rate| for a forecast to count as high confidence.
# 1.0 means the model puts ~2.7x the baseline odds on its side of the trade.
HIGH_CONF_LIFT = float(os.environ.get("HIGH_CONF_LIFT", "1.0"))
# Weaker than HIGH, but still refuses lukewarm BUY/SELL that lost money as MEDIUM.
DIRECTION_MIN_LIFT = float(os.environ.get("DIRECTION_MIN_LIFT", "0.5"))
# Dual-head: the winning side must beat the other by this after centering.
SIDE_GAP = float(os.environ.get("SIDE_GAP", "0.05"))
MIN_AGREEMENT_GAP = 12

INDIAN_STOCKS = { "RELIANCE": "RELIANCE.NS", "HDFCBANK": "HDFCBANK.NS" , "ICICIBANK": "ICICIBANK.NS", "INFY": "INFY.NS" , "TCS": "TCS.NS", "SBIN": "SBIN.NS" , "BAJFINANCE": "BAJFINANCE.NS", "BHARTIARTL": "BHARTIARTL.NS" , "AXISBANK": "AXISBANK.NS", "ITC": "ITC.NS" , "LT": "LT.NS", "TATASTEEL": "TATASTEEL.NS" , "SUNPHARMA": "SUNPHARMA.NS", "HINDALCO": "HINDALCO.NS" , "MARUTI": "MARUTI.NS", "WIPRO": "WIPRO.NS" , "HCLTECH": "HCLTECH.NS", "TATAMOTORS": "TATAMOTORS.NS" , "ADANIENT": "ADANIENT.NS", "KOTAKBANK": "KOTAKBANK.NS" , "M&M": "M&M.NS", "TATAPOWER": "TATAPOWER.NS", "NTPC": "NTPC.NS", "NIFTY": "^NSEI" , "BANKNIFTY": "^NSEBANK", "SENSEX": "^BSESN" , }

CRYPTO_MAP = { "BTC": "BTC-USD", "ETH": "ETH-USD", "SOL": "SOL-USD" , "BTCUSD": "BTC-USD", "ETHUSD": "ETH-USD" , }

# ================================================================
# SECTION 4: TECHNICAL INDICATORS (pure numpy/pandas)
# ================================================================

def sma(series, period):
    return series.rolling(window=period, min_periods=period).mean()


def ema(series, period):
    return series.ewm(span=period, adjust=False).mean()


def rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100.0 - (100.0 / (1.0 + rs))


def macd(series, fast=12, slow=26, signal_period=9):
    ema_fast = ema(series, fast)
    ema_slow = ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = ema(macd_line, signal_period)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def bollinger_bands(series, period=20, num_std=2):
    mid = sma(series, period)
    std = series.rolling(window=period, min_periods=period).std()
    upper = mid + num_std * std
    lower = mid - num_std * std
    pct_b = (series - lower) / (upper - lower).replace(0, np.nan)
    bandwidth = ((upper - lower) / mid.replace(0, np.nan)) * 100
    return upper, mid, lower, pct_b, bandwidth


def atr(high, low, close, period=14):
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(window=period, min_periods=period).mean()


def stochastic(high, low, close, k_period=14, d_period=3):
    lowest = low.rolling(window=k_period, min_periods=k_period).min()
    highest = high.rolling(window=k_period, min_periods=k_period).max()
    denom = (highest - lowest).replace(0, np.nan)
    k_val = 100.0 * (close - lowest) / denom
    d_val = k_val.rolling(window=d_period, min_periods=d_period).mean()
    return k_val, d_val


def williams_r(high, low, close, period=14):
    highest = high.rolling(window=period, min_periods=period).max()
    lowest = low.rolling(window=period, min_periods=period).min()
    denom = (highest - lowest).replace(0, np.nan)
    return -100.0 * (highest - close) / denom


def cci(high, low, close, period=20):
    tp = (high + low + close) / 3.0
    sma_tp = tp.rolling(window=period, min_periods=period).mean()
    mad = tp.rolling(window=period, min_periods=period).apply( lambda x: np.mean(np.abs(x - np.mean(x))), raw=True
    )
    return (tp - sma_tp) / (0.015 * mad).replace(0, np.nan)


def adx(high, low, close, period=14):
    plus_dm = high.diff().clip(lower=0)
    minus_dm = (-low.diff()).clip(lower=0)

    cond = plus_dm > minus_dm
    plus_dm = plus_dm.where(cond, 0.0)
    minus_dm = minus_dm.where(~cond, 0.0)

    atr_val = atr(high, low, close, period).replace(0, np.nan)
    plus_di = 100.0 * ema(plus_dm, period) / atr_val
    minus_di = 100.0 * ema(minus_dm, period) / atr_val

    di_sum = (plus_di + minus_di).replace(0, np.nan)
    dx = 100.0 * (plus_di - minus_di).abs() / di_sum
    adx_val = ema(dx, period)
    return adx_val, plus_di, minus_di


def obv(close, volume):
    if close is None or len(close) == 0:
        idx = close.index if hasattr(close, "index") else pd.RangeIndex(0)
        return pd.Series(0.0, index=idx, dtype=float)
    direction = np.sign(close.diff()).copy()
    if len(direction) > 0:
        direction.iat[0] = 0.0
    return (volume * direction).cumsum()


def mfi(high, low, close, volume, period=14):
    tp = (high + low + close) / 3.0
    mf = tp * volume
    pos_mf = mf.where(tp > tp.shift(1), 0.0)
    neg_mf = mf.where(tp <= tp.shift(1), 0.0)
    pos_sum = pos_mf.rolling(window=period, min_periods=period).sum()
    neg_sum = neg_mf.rolling(window=period, min_periods=period).sum().replace(0, np.nan)
    mfr = pos_sum / neg_sum
    return 100.0 - (100.0 / (1.0 + mfr))


def roc(series, period=12):
    shifted = series.shift(period).replace(0, np.nan)
    return ((series - shifted) / shifted) * 100.0


# ================================================================
# SECTION 5: FEATURE ENGINEERING
# ================================================================

def supertrend(high, low, close, period=10, multiplier=3.0):
    """ATR trailing band. Direction is +1 above the band and -1 below it."""
    mid = atr(high, low, close, period)
    hl2 = (high + low) / 2.0
    upper = hl2 + multiplier * mid
    lower = hl2 - multiplier * mid
    direction = pd.Series(1.0, index=close.index)
    line = pd.Series(np.nan, index=close.index)
    prev_lower = lower.iloc[0]
    prev_upper = upper.iloc[0]
    prev_dir = 1.0
    for i in range(len(close)):
        lo = lower.iloc[i]
        up = upper.iloc[i]
        if i and close.iloc[i - 1] > prev_lower:
            lo = max(lo, prev_lower)
        if i and close.iloc[i - 1] < prev_upper:
            up = min(up, prev_upper)
        if close.iloc[i] > prev_upper:
            prev_dir = 1.0
        elif close.iloc[i] < prev_lower:
            prev_dir = -1.0
        direction.iloc[i] = prev_dir
        line.iloc[i] = lo if prev_dir > 0 else up
        prev_lower, prev_upper = lo, up
    return line, direction


def ichimoku(high, low, close):
    """Distance of price from the cloud midpoint, in percent. Positive is above the cloud."""
    conv = (high.rolling(9, min_periods=9).max() + low.rolling(9, min_periods=9).min()) / 2.0
    base = (high.rolling(26, min_periods=26).max() + low.rolling(26, min_periods=26).min()) / 2.0
    span_a = ((conv + base) / 2.0).shift(26)
    span_b = ((high.rolling(52, min_periods=52).max() + low.rolling(52, min_periods=52).min()) / 2.0).shift(26)
    mid = (span_a + span_b) / 2.0
    return (close - mid) / close.replace(0, np.nan) * 100.0


def parabolic_sar_dir(high, low, close, step=0.02, max_step=0.2):
    """+1 while the stop-and-reverse sits under price, -1 when it sits above."""
    n = len(close)
    direction = pd.Series(1.0, index=close.index)
    if n < 3:
        return direction
    bull = True
    af = step
    ep = float(high.iloc[0])
    sar = float(low.iloc[0])
    for i in range(1, n):
        sar = sar + af * (ep - sar)
        if bull:
            sar = min(sar, float(low.iloc[i - 1]), float(low.iloc[max(0, i - 2)]))
            if float(low.iloc[i]) < sar:
                bull = False
                sar = ep
                ep = float(low.iloc[i])
                af = step
            elif float(high.iloc[i]) > ep:
                ep = float(high.iloc[i])
                af = min(max_step, af + step)
        else:
            sar = max(sar, float(high.iloc[i - 1]), float(high.iloc[max(0, i - 2)]))
            if float(high.iloc[i]) > sar:
                bull = True
                sar = ep
                ep = float(high.iloc[i])
                af = step
            elif float(low.iloc[i]) < ep:
                ep = float(low.iloc[i])
                af = min(max_step, af + step)
        direction.iloc[i] = 1.0 if bull else -1.0
    return direction


def compute_all_features(df):
    """Compute 30+ technical indicator features from OHLCV data. """
    if df is None or len(df) < 2:
        raise ValueError("Need at least 2 OHLCV rows for indicators")
    c, h, l, v = df["Close"], df["High"], df["Low"], df["Volume"]
    o = df["Open"]

    feat = pd.DataFrame(index=df.index)

    # --- Trend indicators ---
    feat["ema_9"] = ema(c, 9)
    feat["ema_21"] = ema(c, 21)
    feat["sma_50"] = sma(c, 50)
    feat["sma_200"] = sma(c, 200)

    macd_line, macd_sig, macd_hist = macd(c)
    feat["macd_line"] = macd_line
    feat["macd_signal"] = macd_sig
    feat["macd_hist"] = macd_hist

    adx_val, plus_di, minus_di = adx(h, l, c)
    feat["adx"] = adx_val
    feat["plus_di"] = plus_di
    feat["minus_di"] = minus_di

    # --- Momentum indicators ---
    feat["rsi_14"] = rsi(c, 14)

    stoch_k, stoch_d = stochastic(h, l, c)
    feat["stoch_k"] = stoch_k
    feat["stoch_d"] = stoch_d

    feat["williams_r"] = williams_r(h, l, c)
    feat["cci_20"] = cci(h, l, c, 20)
    feat["roc_12"] = roc(c, 12)
    feat["mfi_14"] = mfi(h, l, c, v, 14)

    # --- Volatility indicators ---
    bb_upper, bb_mid, bb_lower, bb_pctb, bb_bw = bollinger_bands(c)
    feat["bb_pctb"] = bb_pctb
    feat["bb_bandwidth"] = bb_bw
    feat["atr_14"] = atr(h, l, c, 14)
    st_line, st_dir = supertrend(h, l, c, period=10, multiplier=3.0)
    feat["supertrend"] = st_line
    feat["supertrend_dir"] = st_dir
    ichi = ichimoku(h, l, c)
    feat["ichimoku_dist"] = ichi
    feat["psar_dir"] = parabolic_sar_dir(h, l, c)

    # Historical volatility (20-day)
    log_ret = np.log(c / c.shift(1))
    feat["hist_volatility"] = log_ret.rolling(window=20, min_periods=20).std() * np.sqrt(252)

    # --- Volume indicators ---
    feat["obv_norm"] = obv(c, v)
    obv_series = feat["obv_norm"]
    obv_sma = sma(obv_series, 20)
    feat["obv_norm"] = (obv_series - obv_sma) / obv_sma.abs().replace(0, np.nan)

    vol_sma = sma(v.astype(float), 20)
    feat["vol_ratio"] = v / vol_sma.replace(0, np.nan)

    # --- Price-based features ---
    feat["return_1d"] = c.pct_change(1) * 100
    feat["return_5d"] = c.pct_change(5) * 100
    feat["return_10d"] = c.pct_change(10) * 100
    feat["return_20d"] = c.pct_change(20) * 100

    feat["price_vs_sma50"] = ((c - feat["sma_50"]) / feat["sma_50"].replace(0, np.nan)) * 100
    feat["price_vs_sma200"] = ((c - feat["sma_200"]) / feat["sma_200"].replace(0, np.nan)) * 100

    # Distance from 52-week high/low
    high_52w = h.rolling(window=252, min_periods=100).max()
    low_52w = l.rolling(window=252, min_periods=100).min()
    range_52w = (high_52w - low_52w).replace(0, np.nan)
    feat["dist_52w_high"] = ((c - high_52w) / range_52w) * 100
    feat["dist_52w_low"] = ((c - low_52w) / range_52w) * 100

    # --- Candle features ---
    body = (c - o).abs()
    full_range = (h - l).replace(0, np.nan)
    feat["candle_body_ratio"] = body / full_range
    feat["upper_wick_ratio"] = (h - pd.concat([c, o], axis=1).max(axis=1)) / full_range
    feat["lower_wick_ratio"] = (pd.concat([c, o], axis=1).min(axis=1) - l) / full_range

    # --- Time features (cyclical encoding) ---
    if hasattr(df.index, "dayofweek"):
        dow = df.index.dayofweek
    else:
        dow = pd.to_datetime(df.index).dayofweek
    feat["day_sin"] = np.sin(2 * np.pi * dow / 5)
    feat["day_cos"] = np.cos(2 * np.pi * dow / 5)

    # --- Extended analysis (v2) ---
    feat["ema_50"] = ema(c, 50)
    feat["sma_20"] = sma(c, 20)
    feat["rsi_7"] = rsi(c, 7)
    feat["rsi_21"] = rsi(c, 21)
    feat["atr_pct"] = feat["atr_14"] / c.replace(0, np.nan) * 100
    feat["ema_cross"] = (feat["ema_9"] > feat["ema_21"]).astype(int)
    feat["trend_strength"] = feat["adx"] * np.sign(feat["plus_di"] - feat["minus_di"])
    feat["gap_pct"] = (o - c.shift(1)) / c.shift(1).replace(0, np.nan) * 100
    feat["hl_range_pct"] = (h - l) / c.replace(0, np.nan) * 100
    feat["momentum_3d"] = c.pct_change(3) * 100
    feat["vol_change"] = v.pct_change(5)
    feat["consec_up"] = (c.diff() > 0).astype(int).groupby((c.diff() <= 0).cumsum()).cumsum()
    pivot = (h + l + c) / 3
    feat["pivot_dist"] = (c - pivot) / pivot.replace(0, np.nan) * 100
    feat["bb_squeeze"] = (feat["bb_bandwidth"] < feat["bb_bandwidth"].rolling(20).mean()).astype(int)
    feat["macd_cross"] = (macd_line > macd_sig).astype(int)
    feat["di_spread"] = plus_di - minus_di
    feat["price_vs_ema9"] = ((c - feat["ema_9"]) / feat["ema_9"].replace(0, np.nan)) * 100
    feat["price_vs_sma20"] = ((c - feat["sma_20"]) / feat["sma_20"].replace(0, np.nan)) * 100

    # Replace inf with NaN
    feat = feat.replace([np.inf, -np.inf], np.nan)

    # Store raw indicator values for technical scoring (use last bar; fill key fields)
    raw_indicators = {}
    if len(feat) > 0:
        last_row = feat.iloc[-1]
        raw_indicators = {k: (None if pd.isna(v) else float(v)) for k, v in last_row.items()}
        for key in ("rsi_14", "macd_hist", "cci_20", "roc_12", "adx", "stoch_k", "stoch_d", "vol_ratio", "price_vs_sma50", "price_vs_sma200", "williams_r", "mfi_14", "bb_pctb", "ema_cross", "macd_cross"):
            if key in feat.columns:
                val = feat[key].iloc[-1]
                if pd.notna(val):
                    raw_indicators[key] = float(val)
        raw_indicators["close"] = float(c.iloc[-1])
        raw_indicators["atr_raw"] = float(atr(h, l, c, 14).iloc[-1]) if not pd.isna(atr(h, l, c, 14).iloc[-1]) else 0
        hist_vals = macd_hist.dropna()
        if len(hist_vals) >= 2:
            raw_indicators["prev_macd_hist"] = float(hist_vals.iloc[-2])

    feat = regime_features.attach_regime_features(feat)
    return feat, raw_indicators


def build_training_data(df, features_df):
    """Create X and two mutually exclusive targets.

    y_up   = next close is more than TARGET_MIN_RETURN higher
    y_down = next close is more than TARGET_MIN_RETURN lower

    A single "not a big-up day" label is not a sell signal: it mixes flats,
    tiny ups, and genuine downs. SELL must come from y_down.

    Default (20+ bars): next-bar 2×ATR target / 1×ATR stop. Set LABEL_MODE=return
    for next-close vs TARGET_MIN_RETURN.
    """
    mode = str(os.environ.get("LABEL_MODE") or "barrier").strip().lower()
    if mode == "return" or len(df) < 20:
        thr = float(os.environ.get("TARGET_MIN_RETURN", str(TARGET_MIN_RETURN)))
        fwd_return = df["Close"].shift(-1) / df["Close"] - 1
        y_up = (fwd_return > thr).astype(int)
        y_down = (fwd_return < -thr).astype(int)
    else:
        import triple_barrier

        atr_s = atr(df["High"], df["Low"], df["Close"], 14)
        y_up, y_down = triple_barrier.daily_next_bar_labels(df, atr_s)

    combined = features_df.copy()
    combined["target_up"] = y_up
    combined["target_down"] = y_down

    feature_cols = [c for c in features_df.columns]
    combined = combined.dropna(subset=feature_cols + ["target_up", "target_down"])

    X = combined[feature_cols]
    y = combined["target_up"].astype(int)
    y_dn = combined["target_down"].astype(int)
    return X, y, feature_cols, y_dn


def unpack_training_data(pack):
    """Accept 3-tuple legacy returns or the 4-tuple (X, y_up, cols, y_down)."""
    if pack is None:
        return None, None, None, None
    if len(pack) >= 4:
        return pack[0], pack[1], pack[2], pack[3]
    return pack[0], pack[1], pack[2], None


def model_predict_sides(model, X_s):
    """Return (p_up, p_down). p_down is None for leftover single-head pickles."""
    if isinstance(model, dict):
        p_up = float(np.asarray(model["up"].predict_proba(X_s))[0, 1])
        down = model.get("down")
        p_down = float(np.asarray(down.predict_proba(X_s))[0, 1]) if down is not None else None
        return p_up, p_down
    return float(np.asarray(model.predict_proba(X_s))[0, 1]), None


def model_predict_up_batch(model, X_s):
    head = model["up"] if isinstance(model, dict) else model
    return np.asarray(head.predict_proba(X_s))[:, 1]


# ================================================================
# SECTION 6: DATA MANAGER
# ================================================================


def finite_float(value: Any, default: float = 0.0) -> float:
    """Coerce to float; NaN/Inf/`or 0` traps → default (NaN is truthy in Python!)."""
    try:
        if value is None:
            return float(default)
        v = float(value)
        return v if math.isfinite(v) else float(default)
    except (TypeError, ValueError):
        return float(default)


def sanitize_for_json(obj):
    """Convert numpy/pandas values and strip NaN/Inf so browser JSON.parse works.

    Candle frames stay on the server for the alert check. They are not part of
    the UI payload. NIFTY and BANKNIFTY share this path.
    """
    if obj is None:
        return None
    if isinstance(obj, dict):
        return {str(k): sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [sanitize_for_json(v) for v in obj]
    if isinstance(obj, (pd.DataFrame, pd.Series)):
        return None
    if isinstance(obj, np.ndarray):
        return sanitize_for_json(obj.tolist())
    if isinstance(obj, np.generic):
        if isinstance(obj, np.bool_):
            return bool(obj)
        if isinstance(obj, np.floating):
            v = float(obj)
            return v if math.isfinite(v) else None
        if isinstance(obj, np.integer):
            return int(obj)
        try:
            return sanitize_for_json(obj.item())
        except Exception:
            return None
    if isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, int) and not isinstance(obj, bool):
        return int(obj)
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    # Catch numpy scalars / Decimal-like that slipped past isinstance(float)
    try:
        if hasattr(obj, "item") and not isinstance(obj, (str, bytes, dict, list, tuple)):
            return sanitize_for_json(obj.item())
    except Exception:
        pass
    try:
        # pandas NA / NaT
        if pd.isna(obj):
            return None
    except Exception:
        pass
    return obj


def api_json(payload: Any, status: int = 200):
    """Prod-safe JSON responses (numpy/pandas scalars + NaN→null)."""
    return jsonify(sanitize_for_json(payload)), status


def resolve_symbol(stock_input):
    """Resolve user input to a Yahoo Finance ticker symbol. """
    s = stock_input.strip().upper()

    if s in INDIAN_STOCKS:
        return INDIAN_STOCKS[s]
    if s in CRYPTO_MAP:
        return CRYPTO_MAP[s]
    try:
        import user_watchlists

        if user_watchlists.contains(BASE_DIR, s):
            return f"{s}.NS"
    except Exception:
        pass

    # Already has suffix
    if "." in s or s.startswith("^") or "-" in s:
        return s

    # Try as-is (US stock like AAPL, MSFT)
    return s


def _apply_index_volume_rules(df, stock_key=None, symbol=None):
    """Index daily bars from Kite often have volume 0; keep rows and allow volume features."""
    if df is None or len(df) == 0:
        return df
    idx_key = (stock_key or "").strip().upper()
    sym = symbol or ""
    if idx_key not in market_symbols.INDEX_SYMBOLS and not str(sym).startswith("^"):
        return df
    out = df.copy()
    if "Volume" not in out.columns:
        out["Volume"] = 1.0
        return out
    out["Volume"] = out["Volume"].fillna(0)
    if (out["Volume"] <= 0).all():
        out["Volume"] = 1.0
    return out


def _read_ohlcv_cache(cache_file: str) -> pd.DataFrame:
    df = pd.read_csv(cache_file, index_col=0, parse_dates=True)
    if df is None or len(df) < 10:
        raise ValueError("cache too short")
    return df


def download_data(symbol, years=DATA_YEARS, force=False, stock_key=None):
    """Download OHLCV with cache. Indian watchlist uses Kite history when configured."""
    cache_file = os.path.join(CACHE_DIR, f"{symbol.replace('^', 'IDX_').replace('.', '_')}.csv")

    if not force and os.path.exists(cache_file):
        age_hours = (time.time() - os.path.getmtime(cache_file)) / 3600
        if age_hours < 6:
            try:
                df = _read_ohlcv_cache(cache_file)
                df = _apply_index_volume_rules(df, stock_key=stock_key, symbol=symbol)
                if len(df) > 100:
                    df.attrs["historical_source"] = "cache"
                    return df
            except (OSError, ValueError, pd.errors.EmptyDataError) as exc:
                print(f"  Cache corrupt for {symbol} ({exc}), re-downloading... ", end=" ", flush=True)
                try:
                    os.remove(cache_file)
                except OSError:
                    pass
        elif age_hours >= 6:
            try:
                df = _read_ohlcv_cache(cache_file)
                df = _apply_index_volume_rules(df, stock_key=stock_key, symbol=symbol)
                if len(df) > 100:
                    df.attrs["historical_source"] = "cache_stale"
                    return df
            except (OSError, ValueError, pd.errors.EmptyDataError):
                try:
                    os.remove(cache_file)
                except OSError:
                    pass

    df = None
    hist_source = "yahoo_finance"

    key = (stock_key or "").strip().upper()
    if key and kite_data.kite_enabled() and kite_data.is_kite_eligible(key, INDIAN_STOCKS):
        print(f"  Kite historical {years}y for {key}... ", end=" ", flush=True)
        kdf, kerr = kite_data.fetch_daily_ohlcv(key, years=years)
        if kdf is not None and len(kdf) >= 50:
            df = kdf
            hist_source = "kite_connect"
            print(f"{len(df)} rows (Kite)")
        elif kerr:
            print(f"Kite failed ({kerr[:60]})")
            allow_yahoo = os.environ.get("KITE_YAHOO_FALLBACK", "").strip().lower() in (
                "1",
                "true",
                "yes",
            )
            if not allow_yahoo:
                raise RuntimeError(
                    f"Kite historical failed for {key}: {kerr}. "
                    "Fix Kite token/plan or set KITE_YAHOO_FALLBACK=1 for Yahoo backup."
                )

    if df is None:
        print(f"  Downloading {years} years of data for {symbol}... ", end=" ", flush=True)
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=f"{years}y", auto_adjust=False)
            if df is None or len(df) < 50:
                end = datetime.now()
                start = end - timedelta(days=int(years * 365.25))
                df = ticker.history(
                    start=start.strftime("%Y-%m-%d"),
                    end=end.strftime("%Y-%m-%d"),
                    auto_adjust=False,
                )
        except Exception as e:
            raise RuntimeError(f"Failed to download data for {symbol}: {e}")
        print(f"{len(df)} rows (Yahoo)")

    if df is None or len(df) < 50:
        raise RuntimeError(
            f"Insufficient data for {symbol} ({len(df) if df is not None else 0} rows). "
            f"Check if the symbol is valid on Yahoo Finance. "
        )

    for col in ["Open", "High", "Low", "Close", "Volume"]:
        if col not in df.columns:
            raise RuntimeError(f"Missing column '{col}' in data for {symbol}")

    df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
    df = _apply_index_volume_rules(df, stock_key=stock_key, symbol=symbol)
    idx_key = (stock_key or "").strip().upper()
    if idx_key not in market_symbols.INDEX_SYMBOLS and not symbol.startswith("^"):
        df = df[df["Volume"] > 0]
    df.attrs["historical_source"] = hist_source

    df.to_csv(cache_file)
    return df


def _symbol_cache_path(symbol):
    safe = symbol.replace("^", "IDX_").replace(".", "_")
    return os.path.join(CACHE_DIR, f"{safe}.csv")


def _cache_row_stats(symbol, stock_key=None):
    """Read one cache file and return metadata (no full load for API)."""
    path = _symbol_cache_path(symbol)
    if not os.path.exists(path):
        return {
            "stock": (stock_key or symbol).upper(),
            "yahoo_symbol": symbol,
            "cached": False,
            "rows": 0,
        }
    try:
        df = pd.read_csv(path, index_col=0, parse_dates=True)
        if len(df) == 0:
            return {"stock": (stock_key or symbol).upper(), "yahoo_symbol": symbol, "cached": True, "rows": 0}
        start = df.index.min()
        end = df.index.max()
        start_d = start.date() if hasattr(start, "date") else str(start)[:10]
        end_d = end.date() if hasattr(end, "date") else str(end)[:10]
        span_years = (end - start).days / 365.25 if hasattr(end - start, "days") else None
        mtime = datetime.fromtimestamp(os.path.getmtime(path))
        return {
            "stock": (stock_key or symbol).upper(),
            "yahoo_symbol": symbol,
            "cached": True,
            "rows": int(len(df)),
            "start_date": str(start_d),
            "end_date": str(end_d),
            "span_years": round(span_years, 2) if span_years else None,
            "cache_file": os.path.basename(path),
            "cache_updated": mtime.isoformat(),
            "configured_years": DATA_YEARS,
        }
    except Exception as exc:
        return {
            "stock": (stock_key or symbol).upper(),
            "yahoo_symbol": symbol,
            "cached": True,
            "error": str(exc),
        }


def get_training_stats():
    """Summary of cached Yahoo OHLCV used as ML knowledge source."""
    symbols_detail = []
    for item in WATCHLIST:
        key = item["symbol"]
        yahoo = resolve_symbol(key)
        symbols_detail.append(_cache_row_stats(yahoo, stock_key=key))

    cached = [s for s in symbols_detail if s.get("cached") and s.get("rows", 0) > 0]
    rows_list = [s["rows"] for s in cached if s.get("rows")]
    spans = [s["span_years"] for s in cached if s.get("span_years")]

    return {
        "data_source": "yahoo_finance_daily_ohlcv",
        "configured_history_years": DATA_YEARS,
        "watchlist_count": len(WATCHLIST),
        "cached_symbols_count": len(cached),
        "missing_from_cache": [
            s["stock"] for s in symbols_detail if not s.get("rows")
        ],
        "total_daily_bars_cached": int(sum(rows_list)) if rows_list else 0,
        "avg_rows_per_symbol": int(sum(rows_list) / len(rows_list)) if rows_list else 0,
        "min_span_years": min(spans) if spans else None,
        "max_span_years": max(spans) if spans else None,
        "symbols": symbols_detail,
        "note": (
            "ML trains per symbol from this daily cache on each /predict. "
            f"Target window is {DATA_YEARS} years; actual span depends on Yahoo history returned."
        ),
    }


def prefetch_watchlist(force=False, years=DATA_YEARS):
    """Download Yahoo OHLCV for every watchlist symbol (ML knowledge base)."""
    results = []
    ok = 0
    for item in WATCHLIST:
        key = item["symbol"]
        yahoo = resolve_symbol(key)
        print(f"\n  Prefetch {key} ({yahoo})...")
        try:
            if force and os.path.exists(_symbol_cache_path(yahoo)):
                os.remove(_symbol_cache_path(yahoo))
            download_data(yahoo, years=years, force=force, stock_key=key)
            stats = _cache_row_stats(yahoo, stock_key=key)
            results.append({**stats, "status": "ok"})
            ok += 1
        except Exception as exc:
            results.append({
                "stock": key,
                "yahoo_symbol": yahoo,
                "status": "error",
                "error": str(exc),
            })
    summary = get_training_stats()
    summary["prefetch"] = {
        "attempted": len(WATCHLIST),
        "succeeded": ok,
        "failed": len(WATCHLIST) - ok,
        "force_refresh": force,
        "results": results,
    }
    return summary


def prefetch_all_data(force=False, years=DATA_YEARS, news_quick=False) -> Dict[str, Any]:
    """OHLCV + news for full watchlist (max free history for training/audit)."""
    out: Dict[str, Any] = {"ohlcv": None, "news": None}
    out["ohlcv"] = prefetch_watchlist(force=force, years=years)
    print("\n  Prefetch news for watchlist...")
    out["news"] = news_data.prefetch_watchlist_news(
        NEWS_DB_PATH,
        WATCHLIST,
        years=years,
        max_months_per_symbol=3 if news_quick else None,
    )
    analysis_store.ensure_analysis_tables(KNOWLEDGE_DB_PATH)
    return out


def run_audit_watchlist(
    holdout_start: str = "2024-01-01",
    *,
    retrain_every: int = 42,
    step_days: int = 1,
    symbols: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Historical day-by-day audit for all watchlist symbols (stored in knowledge.db)."""
    analysis_store.ensure_analysis_tables(KNOWLEDGE_DB_PATH)
    return historical_audit.run_watchlist_audit(
        WATCHLIST,
        db_path=KNOWLEDGE_DB_PATH,
        news_db_path=NEWS_DB_PATH,
        model_dir=MODEL_DIR,
        holdout_start=holdout_start,
        target_min_return=TARGET_MIN_RETURN,
        download_fn=lambda sym, stock_key=None: download_data(sym, stock_key=stock_key),
        resolve_fn=resolve_symbol,
        compute_features_fn=compute_all_features,
        build_training_data_fn=build_training_data,
        train_models_fn=train_models,
        generate_decision_fn=generate_decision,
        compute_technical_score_fn=compute_technical_score,
        retrain_every=retrain_every,
        step_days=step_days,
        symbols_filter=symbols,
    )


# ================================================================
# SECTION 7: ML ENGINE
# ================================================================

def walk_forward_metrics(model, X, y, n_splits=WF_SPLITS):
    """Time-series walk-forward validation with high-confidence accuracy."""
    tscv = TimeSeriesSplit(n_splits=n_splits)
    fold_acc, hc_acc, hc_total = [], [], 0

    for train_idx, test_idx in tscv.split(X):
        X_tr, X_te = X.iloc[train_idx], X.iloc[test_idx]
        y_tr, y_te = y.iloc[train_idx], y.iloc[test_idx]
        if len(np.unique(y_tr)) < 2:
            continue

        scaler = StandardScaler()
        X_tr_s = scaler.fit_transform(X_tr)
        X_te_s = scaler.transform(X_te)
        fold_model = clone(model)
        fold_model.fit(X_tr_s, y_tr)

        proba = fold_model.predict_proba(X_te_s)[:, 1]
        pred = (proba >= 0.5).astype(int)
        fold_acc.append(accuracy_score(y_te, pred))

        hc_mask = (proba >= HIGH_CONF_PROBA) | (proba <= (1 - HIGH_CONF_PROBA))
        if hc_mask.sum() > 0:
            hc_pred = (proba[hc_mask] >= 0.5).astype(int)
            hc_acc.append(accuracy_score(y_te.values[hc_mask], hc_pred))
            hc_total += int(hc_mask.sum())

    return {
        "walk_forward_accuracy": float(np.mean(fold_acc)) if fold_acc else 0.0,
        "walk_forward_std": float(np.std(fold_acc)) if fold_acc else 0.0,
        "high_confidence_accuracy": float(np.mean(hc_acc)) if hc_acc else 0.0,
        "high_confidence_samples": hc_total,
        "fold_count": len(fold_acc),
    }


def select_features(X_train, y_train, feature_cols, top_k=45):
    """Pick top features by RandomForest importance."""
    selector = RandomForestClassifier(
        n_estimators=120, max_depth=7, min_samples_leaf=8,
        class_weight="balanced", random_state=42, n_jobs=-1,
    )
    selector.fit(X_train, y_train)
    importances = selector.feature_importances_
    k = min(top_k, len(feature_cols))
    top_idx = np.argsort(importances)[-k:]
    selected = [feature_cols[i] for i in top_idx]
    ranking = sorted(zip(feature_cols, importances), key=lambda x: x[1], reverse=True)
    return selected, ranking


def _estimator_specs():
    specs = [
        ("rf", RandomForestClassifier(
            n_estimators=250, max_depth=9, min_samples_split=8,
            min_samples_leaf=4, class_weight="balanced", random_state=42, n_jobs=-1,
        )),
        ("hgb", HistGradientBoostingClassifier(
            max_depth=7, learning_rate=0.04, max_iter=250,
            min_samples_leaf=8, random_state=42,
        )),
        ("gb", GradientBoostingClassifier(
            n_estimators=180, max_depth=5, learning_rate=0.04,
            min_samples_split=10, min_samples_leaf=5, subsample=0.85, random_state=42,
        )),
    ]
    if HAS_XGBOOST:
        specs.append(("xgb", XGBClassifier(
            n_estimators=180, max_depth=5, learning_rate=0.04,
            subsample=0.85, colsample_bytree=0.85,
            eval_metric="logloss", random_state=42, n_jobs=-1,
        )))
    return specs


def _fit_directional_head(X_train_s, y_train, X_test_s, y_test, X_sel, y_all, tag):
    """Calibrated voting ensemble for one side (up or down)."""
    print(f"  Training {tag} head (v3 — walk-forward + calibration):")
    results = {}
    wf_all = []
    fitted = []
    for name, base_model in _estimator_specs():
        if y_train.nunique() < 2:
            continue
        calibrated = CalibratedClassifierCV(base_model, cv=3, method="isotonic")
        calibrated.fit(X_train_s, y_train)
        y_pred = calibrated.predict(X_test_s)
        acc = accuracy_score(y_test, y_pred)
        f1 = f1_score(y_test, y_pred, zero_division=0)
        prec = precision_score(y_test, y_pred, zero_division=0)
        rec = recall_score(y_test, y_pred, zero_division=0)
        wf = walk_forward_metrics(base_model, X_sel, y_all)
        wf_all.append(wf)
        results[name] = {
            "model": calibrated, "accuracy": acc, "f1": f1,
            "precision": prec, "recall": rec, "walk_forward": wf,
        }
        fitted.append((name, calibrated))
        print(f"    {name:6s} Test: {acc:.1%}  F1: {f1:.3f}  WF: {wf['walk_forward_accuracy']:.1%}  HC: {wf['high_confidence_accuracy']:.1%}")

    if len(fitted) < 1:
        return None, {}, {}

    ensemble = VotingClassifier(estimators=fitted, voting="soft")
    ensemble.fit(X_train_s, y_train)
    y_pred_ens = ensemble.predict(X_test_s)
    proba_ens = ensemble.predict_proba(X_test_s)[:, 1]
    acc_ens = accuracy_score(y_test, y_pred_ens)
    f1_ens = f1_score(y_test, y_pred_ens, zero_division=0)
    hc_mask = (proba_ens >= HIGH_CONF_PROBA) | (proba_ens <= (1 - HIGH_CONF_PROBA))
    if hc_mask.sum() > 0:
        hc_acc_test = accuracy_score(
            y_test.values[hc_mask],
            (proba_ens[hc_mask] >= 0.5).astype(int),
        )
    else:
        hc_acc_test = 0.0
    wf_ensemble = {
        "walk_forward_accuracy": float(np.mean([w["walk_forward_accuracy"] for w in wf_all])) if wf_all else 0.0,
        "walk_forward_std": float(np.mean([w["walk_forward_std"] for w in wf_all])) if wf_all else 0.0,
        "high_confidence_accuracy": float(np.mean([w["high_confidence_accuracy"] for w in wf_all if w["high_confidence_accuracy"] > 0] or [0])),
        "high_confidence_samples": sum(w["high_confidence_samples"] for w in wf_all),
    }
    print(f"    {'ENS':6s} Test: {acc_ens:.1%}  F1: {f1_ens:.3f}  HC-test: {hc_acc_test:.1%}")
    metrics = {
        "individual": {
            n: {
                "accuracy": m["accuracy"], "f1": m["f1"],
                "precision": m["precision"], "recall": m["recall"],
                "walk_forward_accuracy": m["walk_forward"]["walk_forward_accuracy"],
                "high_confidence_accuracy": m["walk_forward"]["high_confidence_accuracy"],
            }
            for n, m in results.items()
        },
        "ensemble_accuracy": acc_ens,
        "ensemble_f1": f1_ens,
        "ensemble_precision": precision_score(y_test, y_pred_ens, zero_division=0),
        "ensemble_recall": recall_score(y_test, y_pred_ens, zero_division=0),
        "walk_forward_accuracy": wf_ensemble["walk_forward_accuracy"],
        "walk_forward_std": wf_ensemble["walk_forward_std"],
        "high_confidence_accuracy": max(hc_acc_test, wf_ensemble["high_confidence_accuracy"]),
        "high_confidence_test_accuracy": hc_acc_test,
        "high_confidence_samples": wf_ensemble["high_confidence_samples"],
    }
    return ensemble, metrics, wf_ensemble


def train_models(X, y, feature_cols, y_down=None):
    """Train calibrated up/down ensembles with walk-forward validation metrics."""
    split_idx = int(len(X) * TRAIN_RATIO)
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]

    scaler_full = StandardScaler()
    X_train_scaled = scaler_full.fit_transform(X_train)
    selected_cols, importances = select_features(X_train_scaled, y_train, feature_cols)

    X_train_sel = X_train[selected_cols]
    X_test_sel = X_test[selected_cols]
    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train_sel)
    X_test_s = scaler.transform(X_test_sel)
    X_sel = X[selected_cols]

    up_model, up_metrics, _ = _fit_directional_head(
        X_train_s, y_train, X_test_s, y_test, X_sel, y, "up"
    )
    if up_model is None:
        raise RuntimeError("Up-head training failed (single-class labels)")

    print("  Top 10 features:")
    for fname, imp in importances[:10]:
        print(f"    {fname:25s} {imp:.4f}")

    metrics = {
        "model_version": MODEL_VERSION,
        **up_metrics,
        "train_samples": len(X_train),
        "test_samples": len(X_test),
        "feature_count": len(selected_cols),
        "total_features": len(feature_cols),
        "selected_features": selected_cols,
        "feature_importance": importances[:15],
        "target_threshold_pct": TARGET_MIN_RETURN * 100,
        "base_rate": float(y_train.mean()),
        "heads": ["up"],
    }
    pack = {"up": up_model, "down": None}

    if y_down is not None:
        y_dn = y_down.reindex(y.index)
        y_d_train, y_d_test = y_dn.iloc[:split_idx], y_dn.iloc[split_idx:]
        if y_d_train.nunique() >= 2:
            down_model, down_metrics, _ = _fit_directional_head(
                X_train_s, y_d_train, X_test_s, y_d_test, X_sel, y_dn, "down"
            )
            if down_model is not None:
                pack["down"] = down_model
                metrics["heads"].append("down")
                metrics["base_rate_down"] = float(y_d_train.mean())
                metrics["ensemble_accuracy_down"] = down_metrics.get("ensemble_accuracy")
                metrics["walk_forward_accuracy_down"] = down_metrics.get("walk_forward_accuracy")
                metrics["individual_down"] = down_metrics.get("individual")

    return pack, scaler, metrics, selected_cols


_MODEL_MEM: Dict[str, Any] = {}
_MODEL_MEM_LOCK = threading.Lock()


def get_cached_model(symbol):
    """Load saved model if present and version matches (no expiry retrain on predict). """
    safe_name = symbol.replace("^", "IDX_").replace(".", "_")
    model_path = os.path.join(MODEL_DIR, f"{safe_name}_model.pkl")

    if os.path.exists(model_path):
        try:
            mtime = os.path.getmtime(model_path)
        except OSError:
            mtime = None
        with _MODEL_MEM_LOCK:
            hit = _MODEL_MEM.get(model_path)
        if hit and mtime is not None and hit[0] == mtime:
            data = hit[1]
        else:
            try:
                data = joblib.load(model_path)
            except (EOFError, OSError, ValueError) as exc:
                print(f"  Corrupt model cache {safe_name}, will retrain ({exc})")
                try:
                    os.remove(model_path)
                except OSError:
                    pass
                return None, None, None, None
        if data.get("model_version") != MODEL_VERSION:
            return None, None, None, None
        if mtime is not None:
            with _MODEL_MEM_LOCK:
                _MODEL_MEM[model_path] = (mtime, data)
        metrics = data.get("metrics") or {}
        if os.path.getmtime(model_path):
            age_h = (time.time() - os.path.getmtime(model_path)) / 3600
            metrics = {**metrics, "model_age_hours": round(age_h, 1), "model_stale_hint": age_h > MODEL_CACHE_HOURS}
        return data["model"], data["scaler"], metrics, data["selected_features"]
    return None, None, None, None


def _ohlcv_for_indicators(df, live_quote=None):
    """Exclude today's partial session bar from indicator/ML rows when live LTP patched in."""
    if df is None or len(df) < 30 or not live_quote:
        return df
    try:
        from zoneinfo import ZoneInfo
        today = datetime.now(ZoneInfo("Asia/Kolkata")).date()
    except Exception:
        today = datetime.now().date()
    last = df.index[-1]
    last_d = last.date() if hasattr(last, "date") else pd.Timestamp(last).date()
    if last_d >= today:
        trimmed = df.iloc[:-1]
        if len(trimmed) >= 30:
            return trimmed.copy()
    return df


def save_model(symbol, model, scaler, metrics, selected_features):
    """Cache trained model to disk. """
    safe_name = symbol.replace("^", "IDX_").replace(".", "_")
    model_path = os.path.join(MODEL_DIR, f"{safe_name}_model.pkl")
    joblib.dump({
        "model": model, "scaler": scaler, "metrics": metrics,
        "selected_features": selected_features, "model_version": MODEL_VERSION,
    }, model_path)


# ================================================================
# SECTION 8: SIGNAL GENERATOR
# ================================================================

def compute_technical_score(ind):
    """ Score 0-100 from current indicator readings. 0-30: Strongly bearish 30-45: Bearish 45-55: Neutral 55-70: Bullish 70-100: Strongly bullish """
    score = 50.0

    # RSI
    r = ind.get("rsi_14", 50)
    if r < 30:
        score += 10
    elif r < 40:
        score += 5
    elif r > 70:
        score -= 10
    elif r > 60:
        score -= 5

    # MACD histogram
    mh = ind.get("macd_hist", 0)
    if mh > 0:
        score += 7
        if mh > ind.get("prev_macd_hist", 0):
            score += 3
    elif mh < 0:
        score -= 7

    # Bollinger %B
    bb = ind.get("bb_pctb", 0.5)
    if bb < 0.2:
        score += 8
    elif bb < 0.35:
        score += 4
    elif bb > 0.8:
        score -= 8
    elif bb > 0.65:
        score -= 4

    try:
        st_dir = float(ind.get("supertrend_dir") or 0)
    except (TypeError, ValueError):
        st_dir = 0.0
    if st_dir > 0:
        score += 4
    elif st_dir < 0:
        score -= 4
    try:
        sar_dir = float(ind.get("psar_dir") or 0)
    except (TypeError, ValueError):
        sar_dir = 0.0
    if sar_dir > 0:
        score += 3
    elif sar_dir < 0:
        score -= 3
    try:
        cloud = float(ind["ichimoku_dist"]) if ind.get("ichimoku_dist") is not None else None
    except (TypeError, ValueError):
        cloud = None
    if cloud is not None and cloud == cloud:
        if cloud > 0.4:
            score += 3
        elif cloud < -0.4:
            score -= 3

    # Price vs moving averages
    close = ind.get("close", 0)
    if close > ind.get("ema_21", close):
        score += 5
    else:
        score -= 5

    if close > ind.get("sma_50", close):
        score += 5
    else:
        score -= 5

    if close > ind.get("sma_200", close):
        score += 7
    else:
        score -= 7

    # ADX (trend strength amplifier)
    a = ind.get("adx", 0)
    if a > 25:
        if score > 50:
            score += 4
        elif score < 50:
            score -= 4

    # Stochastic
    sk = ind.get("stoch_k", 50)
    if sk < 20:
        score += 6
    elif sk > 80:
        score -= 6

    # Volume ratio
    vr = ind.get("vol_ratio", 1.0)
    if vr > 1.5:
        if score > 50:
            score += 3
        else:
            score -= 3

    # MFI
    m = ind.get("mfi_14", 50)
    if m < 20:
        score += 5
    elif m > 80:
        score -= 5

    # Williams %R
    wr = ind.get("williams_r", -50)
    if wr < -80:
        score += 4
    elif wr > -20:
        score -= 4

    # CCI
    cc = ind.get("cci_20", 0)
    if cc < -100:
        score += 4
    elif cc > 100:
        score -= 4

    roc12 = ind.get("roc_12", 0)
    if roc12 > 5:
        score += 3
    elif roc12 < -5:
        score -= 3

    di = ind.get("di_spread", 0)
    if di > 5:
        score += 3
    elif di < -5:
        score -= 3

    if ind.get("ema_cross") == 1:
        score += 2
    elif ind.get("ema_cross") == 0 and ind.get("ema_cross") is not None:
        score -= 2

    if ind.get("macd_cross") == 1:
        score += 2

    if ind.get("bb_squeeze") == 1:
        score += 1

    stoch_d = ind.get("stoch_d", 50)
    if sk < 25 and stoch_d < 30:
        score += 2
    elif sk > 75 and stoch_d > 70:
        score -= 2

    return max(0.0, min(100.0, score))


def confidence_lift(ml_proba, base_rate):
    """Log odds ratio of the forecast against the base rate; 0 means no information.

    Confidence cannot be read off the centred scale: centring is a rank stretch, so with a
    0.32 base rate a lukewarm 0.45 maps to 0.70 and would clear any 0-1 confidence bar.
    The odds ratio is symmetric around the base rate and unbounded in both directions.
    """
    p = min(max(float(ml_proba), 1e-6), 1 - 1e-6)
    br = min(max(float(base_rate), 1e-6), 1 - 1e-6)
    return math.log((p / (1 - p)) / (br / (1 - br)))


def center_probability(ml_proba, base_rate):
    """Map a raw probability onto a 0-1 scale where `base_rate` becomes 0.5.

    The ML target is "next close is more than TARGET_MIN_RETURN higher", which is
    not a 50/50 event (index base rate is ~0.32). Comparing the raw probability
    against 0.5 therefore reads every honest forecast as bearish.
    """
    p = max(0.0, min(1.0, float(ml_proba)))
    br = float(base_rate)
    if not (0.05 <= br <= 0.95):
        return p
    if p <= br:
        return 0.5 * p / br
    return 0.5 + 0.5 * (p - br) / (1.0 - br)


def generate_decision(ml_proba, tech_score, current_price, atr_val, metrics, combined_adjust=0.0, ml_proba_down=None):
    """Combine ML + technical analysis with agreement-based confidence.

    When `ml_proba_down` is supplied, SELL is driven by the down-head (P of a
    meaningful drop), not by a weak up-head. A low P(big-up) is not a short.
    """
    base_rate = metrics.get("base_rate")
    if base_rate is None:
        base_rate = 0.5
    base_rate_down = metrics.get("base_rate_down")
    up_c = center_probability(ml_proba, base_rate)
    lift_up = confidence_lift(ml_proba, base_rate)

    dual = ml_proba_down is not None and base_rate_down is not None
    if dual:
        down_c = center_probability(ml_proba_down, base_rate_down)
        lift_down = confidence_lift(ml_proba_down, base_rate_down)
        ml_bull = up_c >= 0.55 and up_c > down_c + SIDE_GAP
        ml_bear = down_c >= 0.55 and down_c > up_c + SIDE_GAP
        if ml_bull:
            ml_centered = up_c
            lift = lift_up
        elif ml_bear:
            ml_centered = 1.0 - down_c
            lift = -lift_down
        else:
            ml_centered = 0.5 + 0.5 * (up_c - down_c)
            lift = lift_up - lift_down
    else:
        down_c = None
        ml_centered = up_c
        lift = lift_up
        ml_bull = ml_centered >= 0.55
        ml_bear = ml_centered <= 0.45

    ml_side = ml_centered * 100
    tech_side = tech_score
    agreement = 100 - abs(ml_side - tech_side)
    combined = 0.55 * ml_centered + 0.45 * (tech_score / 100.0) + combined_adjust
    combined = max(0.0, min(1.0, combined))

    wf_acc = metrics.get("walk_forward_accuracy", metrics.get("ensemble_accuracy", 0.55))
    hc_acc = metrics.get("high_confidence_accuracy", wf_acc)
    reliability = min(max(wf_acc, 0.5), 0.75)

    tech_bull = tech_score >= 55
    tech_bear = tech_score <= 45
    signals_agree = (ml_bull and tech_bull) or (ml_bear and tech_bear)
    high_conf_ml = abs(lift) >= HIGH_CONF_LIFT
    tradeable = abs(lift) >= DIRECTION_MIN_LIFT

    # Symmetric ladder centred on 0.5. HOLD is the default: a directional call
    # always needs ML and TA pointing the same way, in both directions.
    if combined > 0.65 and ml_centered > 0.5 and signals_agree and high_conf_ml:
        decision = "STRONG BUY"
    elif combined < 0.35 and ml_centered < 0.5 and signals_agree and high_conf_ml:
        decision = "STRONG SELL"
    elif combined > 0.58 and ml_bull and tech_bull and tradeable:
        decision = "BUY"
    elif combined < 0.42 and ml_bear and tech_bear and tradeable:
        decision = "SELL"
    else:
        decision = "HOLD"

    if decision in ("STRONG BUY", "STRONG SELL") and signals_agree and high_conf_ml:
        signal_quality = "HIGH"
        confidence = min(agreement * hc_acc * 1.15, 92)
    elif signals_agree and (high_conf_ml or agreement > 70):
        signal_quality = "MEDIUM"
        confidence = min(agreement * reliability * 100, 85)
    else:
        signal_quality = "LOW"
        confidence = 50 + abs(combined - 0.5) * 60

    if signal_quality == "HIGH" and not signals_agree:
        signal_quality = "MEDIUM"
        confidence = min(confidence, 75)

    if atr_val > 0:
        bearish = "SELL" in decision
        if bearish:
            stop_loss = round(current_price + 2 * atr_val, 2)
            target_1 = round(current_price - 2 * atr_val, 2)
            target_2 = round(current_price - 3 * atr_val, 2)
            risk_bias = "REDUCE_LONG"
            position_advice = "Bearish bias — trim/hedge longs; levels are reference (not short-sale advice)."
        else:
            stop_loss = round(current_price - 2 * atr_val, 2)
            target_1 = round(current_price + 2 * atr_val, 2)
            target_2 = round(current_price + 3 * atr_val, 2)
            risk_bias = "LONG"
            position_advice = "Risk max 2% of capital per trade; stop below ATR-based level."
        risk_reward = 1.0
    else:
        bearish = "SELL" in decision
        if bearish:
            stop_loss = round(current_price * 1.03, 2)
            target_1 = round(current_price * 0.97, 2)
            target_2 = round(current_price * 0.95, 2)
            risk_bias = "REDUCE_LONG"
            position_advice = "Bearish bias — reference levels only."
        else:
            stop_loss = round(current_price * 0.97, 2)
            target_1 = round(current_price * 1.03, 2)
            target_2 = round(current_price * 1.05, 2)
            risk_bias = "LONG"
            position_advice = "Risk max 2% of capital per trade"
        risk_reward = 1.5

    return {
        "decision": decision,
        "confidence": round(confidence, 1),
        "combined_score": round(combined, 4),
        "signal_quality": signal_quality,
        "agreement_score": round(agreement, 1),
        "signals_agree": bool(signals_agree),
        "ml_probability_centered": round(ml_centered, 4),
        "ml_confidence_lift": round(lift, 4),
        "base_rate": round(float(base_rate), 4),
        "base_rate_down": None if base_rate_down is None else round(float(base_rate_down), 4),
        "ml_probability_down": None if ml_proba_down is None else round(float(ml_proba_down), 4),
        "ml_probability_down_centered": None if down_c is None else round(float(down_c), 4),
        "dual_head": bool(dual),
        "risk_management": {
            "bias": risk_bias,
            "stop_loss": stop_loss,
            "target_1": target_1,
            "target_2": target_2,
            "risk_reward_ratio": risk_reward,
            "atr_14": round(atr_val, 2),
            "position_advice": position_advice,
        },
    }


# ================================================================
# SECTION 9: DATABASE (SQLite for prediction history)
# ================================================================

def setup_database():
    """Create SQLite database for prediction history. """
    conn = sqlite3.connect(DB_PATH)
    conn.execute(""" CREATE TABLE IF NOT EXISTS predictions ( id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL, stock TEXT NOT NULL, symbol TEXT NOT NULL, decision TEXT NOT NULL, confidence REAL, ml_probability REAL, technical_score REAL, combined_score REAL, current_price REAL, stop_loss REAL, target_1 REAL, model_accuracy REAL ) """)
    conn.commit()
    conn.close()


def save_prediction(result):
    """Save a prediction to the database. """
    conn = sqlite3.connect(DB_PATH)
    conn.execute( """INSERT INTO predictions (timestamp, stock, symbol, decision, confidence, ml_probability, technical_score, combined_score, current_price, stop_loss, target_1, model_accuracy) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""" , ( result["metadata"]["timestamp"], result["stock_input"], result["symbol"], result["decision"], result["confidence"], result["ml_prediction"]["probability_up"], result["technical_analysis"]["technical_score"], result["combined_score"], result["current_price"], result["risk_management"]["stop_loss"], result["risk_management"]["target_1"], result["ml_prediction"]["model_accuracy_test"], ), )
    conn.commit()
    conn.close()


def get_prediction_history(stock=None, limit=50):
    """Retrieve prediction history from database. """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    if stock:
        rows = conn.execute( "SELECT * FROM predictions WHERE stock = ? ORDER BY id DESC LIMIT ?" , (stock.upper(), limit), ).fetchall()
    else:
        rows = conn.execute( "SELECT * FROM predictions ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ================================================================
# SECTION 10: CHART GENERATOR (optional)
# ================================================================

def generate_chart(df, symbol, decision_info):
    """Generate and save a PNG chart with candlesticks, SMA, RSI, MACD."""
    if not HAS_MATPLOTLIB:
        return None

    from matplotlib.patches import Rectangle
    import matplotlib.dates as mdates

    safe_name = symbol.replace("^", "IDX_").replace(".", "_")
    chart_path = os.path.join(CHART_DIR, f"{safe_name}_chart.png")

    last_90 = df.tail(90).copy()

    fig, axes = plt.subplots(3, 1, figsize=(14, 10), gridspec_kw={"height_ratios": [3, 1, 1]})
    fig.suptitle(
        f"{symbol} — Signal: {decision_info['decision']} ({decision_info['confidence']}%)",
        fontsize=14,
        fontweight="bold",
    )

    ax1 = axes[0]
    xnums = mdates.date2num(last_90.index.to_pydatetime())
    for i, (_, row) in enumerate(last_90.iterrows()):
        o, h, l, c = float(row["Open"]), float(row["High"]), float(row["Low"]), float(row["Close"])
        color = "#16a34a" if c >= o else "#dc2626"
        ax1.plot([xnums[i], xnums[i]], [l, h], color=color, linewidth=0.9, solid_capstyle="round")
        body_h = max(abs(c - o), (h - l) * 0.02)
        body_b = min(o, c)
        ax1.add_patch(
            Rectangle(
                (xnums[i] - 0.25, body_b),
                0.5,
                body_h,
                facecolor=color,
                edgecolor=color,
                linewidth=0.5,
            )
        )
    if "sma_50_raw" in last_90.columns:
        ax1.plot(last_90.index, last_90["sma_50_raw"], color="#f59e0b", linewidth=1.2, alpha=0.85, label="SMA 50")
    if "sma_200_raw" in last_90.columns:
        ax1.plot(last_90.index, last_90["sma_200_raw"], color="#6366f1", linewidth=1.2, alpha=0.85, label="SMA 200")
    ax1.set_ylabel("Price")
    ax1.legend(loc="upper left", fontsize=8)
    ax1.grid(True, alpha=0.3)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))

    # RSI
    ax2 = axes[1]
    if "rsi_raw" in last_90.columns:
        ax2.plot(last_90.index, last_90["rsi_raw"], color="#8b5cf6", linewidth=1)
        ax2.axhline(70, color="#ef4444", linestyle="--", linewidth=0.8, alpha=0.5)
        ax2.axhline(30, color="#22c55e", linestyle="--", linewidth=0.8, alpha=0.5)
        ax2.fill_between(last_90.index, 30, 70, alpha=0.05, color="gray")
    ax2.set_ylabel("RSI")
    ax2.set_ylim(0, 100)
    ax2.grid(True, alpha=0.3)

    # MACD
    ax3 = axes[2]
    if "macd_hist_raw" in last_90.columns:
        colors = ["#22c55e" if v >= 0 else "#ef4444" for v in last_90["macd_hist_raw"]]
        ax3.bar(last_90.index, last_90["macd_hist_raw"], color=colors, width=0.8, alpha=0.7)
    ax3.set_ylabel("MACD Hist")
    ax3.grid(True, alpha=0.3)

    plt.tight_layout()
    fig.savefig(chart_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return chart_path


# ================================================================
# SECTION 11: MAIN PREDICTION ENGINE
# ================================================================

def train_watchlist_models(force_retrain=False, symbols: Optional[List[str]] = None):
    """Train and cache ML models for every watchlist symbol (no live poll / chart)."""
    results = []
    ok = 0
    only = {s.strip().upper() for s in symbols} if symbols else None
    for item in WATCHLIST:
        key = item["symbol"]
        if only and key.upper() not in only:
            continue
        yahoo = resolve_symbol(key)
        print(f"\n  Train model {key} ({yahoo})...")
        try:
            df = download_data(yahoo, force=force_retrain, stock_key=key)
            features_df, _ = compute_all_features(df)
            X, y, feature_cols, y_down = build_training_data(df, features_df)
            if len(X) < 100:
                raise RuntimeError(f"Only {len(X)} samples after features")
            if not force_retrain:
                cached = get_cached_model(yahoo)
                if cached[0] is not None:
                    results.append({
                        "stock": key,
                        "status": "cached",
                        "samples": len(X),
                        "walk_forward_accuracy": cached[2].get("walk_forward_accuracy"),
                    })
                    ok += 1
                    continue
            model, scaler_obj, metrics, selected_cols = train_models(
                X, y, feature_cols, y_down=y_down
            )
            save_model(yahoo, model, scaler_obj, metrics, selected_cols)
            results.append({
                "stock": key,
                "status": "trained",
                "samples": len(X),
                "walk_forward_accuracy": metrics.get("walk_forward_accuracy"),
                "historical_source": df.attrs.get("historical_source"),
            })
            ok += 1
        except Exception as exc:
            results.append({"stock": key, "status": "error", "error": str(exc)})
    attempted = len(results) if only else len(WATCHLIST)
    return {"attempted": attempted, "succeeded": ok, "results": results}


def train_knowledge_base() -> Dict[str, Any]:
    """Scan watchlist history + news DB; store events, rules, and memory ML models."""
    pattern_memory.setup_knowledge_database(KNOWLEDGE_DB_PATH)
    return pattern_memory.run_knowledge_training(
        KNOWLEDGE_DB_PATH,
        MODEL_DIR,
        NEWS_DB_PATH,
        WATCHLIST,
        download_data,
        resolve_symbol,
        compute_all_features,
        INDIAN_STOCKS,
    )


def _opening_tape_read(stock_key, bars, news):
    """Candle + news shock read. Does not alter the model decision."""
    try:
        import opening_tape

        return opening_tape.read_opening(stock_key, bars, news=news or {})
    except Exception as exc:
        return {
            "available": False,
            "call": "WATCH",
            "separate_from_model": True,
            "headline": f"Tape read failed: {exc}",
        }


def predict_stock(stock_input, force_retrain=False, mode=None, product=None, lite=False):
    """Complete prediction pipeline. product: None | 'fno' | 'intraday' for product-specific decisions."""
    if product == "intraday" and mode in (None, "auto", ""):
        mode = "intraday"
    elif product == "fno" and mode in (None, "auto", ""):
        mode = analysis_engine.resolve_analysis_mode("intraday")
    print(f"\n{'='*60}")
    print(f"  PREDICTING: {stock_input}")
    print(f"{'='*60}")
    set_analyze_progress(8, "Loading prices", stock_input)

    # 1. Resolve symbol
    symbol = resolve_symbol(stock_input)
    print(f"  Symbol: {symbol}")

    stock_key = stock_input.strip().upper()

    # 2. Download data
    df = download_data(symbol, stock_key=stock_key)
    hist_source = df.attrs.get("historical_source", "yahoo_finance")

    live_quote, live_err = None, None
    if live_market.is_live_eligible(stock_key, INDIAN_STOCKS):
        live_quote, live_err = live_market.fetch_live_quote(stock_key, INDIAN_STOCKS)
        if live_quote:
            df_display = market_symbols.apply_live_quote_to_daily_df(df.copy(), live_quote)
            print(f"  Live {live_quote.get('source', 'market')} LTP: {live_quote['last_price']}")
        else:
            df_display = df
    else:
        df_display = df

    df_ml = _ohlcv_for_indicators(df, live_quote)

    set_analyze_progress(28, "Reading the tape", stock_input)
    # 3. Compute features on closed bars (avoid partial intraday bar skew)
    print("  Computing 50+ technical indicators... ", flush=True)
    features_df, raw_indicators = compute_all_features(df_ml)

    # 4. Build training data
    X, y, feature_cols, y_down = build_training_data(df_ml, features_df)
    print(f"  Features: {len(feature_cols)}, Samples: {len(X)}")

    if len(X) < 100:
        raise RuntimeError(f"Not enough data after feature computation ({len(X)} rows). Need at least 100. ")

    set_analyze_progress(48, "Scoring the model", stock_input)
    # 5. Load model (train only if missing or force_retrain)
    model, scaler_obj, metrics, selected_cols = (None, None, None, None)
    if not force_retrain:
        model, scaler_obj, metrics, selected_cols = get_cached_model(symbol)

    if model is not None and selected_cols:
        print("  Using saved model (train via --train-watchlist to refresh)")
    elif force_retrain or model is None:
        print("  Training ML models... ", flush=True)
        model, scaler_obj, metrics, selected_cols = train_models(
            X, y, feature_cols, y_down=y_down
        )
        save_model(symbol, model, scaler_obj, metrics, selected_cols)

    # Models saved before base-rate centring carry no neutral point; without this they
    # would be scored against 0.5 and read as bearish on almost every day.
    if metrics is not None and metrics.get("base_rate") is None:
        metrics = {**metrics, "base_rate": float(y.mean()), "base_rate_source": "recomputed"}
    if metrics is not None and metrics.get("base_rate_down") is None and y_down is not None:
        metrics = {**metrics, "base_rate_down": float(y_down.mean())}

    set_analyze_progress(72, "Building the call", stock_input)
    # 6. Predict on latest data point
    full_features = features_df[selected_cols].dropna()
    if len(full_features) == 0:
        raise RuntimeError("No valid feature rows after NaN removal")

    latest_features = full_features.iloc[[-1]]
    latest_scaled = scaler_obj.transform(latest_features)
    ml_proba, ml_proba_down = model_predict_sides(model, latest_scaled)

    # 7. Technical score
    tech_score = compute_technical_score(raw_indicators)

    # 8. Current price and ATR (prefer Groww live LTP for Indian symbols)
    current_price = float(df_display["Close"].iloc[-1])
    if live_quote and live_quote.get("last_price"):
        current_price = float(live_quote["last_price"])
    atr_val = raw_indicators.get("atr_raw", current_price * 0.02)

    if lite:
        fund = {
            "available": False,
            "reason": "Skipped on the fast morning pass",
            "fundamental_score": 50.0,
            "bias": "NEUTRAL",
            "combined_adjust": 0.0,
        }
    else:
        fund = fundamentals.analyze_fundamentals(symbol, stock_key)
    recent_news = news_data.get_recent_for_symbol(NEWS_DB_PATH, stock_key, limit=8)
    pre_combined = 0.55 * ml_proba + 0.45 * (tech_score / 100.0)
    enrichment = analysis_engine.enrich_prediction(
        df_display,
        ml_proba,
        tech_score,
        pre_combined,
        current_price,
        atr_val,
        live_quote,
        recent_news,
        mode=mode,
    )
    adj_tech = enrichment["adjusted_technical_score"]

    struct = structural_analysis.run_structural_analysis(
        df_ml, current_price, stock_key,
    )
    struct["reason_lines"] = structural_analysis.structural_reason_lines(struct)

    knowledge = pattern_memory.apply_knowledge_to_prediction(
        KNOWLEDGE_DB_PATH,
        MODEL_DIR,
        stock_key,
        enrichment["candlestick"].get("patterns") or [],
        recent_news,
        raw_indicators=raw_indicators,
        intraday_interval="5minute" if product == "intraday" else None,
    )
    market_pack = full_market_analysis.build_full_stack(
        stock_key=stock_key,
        df=df_ml,
        current_price=current_price,
        live_quote=live_quote,
        is_indian=market_symbols.is_indian_symbol(stock_key, INDIAN_STOCKS),
        want_derivatives=not lite and (product == "fno" or product_analysis.is_fno_primary(stock_key)),
    )
    india_ctx = market_pack.get("india") or {"available": False, "combined_adjust": 0.0}

    combined_adjust = (
        enrichment["combined_adjust"]
        + knowledge.get("combined_adjust", 0)
        + struct.get("combined_adjust", 0)
        + fund.get("combined_adjust", 0)
        + float(india_ctx.get("combined_adjust") or 0)
        + float(market_pack.get("combined_adjust") or 0)
    )

    dr = dict(enrichment["day_range_forecast"])
    sr = struct.get("support_resistance") or {}
    dr["nearest_support"] = sr.get("nearest_support")
    dr["nearest_resistance"] = sr.get("nearest_resistance")
    enrichment["day_range_forecast"] = dr

    # 9. Generate decision (ML + adjusted technical + enrichment + historical memory)
    decision_info = generate_decision(
        ml_proba,
        adj_tech,
        current_price,
        atr_val,
        metrics,
        combined_adjust=combined_adjust,
        ml_proba_down=ml_proba_down,
    )

    reasons = analysis_engine.build_reasons(
        decision_info["decision"],
        ml_proba,
        adj_tech,
        bool(decision_info["signals_agree"]),
        enrichment["candlestick"],
        enrichment["news_sentiment"],
        enrichment["global_lead"],
        enrichment["mode"],
        enrichment["day_range_forecast"],
        structural=struct,
        fundamentals=fund,
        india_context=india_ctx if india_ctx.get("available") else None,
    )
    for line in knowledge.get("rule_summaries") or []:
        reasons.append({"category": "Historical memory", "text": line})
    htf = (market_pack.get("higher_timeframe") or {})
    if htf.get("available"):
        reasons.append({
            "category": "Higher timeframe",
            "text": f"Weekly { (htf.get('weekly') or {}).get('bias') } / monthly { (htf.get('monthly') or {}).get('bias') }.",
        })
    deriv = market_pack.get("derivatives") or {}
    if deriv.get("available") and deriv.get("notes"):
        reasons.append({"category": "Derivatives", "text": "; ".join(deriv["notes"][:2])})
    if fund.get("next_earnings"):
        reasons.append({"category": "Fundamentals", "text": f"Next earnings {fund['next_earnings']}."})

    session_thesis = india_market_context.build_session_thesis(
        stock_key,
        decision_info["decision"],
        enrichment["day_range_forecast"],
        india_ctx,
        struct,
        decision_info["risk_management"]["stop_loss"],
        decision_info["signal_quality"],
    )
    trading_gate = india_market_context.compute_trading_gate(
        decision_info["decision"],
        decision_info["signal_quality"],
        bool(decision_info["signals_agree"]),
    )

    wf_acc = metrics.get("walk_forward_accuracy", metrics["ensemble_accuracy"])
    hc_acc = metrics.get("high_confidence_accuracy", 0)

    # 10. Build full response
    result = {
        "stock_input": stock_input.upper(),
        "symbol": symbol,
        "current_price": round(current_price, 2),
        "live_market": live_quote if live_quote else {"available": False, "error": live_err},
        "decision": decision_info["decision"],
        "confidence": decision_info["confidence"],
        "combined_score": decision_info["combined_score"],
        "signal_quality": decision_info["signal_quality"],
        "agreement_score": decision_info["agreement_score"],
        "signals_agree": bool(decision_info["signals_agree"]),
        "analysis_mode": enrichment["mode"],
        "india_market_context": india_ctx,
        "session_thesis": session_thesis,
        "trading_gate": trading_gate,
        "day_range_forecast": enrichment["day_range_forecast"],
        "candlestick": enrichment["candlestick"],
        "news_sentiment": enrichment["news_sentiment"],
        "global_lead": enrichment["global_lead"],
        "structural_analysis": struct,
        "reasons": reasons,
        "summary": _build_summary(decision_info, adj_tech, ml_proba, metrics),
        "technical_analysis": {
            "technical_score": round(adj_tech, 1),
            "base_technical_score": round(tech_score, 1),
            "trend": "BULLISH" if tech_score > 55 else ("BEARISH" if tech_score < 45 else "NEUTRAL"),
            "rsi_14": round(raw_indicators.get("rsi_14", 0), 1),
            "macd_histogram": round(raw_indicators.get("macd_hist", 0), 4),
            "macd_signal_status": "BULLISH" if raw_indicators.get("macd_hist", 0) > 0 else "BEARISH",
            "bollinger_pctb": round(raw_indicators.get("bb_pctb", 0.5), 3),
            "adx": round(raw_indicators.get("adx", 0), 1),
            "stochastic_k": round(raw_indicators.get("stoch_k", 50), 1),
            "williams_r": round(raw_indicators.get("williams_r", -50), 1),
            "mfi_14": round(raw_indicators.get("mfi_14", 50), 1),
            "volume_ratio": round(raw_indicators.get("vol_ratio", 1), 2),
            "price_vs_sma50": round(raw_indicators.get("price_vs_sma50", 0), 2),
            "price_vs_sma200": round(raw_indicators.get("price_vs_sma200", 0), 2),
            "cci_20": round(raw_indicators.get("cci_20", 0), 1),
            "roc_12": round(raw_indicators.get("roc_12", 0), 2),
            "stochastic_d": round(raw_indicators.get("stoch_d", 50), 1),
            "ema_cross_bullish": bool(raw_indicators.get("ema_cross") == 1),
            "macd_cross_bullish": bool(raw_indicators.get("macd_cross") == 1),
        },
        "fundamental_analysis": fund,
        "ml_prediction": {
            "direction": "UP" if decision_info["ml_probability_centered"] > 0.5 else "DOWN",
            "probability_up": round(ml_proba, 4),
            "probability_down": round(
                ml_proba_down if ml_proba_down is not None else (1 - ml_proba), 4
            ),
            "probability_up_centered": decision_info["ml_probability_centered"],
            "base_rate": decision_info["base_rate"],
            "base_rate_down": decision_info.get("base_rate_down"),
            "dual_head": bool(decision_info.get("dual_head")),
            "base_rate_note": (
                f"Up-target fires on {decision_info['base_rate']:.0%} of days "
                f"(down-target {decision_info.get('base_rate_down') or 0:.0%}). "
                "SELL needs the down-head, not a weak up-head."
            ),
            "model_accuracy_test": round(metrics["ensemble_accuracy"], 4),
            "walk_forward_accuracy": round(wf_acc, 4),
            "high_confidence_accuracy": round(hc_acc, 4),
            "model_f1_test": round(metrics["ensemble_f1"], 4),
            "model_precision": round(metrics.get("ensemble_precision", 0), 4),
            "model_recall": round(metrics.get("ensemble_recall", 0), 4),
            "models_used": list(metrics["individual"].keys()) + ["Ensemble"],
            "training_samples": metrics["train_samples"],
            "test_samples": metrics["test_samples"],
            "feature_count": metrics["feature_count"],
            "target_threshold_pct": metrics.get("target_threshold_pct", TARGET_MIN_RETURN * 100),
        },
        "risk_management": decision_info["risk_management"],
        "metadata": {
            "timestamp": datetime.now().isoformat(),
            "as_of_date": datetime.now().strftime("%Y-%m-%d"),
            "data_points": len(df_display),
            "last_data_date": str(df_display.index[-1].date()) if hasattr(df_display.index[-1], "date") else str(df_display.index[-1]),
            "data_period_years": DATA_YEARS,
            "model_version": MODEL_VERSION,
            "historical_source": hist_source,
            "features_use_closed_bar": bool(live_quote),
            "price_source": live_quote.get("source", hist_source) if live_quote else hist_source,
            "disclaimer": "Educational tool. Directional accuracy ~55–70%; day range is statistical, not a guarantee.",
        },
        "recent_news": recent_news,
        "knowledge_memory": {
            "source_db": KNOWLEDGE_DB_PATH,
            "matched_rule_count": len(knowledge.get("matched_rules") or []),
            "memory_ml": knowledge.get("memory_ml"),
            "topics_checked": knowledge.get("topics_checked"),
            "adjust_applied": knowledge.get("combined_adjust"),
        },
        "market_analysis": market_pack,
        "analysis_breakdown": {
            "candlestick_patterns": enrichment["candlestick"].get("patterns") or [],
            "candlestick_bias": enrichment["candlestick"].get("bias"),
            "technical_score": round(adj_tech, 1),
            "base_technical_score": round(tech_score, 1),
            "ml_probability_up": round(ml_proba, 4),
            "combined_score": decision_info["combined_score"],
            "adjustments": {
                "candlestick_news_ta": enrichment.get("combined_adjust"),
                "structure": struct.get("combined_adjust"),
                "knowledge_memory": knowledge.get("combined_adjust"),
                "fundamentals": fund.get("combined_adjust"),
                "india_premarket": float(india_ctx.get("combined_adjust") or 0),
            },
            "indicators_in_ml": metrics.get("feature_count"),
            "decision_formula": (
                "combined = 0.55×ML_up + 0.45×(tech/100) + structure + memory + fundamentals + India (pre-market); "
                "decision from combined + ML/tech agreement + walk-forward calibrated confidence"
            ),
            "rule_candles_detected": [
                "Doji/Dragonfly/Gravestone", "Hammer/Hanging man", "Shooting star/Inverted hammer",
                "Engulfing", "Inside/Outside bar", "Three white soldiers/black crows",
                "Morning/Evening star + doji star", "Harami/Harami cross", "Marubozu/Belt hold",
                "Piercing/Dark cloud", "Kicker", "Tweezer", "Rising/Falling three methods",
                "Tasuki gap", "Window", "Three line strike", "Abandoned baby", "Separating lines",
                "Advance block", "Stick sandwich",
            ],
            "technical_rules_in_score": [
                "RSI", "MACD", "Bollinger %B", "ADX", "Stochastic", "Williams %R", "MFI", "CCI", "ROC",
                "SMA50/200", "EMA cross", "Volume ratio", "ATR context", "Supertrend", "Ichimoku", "Parabolic SAR",
            ],
        },
    }

    result["core_decision"] = decision_info["decision"]
    result["product"] = product or "daily"

    if product == "fno":
        if live_market.is_live_eligible(stock_key, INDIAN_STOCKS):
            lq_fresh, _lerr = live_market.fetch_live_quote(stock_key, INDIAN_STOCKS)
            if lq_fresh and lq_fresh.get("last_price"):
                live_quote = lq_fresh
                current_price = float(lq_fresh["last_price"])
                result["live_market"] = live_quote
        idf5, idf15 = None, None
        fno_bar_err = None
        if kite_data.kite_enabled() and live_market.is_live_eligible(stock_key, INDIAN_STOCKS):
            try:
                # Keep the forming 5m candle so short-horizon / live scan track *this* bar.
                idf5, _ = kite_data.fetch_historical_candles(
                    stock_key, "5minute", days=2, keep_partial=True
                )
                idf15, fno_bar_err = kite_data.fetch_historical_candles(stock_key, "15minute", days=10)
            except Exception as exc:
                fno_bar_err = str(exc)
        if live_quote and live_quote.get("open"):
            result["day_range_forecast"] = analysis_engine.refresh_day_range(
                result.get("day_range_forecast") or {},
                live_quote,
                idf15,
            )
        try:
            import fno_short_horizon

            idf5 = fno_short_horizon.patch_forming_5m(
                idf5, current_price, asof=(live_quote or {}).get("received_at_ist")
            )
        except Exception:
            pass
        live_ctx = fno_live_engine.build_fno_live_context(
            live_quote,
            idf5,
            idf15,
            ml_proba,
            adj_tech,
            float(decision_info.get("combined_score") or 0.5),
            decision_info.get("decision") or "HOLD",
        )
        live_ctx["bars_5m"] = idf5
        live_ctx["bars_15m"] = idf15
        import fno_model

        fno_bars = idf15 if idf15 is not None and len(idf15) else None
        fno_pack = fno_model.load(symbol=stock_key)
        if not fno_model.pack_usable(fno_pack):
            # Training stays in the daily job. Doing it inside analysis was several minutes.
            fno_pack = {"available": False, "model_version": fno_model.MODEL_VERSION}
        if fno_bar_err:
            live_ctx.setdefault("notes", []).append(f"F&O 15m history: {fno_bar_err}")
        try:
            news_delta = float((enrichment.get("news_sentiment") or {}).get("score_delta") or 0)
            if not math.isfinite(news_delta):
                news_delta = 0.0
        except (TypeError, ValueError):
            news_delta = 0.0
        vix_level = finite_float(((india_ctx or {}).get("india_vix") or {}).get("level"), 0.0)
        deriv = dict((market_pack or {}).get("derivatives") or {})
        if vix_level > 0:
            deriv["vix_level"] = vix_level
        else:
            # Never leave a prior NaN vix_level in the derivatives blob
            if "vix_level" in deriv:
                deriv["vix_level"] = finite_float(deriv.get("vix_level"), 0.0) or None
                if not deriv["vix_level"]:
                    deriv.pop("vix_level", None)
        prev_snap = fno_ws_rescore.get_snapshot(stock_key) or {}
        if prev_snap.get("last_pcr") is not None:
            deriv["pcr_prev"] = prev_snap["last_pcr"]
        gex = deriv.get("gex") if isinstance(deriv.get("gex"), dict) else None
        if not (gex and gex.get("available")):
            try:
                import option_gex

                gex = option_gex.snapshot(stock_key, float(current_price), vix_level=vix_level)
                deriv["gex"] = gex
            except Exception:
                gex = None
        try:
            import dark_pool

            deriv["dix"] = dark_pool.latest(stock_key)
        except Exception:
            deriv["dix"] = {"available": False}
        try:
            import chain_flow

            saved = chain_flow.capture(
                stock_key,
                deriv,
                live_quote=live_quote,
                vix_level=vix_level,
                spot=float(current_price or 0),
            )
            if not saved.get("stored"):
                prior = chain_flow.readings_asof(stock_key)
                if prior:
                    deriv = prior
        except Exception:
            pass
        import fno_session_rules as fsrules

        prev_ticket = prev_snap.get("session_ticket")
        today_s = str(market_symbols.ist_now().date())
        if prev_ticket and str(prev_ticket.get("session_date") or "")[:10] != today_s:
            prev_ticket = None
        if not prev_ticket:
            # Cold start (server restart): today's tickets come back from the DB.
            try:
                import session_calls as _sc

                prev_ticket = _sc.session_ticket_from_db(
                    KNOWLEDGE_DB_PATH, stock_key, session_date=market_symbols.ist_now().date()
                )
            except Exception:
                prev_ticket = None
        ticket_before = dict(prev_ticket) if isinstance(prev_ticket, dict) else prev_ticket
        live0 = fsrules.open_ticket(prev_ticket)
        hi, lo = float(current_price), float(current_price)
        if live0:
            hi, lo = fsrules.path_extremes(fno_bars, live0.get("taken_at"), current_price)
        import fno_alerts

        prev_ticket, skip_mark = fno_alerts.settle_open_call(
            prev_ticket,
            float(current_price),
            idf5,
            market_symbols.ist_now(),
            bars_15m=fno_bars,
        )
        if not skip_mark:
            prev_ticket = fsrules.mark_ticket_from_tape(
                prev_ticket,
                last=float(current_price),
                session_high=hi,
                session_low=lo,
                bars=fno_bars,
                symbol=stock_key,
                asof=market_symbols.ist_now(),
            )
        orb = ((live_ctx.get("microstructure") or {}).get("opening_range") or {})
        fno_head = fno_model.infer(
            fno_bars,
            fno_pack,
            derivatives=deriv,
            news_delta=news_delta,
            vix_level=vix_level,
            five_min_conflict=bool((live_ctx.get("microstructure") or {}).get("five_min_conflict")),
            daily_decision=decision_info.get("decision"),
            gex=gex,
            asof=market_symbols.ist_now(),
            force_side=fsrules.infer_side_override(
                prev_ticket, orb, current_price, asof=market_symbols.ist_now()
            ),
            first_clip=fsrules.is_first_clip(prev_ticket),
            symbol=stock_key,
            context={
                "ml_proba": ml_proba,
                "adj_tech": adj_tech,
                "news_delta": news_delta,
                "candle_bias": (enrichment.get("candlestick") or {}).get("bias"),
                "session_bias": (live_ctx.get("session") or {}).get("session_bias"),
                "vix": (india_ctx or {}).get("india_vix"),
            },
        )
        if product_analysis.is_fno_primary(stock_key) and not fno_head.get("available"):
            fno_head = {
                "available": True,
                "decision": "HOLD",
                "p_up": 0.5,
                "confidence": 45,
                "source": "fno_model_missing",
            }
        live_ctx["fno_model"] = fno_head
        live_ctx["session_model"] = fno_head
        dual_ev = None
        contracts = None
        try:
            contracts = fno_instruments.resolve_contracts(stock_key, current_price)
        except Exception:
            contracts = {"available": False, "error": "contract resolve failed"}
        intraday_ready = None
        intraday_decision = None
        if not product_analysis.is_fno_primary(stock_key):
            intra_tech = {"available": False}
            bars_ok = None
            blended = None
            if idf5 is not None and len(idf5) > 0:
                try:
                    intra_tech = intraday_engine.compute_intraday_technical(idf5, "5minute")
                    core = decision_info["decision"]
                    if "BUY" in core:
                        bars_ok = product_analysis.intraday_5m_confirms(idf5, True)
                    elif "SELL" in core:
                        bars_ok = product_analysis.intraday_5m_confirms(idf5, False)
                    if intra_tech.get("available"):
                        intra_p = intraday_engine.intraday_probability_up(intra_tech)
                        blended = round(
                            0.45 * float(decision_info.get("combined_score") or 0.5) + 0.55 * intra_p, 4
                        )
                except Exception:
                    pass
            intra_block = product_analysis.build_intraday_analysis(
                stock_key,
                decision_info,
                ml_proba,
                adj_tech,
                enrichment["candlestick"],
                trading_gate,
                india_ctx if india_ctx.get("available") else None,
                intraday_bars_ok=bars_ok,
                intraday_tech=intra_tech,
                blended_intraday_score=blended,
            )
            result["intraday_analysis"] = intra_block
            intraday_ready = bool(intra_block.get("intraday_ready"))
            intraday_decision = intra_block.get("decision")
        indications = None
        if product_analysis.is_fno_primary(stock_key):
            try:
                import fno_indications

                indications = fno_indications.build(
                    stock_key, bars=fno_bars, price=current_price, india_ctx=india_ctx
                )
            except Exception as exc:
                indications = {"available": False, "error": str(exc)}
        fno_block = product_analysis.build_fno_analysis(
            stock_key,
            decision_info,
            ml_proba,
            adj_tech,
            combined_adjust,
            enrichment["candlestick"],
            india_ctx if india_ctx.get("available") else None,
            current_price,
            atr_val,
            fno_contracts=contracts,
            live_context=live_ctx,
            live_quote=live_quote,
            structural=struct,
            indicators=raw_indicators,
            market_tilt=full_market_analysis.extra_horizon_tilt(market_pack),
            day_range=result.get("day_range_forecast") or enrichment.get("day_range_forecast"),
            intraday_ready=intraday_ready,
            intraday_decision=intraday_decision,
            same_session_only=True,
            asof=market_symbols.ist_now(),
            session_ticket=prev_ticket,
            fno_model=fno_head,
            indications=indications,
        )
        _pulse_snap = fno_ws_rescore.get_snapshot(stock_key) or {}
        fno_block = fno_ws_rescore.merge_volatility_into_block(
            _pulse_snap,
            stock_key,
            current_price,
            fno_block,
            live_context=live_ctx,
            live_quote=live_quote,
        )
        result["fno_analysis"] = fno_block
        result["fno_model"] = fno_head
        result["tape_read"] = _opening_tape_read(stock_key, idf15, enrichment.get("news_sentiment"))
        result["decision"] = fno_block["decision"]
        if fno_block.get("risk"):
            import fno_risk_engine

            result["risk_management"] = fno_risk_engine.fno_risk_for_api(fno_block["risk"])
        import opening_tape

        desk_decision = str((fno_block.get("decision") or "HOLD")).upper()
        already = bool(fsrules.closed_ticket_count(prev_ticket) or fsrules.open_ticket(prev_ticket))
        tape_overrode = False
        import fno_live_config

        if not already:
            # A confirmed opening drive fills the first call when the 15m book was held.
            opening_tape.apply_fno_call(
                result,
                result.get("tape_read"),
                allow_override=desk_decision in ("HOLD", "") and not fno_live_config.is_fno_live_index(stock_key),
            )
            tape_overrode = bool((result.get("opening_ticket") or {}).get("available")) and str(
                result.get("decision")
            ) != str(fno_block.get("decision"))
        elif result.get("tape_read"):
            tape = dict(result["tape_read"])
            tape["historical"] = True
            result["tape_read"] = tape
        if not tape_overrode:
            result["confidence"] = fno_block["confidence"]
            result["summary"] = fno_block["headline"]
        result["current_price"] = round(current_price, 2)
        now_ist = market_symbols.ist_now()
        if stock_key == "NIFTY":
            import nifty_fno_runtime

            result["session_ticket"] = prev_ticket
            nifty_fno_runtime.finalize_result(
                result, bars=fno_bars, quote=live_quote, asof=now_ist
            )
        dual_ev = None

        use_dual = fno_live_config.use_dual_track()
        stacked = fno_live_config.enable_stacked_calls()
        result["use_dual_track"] = use_dual
        result["stacked_calls"] = stacked
        run_dual = bool(
            fno_live_config.is_fno_live_index(stock_key) and (use_dual or stacked)
        )
        if run_dual:
            try:
                import fno_live_dual_track

                dual_ev = fno_live_dual_track.apply_to_analyze_result(
                    stock_key,
                    result,
                    bars=fno_bars,
                    asof=now_ist,
                    session_ticket=prev_ticket,
                    price=current_price,
                    day_range=result.get("day_range_forecast") or enrichment.get("day_range_forecast"),
                )
                if isinstance(result.get("fno_model"), dict):
                    fno_head = result["fno_model"]
                    live_ctx["fno_model"] = fno_head
                    live_ctx["session_model"] = fno_head
            except Exception as exc:
                dual_ev = None
                result["dual_track_error"] = str(exc)
                print(f"[predict] dual_track failed for {stock_key}: {exc}")
        trade = ((result.get("risk_management") or {}).get("fno_trade") or {})
        tape_lv = ((result.get("tape_read") or {}).get("ticket") or {})
        live_decision = str(result.get("decision") or "HOLD")
        live_sl = trade.get("stop_loss") if trade.get("stop_loss") is not None else tape_lv.get("stop_loss")
        live_t1 = trade.get("target_1") if trade.get("target_1") is not None else tape_lv.get("target_1")
        dual_call = (dual_ev or {}).get("call_payload") if isinstance(dual_ev, dict) else None
        good_decision = live_decision
        stack_pick = None
        if stacked and fno_live_config.is_fno_live_index(stock_key):
            try:
                import fno_stacked_calls

                stack_pick = fno_stacked_calls.choose_list_source(
                    dual_call=dual_call if isinstance(dual_call, dict) else None,
                    good_decision=good_decision,
                    session_ticket=prev_ticket,
                    symbol=stock_key,
                    asof=now_ist,
                )
                result["stacked_pick"] = {
                    "track": stack_pick.get("track"),
                    "decision": stack_pick.get("decision"),
                    "reason": stack_pick.get("reason"),
                    "candidates": stack_pick.get("candidates"),
                    "htf": stack_pick.get("htf"),
                }
                if stack_pick.get("use_dual_payload") and isinstance(
                    stack_pick.get("call_payload"), dict
                ):
                    dual_call = stack_pick["call_payload"]
                else:
                    dual_call = None
                    if stack_pick.get("use_good") and stack_pick.get("decision") in (
                        "BUY",
                        "SELL",
                    ):
                        live_decision = str(stack_pick["decision"])
                    elif not stack_pick.get("track"):
                        # Cap / opposite-side / no fire — do not force a weak list
                        if good_decision in ("BUY", "SELL") and stack_pick.get(
                            "reason"
                        ) in ("day_cap", "opposite_side", "no_candidate"):
                            pass
            except Exception as exc:
                result["stacked_calls_error"] = str(exc)
                print(f"[predict] stacked_calls failed for {stock_key}: {exc}")
        suppress_dual = bool(fno_live_config.suppress_dual_list())
        result["suppress_dual_list"] = suppress_dual
        if isinstance(dual_call, dict) and dual_call.get("decision") in ("BUY", "SELL"):
            fa = dict(result.get("fno_analysis") or {})
            fa["dual_track_call"] = dual_call
            if stacked:
                fa["stacked_calls"] = True
            if suppress_dual:
                # Keep dual for annotate; Calls board fills via CHAMP_PLUS / crown.
                fa["dual_list_suppressed"] = True
                notes = list(fa.get("desk_alerts") or [])
                msg = (
                    "Dual proven/champion list suppressed — "
                    "CHAMP_PLUS / crown fill when board empty."
                )
                if msg not in notes:
                    notes.insert(0, msg)
                fa["desk_alerts"] = notes
                held = fno_live_config.suppress_core_list_if_needed(
                    live_decision, dual_call=None
                )
                if held != live_decision:
                    live_decision = held
                    result["decision"] = "HOLD"
                    fa["decision"] = "HOLD"
                    fa["extra_trees_single_disabled"] = True
                    result["summary"] = msg
                result["fno_analysis"] = fa
            else:
                # Dual-track lists proven / champion — each keeps its accuracy tag.
                live_decision = str(dual_call["decision"])
                live_sl = dual_call.get("stop_loss", live_sl)
                live_t1 = dual_call.get("target_1", live_t1)
                result["decision"] = live_decision
                fa["decision"] = live_decision
                result["fno_analysis"] = fa
                result["summary"] = dual_call.get("accuracy_label") or result.get("summary")
                if trade.get("stop_loss") is None or dual_call.get("stop_loss") is not None:
                    rm = dict(result.get("risk_management") or {})
                    ft = dict(rm.get("fno_trade") or {})
                    ft["stop_loss"] = live_sl
                    ft["target_1"] = live_t1
                    ft["entry"] = dual_call.get("entry") or current_price
                    rm["fno_trade"] = ft
                    result["risk_management"] = rm
        elif (
            fno_live_config.is_fno_live_index(stock_key)
            and fno_live_config.enable_pre_dual_single()
            and (not use_dual or stacked)
        ):
            # Pre-dual single modal (research prod2): list from core fno_model only.
            # Stacked mode keeps this as the good_prod2 core channel.
            fa = dict(result.get("fno_analysis") or {})
            fa["pre_dual_single"] = True
            fa["good"] = True
            if stacked:
                fa["stacked_calls"] = True
            result["fno_analysis"] = fa
            if stacked:
                result["summary"] = (
                    f"Stacked · good core (~{fno_live_config.STACK_HIT_PCT_6M:.0f}% 6m research)"
                    if live_decision in ("BUY", "SELL")
                    else result.get("summary")
                )
            else:
                result["summary"] = "Good · pre-dual single (~71%)"
        elif fno_live_config.is_fno_live_index(stock_key):
            # Dual exclusive: never list ExtraTrees single fall-through.
            dual_for_core = (
                None
                if suppress_dual
                else (dual_call if isinstance(dual_call, dict) else None)
            )
            held = fno_live_config.suppress_core_list_if_needed(
                live_decision, dual_call=dual_for_core
            )
            if held != live_decision:
                live_decision = held
                result["decision"] = "HOLD"
                fa = dict(result.get("fno_analysis") or {})
                fa["decision"] = "HOLD"
                fa["extra_trees_single_disabled"] = True
                notes = list(fa.get("desk_alerts") or [])
                msg = (
                    "ExtraTrees single 15m listing disabled — "
                    + (
                        "CHAMP_PLUS / crown fill path (dual list suppressed)."
                        if suppress_dual
                        else "dual proven/champion only."
                    )
                )
                if msg not in notes:
                    notes.insert(0, msg)
                fa["desk_alerts"] = notes
                result["fno_analysis"] = fa
                result["summary"] = msg
        # Live confluence is suggestion-only — never flips decision / never lists on Calls.
        live_conf_suggest = None
        if fno_live_config.is_fno_live_index(stock_key) and live_decision in ("HOLD", ""):
            try:
                import fno_live_confluence_call

                live_conf_suggest = fno_live_confluence_call.apply_if_hold(
                    result,
                    price=current_price,
                    open_call=None,
                    session_ticket=prev_ticket,
                    asof=now_ist,
                    symbol=stock_key,
                )
            except Exception:
                live_conf_suggest = None
        # Retire any previously listed live-confluence tickets from Calls.
        if fsrules.open_ticket(prev_ticket) and fsrules.is_live_confluence_ticket(prev_ticket):
            prev_ticket = fsrules.cancel_open_ticket(
                prev_ticket,
                closed_at=now_ist.isoformat(),
            )
            fa = dict(result.get("fno_analysis") or {})
            notes = list(fa.get("desk_alerts") or [])
            msg = "Prior live-indication call cancelled — live path is suggest-only now."
            if msg not in notes:
                notes.insert(0, msg)
            fa["desk_alerts"] = notes
            result["fno_analysis"] = fa
        orb = ((live_ctx or {}).get("microstructure") or {}).get("opening_range")
        soft_good = (not use_dual) and fno_live_config.is_fno_live_index(stock_key)
        try:
            soft_good = soft_good and fno_live_config.pre_dual_soft_gates()
        except Exception:
            pass
        shallow_note = fsrules.shallow_break_hold(
            live_decision, current_price, orb, prev_ticket, asof=now_ist
        )
        if shallow_note and soft_good:
            # Soft good path: alert only — do not force HOLD / hard-block list.
            fa = dict(result.get("fno_analysis") or {})
            notes = list(fa.get("desk_alerts") or [])
            alerts = list(fa.get("alerts") or [])
            warn = f"{shallow_note} (soft — still listing)"
            if warn not in notes and shallow_note not in notes:
                notes.append(warn)
                alerts.append(
                    {"code": "shallow_break_soft", "severity": "warning", "message": warn}
                )
            fa["desk_alerts"] = notes
            fa["alerts"] = alerts
            result["fno_analysis"] = fa
        elif shallow_note:
            live_decision = "HOLD"
            result["decision"] = "HOLD"
            fa = dict(result.get("fno_analysis") or {})
            fa["decision"] = "HOLD"
            notes = list(fa.get("desk_alerts") or [])
            alerts = list(fa.get("alerts") or [])
            if shallow_note not in notes:
                notes.append(shallow_note)
                alerts.append({"code": "shallow_break", "severity": "warning", "message": shallow_note})
            fa["desk_alerts"] = notes
            fa["alerts"] = alerts
            result["fno_analysis"] = fa
            result["summary"] = shallow_note
        if live_decision not in ("HOLD",):
            extra = [
                n
                for n in (
                    fsrules.clock_alert(now_ist),
                    fsrules.live_room_hold(live_decision, current_price, live_sl, live_t1),
                )
                if n
            ]
            safety_notes = fsrules.safety_entry_alerts(
                live_decision,
                session_ticket=prev_ticket,
                opening_range=orb,
                price=current_price,
                t1=live_t1,
                p_t1=(fno_head or {}).get("p_t1"),
                fresh_break=float(((fno_head or {}).get("features") or {}).get("first_break") or 0) >= 1.0,
                asof=now_ist,
            )
            fa = dict(result.get("fno_analysis") or {})
            notes = list(fa.get("desk_alerts") or [])
            alerts = list(fa.get("alerts") or [])
            for n in extra + safety_notes:
                if n not in notes:
                    notes.append(n)
                    alerts.append({"code": "desk_notice", "severity": "warning", "message": n})
            fa["desk_alerts"] = notes
            fa["alerts"] = alerts
            result["fno_analysis"] = fa
        import session_calls

        dual_entry = None
        dual_tags = None
        dual_view = None
        if isinstance(dual_call, dict):
            dual_entry = dual_call.get("entry")
            dual_tags = dual_call.get("accuracy_tags")
            dual_view = dual_call.get("model_view")
        readings = session_calls.live_readings(
            fno_head=fno_head,
            live_context=live_ctx,
            candlestick=enrichment.get("candlestick"),
            derivatives=deriv,
            news_delta=news_delta,
            vix_level=vix_level,
            setup_type=(result.get("fno_analysis") or {}).get("setup_type"),
            core_decision=decision_info.get("decision"),
        )
        listed_from_dual = (
            isinstance(dual_call, dict)
            and dual_call.get("decision") in ("BUY", "SELL")
            and not suppress_dual
        )
        if isinstance(readings, dict) and listed_from_dual:
            if dual_tags:
                readings["accuracy_tags"] = dual_tags
            if dual_view:
                readings["model_view"] = dual_view
                readings["p_sl"] = dual_view.get("p_sl")
            if stacked:
                fno_live_config.stamp_stack_dual_readings(
                    readings, dual_call=dual_call
                )
            else:
                readings["dual_track"] = True
                readings["track"] = dual_call.get("track") or "champion"
                readings["accuracy_label"] = dual_call.get("accuracy_label")
                readings["proven_100"] = dual_call.get("track") == "proven_100"
                readings["history_eligible"] = True
                track = str(dual_call.get("track") or "champion")
                readings["priority"] = (
                    100 if track == "proven_100" else (80 if track == "champion" else 60)
                )
                readings["source"] = track
                readings["live_confluence"] = False
        elif isinstance(readings, dict) and (not use_dual or stacked) and fno_live_config.is_fno_live_index(stock_key):
            fno_live_config.stamp_good_readings(readings, decision=live_decision)
        # FINAL accurate books (NIFTY P2F · SENSEX dual+fb ±50) — BANKNIFTY off
        if stock_key == "NIFTY" and (stacked or use_dual):
            try:
                import fno_p2f_live

                fno_p2f_live.annotate(
                    result,
                    symbol=stock_key,
                    dual_call=dual_call if isinstance(dual_call, dict) else None,
                    readings=readings if isinstance(readings, dict) else None,
                )
            except Exception as exc:
                result["p2f_live_error"] = str(exc)
        elif stock_key == "SENSEX" and (stacked or use_dual):
            try:
                import fno_sensex_final_live

                fno_sensex_final_live.annotate(
                    result,
                    symbol=stock_key,
                    dual_call=dual_call if isinstance(dual_call, dict) else None,
                    readings=readings if isinstance(readings, dict) else None,
                )
                if isinstance(dual_call, dict) and dual_call.get("decision") in ("BUY", "SELL"):
                    live_sl = dual_call.get("stop_loss", live_sl)
                    live_t1 = dual_call.get("target_1", live_t1)
            except Exception as exc:
                result["final_sensex_fno_error"] = str(exc)
        # Live confluence never lists. Index dual-track / other non-live paths still may.
        session_ticket = fsrules.persist_new_ticket(
            prev_ticket,
            decision=live_decision,
            stop_loss=live_sl,
            target_1=live_t1,
            taken_at=now_ist.isoformat(),
            session_date_value=now_ist.date(),
            entry=dual_entry
            if dual_entry is not None
            else (current_price if current_price is not None else tape_lv.get("entry")),
            target_2=trade.get("target_2"),
            p_t1=(
                (dual_call.get("p_t1") if isinstance(dual_call, dict) else None)
                or (fno_head or {}).get("p_t1")
            ),
            p_meta=(
                (dual_call.get("p_t1") if isinstance(dual_call, dict) else None)
                or ((fno_head or {}).get("p_meta") or (fno_head or {}).get("p_t1"))
            ),
            regime=((fno_head or {}).get("regime") or {}).get("name")
            or (dual_call or {}).get("regime"),
            readings=readings,
            symbol=stock_key,
            bars=fno_bars,
            live_quote=live_quote,
        )
        result["session_ticket"] = session_ticket
        try:
            result["session_tickets"] = session_calls.sync_session(
                KNOWLEDGE_DB_PATH,
                stock=stock_key,
                product="fno",
                session_ticket=session_ticket,
                extra={"source": "analyze"},
            )
        except Exception:
            result["session_tickets"] = session_calls.ticket_rows(session_ticket)
        split = session_calls.split_live(result.get("session_tickets"))
        result["active_call"] = split["active"]
        result["call_history"] = split["history"]
        try:
            import fno_live_archive

            fno_live_archive.maybe_record(
                stock=stock_key,
                fno_analysis=result.get("fno_analysis") or fno_block,
                price=current_price,
                active_call=split.get("active"),
                db_path=KNOWLEDGE_DB_PATH,
            )
        except Exception:
            pass
        fsrules.stamp_call_suggestion(
            result,
            fno_head,
            price=current_price,
            session_ticket=session_ticket,
            symbol=stock_key,
            bars=fno_bars,
            live_quote=live_quote,
            live_context=live_ctx,
            day_range=result.get("day_range_forecast") or enrichment.get("day_range_forecast"),
            asof=now_ist,
        )
        import fno_predictions

        fno_predictions.attach(result, stock_key, fno_bars, result.get("suggestion"), asof=now_ist)
        import fno_point_journal

        fno_point_journal.attach(result, stock_key, fno_bars, idf5, fno_head)
        try:
            fno_ws_rescore.attach_overlay_indication(
                result, stock_key, fno_bars, float(current_price or 0)
            )
        except Exception:
            pass
        if fno_live_config.is_fno_live_index(stock_key):
            # Live desk: dual proven/champion + 5m crown + 15m classic (pre-dual prod2);
            # daily_fill shadow/live via flags.
            try:
                import fno_5m_crown

                fno_5m_crown.attach_to_result(
                    result,
                    stock_key,
                    idf5,
                    bars_1m=None,
                    price=float(current_price or 0),
                    asof=now_ist,
                    day_range=result.get("day_range_forecast"),
                )
            except Exception as exc:
                result["crown_5m_error"] = str(exc)
            try:
                import fno_15m_classic

                fno_15m_classic.attach_to_result(
                    result,
                    stock_key,
                    fno_bars,
                    price=float(current_price or 0),
                    asof=now_ist,
                    fno_head=fno_head,
                    day_range=result.get("day_range_forecast"),
                )
            except Exception as exc:
                result["classic_15m_error"] = str(exc)
            try:
                import fno_daily_fill

                if fno_daily_fill.enabled():
                    fno_daily_fill.attach_to_result(
                        result,
                        stock_key,
                        fno_bars,
                        bars_5m=idf5,
                        price=float(current_price or 0),
                        asof=now_ist,
                        day_range=result.get("day_range_forecast"),
                    )
            except Exception as exc:
                result["daily_fill_error"] = str(exc)
            # 10m CHAMP / 5m crown → Calls board when 15m dual did not list.
            try:
                import fno_dual_modal_list

                session_ticket = fno_dual_modal_list.fill_from_channels(
                    result,
                    symbol=stock_key,
                    session_ticket=session_ticket,
                    bars=fno_bars,
                    live_quote=live_quote,
                    db_path=KNOWLEDGE_DB_PATH,
                    asof=now_ist,
                )
                result["session_ticket"] = session_ticket
                rows = session_calls.ticket_rows(session_ticket)
                split = session_calls.split_live(rows)
                result["session_tickets"] = split["all"]
                result["active_call"] = split["active"]
                result["call_history"] = split["history"]
            except Exception as exc:
                result["dual_modal_list_error"] = str(exc)
        import option_ticket

        set_analyze_progress(88, "Pricing the option", stock_key)
        # Prefer UI max_loss from this request body, else snapshot/default.
        option_ticket.attach_for_open_call(
            result,
            stock_key,
            split.get("active"),
            float(current_price or 0),
            max_loss_inr=option_ticket.resolve_max_loss_inr(),
        )
        try:
            session_calls.note_option(
                KNOWLEDGE_DB_PATH,
                stock=stock_key,
                product="fno",
                session_ticket=session_ticket,
                order=result.get("option_order"),
            )
        except Exception:
            pass
        try:
            import desktop_notify

            if isinstance(session_ticket, dict) and isinstance(result.get("option_order"), dict):
                readings = dict(session_ticket.get("readings") or {})
                if not readings.get("option") and result["option_order"].get("tradingsymbol"):
                    readings["option"] = result["option_order"]
                    session_ticket["readings"] = readings
            desktop_notify.notify_ticket_change(stock_key, ticket_before, session_ticket)
        except Exception:
            pass
        try:
            import kite_ticker

            kite_ticker.ensure_stream([stock_key])
        except Exception:
            pass
        fno_ws_rescore.save_snapshot(
            stock_key,
            {
                "ml_proba": ml_proba,
                "adj_tech": adj_tech,
                "combined_score": float(decision_info.get("combined_score") or 0.5),
                "combined_adjust": combined_adjust,
                "core_decision": decision_info.get("decision"),
                "anchored_decision": result.get("decision"),
                "opening_ticket": result.get("opening_ticket"),
                "anchored_setup_type": fno_block.get("setup_type"),
                "decision_info": decision_info,
                "candlestick": enrichment["candlestick"],
                "india_ctx": india_ctx if india_ctx.get("available") else None,
                "atr_val": atr_val,
                "microstructure": live_ctx.get("microstructure"),
                "micro_ts": time.time(),
                "fno_contracts": contracts,
                "structural": struct,
                "indicators": raw_indicators,
                "market_tilt": full_market_analysis.extra_horizon_tilt(market_pack),
                "day_range": result.get("day_range_forecast") or enrichment.get("day_range_forecast"),
                "fno_model": fno_head,
                "session_ticket": session_ticket,
                "last_pcr": deriv.get("pcr"),
                "gex": (deriv.get("gex") if isinstance(deriv.get("gex"), dict) else None),
                "derivatives": deriv,
                "bars_15m": fno_bars,
                "bars_5m": idf5,
                "bars_ts": time.time(),
                "news_delta": news_delta,
                "tape_read": result.get("tape_read"),
                "option_order": result.get("option_order"),
                "suggestion": result.get("suggestion"),
                "predictions": result.get("predictions"),
                "option_fp": fno_ws_rescore.option_fingerprint(
                    split.get("active"),
                    (result.get("option_order") or {}).get("max_loss_inr"),
                ),
                "price_samples": _pulse_snap.get("price_samples"),
                "volatility_pulse": _pulse_snap.get("volatility_pulse"),
            },
        )
    elif product == "intraday":
        bars_ok = None
        intraday_tech: Dict[str, Any] = {"available": False}
        blended_intraday = None
        idf = None
        idf15 = None
        if kite_data.kite_enabled() and live_market.is_live_eligible(stock_key, INDIAN_STOCKS):
            try:
                idf, _ierr = kite_data.fetch_historical_candles(stock_key, "5minute", days=3)
                idf15, _ = kite_data.fetch_historical_candles(stock_key, "15minute", days=10)
            except Exception:
                pass
        import intraday_session_model as ism
        pack = ism.load(symbol=stock_key)
        tape = idf15 if idf15 is not None and len(idf15) else idf
        session_head = ism.infer(tape, pack, symbol=stock_key) if tape is not None and len(tape) else {"available": False}
        confirm_dir = session_head.get("decision") if session_head.get("available") else decision_info["decision"]
        if idf is not None and len(idf) > 0:
            try:
                intraday_tech = intraday_engine.compute_intraday_technical(idf, "5minute")
                if "BUY" in str(confirm_dir):
                    bars_ok = product_analysis.intraday_5m_confirms(idf, True)
                    if intraday_tech.get("available"):
                        bars_ok = bars_ok and intraday_engine.intraday_score_confirms(confirm_dir, intraday_tech)
                elif "SELL" in str(confirm_dir):
                    bars_ok = product_analysis.intraday_5m_confirms(idf, False)
                    if intraday_tech.get("available"):
                        bars_ok = bars_ok and intraday_engine.intraday_score_confirms(confirm_dir, intraday_tech)
                if intraday_tech.get("available"):
                    intra_p = intraday_engine.intraday_probability_up(intraday_tech)
                    blended_intraday = round(
                        0.45 * float(decision_info.get("combined_score") or 0.5) + 0.55 * intra_p,
                        4,
                    )
            except Exception:
                bars_ok = None
        intra_block = product_analysis.build_intraday_analysis(
            stock_key,
            decision_info,
            ml_proba,
            adj_tech,
            enrichment["candlestick"],
            trading_gate,
            india_ctx if india_ctx.get("available") else None,
            intraday_bars_ok=bars_ok,
            intraday_tech=intraday_tech,
            blended_intraday_score=blended_intraday,
            session_model=session_head,
        )
        result["intraday_analysis"] = intra_block
        result["tape_read"] = _opening_tape_read(stock_key, idf15 if idf15 is not None else idf, enrichment.get("news_sentiment"))
        result["decision"] = intra_block["decision"]
        result["confidence"] = intra_block["confidence"]
        result["summary"] = intra_block["headline"]
        if intra_block.get("risk_reference"):
            result["risk_management"] = {
                **decision_info["risk_management"],
                "intraday_reference": intra_block["risk_reference"],
            }

    result["data_provenance"] = ui_provenance.build_data_provenance(
        symbol,
        stock_key,
        hist_source,
        live_quote,
        live_err,
        CACHE_DIR,
    )
    result["panel_hints"] = ui_provenance.build_panel_hints(
        stock_key,
        fund,
        struct,
        live_quote,
        live_err,
        result["knowledge_memory"],
        INDIAN_STOCKS,
    )
    result["validation"] = morning_job.validate_stock_analysis(result)

    # 11. Save to history + knowledge DB snapshot
    try:
        save_prediction(result)
        analysis_store.save_live_analysis(KNOWLEDGE_DB_PATH, result, product=product)
    except Exception:
        pass

    # 12. Generate chart (optional)
    try:
        chart_df = df_display.copy()
        chart_df["sma_50_raw"] = sma(df["Close"], 50)
        chart_df["sma_200_raw"] = sma(df["Close"], 200)
        chart_df["rsi_raw"] = rsi(df["Close"], 14)
        _, _, mh = macd(df["Close"])
        chart_df["macd_hist_raw"] = mh
        chart_path = generate_chart(chart_df, symbol, decision_info)
        if chart_path:
            result["chart_path"] = chart_path
            result["chart_url"] = f"/charts/{os.path.basename(chart_path)}"
    except Exception:
        pass

    # Print summary
    print(f"\n  >>> DECISION: {result['decision']}  (Confidence: {result['confidence']}%)")
    print(f"  >>> ML Probability Up: {ml_proba:.1%}  |  Technical Score: {tech_score:.0f}/100")
    print(f"  >>> Price: {current_price}  |  Stop Loss: {decision_info['risk_management']['stop_loss']}")
    print(f"  >>> Target 1: {decision_info['risk_management']['target_1']}  |  Target 2: {decision_info['risk_management']['target_2']}")

    return sanitize_for_json(result)


def _build_summary(decision_info, tech_score, ml_proba, metrics):
    """Build a human-readable summary string. """
    d = decision_info["decision"]
    parts = []

    if "BUY" in d:
        parts.append(f"Bullish signal detected. ")
    elif "SELL" in d:
        parts.append(f"Bearish signal detected. ")
    else:
        parts.append(f"Mixed/neutral signals. ")

    parts.append(f"ML model predicts {ml_proba:.1%} probability of upward movement")
    parts.append(f"(walk-forward accuracy: {metrics.get('walk_forward_accuracy', metrics['ensemble_accuracy']):.1%}, ")
    parts.append(f"high-confidence accuracy: {metrics.get('high_confidence_accuracy', 0):.1%}). ")
    parts.append(f"Technical score: {tech_score:.0f}/100. ")
    parts.append(f"Signal quality: {decision_info.get('signal_quality', 'MEDIUM')}. ")

    if decision_info.get("signals_agree") and decision_info.get("signal_quality") == "HIGH":
        parts.append("ML and technical indicators strongly agree — high-quality signal. ")
    elif decision_info.get("signals_agree"):
        parts.append("ML and technical indicators agree. ")
    else:
        parts.append("Signals diverge — wait for confirmation before trading. ")

    return " ".join(parts)


# ================================================================
# SECTION 12: FLASK API
# ================================================================

def bootstrap_kite_services() -> None:
    """Warm instrument cache, calendar, and WebSocket stream for watchlist."""
    if not kite_data.kite_enabled():
        return
    try:
        import kite_auth
        kite_auth.reload_access_token_from_env_file()
        kite_data.reset_client()
        import kite_calendar
        import kite_instruments
        import kite_ticker

        kite_calendar.ensure_loaded()
        ok, err = kite_instruments.ensure_cache()
        if not ok:
            print(f"  Kite instruments: {err or 'cache miss'}")
        else:
            print("  Kite instruments cache ready")
        import instrument_search

        if not instrument_search.catalog_ready():
            kite_instruments.refresh_instruments(force=True)
            if instrument_search.catalog_ready():
                print("  NSE symbol search catalog ready")
        symbols = [w["symbol"] for w in WATCHLIST]
        ok, err = kite_ticker.ensure_stream(symbols)
        if ok:
            print("  KiteTicker WebSocket started for watchlist")
        elif err and err not in ("disabled",):
            print(f"  KiteTicker: {err}")
    except Exception as exc:
        print(f"  Kite bootstrap: {exc}")


_morning_job_lock = threading.Lock()
_morning_job_state: Dict[str, Any] = {
    "running": False,
    "started_at": None,
    "finished_at": None,
    "error": None,
    "progress": None,
}
_analyze_lock = threading.Lock()
_analyze_progress: Dict[str, Any] = {
    "running": False,
    "pct": 0,
    "label": "",
    "stock": "",
}


def set_analyze_progress(pct: int, label: str, stock: str = "", running: bool = True) -> None:
    with _analyze_lock:
        _analyze_progress["running"] = running
        _analyze_progress["pct"] = max(0, min(100, int(pct)))
        _analyze_progress["label"] = label
        if stock:
            _analyze_progress["stock"] = stock


def _watchlist_rows(list_id: Optional[str] = None) -> List[Dict[str, str]]:
    import user_watchlists

    return user_watchlists.as_rows(BASE_DIR, [w["symbol"] for w in WATCHLIST], list_id)


def _morning_job_runner(
    refresh_news: bool,
    symbols: Optional[List[str]],
    force_retrain: bool,
    list_id: Optional[str] = None,
):
    global _morning_job_state

    def _progress(done: int, total: int, label: str) -> None:
        pct = 0 if not total else min(99, int(round(100 * done / total)))
        with _morning_job_lock:
            _morning_job_state["progress"] = {
                "done": done,
                "total": total,
                "pct": pct,
                "label": label,
            }

    try:
        with _morning_job_lock:
            _morning_job_state["running"] = True
            _morning_job_state["started_at"] = datetime.now().isoformat()
            _morning_job_state["error"] = None
            _morning_job_state["progress"] = {"done": 0, "total": 0, "pct": 0, "label": "Starting"}
        rows = _watchlist_rows(list_id)
        if symbols:
            rows = [{"symbol": s, "name": s, "sector": ""} for s in symbols]
        report = morning_job.run_morning_brief(
            predict_stock,
            rows,
            NEWS_DB_PATH,
            MORNING_REPORT_DIR,
            refresh_news=refresh_news,
            symbols=symbols,
            force_retrain=force_retrain,
            train_knowledge_if_empty=True,
            train_knowledge_fn=train_knowledge_base,
            knowledge_db_path=KNOWLEDGE_DB_PATH,
            progress_fn=_progress,
            cache_dir=CACHE_DIR,
            nifty_daily_path=os.path.join(BASE_DIR, "fno_validate", "NIFTY_daily_nse.csv"),
        )
        try:
            import daily_fno_train

            daily_fno_train.run_daily_train(db_path=KNOWLEDGE_DB_PATH, refresh_kite_days=0)
        except Exception:
            pass
        with _morning_job_lock:
            _morning_job_state["running"] = False
            _morning_job_state["finished_at"] = datetime.now().isoformat()
            _morning_job_state["progress"] = {
                "done": report.get("stocks_analyzed"),
                "total": report.get("stocks_analyzed"),
                "pct": 100,
                "label": "Done",
                "stocks_analyzed": report.get("stocks_analyzed"),
                "stocks_failed": report.get("stocks_failed"),
                "report_path": report.get("report_path"),
            }
    except Exception as exc:
        with _morning_job_lock:
            _morning_job_state["running"] = False
            _morning_job_state["error"] = str(exc)
            _morning_job_state["finished_at"] = datetime.now().isoformat()


def _cache_path(symbol):
    return _symbol_cache_path(symbol)


def create_api(engine_predict_fn):
    """Create Flask API application. """
    app = Flask(__name__)

    # All jsonify responses: NaN/Inf → null (browser JSON.parse is strict)
    try:
        from flask.json.provider import DefaultJSONProvider

        class _SafeJSONProvider(DefaultJSONProvider):
            def dumps(self, obj, **kwargs):
                kwargs.setdefault("allow_nan", False)
                clean = sanitize_for_json(obj)
                try:
                    return super().dumps(clean, **kwargs)
                except (ValueError, TypeError):
                    # Last resort: scrub again after default() conversions
                    return json.dumps(
                        sanitize_for_json(clean),
                        allow_nan=False,
                        default=str,
                    )

        app.json = _SafeJSONProvider(app)
    except Exception:
        pass

    @app.after_request
    def add_cors_headers(response):
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, DELETE, OPTIONS"
        return response

    @app.route("/health", methods=["GET"])
    def health():
        import kite_instruments

        kite = kite_data.get_provider_status()
        nfo = fno_instruments.get_status()
        inst = kite_instruments.get_status()
        return jsonify({
            "status": "ok",
            "version": MODEL_VERSION,
            "timestamp": datetime.now().isoformat(),
            "live_data": live_market.get_provider_status(),
            "kite_ready": bool(kite.get("ready")),
            "fno_platform": {
                "kite_ready": bool(kite.get("ready")),
                "instruments": inst,
                "nfo_cache": nfo,
            },
            "api_features": {
                "self_test": True,
                "india_market_context": True,
                "morning_global_v2": True,
                "fno_status": True,
            },
        })

    @app.route("/data/training-stats", methods=["GET"])
    def training_stats():
        return jsonify(get_training_stats())

    @app.route("/data/prefetch-watchlist", methods=["POST", "GET"])
    def prefetch_watchlist_route():
        force = request.args.get("force", "false").lower() in ("1", "true", "yes")
        years = request.args.get("years", DATA_YEARS, type=int)
        try:
            summary = prefetch_watchlist(force=force, years=years)
            return jsonify(summary)
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

    @app.route("/news", methods=["GET"])
    def news_list():
        symbol = request.args.get("symbol") or request.args.get("stock")
        limit = request.args.get("limit", 50, type=int)
        item_type = request.args.get("type")
        include_market = request.args.get("include_market", "true").lower() not in ("0", "false", "no")
        items = news_data.get_news(
            NEWS_DB_PATH,
            symbol=symbol,
            limit=limit,
            item_type=item_type,
            include_market=include_market,
        )
        return jsonify({
            "count": len(items),
            "symbol": symbol.upper() if symbol else None,
            "items": items,
        })

    @app.route("/news/stats", methods=["GET"])
    def news_stats_route():
        return jsonify(news_data.get_news_stats(NEWS_DB_PATH))

    @app.route("/news/prefetch-watchlist", methods=["POST", "GET"])
    def news_prefetch_route():
        years = request.args.get("years", DATA_YEARS, type=float)
        quick = request.args.get("quick", "false").lower() in ("1", "true", "yes")
        max_months = 3 if quick else None
        try:
            summary = news_data.prefetch_watchlist_news(
                NEWS_DB_PATH,
                WATCHLIST,
                years=years,
                include_market_headlines=True,
                max_months_per_symbol=max_months,
            )
            return jsonify(summary)
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

    def _morning_removed():
        return jsonify({
            "error": "Morning job removed — use Stocks / F&O / Scalper",
            "removed": True,
        }), 410

    @app.route("/morning/global", methods=["GET"])
    def morning_global():
        return _morning_removed()

    @app.route("/market/india-context", methods=["GET"])
    def market_india_context():
        try:
            return api_json(india_market_context.fetch_india_market_context())
        except Exception as exc:
            return api_json({"available": False, "error": str(exc)}, 503)

    @app.route("/backtest/<stock>", methods=["GET"])
    def backtest_route(stock):
        holdout = request.args.get("holdout", "2025-01-01")
        years = request.args.get("years", DATA_YEARS, type=int)
        key = stock.strip().upper()
        symbol = resolve_symbol(key)
        try:
            df = download_data(symbol, years=years, stock_key=key)
            summary, err = backtest.run_holdout_backtest(
                df,
                compute_all_features,
                build_training_data,
                train_models,
                holdout,
                TARGET_MIN_RETURN,
            )
            if err:
                return jsonify({"error": err, "stock": key}), 400
            return jsonify({"stock": key, "symbol": symbol, "backtest": summary})
        except Exception as exc:
            return jsonify({"error": str(exc), "stock": key}), 500

    @app.route("/self-test", methods=["GET"])
    def self_test():
        checks: List[Dict[str, Any]] = []

        def record(name: str, passed: bool, detail: str = "") -> None:
            checks.append({"name": name, "passed": bool(passed), "detail": detail})

        record("sanitize_bool", isinstance(sanitize_for_json({"x": np.bool_(True)})["x"], bool))
        try:
            json.dumps(sanitize_for_json({"nested": [np.float64(1.5)]}))
            record("json_dumps", True)
        except Exception as exc:
            record("json_dumps", False, str(exc))

        try:
            ctx = india_market_context.fetch_india_market_context()
            partial = bool(
                ctx.get("available")
                or (ctx.get("india_vix") or {}).get("available")
                or (ctx.get("nifty_open_proxy") or {}).get("available")
            )
            record("india_market_context", partial, ctx.get("bias", ""))
        except Exception as exc:
            record("india_market_context", False, str(exc))

        try:
            panel = analysis_engine.fetch_global_overnight_panel()
            record("overnight_panel", panel.get("available"), panel.get("bias", ""))
        except Exception as exc:
            record("overnight_panel", False, str(exc))

        if os.path.exists(NEWS_DB_PATH):
            try:
                ns = news_data.get_news_stats(NEWS_DB_PATH)
                record("news_db", ns.get("total_items", 0) > 0, f"items={ns.get('total_items')}")
            except Exception as exc:
                record("news_db", False, str(exc))
        else:
            record("news_db", False, "missing news.db")

        if os.path.exists(KNOWLEDGE_DB_PATH):
            try:
                ks = pattern_memory.get_knowledge_stats(KNOWLEDGE_DB_PATH)
                record("knowledge_db", True, f"rules={ks.get('learned_rules')}")
            except Exception as exc:
                record("knowledge_db", False, str(exc))
        else:
            record("knowledge_db", False, "missing knowledge.db")

        passed = all(c["passed"] for c in checks)
        return api_json({
            "passed": passed,
            "checks": checks,
            "timestamp": datetime.now().isoformat(),
            "disclaimer": "Smoke checks only — run Analyze on RELIANCE pre-market for full path.",
        })

    @app.route("/morning/latest", methods=["GET"])
    def morning_latest():
        return _morning_removed()

    @app.route("/morning/status", methods=["GET"])
    def morning_status():
        return _morning_removed()

    @app.route("/morning/run", methods=["POST", "GET"])
    def morning_run():
        return _morning_removed()

    @app.route("/data/kite-capabilities", methods=["GET"])
    def kite_capabilities():
        return jsonify(kite_data.get_api_capabilities())

    @app.route("/kite/auth/status", methods=["GET"])
    def kite_auth_status():
        import kite_auth as ka

        token = os.environ.get("KITE_ACCESS_TOKEN", "").strip()
        valid = ka.validate_access_token(token) if token else False
        st = ka.get_auth_status()
        st["access_token_valid"] = valid
        return jsonify(st)

    @app.route("/kite/auth/login-url", methods=["GET"])
    def kite_auth_login_url():
        import kite_auth as ka

        key = os.environ.get("KITE_API_KEY", "").strip()
        if not key:
            return jsonify({"error": "KITE_API_KEY not set in .env"}), 400
        return jsonify({
            "login_url": ka.kite_connect_login_url(key),
            "redirect_url": os.environ.get("KITE_REDIRECT_URL", "http://127.0.0.1/"),
            "paste_hint": "After login, copy the full redirect URL and POST /kite/auth/exchange with {\"request_token\": \"...\"} or run: python kite_login.py --paste",
        })

    @app.route("/kite/auth/refresh", methods=["POST", "GET"])
    def kite_auth_refresh():
        import kite_auth as ka

        access, err = ka.get_access_token(force_refresh=True)
        if access:
            kite_data.reset_client()
            return jsonify({"ok": True, "message": "Kite access token refreshed", "auth": ka.get_auth_status()})
        key = os.environ.get("KITE_API_KEY", "").strip()
        return jsonify({
            "ok": False,
            "error": err,
            "auto_login_configured": ka.auto_login_configured(),
            "login_url": ka.kite_connect_login_url(key) if key else None,
            "manual": "Run: python kite_login.py --paste  (paste redirect URL after browser login)",
        }), 503

    @app.route("/kite/auth/exchange", methods=["POST"])
    def kite_auth_exchange():
        import kite_auth as ka

        data = request.get_json(silent=True) or {}
        raw = (data.get("request_token") or data.get("url") or "").strip()
        if not raw:
            return jsonify({"error": "Send JSON: {\"url\": \"<full redirect URL>\"} or {\"request_token\": \"...\"}"}), 400
        tok = ka.extract_request_token(raw)
        if not tok:
            return jsonify({"error": "Could not parse request_token"}), 400
        access, err = ka.exchange_request_token(tok)
        if err:
            return jsonify({"ok": False, "error": err}), 400
        kite_data.reset_client()
        return jsonify({"ok": True, "message": "KITE_ACCESS_TOKEN saved to .env", "auth": ka.get_auth_status()})

    @app.route("/kite/instruments/refresh", methods=["POST", "GET"])
    def kite_instruments_refresh():
        import kite_instruments

        force = request.args.get("force", "false").lower() in ("1", "true", "yes")
        ok, err = kite_instruments.refresh_instruments(force=force)
        if not ok:
            return jsonify({"ok": False, "error": err, "status": kite_instruments.get_status()}), 503
        return jsonify({"ok": True, "status": kite_instruments.get_status()})

    @app.route("/kite/calendar", methods=["GET"])
    def kite_calendar_route():
        import kite_calendar

        return jsonify(kite_calendar.get_status())

    @app.route("/kite/calendar/refresh", methods=["POST", "GET"])
    def kite_calendar_refresh():
        import kite_calendar

        return jsonify(kite_calendar.refresh_calendar(force_nse=True))

    @app.route("/kite/stream/status", methods=["GET"])
    def kite_stream_status():
        import kite_ticker

        return jsonify(kite_ticker.get_status())

    @app.route("/kite/stream/start", methods=["POST", "GET"])
    def kite_stream_start():
        import kite_ticker

        raw = request.args.get("symbols", "")
        keys = [s.strip().upper() for s in raw.split(",") if s.strip()]
        if not keys:
            keys = [w["symbol"] for w in WATCHLIST]
        force = request.args.get("force", "false").lower() in ("1", "true", "yes")
        ok, err = kite_ticker.start_stream(keys, force=force)
        if not ok:
            return jsonify({"ok": False, "error": err}), 503
        return jsonify({"ok": True, "status": kite_ticker.get_status()})

    @app.route("/kite/stream/ltp", methods=["GET"])
    def kite_stream_ltp():
        import kite_ticker

        raw = request.args.get("symbols", "")
        keys = [s.strip().upper() for s in raw.split(",") if s.strip()]
        if not keys:
            keys = [w["symbol"] for w in WATCHLIST]
        return jsonify({
            "ltp": kite_ticker.get_ltps(keys),
            "status": kite_ticker.get_status(),
            "timestamp": datetime.now().isoformat(),
        })

    @app.route("/kite/trading/status", methods=["GET"])
    def kite_trading_status_route():
        import kite_trading

        return jsonify(kite_trading.trading_status())

    @app.route("/kite/profile", methods=["GET"])
    def kite_profile_route():
        import kite_trading

        data, err = kite_trading.get_profile()
        if err:
            return jsonify({"error": err}), 503
        return jsonify(data)

    @app.route("/kite/margins", methods=["GET"])
    def kite_margins_route():
        import kite_trading

        segment = request.args.get("segment")
        data, err = kite_trading.get_margins(segment)
        if err:
            return jsonify({"error": err}), 503
        return jsonify(data)

    @app.route("/kite/holdings", methods=["GET"])
    def kite_holdings_route():
        import kite_trading

        data, err = kite_trading.get_holdings()
        if err:
            return jsonify({"error": err}), 503
        return jsonify({"holdings": data})

    @app.route("/kite/positions", methods=["GET"])
    def kite_positions_route():
        import kite_trading

        data, err = kite_trading.get_positions()
        if err:
            return jsonify({"error": err}), 503
        return jsonify(data)

    @app.route("/kite/orders", methods=["GET"])
    def kite_orders_list():
        import kite_trading

        data, err = kite_trading.list_orders()
        if err:
            return jsonify({"error": err}), 503
        return jsonify({"orders": data})

    @app.route("/kite/orders", methods=["POST"])
    def kite_orders_place():
        import kite_trading

        payload = request.get_json(silent=True) or {}
        dry = payload.get("dry_run", True)
        if isinstance(dry, str):
            dry = dry.lower() not in ("0", "false", "no")
        data, err = kite_trading.place_order(payload, dry_run=bool(dry))
        if err:
            return jsonify({"error": err}), 400
        return jsonify(data)

    @app.route("/kite/gtt", methods=["GET"])
    def kite_gtt_list():
        import kite_trading

        data, err = kite_trading.list_gtts()
        if err:
            return jsonify({"error": err}), 503
        return jsonify({"gtts": data})

    @app.route("/kite/gtt", methods=["POST"])
    def kite_gtt_place():
        import kite_trading

        payload = request.get_json(silent=True) or {}
        dry = payload.pop("dry_run", True)
        data, err = kite_trading.place_gtt(payload, dry_run=bool(dry))
        if err:
            return jsonify({"error": err}), 400
        return jsonify(data)

    @app.route("/kite/gtt/<int:trigger_id>", methods=["DELETE"])
    def kite_gtt_delete(trigger_id):
        import kite_trading

        dry = request.args.get("dry_run", "true").lower() not in ("0", "false", "no")
        data, err = kite_trading.delete_gtt(trigger_id, dry_run=dry)
        if err:
            return jsonify({"error": err}), 400
        return jsonify(data)

    @app.route("/data/status", methods=["GET"])
    def data_status():
        kite = kite_data.get_provider_status()
        hist = "kite_connect" if kite.get("ready") else "yahoo_finance"
        if kite.get("ready"):
            hist += " (Indian EOD; set KITE_YAHOO_FALLBACK=1 for Yahoo backup on Kite errors)"
        return jsonify({
            "historical_eod": hist,
            "live_quotes": live_market.get_provider_status(),
            "analysis_modes": ["auto", "premarket", "intraday"],
            "kite_capabilities": "/data/kite-capabilities",
        })

    @app.route("/live/<stock>", methods=["GET"])
    def live_quote_route(stock):
        key = stock.strip().upper()
        if not live_market.is_live_eligible(key, INDIAN_STOCKS):
            return jsonify({
                "error": "Live quotes support Indian watchlist symbols (e.g. RELIANCE, NIFTY).",
                "stock": key,
            }), 400
        quote, err = live_market.fetch_live_quote(key, INDIAN_STOCKS)
        if err and not quote:
            return jsonify({"error": err, "stock": key}), 503
        out = dict(quote or {})
        if product_analysis.is_fno_primary(key) and out.get("last_price") is not None:
            try:
                snap = fno_ws_rescore.get_snapshot(key) or {}
                pulse = fno_ws_rescore.update_volatility_pulse(
                    snap,
                    key,
                    float(out["last_price"]),
                    ts=out.get("received_at_ist"),
                    india_ctx=snap.get("india_ctx"),
                )
                fno_ws_rescore.save_snapshot(key, snap)
                out["volatility_pulse"] = pulse
            except Exception:
                pass
        return jsonify(out if out else {"error": err})

    @app.route("/live", methods=["GET"])
    def live_batch():
        raw = request.args.get("symbols", "")
        keys = [s.strip().upper() for s in raw.split(",") if s.strip()]
        if not keys:
            keys = [w["symbol"] for w in WATCHLIST]
        keys = [k for k in keys if live_market.is_live_eligible(k, INDIAN_STOCKS)][:50]
        ltps, err = live_market.fetch_live_ltp(keys, INDIAN_STOCKS)
        prov = live_market.get_provider_status()
        return jsonify({
            "count": len(ltps),
            "ltp": ltps,
            "error": err,
            "mode": prov.get("mode", "free"),
            "primary": prov.get("primary"),
            "timestamp": datetime.now().isoformat(),
        })

    @app.route("/predict", methods=["POST", "OPTIONS"])
    def predict():
        if request.method == "OPTIONS":
            return "", 204
        data = request.get_json(silent=True)
        if not data or "stock" not in data:
            return jsonify({"error": "Missing 'stock' in request body. Example: {\"stock\": \"RELIANCE\"}"}), 400

        stock = data["stock"]
        force = data.get("force_retrain", False)
        mode = data.get("mode")
        if mode in ("auto", "", None):
            mode = None

        try:
            set_analyze_progress(5, "Starting", stock)
            result = engine_predict_fn(stock, force_retrain=force, mode=mode)
            set_analyze_progress(100, "Done", stock, running=False)
            return api_json(result)
        except Exception as e:
            set_analyze_progress(100, "Stopped", stock, running=False)
            return jsonify({"error": str(e), "stock": stock}), 500

    @app.route("/predict/fno", methods=["POST", "OPTIONS"])
    def predict_fno():
        if request.method == "OPTIONS":
            return "", 204
        data = request.get_json(silent=True)
        if not data or "stock" not in data:
            return jsonify({"error": "Missing 'stock'. Example: {\"stock\": \"NIFTY\"}"}), 400
        stock = data["stock"]
        force = data.get("force_retrain", False)
        mode = data.get("mode")
        if mode in ("auto", "", None):
            mode = None
        try:
            if data.get("fast"):
                raw_ml = data.get("max_loss")
                try:
                    fast_max_loss = float(raw_ml) if raw_ml is not None else None
                    if fast_max_loss is not None and fast_max_loss <= 0:
                        fast_max_loss = None
                except (TypeError, ValueError):
                    fast_max_loss = None
                result, err = fno_ws_rescore.scheduled_refresh(
                    stock, INDIAN_STOCKS, max_loss_inr=fast_max_loss
                )
                if err or result is None:
                    return jsonify({"error": err or "F&O refresh failed", "stock": stock}), 400
                return api_json(result)
            set_analyze_progress(5, "Starting", stock)
            result = engine_predict_fn(stock, force_retrain=force, mode=mode, product="fno")
            set_analyze_progress(100, "Done", stock, running=False)
            return api_json(result)
        except Exception as e:
            set_analyze_progress(100, "Stopped", stock, running=False)
            return jsonify({"error": str(e), "stock": stock}), 500

    @app.route("/predict/fno/live-signal", methods=["POST", "OPTIONS"])
    def predict_fno_live_signal():
        """Fresh session + 5m/15m read (no full ML retrain). Pair with periodic /predict/fno refresh."""
        if request.method == "OPTIONS":
            return "", 204
        data = request.get_json(silent=True) or {}
        stock = (data.get("stock") or "").strip().upper()
        if not stock:
            return jsonify({"error": "Missing stock"}), 400
        live_quote, err = None, None
        if live_market.is_live_eligible(stock, INDIAN_STOCKS):
            live_quote, err = live_market.fetch_live_quote(stock, INDIAN_STOCKS)
        idf5, idf15 = None, None
        if kite_data.kite_enabled() and live_market.is_live_eligible(stock, INDIAN_STOCKS):
            idf5, _ = kite_data.fetch_historical_candles(stock, "5minute", days=2)
            idf15, _ = kite_data.fetch_historical_candles(stock, "15minute", days=2)
        ctx = fno_live_engine.build_fno_live_context(
            live_quote,
            idf5,
            idf15,
            float(data.get("ml_proba") or 0.5),
            float(data.get("tech_score") or 50),
            float(data.get("combined_score") or 0.5),
            str(data.get("core_decision") or "HOLD"),
        )
        return api_json({
            "stock": stock,
            "live_market": live_quote or {"available": False, "error": err},
            "live_context": ctx,
            "timestamp": datetime.now().isoformat(),
        })

    @app.route("/predict/fno/ws-rescore", methods=["POST", "OPTIONS"])
    def predict_fno_ws_rescore():
        """Fast F&O refresh: WebSocket LTP + cached swing snapshot (no ML retrain). ~15s polling."""
        if request.method == "OPTIONS":
            return "", 204
        data = request.get_json(silent=True) or {}
        stock = (data.get("stock") or "").strip().upper()
        if not stock:
            return jsonify({"error": "Missing stock"}), 400
        try:
            payload, err = fno_ws_rescore.rescore_from_websocket(stock, INDIAN_STOCKS)
            if err or not payload:
                return jsonify({"error": err or "rescore failed", "stock": stock}), 404
            return api_json(payload)
        except Exception as exc:
            return jsonify({"error": str(exc), "stock": stock}), 500

    @app.route("/predict/intraday", methods=["POST", "OPTIONS"])
    def predict_intraday():
        if request.method == "OPTIONS":
            return "", 204
        return jsonify({
            "error": "Intraday product removed — use Stocks (/predict) or F&O (/predict/fno)",
            "removed": True,
        }), 410

    @app.route("/fno/universe", methods=["GET", "POST", "OPTIONS"])
    def fno_universe_route():
        import fno_universe

        if request.method == "OPTIONS":
            return "", 204
        if request.method == "POST":
            sym = ((request.get_json(silent=True) or {}).get("symbol") or "").strip().upper()
            ok, err = fno_universe.add(sym)
            if not ok:
                return jsonify({"error": err, "symbol": sym}), 400
        return jsonify({
            "symbols": fno_universe.status(),
            "stock_fno_universe": sorted(product_analysis.FNO_STOCK_UNIVERSE),
        })

    @app.route("/fno/universe/<symbol>", methods=["DELETE", "OPTIONS"])
    def fno_universe_remove(symbol):
        import fno_universe

        if request.method == "OPTIONS":
            return "", 204
        ok, err = fno_universe.remove(symbol)
        if not ok:
            return jsonify({"error": err, "symbol": symbol.upper()}), 400
        return jsonify({"symbols": fno_universe.status()})

    @app.route("/session-calls", methods=["GET"])
    def session_calls_list():
        import session_calls

        stock = (request.args.get("stock") or request.args.get("symbol") or "").strip().upper()
        day = request.args.get("date")
        product = (request.args.get("product") or "fno").strip().lower()
        try:
            rows = session_calls.list_calls(KNOWLEDGE_DB_PATH, stock or None, day, product)
            if str(request.args.get("recent") or "").strip() in ("1", "true", "yes"):
                rows = session_calls.list_recent(KNOWLEDGE_DB_PATH, stock or None, product, limit=40)
            split = session_calls.split_live(rows)
        except Exception as exc:
            return jsonify({
                "stock": stock or None,
                "date": (day or "")[:10],
                "product": product,
                "calls": [],
                "active_call": None,
                "call_history": [],
                "error": str(exc),
            })
        return jsonify({
            "stock": stock or None,
            "date": (day or "")[:10],
            "product": product,
            "calls": split["all"],
            "active_call": split["active"],
            "call_history": split["history"],
        })

    @app.route("/overlay-indication-calls", methods=["GET"])
    def overlay_indication_calls_list():
        """Retired — overlay indication channel removed (dual accurate only)."""
        stock = (request.args.get("stock") or request.args.get("symbol") or "NIFTY").strip().upper()
        return jsonify({
            "stock": stock,
            "today": [],
            "history": [],
            "open": [],
            "disabled": True,
            "note": "Overlay indication removed. Desk calls = dual proven/champion only.",
        })

    @app.route("/history", methods=["GET"])
    def history():
        stock = request.args.get("stock", None)
        limit = request.args.get("limit", 50, type=int)
        records = get_prediction_history(stock, limit)
        return jsonify({"count": len(records), "predictions": records})

    @app.route("/symbols", methods=["GET"])
    def symbols():
        return jsonify({
            "indian_stocks": INDIAN_STOCKS,
            "crypto": CRYPTO_MAP,
            "watchlist": WATCHLIST,
            "usage": "Pass any key as the 'stock' parameter, or use Yahoo Finance symbol directly",
            "examples": ["RELIANCE", "HDFCBANK", "AAPL", "BTC", "MSFT", "TCS"],
        })

    @app.route("/analyze/progress", methods=["GET"])
    def analyze_progress():
        with _analyze_lock:
            return jsonify(dict(_analyze_progress))

    @app.route("/kite/callback", methods=["GET"])
    def kite_callback():
        import kite_auth as ka

        raw = (request.args.get("request_token") or "").strip()
        if not raw and request.query_string:
            raw = request.query_string.decode("utf-8", errors="ignore")
        tok = ka.extract_request_token(raw) if raw and "request_token=" in raw else raw
        if not tok:
            return redirect("/dashboard?login=1")
        access, err = ka.exchange_request_token(tok)
        kite_data.reset_client()
        if err or not access:
            return redirect("/dashboard?login=1")
        return redirect("/dashboard")

    def _watch_defaults() -> List[str]:
        return [w["symbol"] for w in WATCHLIST]

    @app.route("/watchlists", methods=["GET"])
    def watchlists_get():
        import user_watchlists

        return jsonify(user_watchlists.public_view(BASE_DIR, _watch_defaults()))

    @app.route("/watchlists", methods=["POST"])
    def watchlists_create():
        import user_watchlists

        data = request.get_json(silent=True) or {}
        try:
            view = user_watchlists.create_list(BASE_DIR, _watch_defaults(), data.get("name") or "")
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify(view)

    @app.route("/watchlists/active", methods=["POST"])
    def watchlists_active():
        import user_watchlists

        data = request.get_json(silent=True) or {}
        try:
            view = user_watchlists.set_active(BASE_DIR, _watch_defaults(), str(data.get("id") or ""))
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify(view)

    @app.route("/watchlists/<list_id>", methods=["DELETE"])
    def watchlists_delete(list_id):
        import user_watchlists

        try:
            view = user_watchlists.delete_list(BASE_DIR, _watch_defaults(), list_id)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify(view)

    @app.route("/instruments/search", methods=["GET"])
    def instruments_search():
        import instrument_search

        q = request.args.get("q") or request.args.get("query") or ""
        scope = (request.args.get("scope") or "").strip().lower()
        try:
            limit = int(request.args.get("limit") or 12)
        except (TypeError, ValueError):
            limit = 12
        if scope in ("scalper", "options", "fno_scalper"):
            market = (request.args.get("market") or "india").strip().lower()
            if market == "crypto":
                import binance_data

                return jsonify(binance_data.search_crypto(q, limit=limit))
            import fno_scalper_symbol

            return jsonify(fno_scalper_symbol.search_scalper(q, limit=limit))
        if q.strip() and not instrument_search.catalog_ready():
            instrument_search.ensure_catalog()
        return jsonify(instrument_search.search(q, limit=limit))

    @app.route("/watchlists/<list_id>/symbols", methods=["POST"])
    def watchlists_add_symbol(list_id):
        import instrument_search
        import user_watchlists

        data = request.get_json(silent=True) or {}
        raw = data.get("symbol") or ""
        key = instrument_search.resolve_addable_symbol(raw)
        if not key:
            hint = instrument_search.search("", limit=1).get("hint")
            return jsonify(
                {
                    "error": "Pick a symbol from the NSE list. Options (calls and puts) are not added here.",
                    "hint": hint,
                }
            ), 400
        try:
            view = user_watchlists.add_symbol(BASE_DIR, _watch_defaults(), list_id, key)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify(view)

    @app.route("/watchlists/<list_id>/symbols/<symbol>", methods=["DELETE"])
    def watchlists_remove_symbol(list_id, symbol):
        import user_watchlists

        try:
            view = user_watchlists.remove_symbol(BASE_DIR, _watch_defaults(), list_id, symbol)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify(view)

    @app.route("/watchlist", methods=["GET"])
    def watchlist():
        import user_watchlists

        rows = user_watchlists.as_rows(BASE_DIR, _watch_defaults())
        return jsonify({"count": len(rows), "stocks": rows})

    @app.route("/models/train-watchlist", methods=["POST", "GET"])
    def train_watchlist_route():
        force = request.args.get("force", "false").lower() in ("1", "true", "yes")
        sym_raw = request.args.get("symbols", "")
        sym_list = [s.strip() for s in sym_raw.split(",") if s.strip()] or None
        try:
            return jsonify(train_watchlist_models(force_retrain=force, symbols=sym_list))
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

    @app.route("/knowledge/train", methods=["POST", "GET"])
    def knowledge_train_route():
        try:
            return jsonify(train_knowledge_base())
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

    @app.route("/knowledge/stats", methods=["GET"])
    def knowledge_stats_route():
        stats = pattern_memory.get_knowledge_stats(KNOWLEDGE_DB_PATH)
        stats["analysis_store"] = analysis_store.analysis_stats(KNOWLEDGE_DB_PATH)
        try:
            import training_store

            stats["training_store"] = training_store.range_accuracy_summary(
                KNOWLEDGE_DB_PATH, last_days=14
            )
        except Exception as exc:
            stats["training_store_error"] = str(exc)
        return jsonify(stats)

    @app.route("/training/range-accuracy", methods=["GET"])
    def training_range_accuracy():
        import training_store

        days = request.args.get("days", 7, type=int)
        return jsonify(training_store.range_accuracy_summary(KNOWLEDGE_DB_PATH, last_days=days))

    @app.route("/training/agent", methods=["GET"])
    def training_agent_status():
        import background_agent

        return jsonify(background_agent.agent_state())

    @app.route("/training/backfill-morning", methods=["POST", "GET"])
    def training_backfill_morning():
        return jsonify({"error": "Morning training removed", "removed": True}), 410

    @app.route("/training/score-morning", methods=["POST", "GET"])
    def training_score_morning():
        return jsonify({"error": "Morning training removed", "removed": True}), 410

    @app.route("/training/daily-fno-train", methods=["POST", "GET"])
    def training_daily_fno():
        import daily_fno_train

        refresh = request.args.get("refresh_kite_days", 0, type=int)
        return jsonify(daily_fno_train.run_daily_train(refresh_kite_days=refresh, db_path=KNOWLEDGE_DB_PATH))

    @app.route("/audit/latest", methods=["GET"])
    def audit_latest_route():
        stock = request.args.get("stock", "").strip().upper() or None
        runs = analysis_store.get_audit_summary(KNOWLEDGE_DB_PATH, stock=stock, limit=3)
        return jsonify({"runs": runs})

    @app.route("/audit/run", methods=["POST", "GET"])
    def audit_run_route():
        holdout = request.args.get("holdout", "2024-01-01")
        step = request.args.get("step_days", 1, type=int)
        sym = request.args.get("stock", "").strip().upper()
        syms = [sym] if sym else None
        try:
            summary = run_audit_watchlist(
                holdout_start=holdout,
                step_days=max(1, step),
                symbols=syms,
            )
            return jsonify(summary)
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

    @app.route("/analysis/snapshot/<stock>", methods=["GET"])
    def analysis_snapshot_route(stock):
        day = request.args.get("date")
        mode = request.args.get("mode", "auto")
        snap = analysis_store.get_live_snapshot(
            KNOWLEDGE_DB_PATH, stock, as_of_date=day, analysis_mode=mode
        )
        if not snap:
            return jsonify({"error": "No snapshot", "stock": stock.upper()}), 404
        return jsonify(snap)

    @app.route("/knowledge/rules", methods=["GET"])
    def knowledge_rules_route():
        limit = request.args.get("limit", 50, type=int)
        if not os.path.exists(KNOWLEDGE_DB_PATH):
            return jsonify({"rules": []})
        conn = sqlite3.connect(KNOWLEDGE_DB_PATH)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM learned_rules ORDER BY updated_at DESC LIMIT ?",
            (max(1, min(limit, 200)),),
        ).fetchall()
        conn.close()
        return jsonify({"count": len(rows), "rules": [dict(r) for r in rows]})

    @app.route("/research/chart-overlays/<stock>", methods=["GET"])
    def research_chart_overlays(stock):
        """Candles + S/R/range/desk overlays for visual validation (never lists Calls).

        Query:
          interval — minute | 5minute | 15minute (default 15minute)
          sessions — last N trading sessions
          live=1 — prefer Kite, else local tape
          bars — legacy tape window when sessions omitted (15m only)
        """
        key = (stock or "").strip().upper()
        import fno_live_config

        if not fno_live_config.is_fno_live_index(key):
            return jsonify({"error": "NIFTY or SENSEX only"}), 400
        raw_iv = str(request.args.get("interval") or "15minute").strip().lower()
        if raw_iv in ("minute", "1m", "1minute"):
            interval = "minute"
            default_sessions = 5
        elif raw_iv in ("5minute", "5m"):
            interval = "5minute"
            default_sessions = 8
        else:
            interval = "15minute"
            default_sessions = 15
        try:
            sessions = int(request.args.get("sessions") or default_sessions)
        except (TypeError, ValueError):
            sessions = default_sessions
        sessions = max(1, min(sessions, 30 if interval == "15minute" else 15))
        try:
            bars = int(request.args.get("bars") or 0)
        except (TypeError, ValueError):
            bars = 0
        live = str(request.args.get("live") or "1").strip().lower() in ("1", "true", "yes")

        def _load_mod():
            try:
                from tools.research import research_15m_chart_pack as pack_mod

                return pack_mod
            except Exception:
                import importlib.util

                # Repo root tools/research (NOT app/api/tools/...)
                root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
                path = os.path.join(root, "tools", "research", "research_15m_chart_pack.py")
                if not os.path.isfile(path):
                    raise FileNotFoundError(
                        f"research_15m_chart_pack missing at {path}"
                    )
                spec = importlib.util.spec_from_file_location("research_15m_chart_pack", path)
                mod = importlib.util.module_from_spec(spec)
                assert spec and spec.loader
                spec.loader.exec_module(mod)
                return mod

        try:
            mod = _load_mod()
            if live and hasattr(mod, "build_live_pack"):
                return jsonify(
                    mod.build_live_pack(key, sessions=sessions, interval=interval)
                )
            if interval != "15minute":
                return jsonify(
                    mod.build_live_pack(key, sessions=sessions, interval=interval)
                )
            if bars > 0:
                return jsonify(mod.build_pack(key, n_bars=max(40, min(bars, 400))))
            return jsonify(mod.build_pack(key, sessions=sessions))
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

    @app.route("/ohlcv/<stock>", methods=["GET"])
    def ohlcv(stock):
        stock_key = stock.strip().upper()
        interval = (request.args.get("interval") or "day").lower()
        limit = int(request.args.get("limit", 120))
        days = int(request.args.get("days", 5))

        if interval not in ("day", "daily", "1d"):
            if not kite_data.kite_enabled():
                return jsonify({"error": "Intraday OHLCV requires Kite Connect", "stock": stock_key}), 503
            if interval not in ("minute", "3minute", "5minute", "10minute", "15minute", "30minute", "60minute"):
                return jsonify({"error": f"Unsupported interval {interval}"}), 400
            # Kite caps long 1m history; keep minute windows tighter
            day_cap = 60 if interval == "15minute" else (12 if interval == "minute" else 30)
            df, err = kite_data.fetch_historical_candles(
                stock_key, interval=interval, days=max(1, min(days, day_cap)), keep_partial=True,
            )
            if err or df is None:
                return jsonify({"error": err or "No data", "stock": stock_key}), 404
            tail = df.tail(limit)
            candles = []
            try:
                from zoneinfo import ZoneInfo

                _ist = ZoneInfo("Asia/Kolkata")
            except Exception:
                _ist = None
            for idx, row in tail.iterrows():
                ts = idx
                if hasattr(ts, "timestamp"):
                    dt = ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else ts
                    if getattr(dt, "tzinfo", None) is None and _ist is not None:
                        dt = dt.replace(tzinfo=_ist)
                    time_val = int(dt.timestamp())
                else:
                    time_val = str(ts)
                candles.append({
                    "time": time_val,
                    "open": round(float(row["open"]), 2),
                    "high": round(float(row["high"]), 2),
                    "low": round(float(row["low"]), 2),
                    "close": round(float(row["close"]), 2),
                    "volume": int(row.get("volume") or 0),
                })
            return jsonify({
                "stock": stock_key,
                "interval": interval,
                "source": "kite_historical",
                "candles": candles,
            })

        symbol = resolve_symbol(stock)
        cache_file = _cache_path(symbol)
        if not os.path.exists(cache_file):
            try:
                download_data(symbol, stock_key=stock.strip().upper())
            except Exception as exc:
                return jsonify({"error": str(exc), "stock": stock}), 404
        df = pd.read_csv(cache_file, index_col=0, parse_dates=True)
        tail = df.tail(limit)
        candles = []
        for idx, row in tail.iterrows():
            date_str = idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)[:10]
            candles.append({
                "time": date_str,
                "open": round(float(row["Open"]), 2),
                "high": round(float(row["High"]), 2),
                "low": round(float(row["Low"]), 2),
                "close": round(float(row["Close"]), 2),
                "volume": int(row["Volume"]),
            })
        return jsonify({"stock": stock_key, "symbol": symbol, "interval": "day", "candles": candles})

    @app.route("/fno/cancel-call", methods=["POST", "OPTIONS"])
    def fno_cancel_call():
        """Close the open NIFTY or BANKNIFTY call so the next passed bar can open another."""
        if request.method == "OPTIONS":
            return "", 204
        data = request.get_json(silent=True) or {}
        stock = (data.get("stock") or "").strip().upper()
        if not stock:
            return jsonify({"error": "Missing stock"}), 400
        import fno_session_rules as fsrules
        import session_calls

        stock = market_symbols.stock_key_from_input(stock)
        snap = fno_ws_rescore.get_snapshot(stock) or {}
        ticket = snap.get("session_ticket")
        if not fsrules.open_ticket(ticket):
            try:
                ticket = session_calls.session_ticket_from_db(
                    KNOWLEDGE_DB_PATH,
                    stock,
                    session_date=market_symbols.ist_now().date(),
                    product="fno",
                )
            except Exception:
                ticket = None
        if not fsrules.open_ticket(ticket):
            return jsonify({"ok": False, "error": "No open call to cancel", "stock": stock}), 404
        cancelled = fsrules.cancel_open_ticket(ticket)
        snap = fno_ws_rescore.get_snapshot(stock) or {}
        snap["session_ticket"] = cancelled
        fno_ws_rescore.save_snapshot(stock, snap)
        try:
            session_calls.sync_session(
                KNOWLEDGE_DB_PATH,
                stock=stock,
                product="fno",
                session_ticket=cancelled,
            )
        except Exception:
            pass
        rows = session_calls.ticket_rows(cancelled)
        return api_json({
            "ok": True,
            "stock": stock,
            "session_ticket": cancelled,
            "session_tickets": rows,
            "active_call": None,
            "call_history": [row for row in rows if not row.get("open")],
        })

    @app.route("/fno/confirm-suggestion", methods=["POST", "OPTIONS"])
    def fno_confirm_suggestion():
        """Put the on-screen suggestion onto the call list. A suggestion alone never does this."""
        if request.method == "OPTIONS":
            return "", 204
        data = request.get_json(silent=True) or {}
        stock = (data.get("stock") or "").strip().upper()
        if not stock:
            return jsonify({"error": "Missing stock"}), 400
        import fno_session_rules as fsrules
        import session_calls

        stock = market_symbols.stock_key_from_input(stock)
        snap = fno_ws_rescore.get_snapshot(stock) or {}
        suggestion = snap.get("suggestion") if isinstance(snap.get("suggestion"), dict) else None
        if not suggestion or suggestion.get("decision") not in ("BUY", "SELL"):
            watch = snap.get("pattern_watch") if isinstance(snap.get("pattern_watch"), dict) else None
            if watch and watch.get("decision") in ("BUY", "SELL"):
                suggestion = watch
        ticket = snap.get("session_ticket")
        if fsrules.open_ticket(ticket):
            return jsonify({"ok": False, "error": "A call is already open", "stock": stock}), 409
        if not suggestion or suggestion.get("decision") not in ("BUY", "SELL"):
            return jsonify({"ok": False, "error": "No suggestion to add", "stock": stock}), 404
        if not fsrules.levels_on_side(
            suggestion.get("decision"), suggestion.get("entry"), suggestion.get("stop_loss"), suggestion.get("target_1")
        ):
            return jsonify({"ok": False, "error": "Suggestion levels are not usable", "stock": stock}), 409
        quote = None
        try:
            quote, _err = live_market.fetch_live_quote(stock, INDIAN_STOCKS)
        except Exception:
            quote = None
        if str(stock).upper() == "NIFTY":
            from nifty_fno_data import entry_issue

            blocked = entry_issue(snap.get("bars_15m"), quote, market_symbols.ist_now())
            if blocked:
                return jsonify({"ok": False, "error": blocked, "stock": stock}), 409
        now = market_symbols.ist_now()
        opened = fsrules.persist_new_ticket(
            ticket,
            decision=suggestion.get("decision"),
            stop_loss=suggestion.get("stop_loss"),
            target_1=suggestion.get("target_1"),
            target_2=suggestion.get("target_2"),
            taken_at=now.isoformat(),
            session_date_value=now.date(),
            entry=suggestion.get("entry"),
            p_t1=suggestion.get("p_t1"),
            p_meta=suggestion.get("p_t1"),
            readings={
                "source": suggestion.get("source") or "suggestion",
                "bars_asof": suggestion.get("bars_asof"),
                "need": suggestion.get("need"),
                "kind": suggestion.get("kind"),
            },
            symbol=stock,
            bars=snap.get("bars_15m"),
            live_quote=quote,
        )
        if not isinstance(opened, dict) or fsrules.open_ticket(opened) is None:
            return jsonify({"ok": False, "error": "Could not add the suggestion", "stock": stock}), 409
        snap["session_ticket"] = opened
        snap["suggestion"] = None
        snap["pattern_watch"] = None
        fno_ws_rescore.save_snapshot(stock, snap)
        try:
            rows = session_calls.sync_session(
                KNOWLEDGE_DB_PATH,
                stock=stock,
                product="fno",
                session_ticket=opened,
            )
        except Exception:
            rows = session_calls.ticket_rows(opened)
        active = next((row for row in rows if row.get("open")), None)
        return api_json({
            "ok": True,
            "stock": stock,
            "session_ticket": opened,
            "session_tickets": rows,
            "active_call": active,
            "call_history": [row for row in rows if not row.get("open")],
        })

    @app.route("/fno/status", methods=["GET"])
    def fno_status_route():
        import kite_instruments

        kite = kite_data.get_provider_status()
        return jsonify(
            {
                "kite_ready": bool(kite.get("ready")),
                "live": live_market.get_provider_status(),
                "instruments": kite_instruments.get_status(),
                "nfo_cache": fno_instruments.get_status(),
            }
        )

    @app.route("/fno/short-horizon-quality", methods=["GET"])
    def fno_short_horizon_quality_route():
        """Settled 5m/10m prediction hit-rate for quality improvement."""
        import fno_short_horizon_log

        stock = (request.args.get("stock") or "").strip().upper() or None
        limit = request.args.get("limit", 200, type=int)
        body = fno_short_horizon_log.recent_accuracy(stock=stock, limit=limit or 200)
        body["stock"] = stock
        return jsonify(body)

    @app.route("/fno/contracts/<stock>", methods=["GET"])
    def fno_contracts_route(stock):
        spot = request.args.get("spot", type=float)
        if spot is None:
            return jsonify({"error": "Query param spot required (e.g. ?spot=24500)"}), 400
        body = fno_instruments.resolve_contracts(stock.strip().upper(), spot)
        # Accurate 3-pack CE/PE suggestions under max-loss ₹ cap (default 2000)
        try:
            import option_ticket

            max_loss = request.args.get("max_loss", type=float)
            if max_loss is None or max_loss <= 0:
                max_loss = option_ticket.DEFAULT_MAX_LOSS_INR
            # Optional live-call levels (BUY: SL below / T above). When omitted,
            # each side uses INDEX_CLIP for that index.
            idx_sl = request.args.get("index_stop", type=float)
            idx_t = request.args.get("index_target", type=float)
            # Lock 3-pack to same option expiry as ATM CE/PE
            pref_exp = None
            exp_s = body.get("option_expiry") or body.get("expiry")
            if exp_s:
                try:
                    from datetime import date as _date

                    pref_exp = _date.fromisoformat(str(exp_s)[:10])
                except Exception:
                    pref_exp = None
            sug = option_ticket.build_contracts_suggestions(
                stock.strip().upper(),
                spot=float(spot),
                index_stop=idx_sl,
                index_target=idx_t,
                max_loss_inr=float(max_loss),
                preferred_expiry=pref_exp,
            )
            body["option_suggestions"] = sug
            body["max_loss_inr"] = float(max_loss)
            # Persist into live snapshot so 30s fast refresh keeps the 3-pack.
            try:
                import fno_ws_rescore

                key = stock.strip().upper()
                snap = dict(fno_ws_rescore.get_snapshot(key) or {})
                snap["fno_contracts"] = body
                fno_ws_rescore.save_snapshot(key, snap)
            except Exception:
                pass
        except Exception as exc:
            body["option_suggestions"] = {
                "available": False,
                "reason": f"Could not build option suggestions ({exc}).",
            }
        return jsonify(body)

    @app.route("/replay/candles/<stock>", methods=["GET"])
    def replay_candles_route(stock):
        from tools.validate import replay_validate as rv

        limit = request.args.get("limit", 600, type=int)
        end = request.args.get("end", type=int)
        body, code = rv.candles_payload(stock.strip().upper(), limit=limit, end_unix=end)
        return jsonify(body), code

    @app.route("/replay/scrub/<stock>", methods=["GET"])
    def replay_scrub_route(stock):
        from tools.validate import replay_validate as rv

        at = request.args.get("at")
        if not at:
            return jsonify({"error": "Query param at required (unix seconds or ISO time)"}), 400
        body, code = rv.scrub_payload(stock.strip().upper(), at)
        return jsonify(body), code

    @app.route("/charts/<path:filename>", methods=["GET"])
    def chart_image(filename):
        safe_name = os.path.basename(filename)
        return send_from_directory(CHART_DIR, safe_name)

    @app.route("/dashboard", methods=["GET"])
    @app.route("/dashboard/", methods=["GET"])
    def dashboard():
        return send_from_directory(DASHBOARD_DIR, "index.html")

    @app.route("/dashboard/<path:filename>", methods=["GET"])
    def dashboard_asset(filename):
        safe_name = os.path.basename(filename)
        if safe_name.lower().endswith((".png", ".jpg", ".jpeg", ".svg", ".webp", ".ico")):
            return send_from_directory(DASHBOARD_DIR, safe_name)
        # Static HTML previews (e.g. overlay indication UI mock)
        if safe_name.lower().endswith(".html") and safe_name.lower() != "index.html":
            path = os.path.join(DASHBOARD_DIR, safe_name)
            if os.path.isfile(path):
                return send_from_directory(DASHBOARD_DIR, safe_name)
        return send_from_directory(DASHBOARD_DIR, "index.html")

    @app.route("/", methods=["GET"])
    def index():
        return jsonify({
            "name": "Stock Signal ML Engine",
            "version": MODEL_VERSION,
            "dashboard": "/dashboard",
            "endpoints": {
                "GET /dashboard": "Web dashboard UI",
                "POST /predict": "Get trading decision. Body: {\"stock\": \"RELIANCE\", \"mode\": \"auto|premarket|intraday\"}",
                "POST /predict/fno": "F&O decision (index-first, stock eligibility). Body: {\"stock\": \"NIFTY\"}",
                "POST /predict/fno/ws-rescore": "Fast F&O rescore from WebSocket LTP + cached snapshot (poll ~15s)",
                "POST /predict/fno/live-signal": "Session + 5m read without full predict",
                "POST /predict/intraday": "Strict intraday decision. Body: {\"stock\": \"TCS\"}",
                "GET /fno/universe": "F&O symbols on the desk with model status (POST {symbol} adds, DELETE /fno/universe/<symbol> removes)",
                "GET /session-calls?stock=NIFTY": "Today's saved F&O call tickets",
                "GET /fno/status": "Kite + NFO instrument cache status for F&O dashboard",
                "GET /fno/contracts/<stock>?spot=": "ATM CE/PE + nearest future from cached NFO master",
                "POST /models/train-watchlist?force=true": "Train ML models for all watchlist symbols",
                "POST /knowledge/train": "Scan candle+news history, aggregate rules, train memory ML → knowledge.db",
                "GET /knowledge/stats": "Knowledge DB event counts and top patterns",
                "GET /knowledge/rules": "Learned historical rules (?limit=50)",
                "GET /history": "View prediction history. Optional: ?stock=RELIANCE&limit=20",
                "GET /symbols": "List supported stock symbols",
                "GET /watchlist": "Top Indian stocks watchlist",
                "GET /ohlcv/<stock>": "OHLCV candle data for charts",
                "GET /live/<stock>": "Live quote (Kite → Groww → NSE → Yahoo)",
                "GET /live?symbols=RELIANCE,TCS": "Groww batch LTP",
                "GET /data/status": "Historical vs live data provider status",
                "GET /data/kite-capabilities": "Kite Connect APIs: used, available, rate limits, gaps",
                "GET /kite/stream/ltp": "WebSocket LTP cache for watchlist symbols",
                "GET /kite/calendar": "Trading day / holiday status (NSE seed + refresh)",
                "GET /kite/holdings": "Portfolio holdings (read-only)",
                "POST /kite/orders": "Place order (dry_run default; KITE_ALLOW_LIVE_ORDERS=1 to execute)",
                "GET /data/training-stats": "ML cache: watchlist download coverage and date spans",
                "POST /data/prefetch-watchlist?force=true": "Download all watchlist symbols from Yahoo",
                "GET /news?symbol=RELIANCE&limit=20": "Recent filings and headlines from news DB",
                "GET /news/stats": "News database coverage stats",
                "POST /news/prefetch-watchlist?quick=true": "Ingest Downstox headlines + NSE filings (quick=last 3 months)",
                "GET /morning/global": "Overnight US/Asia/oil/INR panel (Yahoo EOD)",
                "GET /morning/latest": "Last saved morning pre-market report",
                "GET /morning/status": "Background morning job status",
                "POST /morning/run": "Run pre-market brief (news refresh + watchlist analysis). ?sync=true for wait",
                "GET /self-test": "Smoke checks for news DB, knowledge DB, India context (dashboard System check)",
                "GET /market/india-context": "FII/DII, India VIX, Nifty open proxy",
                "GET /charts/<filename>": "Generated analysis chart PNG",
                "GET /health": "Health check",
                "GET /notifications": "Desk notifications (hamburger). ?unread=1&limit=80",
                "POST /notifications/read": "Mark notifications read. Body: {ids:[…]} or {all:true}",
                "GET /fno/live-watch": "Background NIFTY/BN/Sensex 30s watch status + load estimate",
                "GET|POST /fno/frvp": "Chart-only Fixed Range VP (POC/VAH/VAL) · alias /fno/volume-profile/fixed-range · no Calls",
                "GET /fno/scalper/chart": "Scalper 1m chart · mode=oracle_t15|hhll_t15 · EMA34 markers + call table",
                "GET /fno/scalper/live": "Scalper live check (?mode=oracle_t15|hhll_t15&notify=1)",
                "GET /fno/scalper/tick": "Scalper latest 1m candle for live chart append",
                "GET /instruments/search?scope=scalper": "Scalper symbol search (index/equity/CE/PE)",
                "GET /fno/option-blue/calls": "REMOVED — use Scalper (PA pa_no_trap)",
                "GET /fno/option-blue/live": "REMOVED — use /fno/scalper/live",
                "GET /fno/scalper/chart": "Scalper FINAL PA pa_no_trap · levels + calls (?scope=today|history)",
            },
        })

    @app.route("/notifications", methods=["GET", "OPTIONS"])
    def notifications_list():
        if request.method == "OPTIONS":
            return "", 204
        import desk_notifications

        unread = str(request.args.get("unread") or "").lower() in ("1", "true", "yes")
        limit = request.args.get("limit", 80, type=int)
        items = desk_notifications.list_notifications(limit=limit, unread_only=unread)
        return jsonify({
            "unread": desk_notifications.unread_count(),
            "items": items,
        })

    @app.route("/notifications/read", methods=["POST", "OPTIONS"])
    def notifications_read():
        if request.method == "OPTIONS":
            return "", 204
        import desk_notifications

        data = request.get_json(silent=True) or {}
        if data.get("all"):
            n = desk_notifications.mark_read(all_unread=True)
        else:
            n = desk_notifications.mark_read(data.get("ids") or [])
        return jsonify({"marked": n, "unread": desk_notifications.unread_count()})

    @app.route("/fno/live-watch", methods=["GET", "OPTIONS"])
    def fno_live_watch_status():
        if request.method == "OPTIONS":
            return "", 204
        import fno_live_watch

        st = fno_live_watch.watch_state()
        return jsonify({
            **st,
            "load": fno_live_watch.load_estimate(
                float(st.get("poll_sec") or 30),
                float(st.get("full_sec") or 15 * 60),
            ),
        })

    def _fno_frvp_handler():
        """Chart-only Fixed Range Volume Profile (POC / VAH / VAL). No Calls link.

        Body/query: stock|symbol, start, end, rows=auto|N, va_pct=0.70,
        chart_interval (1m/5m/15m of clicks). Any length range. Kite 1m→5m→15m→tape.
        """
        if request.method == "OPTIONS":
            return "", 204
        import fno_fixed_range_vp as frvp

        body = request.get_json(silent=True) if request.method == "POST" else None
        body = body if isinstance(body, dict) else {}
        args = request.args
        stock = (
            body.get("stock")
            or body.get("symbol")
            or args.get("stock")
            or args.get("symbol")
            or "NIFTY"
        )
        start = body.get("start") or args.get("start")
        end = body.get("end") or args.get("end")
        if not start or not end:
            return jsonify({"ok": False, "error": "start and end required (ISO timestamps)"}), 400
        rows_raw = body.get("rows") if "rows" in body else args.get("rows")
        if rows_raw is None or str(rows_raw).strip().lower() in ("", "auto"):
            n_rows = "auto"
        else:
            try:
                n_rows = int(rows_raw)
            except (TypeError, ValueError):
                n_rows = "auto"
        try:
            va_pct = float(body.get("va_pct") or args.get("va_pct") or frvp.DEFAULT_VA_PCT)
        except (TypeError, ValueError):
            va_pct = frvp.DEFAULT_VA_PCT
        row_size = body.get("row_size") if "row_size" in body else args.get("row_size")
        try:
            row_size_f = float(row_size) if row_size not in (None, "") else None
        except (TypeError, ValueError):
            row_size_f = None
        chart_interval = (
            body.get("chart_interval")
            or args.get("chart_interval")
            or body.get("interval")
            or args.get("interval")
            or "minute"
        )
        prefer = body.get("prefer_interval") or args.get("prefer_interval") or chart_interval
        try:
            payload = frvp.build_profile_for_symbol(
                str(stock).strip(),
                start=start,
                end=end,
                n_rows=n_rows,
                va_pct=va_pct,
                row_size=row_size_f,
                prefer_interval=str(prefer),
                chart_interval=str(chart_interval),
            )
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc), "symbol": str(stock).upper()}), 500
        code = 200 if payload.get("ok") else 422
        return jsonify(payload), code

    @app.route("/fno/frvp", methods=["GET", "POST", "OPTIONS"])
    @app.route("/fno/volume-profile/fixed-range", methods=["GET", "POST", "OPTIONS"])
    def fno_volume_profile_fixed_range():
        return _fno_frvp_handler()

    @app.route("/fno/scalper/crypto/top", methods=["GET", "OPTIONS"])
    def fno_scalper_crypto_top():
        """Top-10 liquid USDT pairs for Scalper crypto mode (Binance)."""
        if request.method == "OPTIONS":
            return "", 204
        import fno_scalper_1m

        try:
            return jsonify(fno_scalper_1m.crypto_top10())
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc)}), 500

    @app.route("/fno/scalper/chart", methods=["GET", "OPTIONS"])
    def fno_scalper_chart():
        """Scalper desk: FINAL PA pa_no_trap · 1m candles + S/R levels + calls."""
        if request.method == "OPTIONS":
            return "", 204
        import fno_scalper_1m

        market = (request.args.get("market") or "india").strip().lower()
        default_stock = "BTCUSDT" if market == "crypto" else "NIFTY"
        stock = (request.args.get("stock") or default_stock).strip()
        try:
            days = int(request.args.get("days", 5))
        except (TypeError, ValueError):
            days = 5
        days = max(1, min(days, 40))
        try:
            chart_days = int(request.args.get("chart_days", 1))
        except (TypeError, ValueError):
            chart_days = 1
        # mode ignored — final logic is always pa_no_trap
        mode = (request.args.get("mode") or "pa_no_trap").strip().lower()
        interval = (request.args.get("interval") or "1m").strip().lower()
        scope = (request.args.get("scope") or "history").strip().lower()
        force_refresh = str(request.args.get("refresh") or "0").lower() in ("1", "true", "yes")
        try:
            payload = fno_scalper_1m.scan_scalper(
                stock=stock,
                days=days,
                mode=mode,
                chart_days=chart_days,
                interval=interval,
                force_refresh=force_refresh,
                scope=scope,
                market=market,
            )
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc), "stock": stock}), 500
        code = 200 if payload.get("ok") else 404
        return jsonify(payload), code

    @app.route("/fno/scalper/live", methods=["GET", "OPTIONS"])
    def fno_scalper_live():
        """PA pa_no_trap live check + optional desktop notify."""
        if request.method == "OPTIONS":
            return "", 204
        import fno_scalper_1m

        market = (request.args.get("market") or "india").strip().lower()
        default_stock = "BTCUSDT" if market == "crypto" else "NIFTY"
        stock = (request.args.get("stock") or default_stock).strip()
        notify = str(request.args.get("notify") or "0").lower() in ("1", "true", "yes")
        mode = (request.args.get("mode") or "pa_no_trap").strip().lower()
        try:
            payload = fno_scalper_1m.live_scalper_check(
                stock=stock, notify=notify, mode=mode, market=market
            )
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc), "stock": stock}), 500
        code = 200 if payload.get("ok") else 404
        return jsonify(payload), code

    @app.route("/fno/scalper/reload", methods=["POST", "GET", "OPTIONS"])
    def fno_scalper_reload():
        """Hot-reload scalper module + clear caches (no full API restart)."""
        if request.method == "OPTIONS":
            return "", 204
        import importlib
        import sys

        try:
            import fno_scalper_1m

            cleared = fno_scalper_1m.reload_scalper_module()
            mod = importlib.reload(fno_scalper_1m)
            # Keep Flask route imports pointing at refreshed module
            sys.modules["fno_scalper_1m"] = mod
            return jsonify(
                {
                    "ok": True,
                    "reloaded": True,
                    "cleared": (cleared or {}).get("cleared"),
                    "has_fast": hasattr(mod, "scan_oracle_live_fast"),
                }
            )
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc)}), 500

    @app.route("/fno/scalper/tick", methods=["GET", "OPTIONS"])
    def fno_scalper_tick():
        """Latest 1m candle only — for live chart append every ~30s."""
        if request.method == "OPTIONS":
            return "", 204
        import fno_scalper_1m

        market = (request.args.get("market") or "india").strip().lower()
        default_stock = "BTCUSDT" if market == "crypto" else "NIFTY"
        stock = (request.args.get("stock") or default_stock).strip()
        try:
            payload = fno_scalper_1m.scalper_tick(stock=stock, market=market)
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc), "stock": stock}), 500
        code = 200 if payload.get("ok") else 404
        return jsonify(payload), code

    @app.route("/fno/option-blue/calls", methods=["GET", "OPTIONS"])
    def fno_option_blue_calls():
        """Removed — use Scalper (PA pa_no_trap) instead."""
        if request.method == "OPTIONS":
            return "", 204
        return jsonify(
            {
                "ok": False,
                "error": "Option Blue removed. Use Scalper tab (PA pa_no_trap final logic).",
                "redirect": "/#scalper",
                "desk": "REMOVED",
            }
        ), 410

    @app.route("/fno/option-blue/live", methods=["GET", "OPTIONS"])
    def fno_option_blue_live():
        """Removed — use /fno/scalper/live."""
        if request.method == "OPTIONS":
            return "", 204
        return jsonify(
            {
                "ok": False,
                "error": "Option Blue removed. Use /fno/scalper/live.",
                "desk": "REMOVED",
            }
        ), 410

    @app.route("/notifications/whatsapp", methods=["GET", "OPTIONS"])
    def notifications_whatsapp_status():
        if request.method == "OPTIONS":
            return "", 204
        import whatsapp_notify

        return jsonify(whatsapp_notify.status())

    @app.route("/notifications/telegram", methods=["GET", "OPTIONS"])
    def notifications_telegram_status():
        if request.method == "OPTIONS":
            return "", 204
        import telegram_notify

        return jsonify(telegram_notify.status())

    try:
        import desk_notifications
        import fno_live_watch

        desk_notifications.ensure_tables()
        # Full Analyze every 15m (ML/tech/news) — separate from 30s fast tape.
        fno_live_watch.set_full_analyze_fn(engine_predict_fn)
        fno_live_watch.start(INDIAN_STOCKS, poll_sec=30, full_sec=15 * 60)
    except Exception as _watch_exc:
        print(f"  F&O live watch not started: {_watch_exc}")

    return app


# ================================================================
# SECTION 13: ENTRY POINT
# ================================================================

def setup_directories():
    """Create required directories. """
    print("\n[2/3] Setting up directories... ")
    for d in [BASE_DIR, MODEL_DIR, CACHE_DIR, CHART_DIR, DASHBOARD_DIR, MORNING_REPORT_DIR]:
        os.makedirs(d, exist_ok=True)
        print(f"  {os.path.relpath(d)}: OK")


def main():
    banner = """ ================================================================ STOCK SIGNAL ML ENGINE v1.0 ML-Powered Trading Decision System ================================================================ Data:   Yahoo Finance (free, no API key) ML:     RandomForest + GradientBoosting + AdaBoost Ensemble Signals: 30+ Technical Indicators + ML Probability Fusion ================================================================ """
    print(banner)

    # Setup
    setup_directories()
    setup_database()
    news_data.setup_news_database(NEWS_DB_PATH)
    pattern_memory.setup_knowledge_database(KNOWLEDGE_DB_PATH)
    try:
        import knowledge_db
        import training_store

        training_store.ensure_tables(knowledge_db.ensure_db_dir())
    except Exception:
        pass

    # Parse arguments
    parser = argparse.ArgumentParser( description="Stock Signal ML Engine - Get trading decisions powered by ML" , formatter_class=argparse.RawDescriptionHelpFormatter, epilog=""" Examples: py stock_signal_ml.py --predict RELIANCE     Quick prediction py stock_signal_ml.py --predict AAPL         US stock py stock_signal_ml.py --predict BTC          Crypto py stock_signal_ml.py                        Start API server py stock_signal_ml.py --port 8080            Custom port """ , )
    parser.add_argument("--predict", type=str, help="Get instant prediction for a stock symbol")
    parser.add_argument("--port", type=int, default=API_PORT, help=f"API server port (default: {API_PORT})")
    parser.add_argument("--retrain", action="store_true", help="Force retrain models (ignore cache)")
    parser.add_argument(
        "--prefetch-watchlist",
        action="store_true",
        help=f"Download Yahoo OHLCV for all {len(WATCHLIST)} watchlist symbols (ML knowledge base)",
    )
    parser.add_argument(
        "--force-refresh-data",
        action="store_true",
        help="With --prefetch-watchlist, ignore cache and re-download from Yahoo",
    )
    parser.add_argument(
        "--training-stats",
        action="store_true",
        help="Print cached training data stats and exit",
    )
    parser.add_argument(
        "--data-inventory",
        action="store_true",
        help="Report 5y OHLCV + news coverage per watchlist symbol",
    )
    parser.add_argument(
        "--data-repair",
        action="store_true",
        help="Remove corrupt/orphan caches and backfill missing OHLCV + news",
    )
    parser.add_argument(
        "--data-repair-force-ohlcv",
        action="store_true",
        help="With --data-repair, re-download all watchlist OHLCV (not only gaps)",
    )
    parser.add_argument(
        "--prefetch-news",
        action="store_true",
        help="Ingest Downstox market headlines + NSE corporate announcements for watchlist",
    )
    parser.add_argument(
        "--news-quick",
        action="store_true",
        help="With --prefetch-news, only backfill last 3 months per symbol (faster)",
    )
    parser.add_argument(
        "--news-stats",
        action="store_true",
        help="Print news database stats and exit",
    )
    parser.add_argument(
        "--train-watchlist",
        action="store_true",
        help="Train ML models for all watchlist symbols (uses Kite history when configured)",
    )
    parser.add_argument(
        "--train-symbols",
        type=str,
        default="",
        help="With --train-watchlist, comma-separated symbols (default: full watchlist)",
    )
    parser.add_argument(
        "--train-knowledge",
        action="store_true",
        help="Scan all watchlist candles + news impacts, train memory ML, save to knowledge.db",
    )
    parser.add_argument(
        "--knowledge-stats",
        action="store_true",
        help="Print knowledge.db stats and exit",
    )
    parser.add_argument(
        "--mode",
        choices=("auto", "premarket", "intraday"),
        default="auto",
        help="Analysis mode for --predict (default: auto by IST session)",
    )
    parser.add_argument(
        "--morning-report",
        action="store_true",
        help="Run pre-market brief: refresh news + global panel + analyze watchlist (for cron)",
    )
    parser.add_argument(
        "--morning-no-news",
        action="store_true",
        help="With --morning-report, skip news refresh",
    )
    parser.add_argument(
        "--morning-symbols",
        type=str,
        default="",
        help="With --morning-report, comma-separated symbols (default: full watchlist)",
    )
    parser.add_argument("--backtest", type=str, help="Fixed-date holdout backtest for one symbol")
    parser.add_argument(
        "--holdout",
        type=str,
        default="2025-01-01",
        help="Holdout start date (YYYY-MM-DD) for --backtest / --audit-watchlist",
    )
    parser.add_argument(
        "--prefetch-all",
        action="store_true",
        help="Download OHLCV (5y) + news for entire watchlist into local DB/cache",
    )
    parser.add_argument(
        "--audit-watchlist",
        action="store_true",
        help="Point-in-time daily audit on holdout period. Set AUDIT_FAST=1 for a lighter HGB.",
    )
    parser.add_argument(
        "--audit-stock",
        type=str,
        default="",
        help="Audit only these symbols (comma-separated); implies --audit-watchlist",
    )
    parser.add_argument(
        "--audit-report",
        type=int,
        default=0,
        help="Score an existing audit run id: base-rate baselines + paper P&L",
    )
    parser.add_argument(
        "--audit-compare",
        type=str,
        default="",
        help="Compare two audit run ids, e.g. --audit-compare 3,4",
    )
    parser.add_argument(
        "--audit-step-days",
        type=int,
        default=1,
        help="Evaluate every N trading days in audit (5 = weekly, faster)",
    )
    parser.add_argument(
        "--audit-retrain-days",
        type=int,
        default=42,
        help="Retrain ML every N trading days during historical audit",
    )
    args = parser.parse_args()

    if args.news_stats:
        print(json.dumps(news_data.get_news_stats(NEWS_DB_PATH), indent=2, default=str))
        sys.exit(0)

    if args.knowledge_stats:
        print(json.dumps(pattern_memory.get_knowledge_stats(KNOWLEDGE_DB_PATH), indent=2, default=str))
        sys.exit(0)

    if args.train_knowledge:
        summary = train_knowledge_base()
        print(json.dumps(summary, indent=2, default=str))
        sys.exit(0 if not summary.get("errors") else 1)

    if args.backtest:
        key = args.backtest.strip().upper()
        symbol = resolve_symbol(key)
        df = download_data(symbol, stock_key=key)
        summary, err = backtest.run_holdout_backtest(
            df,
            compute_all_features,
            build_training_data,
            train_models,
            args.holdout,
            TARGET_MIN_RETURN,
        )
        if err:
            print(json.dumps({"error": err}, indent=2))
            sys.exit(1)
        print(json.dumps({"stock": key, "backtest": summary}, indent=2, default=str))
        sys.exit(0)

    if args.prefetch_all:
        summary = prefetch_all_data(force=args.force_refresh_data, news_quick=args.news_quick)
        print(json.dumps(summary, indent=2, default=str))
        pf = summary.get("ohlcv", {}).get("prefetch", {})
        sys.exit(0 if pf.get("failed", 1) == 0 else 1)

    if args.audit_watchlist or args.audit_stock.strip():
        print("  AUDIT MODE — not starting the API server")
        syms = [s.strip().upper() for s in args.audit_stock.split(",") if s.strip()] or None
        summary = run_audit_watchlist(
            holdout_start=args.holdout,
            retrain_every=args.audit_retrain_days,
            step_days=args.audit_step_days,
            symbols=syms,
        )
        print(json.dumps(summary, indent=2, default=str))
        run_id = summary.get("audit_run_id")
        if run_id:
            print()
            print(audit_report.format_report(
                audit_report.full_report(KNOWLEDGE_DB_PATH, run_id)
            ))
        sys.exit(0)

    if args.audit_report:
        print(audit_report.format_report(
            audit_report.full_report(KNOWLEDGE_DB_PATH, args.audit_report)
        ))
        print()
        print(json.dumps(
            audit_report.full_report(KNOWLEDGE_DB_PATH, args.audit_report),
            indent=2, default=str,
        ))
        sys.exit(0)

    if args.audit_compare:
        try:
            a_id, b_id = [int(x) for x in args.audit_compare.split(",")[:2]]
        except ValueError:
            print("--audit-compare expects two run ids, e.g. 3,4")
            sys.exit(1)
        print(json.dumps(
            audit_report.compare_runs(KNOWLEDGE_DB_PATH, a_id, b_id),
            indent=2, default=str,
        ))
        sys.exit(0)

    if args.prefetch_news:
        summary = news_data.prefetch_watchlist_news(
            NEWS_DB_PATH,
            WATCHLIST,
            years=DATA_YEARS,
            max_months_per_symbol=3 if args.news_quick else None,
        )
        print(json.dumps(summary, indent=2, default=str))
        sys.exit(0)

    if args.morning_report:
        print(json.dumps({
            "error": "Morning job removed — use Stocks / F&O / Scalper",
            "removed": True,
        }))
        sys.exit(1)

    if args.training_stats:
        print(json.dumps(get_training_stats(), indent=2, default=str))
        sys.exit(0)

    if args.data_inventory:
        report = data_inventory.full_inventory_report(
            CACHE_DIR,
            NEWS_DB_PATH,
            WATCHLIST,
            resolve_symbol,
            _cache_row_stats,
            DATA_YEARS,
        )
        print(json.dumps(report, indent=2, default=str))
        sys.exit(0)

    if args.data_repair:
        summary = data_inventory.repair_data_gaps(
            WATCHLIST,
            CACHE_DIR,
            NEWS_DB_PATH,
            resolve_symbol,
            download_data,
            _cache_row_stats,
            news_data.prefetch_watchlist_news,
            years=DATA_YEARS,
            force_ohlcv=args.data_repair_force_ohlcv,
        )
        print(json.dumps(summary, indent=2, default=str))
        o_after = summary.get("ohlcv_after", {})
        sys.exit(0 if o_after.get("ok_count") == len(WATCHLIST) else 1)

    if args.prefetch_watchlist:
        summary = prefetch_watchlist(force=args.force_refresh_data)
        print(json.dumps(summary, indent=2, default=str))
        sys.exit(0 if summary.get("prefetch", {}).get("failed", 1) == 0 else 1)

    if args.train_watchlist:
        sym_list = [s.strip() for s in args.train_symbols.split(",") if s.strip()] or None
        summary = train_watchlist_models(force_retrain=args.retrain, symbols=sym_list)
        print(json.dumps(summary, indent=2, default=str))
        sys.exit(0 if summary.get("succeeded", 0) == summary.get("attempted", 1) else 1)

    if args.predict:
        # Quick predict mode (no server)
        try:
            mode = None if args.mode == "auto" else args.mode
            result = predict_stock(args.predict, force_retrain=args.retrain, mode=mode)
            print(f"\n{'='*60}")
            print("  FULL RESULT (JSON):")
            print(f"{'='*60}")
            print(json.dumps(result, indent=2, default=str))
        except Exception as e:
            print(f"\nERROR: {e}")
            sys.exit(1)
    else:
        # API server mode
        app = create_api(predict_stock)
        bootstrap_kite_services()
        try:
            import knowledge_db
            import training_store

            db = knowledge_db.ensure_db_dir()
            training_store.ensure_tables(db)
            training_store.import_morning_reports_dir(MORNING_REPORT_DIR, db)
            print("  Morning brief still runs only from the Morning tab.")
            print("  F&O live watch: NIFTY + SENSEX every 30s (fast) + full Analyze every 15m.")
        except Exception as exc:
            print(f"  Background setup: {exc}")
        print(f""" [3/3] Starting API server...

{'='*60}
  API SERVER RUNNING on http://localhost:{args.port}
{'='*60}

  POST /predict     Get trading decision
    Body: {{"stock": "RELIANCE"}}

  GET  /dashboard   Web UI (open in browser)
  GET  /watchlist   Top Indian stocks
  GET  /notifications  Desk alerts (hamburger)
  GET  /fno/live-watch Background index watch status
  GET  /health      Health check
  GET  /            API documentation

  Open dashboard: http://localhost:{args.port}/dashboard

  Press Ctrl+C to stop.
{'='*60}
""")
        app.run(host="0.0.0.0", port=args.port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
