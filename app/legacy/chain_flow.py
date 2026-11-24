"""Save live option-chain readings and use them on the next call.

The five-year candle tape has no PCR, OI, GEX, or book. Those values are stored
from the session they are actually observed. A missing reading stays missing.
The probability nudge is small so an early opening-range call is not flipped
by one chain print.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None  # type: ignore

import knowledge_db
import training_store

IST = ZoneInfo("Asia/Kolkata") if ZoneInfo else None
MAX_NUDGE = 0.025
PCR_WINDOW = 16  # 16 x 15m = 4 hours


def _f(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def bar_bucket(ts: Any = None) -> str:
    if ts is None:
        dt = datetime.now(IST) if IST else datetime.now()
    elif hasattr(ts, "to_pydatetime"):
        dt = ts.to_pydatetime()
    else:
        text = str(ts).replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            dt = datetime.now(IST) if IST else datetime.now()
    if IST is not None and dt.tzinfo is not None:
        dt = dt.astimezone(IST)
    minute = (dt.minute // 15) * 15
    floored = dt.replace(minute=minute, second=0, microsecond=0)
    return floored.strftime("%Y-%m-%dT%H:%M")


def _session_date(bucket: str) -> str:
    return bucket[:10]


def _extract(deriv: Dict[str, Any], live_quote: Optional[Dict[str, Any]], vix_level: float, spot: float) -> Dict[str, Any]:
    gex = deriv.get("gex") if isinstance(deriv.get("gex"), dict) else {}
    ce = deriv.get("atm_ce") if isinstance(deriv.get("atm_ce"), dict) else {}
    pe = deriv.get("atm_pe") if isinstance(deriv.get("atm_pe"), dict) else {}
    iv = _f(ce.get("implied_volatility"))
    if iv is None:
        fut = deriv.get("future") if isinstance(deriv.get("future"), dict) else {}
        iv = _f(fut.get("implied_volatility"))
    if iv is not None and iv > 2:
        iv = iv / 100.0
    skew = _f(gex.get("iv_skew") if gex.get("available") else deriv.get("iv_skew"))
    book = deriv.get("book") if isinstance(deriv.get("book"), dict) else {}
    if not book.get("available") and live_quote:
        import full_market_analysis

        book = full_market_analysis.book_imbalance(live_quote)
    row = {
        "pcr": _f(deriv.get("pcr")),
        "ce_oi": _f(ce.get("oi")),
        "pe_oi": _f(pe.get("oi")),
        "iv_atm": iv,
        "iv_skew": skew,
        "gex_flip": _f(gex.get("flip")) if gex.get("available") else None,
        "gex_bias": (str(gex.get("bias")) if gex.get("bias") else None) if gex.get("available") else None,
        "fut_basis": _f(deriv.get("futures_basis")),
        "vix_level": _f(vix_level) or _f(deriv.get("vix_level")),
        "book_buy": _f(book.get("buy_quantity")) if book.get("available") else None,
        "book_sell": _f(book.get("sell_quantity")) if book.get("available") else None,
        "spot": _f(spot),
        "book": book,
    }
    return row


def _useful(row: Dict[str, Any]) -> bool:
    return any(row.get(k) is not None for k in ("pcr", "ce_oi", "pe_oi", "gex_flip", "iv_skew", "fut_basis", "book_buy"))


def _in_cash_session(bucket: str) -> bool:
    """Only 15-minute buckets inside the NSE cash session are stored."""
    try:
        day = datetime.strptime(bucket[:10], "%Y-%m-%d")
        hh = int(bucket[11:13])
        mm = int(bucket[14:16])
    except (ValueError, IndexError):
        return False
    if day.weekday() >= 5:
        return False
    mins = hh * 60 + mm
    return (9 * 60 + 15) <= mins <= (15 * 60 + 30)


def _recent(path: str, stock: str, bucket: str) -> List[Dict[str, Any]]:
    conn = training_store._connect(path)
    cur = conn.execute(
        """
        SELECT bar_ts, pcr, ce_oi, pe_oi, spot, book_buy, book_sell, gex_bias
        FROM chain_snapshots
        WHERE stock = ? AND session_date = ? AND bar_ts <= ?
        ORDER BY bar_ts DESC
        LIMIT ?
        """,
        (stock, _session_date(bucket), bucket, PCR_WINDOW),
    )
    cols = ["bar_ts", "pcr", "ce_oi", "pe_oi", "spot", "book_buy", "book_sell", "gex_bias"]
    rows = [dict(zip(cols, rec)) for rec in cur.fetchall()]
    conn.close()
    rows.reverse()
    return rows


def _pcr_var(rows: List[Dict[str, Any]]) -> Optional[float]:
    vals = [float(r["pcr"]) for r in rows if r.get("pcr") is not None]
    if len(vals) < 4:
        return None
    mean = sum(vals) / len(vals)
    return sum((v - mean) ** 2 for v in vals) / len(vals)


def _oi_build(rows: List[Dict[str, Any]]) -> Optional[float]:
    usable = [r for r in rows if r.get("ce_oi") is not None and r.get("pe_oi") is not None and r.get("spot")]
    if len(usable) < 2:
        return None
    prev, last = usable[-2], usable[-1]
    oi_prev = float(prev["ce_oi"]) + float(prev["pe_oi"])
    oi_last = float(last["ce_oi"]) + float(last["pe_oi"])
    if oi_prev <= 0 or oi_last <= oi_prev:
        return 0.0
    if float(last["spot"]) > float(prev["spot"]):
        return 1.0
    if float(last["spot"]) < float(prev["spot"]):
        return -1.0
    return 0.0


def capture(
    stock: str,
    deriv: Dict[str, Any],
    *,
    live_quote: Optional[Dict[str, Any]] = None,
    vix_level: float = 0.0,
    spot: float = 0.0,
    bar_ts: Any = None,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Upsert this 15-minute chain print and attach variance / OI buildup onto deriv."""
    path = training_store.ensure_tables(db_path or knowledge_db.ensure_db_dir())
    bucket = bar_bucket(bar_ts)
    row = _extract(deriv or {}, live_quote, vix_level, spot)
    if _useful(row) and _in_cash_session(bucket):
        now = datetime.now().isoformat()
        conn = training_store._connect(path)
        conn.execute(
            """
            INSERT INTO chain_snapshots (
                stock, bar_ts, session_date, pcr, ce_oi, pe_oi, iv_atm, iv_skew,
                gex_flip, gex_bias, fut_basis, vix_level, book_buy, book_sell, spot, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(stock, bar_ts) DO UPDATE SET
                pcr=COALESCE(excluded.pcr, chain_snapshots.pcr),
                ce_oi=COALESCE(excluded.ce_oi, chain_snapshots.ce_oi),
                pe_oi=COALESCE(excluded.pe_oi, chain_snapshots.pe_oi),
                iv_atm=COALESCE(excluded.iv_atm, chain_snapshots.iv_atm),
                iv_skew=COALESCE(excluded.iv_skew, chain_snapshots.iv_skew),
                gex_flip=COALESCE(excluded.gex_flip, chain_snapshots.gex_flip),
                gex_bias=COALESCE(excluded.gex_bias, chain_snapshots.gex_bias),
                fut_basis=COALESCE(excluded.fut_basis, chain_snapshots.fut_basis),
                vix_level=COALESCE(excluded.vix_level, chain_snapshots.vix_level),
                book_buy=COALESCE(excluded.book_buy, chain_snapshots.book_buy),
                book_sell=COALESCE(excluded.book_sell, chain_snapshots.book_sell),
                spot=COALESCE(excluded.spot, chain_snapshots.spot),
                updated_at=excluded.updated_at
            """,
            (
                stock.strip().upper(),
                bucket,
                _session_date(bucket),
                row["pcr"],
                row["ce_oi"],
                row["pe_oi"],
                row["iv_atm"],
                row["iv_skew"],
                row["gex_flip"],
                row["gex_bias"],
                row["fut_basis"],
                row["vix_level"],
                row["book_buy"],
                row["book_sell"],
                row["spot"],
                now,
            ),
        )
        conn.commit()
        conn.close()
    history = _recent(path, stock.strip().upper(), bucket)
    pcr_var = _pcr_var(history)
    oi_build = _oi_build(history)
    deriv["pcr_var"] = pcr_var
    deriv["pcr_var_present"] = 1.0 if pcr_var is not None else 0.0
    deriv["oi_build"] = oi_build
    book = row.get("book") if isinstance(row.get("book"), dict) else {}
    if book.get("available"):
        deriv["book"] = book
    return {
        "bar_ts": bucket,
        "pcr_var": pcr_var,
        "oi_build": oi_build,
        "stored": bool(_useful(row) and _in_cash_session(bucket)),
    }


def adjust(p_t1: float, *, side: float, derivatives: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Nudge P(T1) only when a real chain or book reading is present."""
    d = derivatives or {}
    delta = 0.0
    reasons: List[str] = []
    side_f = float(side or 0)
    oi_build = _f(d.get("oi_build"))
    if oi_build and side_f:
        if oi_build * side_f > 0:
            delta += 0.015
            reasons.append("OI buildup agrees")
        elif oi_build * side_f < 0:
            delta -= 0.015
            reasons.append("OI buildup opposes")
    gex = d.get("gex") if isinstance(d.get("gex"), dict) else {}
    if gex.get("available") and side_f:
        if gex.get("bias") == "PIN":
            delta -= 0.01
            reasons.append("positive GEX pin")
        elif gex.get("bias") == "SQUEEZE":
            delta += 0.01
            reasons.append("negative GEX squeeze")
    if float(d.get("pcr_var_present") or 0) >= 1 and (_f(d.get("pcr_var")) or 0) >= 0.04:
        delta -= 0.01
        reasons.append("PCR swinging")
    book = d.get("book") if isinstance(d.get("book"), dict) else {}
    if book.get("available") and side_f:
        bias = str(book.get("bias") or "")
        agrees = (side_f > 0 and bias == "BID") or (side_f < 0 and bias == "ASK")
        opposes = (side_f > 0 and bias == "ASK") or (side_f < 0 and bias == "BID")
        if agrees:
            delta += 0.01
            reasons.append("book agrees")
        elif opposes:
            delta -= 0.01
            reasons.append("book opposes")
    delta = max(-MAX_NUDGE, min(MAX_NUDGE, delta))
    nudged = max(0.05, min(0.95, float(p_t1) + delta))
    return {"p_t1": nudged, "delta": round(delta, 4), "reasons": reasons}


def snapshot_rows(stock: str, *, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Every saved chain print for one symbol, oldest first. Used when training."""
    path = training_store.ensure_tables(db_path or knowledge_db.ensure_db_dir())
    if not os.path.isfile(path):
        return []
    conn = training_store._connect(path)
    cur = conn.execute(
        """
        SELECT bar_ts, session_date, pcr, ce_oi, pe_oi, iv_atm, iv_skew, gex_flip, gex_bias,
               fut_basis, vix_level, book_buy, book_sell, spot
        FROM chain_snapshots
        WHERE stock = ?
        ORDER BY bar_ts ASC
        """,
        (stock.strip().upper(),),
    )
    cols = [
        "bar_ts", "session_date", "pcr", "ce_oi", "pe_oi", "iv_atm", "iv_skew", "gex_flip", "gex_bias",
        "fut_basis", "vix_level", "book_buy", "book_sell", "spot",
    ]
    rows = [dict(zip(cols, rec)) for rec in cur.fetchall()]
    conn.close()
    return rows


def reading_from_prints(rows: List[Dict[str, Any]], bar_ts: Any) -> Dict[str, Any]:
    """Last print at or before this bar on the same session. No later bar is used."""
    if not rows:
        return {}
    bucket = bar_bucket(bar_ts)
    day = _session_date(bucket)
    last = None
    prev_pcr = None
    for row in rows:
        if row.get("session_date") != day or str(row.get("bar_ts") or "") > bucket:
            continue
        if last and last.get("pcr") is not None and str(row.get("bar_ts")) > str(last.get("bar_ts")):
            prev_pcr = last.get("pcr")
        elif last is None:
            prev_pcr = None
        if last is None or str(row.get("bar_ts")) >= str(last.get("bar_ts")):
            if last and last.get("pcr") is not None:
                prev_pcr = last.get("pcr")
            last = row
    if not last:
        return {}
    gex_known = last.get("gex_bias") or last.get("gex_flip") is not None
    return {
        "available": True,
        "pcr": last.get("pcr"),
        "pcr_prev": prev_pcr,
        "atm_ce": {"oi": last.get("ce_oi"), "implied_volatility": last.get("iv_atm")},
        "atm_pe": {"oi": last.get("pe_oi")},
        "futures_basis": last.get("fut_basis"),
        "vix_level": last.get("vix_level"),
        "iv_skew": last.get("iv_skew"),
        "gex": {
            "available": bool(gex_known),
            "flip": last.get("gex_flip"),
            "bias": last.get("gex_bias"),
            "iv_skew": last.get("iv_skew"),
        },
    }


def readings_asof(stock: str, bar_ts: Any = None, *, db_path: Optional[str] = None) -> Dict[str, Any]:
    """Chain print from this session at or before bar_ts. A later bar is never used."""
    path = training_store.ensure_tables(db_path or knowledge_db.ensure_db_dir())
    bucket = bar_bucket(bar_ts)
    stock_u = stock.strip().upper()
    conn = training_store._connect(path)
    cur = conn.execute(
        """
        SELECT bar_ts, pcr, ce_oi, pe_oi, iv_atm, iv_skew, gex_flip, gex_bias,
               fut_basis, vix_level, book_buy, book_sell, spot
        FROM chain_snapshots
        WHERE stock = ? AND session_date = ? AND bar_ts <= ?
        ORDER BY bar_ts DESC
        LIMIT 1
        """,
        (stock_u, _session_date(bucket), bucket),
    )
    rec = cur.fetchone()
    conn.close()
    if not rec:
        return {}
    cols = [
        "bar_ts", "pcr", "ce_oi", "pe_oi", "iv_atm", "iv_skew", "gex_flip", "gex_bias",
        "fut_basis", "vix_level", "book_buy", "book_sell", "spot",
    ]
    last = dict(zip(cols, rec))
    history = _recent(path, stock_u, bucket)
    pcr_var = _pcr_var(history)
    oi_build = _oi_build(history)
    prev_pcr = None
    for row in history:
        if row["bar_ts"] < last["bar_ts"] and row.get("pcr") is not None:
            prev_pcr = row["pcr"]
    gex_known = last.get("gex_bias") or last.get("gex_flip") is not None
    book: Dict[str, Any] = {"available": False}
    if last.get("book_buy") is not None and last.get("book_sell") is not None:
        buy_q, sell_q = float(last["book_buy"]), float(last["book_sell"])
        if buy_q + sell_q > 0:
            ratio = buy_q / sell_q if sell_q else 2.0
            book = {
                "available": True,
                "buy_quantity": buy_q,
                "sell_quantity": sell_q,
                "bias": "BID" if ratio >= 1.15 else ("ASK" if ratio <= 0.87 else "BALANCED"),
            }
    return {
        "available": True,
        "source": "chain_snapshot",
        "asof_bar": last["bar_ts"],
        "pcr": last["pcr"],
        "pcr_prev": prev_pcr,
        "atm_ce": {"oi": last["ce_oi"], "implied_volatility": last["iv_atm"]},
        "atm_pe": {"oi": last["pe_oi"]},
        "futures_basis": last["fut_basis"],
        "vix_level": last["vix_level"],
        "iv_skew": last["iv_skew"],
        "gex": {
            "available": bool(gex_known),
            "flip": last["gex_flip"],
            "bias": last["gex_bias"],
            "iv_skew": last["iv_skew"],
        },
        "book": book,
        "oi_build": oi_build,
        "pcr_var": pcr_var,
        "pcr_var_present": 1.0 if pcr_var is not None else 0.0,
    }


def capture_live(
    stock: str,
    *,
    spot: float = 0.0,
    vix_level: float = 0.0,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Store NIFTY/BANKNIFTY chain for this 15-minute bucket without a full analysis."""
    try:
        import full_market_analysis
        import kite_data
    except Exception as exc:
        return {"stored": False, "error": str(exc)}
    px = float(spot or 0)
    quote = None
    if px <= 0:
        quote, err = kite_data.fetch_live_quote(stock)
        if not quote:
            return {"stored": False, "error": err or "no spot"}
        px = float(quote.get("last_price") or 0)
    if px <= 0:
        return {"stored": False, "error": "no spot"}
    deriv = full_market_analysis.derivatives_snapshot(stock, px, vix_level=vix_level)
    if not deriv.get("available"):
        return {"stored": False, "error": deriv.get("error") or "chain unavailable"}
    out = capture(
        stock,
        deriv,
        live_quote=quote,
        vix_level=vix_level,
        spot=px,
        db_path=db_path,
    )
    out["spot"] = px
    return out


def _front_from(expiry: Any, today: Any, lookback_start: Any) -> Any:
    """A weekly is the front chain only in its expiry week. A monthly uses the lookback."""
    from datetime import timedelta

    if (expiry - today).days <= 7:
        return max(lookback_start, expiry - timedelta(days=6))
    return lookback_start


def backfill_listed_oi(
    symbols: Optional[List[str]] = None,
    *,
    days: int = 16,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Fill snapshots from Kite 15m OI for contracts still in the instrument dump.

    Expired weeklies are gone from that dump, so those sessions stay empty.
    """
    import time
    from datetime import date, timedelta

    import pandas as pd

    import fno_instruments
    import kite_data
    import kite_instruments

    import fno_universe

    names = [s.strip().upper() for s in (symbols or fno_universe.symbols())]
    path = training_store.ensure_tables(db_path or knowledge_db.ensure_db_dir())
    kite, err = kite_data._get_kite()
    if err or not kite:
        return {"ok": False, "error": err or "Kite not connected"}
    token_index = kite_instruments._load_index()
    nfo = fno_instruments._load_nfo_rows()
    today = date.today()
    since = today - timedelta(days=int(days))
    root = os.path.dirname(os.path.abspath(__file__))
    report: Dict[str, Any] = {"ok": True, "symbols": {}}

    def _oi_map(token: int, start, end) -> Dict[str, float]:
        candles = kite.historical_data(token, start, end, interval="15minute", oi=True)
        time.sleep(0.35)
        out: Dict[str, float] = {}
        for candle in candles or []:
            bucket = bar_bucket(candle.get("date"))
            if _in_cash_session(bucket):
                out[bucket] = float(candle.get("oi") or 0)
        return out

    for name in names:
        subset = [r for r in nfo if r.get("name") == name]
        expiries = sorted(
            {
                exp
                for r in subset
                if r.get("instrument_type") in ("CE", "PE")
                for exp in [fno_instruments._parse_expiry(r.get("expiry", ""))]
                if exp and exp >= today
            }
        )
        if not expiries:
            report["symbols"][name] = {"stored": 0, "error": "no listed expiry"}
            continue
        chosen = expiries[0]
        active_from = _front_from(chosen, today, since)
        strikes = sorted(
            {
                float(r["strike"])
                for r in subset
                if r.get("instrument_type") == "CE"
                and fno_instruments._parse_expiry(r.get("expiry", "")) == chosen
                and r.get("strike")
            }
        )
        futs = [
            r
            for r in subset
            if r.get("instrument_type") == "FUT" and fno_instruments._parse_expiry(r.get("expiry", "")) == chosen
        ]
        spot_path = os.path.join(root, "stock_signal_data", "fno_validate", f"{name}_15m_5y.csv")
        if not strikes or not os.path.isfile(spot_path):
            report["symbols"][name] = {"stored": 0, "error": "no strikes or spot file"}
            continue
        spot = pd.read_csv(spot_path, usecols=["date", "Close"])
        spot["date"] = pd.to_datetime(spot["date"])
        spot = spot[spot["date"] >= pd.Timestamp(since, tz="Asia/Kolkata")]
        bars = []
        needed = set()
        for ts, px in zip(spot["date"], spot["Close"]):
            price = float(px)
            if price <= 0:
                continue
            bucket = bar_bucket(ts)
            if bucket[:10] < active_from.isoformat() or not _in_cash_session(bucket):
                continue
            strike = min(strikes, key=lambda k: abs(k - price))
            bars.append((bucket, price, strike))
            needed.add(strike)
        start = datetime(since.year, since.month, since.day)
        end = datetime.now()
        oi_ce: Dict[float, Dict[str, float]] = {}
        oi_pe: Dict[float, Dict[str, float]] = {}
        missing = []
        for strike in sorted(needed):
            ce_row = next(
                (
                    r
                    for r in subset
                    if r.get("instrument_type") == "CE"
                    and abs(float(r.get("strike") or 0) - strike) < 0.1
                    and fno_instruments._parse_expiry(r.get("expiry", "")) == chosen
                ),
                None,
            )
            pe_row = next(
                (
                    r
                    for r in subset
                    if r.get("instrument_type") == "PE"
                    and abs(float(r.get("strike") or 0) - strike) < 0.1
                    and fno_instruments._parse_expiry(r.get("expiry", "")) == chosen
                ),
                None,
            )
            ce_tok = token_index.get(fno_instruments.quote_key(ce_row)) if ce_row else None
            pe_tok = token_index.get(fno_instruments.quote_key(pe_row)) if pe_row else None
            if not ce_tok or not pe_tok:
                missing.append(strike)
                continue
            try:
                oi_ce[strike] = _oi_map(int(ce_tok), start, end)
                oi_pe[strike] = _oi_map(int(pe_tok), start, end)
            except Exception:
                missing.append(strike)
        fut_close: Dict[str, float] = {}
        if futs:
            fut_tok = token_index.get(fno_instruments.quote_key(futs[0]))
            if fut_tok:
                try:
                    candles = kite.historical_data(int(fut_tok), start, end, interval="15minute")
                    time.sleep(0.35)
                    for candle in candles or []:
                        bucket = bar_bucket(candle.get("date"))
                        if _in_cash_session(bucket) and candle.get("close") is not None:
                            fut_close[bucket] = float(candle["close"])
                except Exception:
                    fut_close = {}
        stored = 0
        for bucket, price, strike in bars:
            ce_oi = (oi_ce.get(strike) or {}).get(bucket)
            pe_oi = (oi_pe.get(strike) or {}).get(bucket)
            if not ce_oi or not pe_oi:
                continue
            basis = None
            if fut_close.get(bucket) is not None:
                basis = fut_close[bucket] - price
            saved = capture(
                name,
                {
                    "pcr": pe_oi / ce_oi,
                    "atm_ce": {"oi": ce_oi},
                    "atm_pe": {"oi": pe_oi},
                    "futures_basis": basis,
                },
                spot=price,
                bar_ts=bucket,
                db_path=path,
            )
            if saved.get("stored"):
                stored += 1
        report["symbols"][name] = {
            "expiry": chosen.isoformat(),
            "active_from": active_from.isoformat(),
            "strikes": len(needed),
            "missing_strikes": len(missing),
            "stored": stored,
        }
    return report
