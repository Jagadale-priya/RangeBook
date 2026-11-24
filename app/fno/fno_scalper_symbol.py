"""Resolve Scalper symbols: index / equity / NFO|BFO CE-PE."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

import fno_universe

_INDEX = {"NIFTY", "BANKNIFTY", "SENSEX", "FINNIFTY", "MIDCPNIFTY"}
_EX_OPT = ("NFO", "BFO")
_TOKEN = re.compile(r"^[A-Z0-9][A-Z0-9\-_]*$")
# Require a digit before CE/PE so RELIANCE / PEACE are not treated as options
_OPT_SUFFIX = re.compile(r"\d(CE|PE)$", re.I)


def _norm_key(raw: str) -> str:
    s = " ".join(str(raw or "").strip().upper().split())
    return s


def resolve(raw: str) -> Dict[str, Any]:
    """Return scalper instrument descriptor.

    key is what kite_data / load_1m_bars should use (INDEX or EXCHANGE:SYMBOL).
    """
    s = _norm_key(raw)
    if not s:
        return {
            "ok": False,
            "error": "Empty symbol",
            "key": "NIFTY",
            "kind": "index",
            "exchange": "NSE",
            "tradingsymbol": "NIFTY 50",
            "underlying": "NIFTY",
        }

    if ":" in s:
        ex, sym = s.split(":", 1)
        ex, sym = ex.strip(), sym.strip()
        if ex in _EX_OPT and sym:
            kind = "option" if _OPT_SUFFIX.search(sym) else "future"
            und = _guess_underlying(sym)
            it = None
            m_it = _OPT_SUFFIX.search(sym)
            if m_it:
                it = m_it.group(1).upper()
            return {
                "ok": True,
                "key": f"{ex}:{sym}",
                "kind": kind,
                "exchange": ex,
                "tradingsymbol": sym,
                "underlying": und,
                "display": sym,
                "instrument_type": it,
            }
        if ex in ("NSE", "BSE") and sym:
            # Index spot aliases
            for k, (ix_ex, ix_sym) in fno_universe.INDEX_SPOT.items():
                if ex == ix_ex and sym.upper() == ix_sym.upper():
                    return {
                        "ok": True,
                        "key": k,
                        "kind": "index",
                        "exchange": ex,
                        "tradingsymbol": ix_sym,
                        "underlying": k,
                        "display": k,
                    }
            return {
                "ok": True,
                "key": f"{ex}:{sym}" if ex == "BSE" else sym,
                "kind": "equity",
                "exchange": ex,
                "tradingsymbol": sym,
                "underlying": sym,
                "display": sym,
            }

    if s in _INDEX or s in fno_universe.INDEX_SPOT:
        spot = fno_universe.INDEX_SPOT.get(s) or ("NSE", s)
        return {
            "ok": True,
            "key": s,
            "kind": "index",
            "exchange": spot[0],
            "tradingsymbol": spot[1],
            "underlying": s,
            "display": s,
        }

    # Bare option tradingsymbol (e.g. NIFTY25NOV25400CE)
    if _OPT_SUFFIX.search(s) and _TOKEN.match(s):
        row = _find_option_row(s)
        if row:
            ex = str(row.get("exchange") or "NFO").upper()
            return {
                "ok": True,
                "key": f"{ex}:{s}",
                "kind": "option",
                "exchange": ex,
                "tradingsymbol": s,
                "underlying": str(row.get("name") or _guess_underlying(s)).upper(),
                "display": s,
                "strike": row.get("strike"),
                "expiry": row.get("expiry"),
                "instrument_type": row.get("instrument_type"),
            }
        # Still try NFO first — Kite token index may have it
        m_it = _OPT_SUFFIX.search(s)
        return {
            "ok": True,
            "key": f"NFO:{s}",
            "kind": "option",
            "exchange": "NFO",
            "tradingsymbol": s,
            "underlying": _guess_underlying(s),
            "display": s,
            "instrument_type": (m_it.group(1).upper() if m_it else None),
        }

    # Equity / F&O underlying name
    if _TOKEN.match(s):
        return {
            "ok": True,
            "key": s,
            "kind": "equity",
            "exchange": "NSE",
            "tradingsymbol": s,
            "underlying": s,
            "display": s,
        }

    return {
        "ok": False,
        "error": f"Unrecognized symbol: {raw}",
        "key": s,
        "kind": "unknown",
        "exchange": None,
        "tradingsymbol": s,
        "underlying": None,
        "display": s,
    }


def option_call_side(meta: Optional[Dict[str, Any]]) -> Optional[str]:
    """CE/PE options → BUY only; index/equity → None (both BUY and SELL)."""
    m = meta or {}
    kind = str(m.get("kind") or "").lower()
    it = str(m.get("instrument_type") or "").upper()
    if it not in ("CE", "PE"):
        ts = str(m.get("tradingsymbol") or m.get("display") or m.get("key") or "").upper()
        if ":" in ts:
            ts = ts.split(":", 1)[-1]
        m_it = _OPT_SUFFIX.search(ts)
        if m_it:
            it = m_it.group(1).upper()
        elif kind == "option":
            if ts.endswith("CE"):
                it = "CE"
            elif ts.endswith("PE"):
                it = "PE"
    if it in ("CE", "PE") or kind == "option":
        return "BUY"
    return None


def _guess_underlying(sym: str) -> Optional[str]:
    u = str(sym or "").upper()
    for name in ("BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "SENSEX", "NIFTY"):
        if u.startswith(name):
            return name
    # Equity option: letters before first digit
    m = re.match(r"^([A-Z]+)", u)
    return m.group(1) if m else None


def _find_option_row(tradingsymbol: str) -> Optional[Dict[str, Any]]:
    try:
        import fno_instruments

        ts = str(tradingsymbol).upper()
        for row in fno_instruments._load_nfo_rows():
            if str(row.get("tradingsymbol") or "").upper() == ts:
                it = str(row.get("instrument_type") or "").upper()
                if it in ("CE", "PE") or _OPT_SUFFIX.search(ts):
                    return row
    except Exception:
        pass
    return None


def t1_for(kind: str, entry: float, atr: Optional[float], mode: str = "setup_t12") -> float:
    """Asset-aware T1 distance in price points (index pts / equity pts / premium pts)."""
    m = str(mode or "").lower()
    # Proven ≥25pt ignition book uses 25pt target on index
    if "ignition" in m or "ign100" in m:
        base = 25.0
    elif "15" in m:
        base = 15.0
    else:
        base = 12.0
    k = str(kind or "index").lower()
    a = float(atr) if atr is not None and atr == atr and float(atr) > 0 else 0.0
    px = abs(float(entry or 0))
    if k == "index":
        return float(base)
    if k == "option":
        return round(max(0.35 * a if a > 0 else 0.5, 0.5), 2)
    # equity
    pct = px * 0.0015
    return round(max(pct, 0.35 * a if a > 0 else 1.0, 1.0), 2)


_MONTHS = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}


def _parse_option_query(q: str) -> Dict[str, Any]:
    """Parse freestyle queries like 'NIFTY 25300 CE' / 'nifty 23 nov 25450 call'."""
    raw = _norm_key(q)
    out: Dict[str, Any] = {
        "tokens": raw.split(),
        "side": None,
        "strike": None,
        "underlying": None,
        "exp_day": None,
        "exp_month": None,
        "exp_year": None,
        "expiry": None,
    }
    if re.search(r"\b(CE|CALL)\b", raw) or raw.endswith(" CE") or raw.endswith("CALL"):
        out["side"] = "CE"
    if re.search(r"\b(PE|PUT)\b", raw) or raw.endswith(" PE") or raw.endswith("PUT"):
        out["side"] = "PE"

    # Date: "23 NOV" / "23RD NOV 2026" / "NOV 23" / "23-NOV-26"
    m_dm = re.search(
        r"\b(\d{1,2})(?:ST|ND|RD|TH)?[\s\-/]+(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)"
        r"(?:[\s\-/]+(20\d{2}|\d{2}))?\b",
        raw,
    )
    m_md = re.search(
        r"\b(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)"
        r"[\s\-/]+(\d{1,2})(?:ST|ND|RD|TH)?(?:[\s\-/]+(20\d{2}|\d{2}))?\b",
        raw,
    )
    if m_dm:
        out["exp_day"] = int(m_dm.group(1))
        out["exp_month"] = _MONTHS[m_dm.group(2)]
        if m_dm.group(3):
            y = int(m_dm.group(3))
            out["exp_year"] = y if y >= 100 else 2000 + y
    elif m_md:
        out["exp_month"] = _MONTHS[m_md.group(1)]
        out["exp_day"] = int(m_md.group(2))
        if m_md.group(3):
            y = int(m_md.group(3))
            out["exp_year"] = y if y >= 100 else 2000 + y

    if out["exp_day"] and out["exp_month"]:
        from datetime import date

        y = out["exp_year"] or date.today().year
        # If month already passed and no explicit year, roll to next year
        if out["exp_year"] is None:
            try:
                cand = date(y, int(out["exp_month"]), int(out["exp_day"]))
                if cand < date.today():
                    y += 1
            except ValueError:
                pass
        out["exp_year"] = y
        try:
            out["expiry"] = f"{y:04d}-{int(out['exp_month']):02d}-{int(out['exp_day']):02d}"
        except (TypeError, ValueError):
            out["expiry"] = None

    # strip CALL/PUT/CE/PE and month names for strike detection
    cleaned = re.sub(r"\b(CALL|PUT|CE|PE)\b", " ", raw)
    cleaned = re.sub(
        r"\b(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\b", " ", cleaned
    )
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    # Strike = 4–6 digit number (not a 1–2 digit day)
    m_strike = re.search(r"\b(\d{4,6})\b", cleaned)
    if m_strike:
        out["strike"] = float(m_strike.group(1))
    for name in ("BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "SENSEX", "NIFTY"):
        if name in cleaned.replace(" ", "") or cleaned.startswith(name) or name in cleaned.split():
            out["underlying"] = name
            break
    # Compact kite-like fragment without spaces
    out["compact"] = re.sub(r"[^A-Z0-9]", "", raw)
    return out


def _opt_row_payload(row: Dict[str, Any]) -> Dict[str, Any]:
    ts = str(row.get("tradingsymbol") or "").upper()
    name = str(row.get("name") or "").upper()
    it = str(row.get("instrument_type") or "").upper()
    ex = str(row.get("exchange") or "NFO").upper()
    return {
        "symbol": ts,
        "tradingsymbol": ts,
        "name": f"{name} {it} {row.get('strike')} {row.get('expiry') or ''}".strip(),
        "exchange": ex,
        "instrument_type": it,
        "kind": "option",
        "key": f"{ex}:{ts}",
        "display": ts,
        "underlying": name,
        "strike": row.get("strike"),
        "expiry": row.get("expiry"),
    }


def _candidate_option_symbols(parsed: Dict[str, Any]) -> List[str]:
    """Build likely Kite tradingsymbols from freestyle parse."""
    und = str(parsed.get("underlying") or "").upper()
    side = str(parsed.get("side") or "").upper()
    strike = parsed.get("strike")
    if not und or not side or strike is None:
        return []
    try:
        strike_i = int(float(strike))
    except (TypeError, ValueError):
        return []
    y = int(parsed.get("exp_year") or 0)
    m = parsed.get("exp_month")
    d = parsed.get("exp_day")
    out: List[str] = []
    if y and m:
        mon = {v: k for k, v in _MONTHS.items()}.get(int(m), "")
        yy = y % 100
        if mon:
            # Monthly style: NIFTY26NOV25450CE
            out.append(f"{und}{yy:02d}{mon}{strike_i}{side}")
        if d:
            # Weekly style: NIFTY26N2325450CE (YY + M + DD)
            out.append(f"{und}{yy:02d}{str(mon)[:1]}{int(d):02d}{strike_i}{side}")
    return out


def search_scalper(query: str, *, limit: int = 12) -> Dict[str, Any]:
    """Merge NSE equity/index catalog with NFO/BFO CE/PE for Scalper search."""
    import instrument_search

    q = _norm_key(query)
    limit = int(max(1, min(int(limit or 12), 24)))
    parsed = _parse_option_query(q) if q else {}
    option_query = bool(
        parsed.get("strike") is not None
        or parsed.get("side")
        or parsed.get("expiry")
    )

    chips = []
    for k in ("NIFTY", "BANKNIFTY", "SENSEX"):
        if not q or k.startswith(q) or q in k:
            chips.append(
                {
                    "symbol": k,
                    "tradingsymbol": k,
                    "name": k,
                    "exchange": fno_universe.INDEX_SPOT.get(k, ("NSE", k))[0],
                    "instrument_type": "INDEX",
                    "kind": "index",
                    "key": k,
                    "display": k,
                }
            )

    opt_hits: List[Dict[str, Any]] = []
    search_err = None
    if q and (len(q) >= 2 or option_query):
        try:
            import fno_instruments

            rows = fno_instruments._load_nfo_rows()
            und = parsed.get("underlying")
            strike = parsed.get("strike")
            side = parsed.get("side")
            want_exp = str(parsed.get("expiry") or "")[:10] or None
            compact = re.sub(r"[^A-Z0-9]", "", q)
            scored: List[Tuple[int, str, Dict[str, Any]]] = []

            # 1) Direct filter when user gave strike / CE-PE / date (accurate path)
            if option_query:
                for row in rows:
                    it = str(row.get("instrument_type") or "").upper()
                    name = str(row.get("name") or "").upper()
                    if it not in ("CE", "PE"):
                        continue
                    if und and name != und:
                        continue
                    if side and it != side:
                        continue
                    if strike is not None:
                        try:
                            if abs(float(row.get("strike") or 0) - float(strike)) > 0.05:
                                continue
                        except (TypeError, ValueError):
                            continue
                    exp = str(row.get("expiry") or "")[:10]
                    sc = 900
                    if want_exp:
                        if exp == want_exp:
                            sc = 1200
                        elif len(exp) >= 7 and exp[5:7] == want_exp[5:7]:
                            sc = 950
                        else:
                            sc = 700
                    scored.append((sc, exp, _opt_row_payload(row)))

                # Also force-match constructed kite symbols if present in cache
                by_ts = {
                    str(r.get("tradingsymbol") or "").upper(): r
                    for r in rows
                    if str(r.get("instrument_type") or "").upper() in ("CE", "PE")
                }
                for cand in _candidate_option_symbols(parsed):
                    row = by_ts.get(cand)
                    if not row:
                        continue
                    exp = str(row.get("expiry") or "")[:10]
                    sc = 1300 if want_exp and exp == want_exp else 1100
                    scored.append((sc, exp, _opt_row_payload(row)))

            # 2) Symbol / prefix search (NIFTY26NOV25450CE typed directly)
            if not option_query or not scored:
                for row in rows:
                    it = str(row.get("instrument_type") or "").upper()
                    ts = str(row.get("tradingsymbol") or "").upper()
                    name = str(row.get("name") or "").upper()
                    if it not in ("CE", "PE"):
                        continue
                    sc = 0
                    if ts == q or ts == compact:
                        sc = 1000
                    elif compact and ts.startswith(compact):
                        sc = 920
                    elif len(q) >= 5 and ts.startswith(q.replace(" ", "")):
                        sc = 900
                    elif len(q) >= 5 and q.replace(" ", "") in ts:
                        sc = 700
                    elif len(q) >= 3 and name.startswith(q.split()[0]):
                        # bare "NIFTY" — light option browse only when NOT a freestyle option query
                        if not option_query:
                            sc = 500
                    if sc <= 0:
                        continue
                    scored.append((sc, str(row.get("expiry") or "")[:10], _opt_row_payload(row)))

            def _exp_dist(exp: str) -> int:
                if not want_exp or not exp:
                    return 0
                try:
                    from datetime import datetime

                    a = datetime.strptime(want_exp, "%Y-%m-%d")
                    b = datetime.strptime(exp[:10], "%Y-%m-%d")
                    return abs((b - a).days)
                except Exception:
                    return 9999

            # Dedupe by key keeping best score
            best: Dict[str, Tuple[int, str, Dict[str, Any]]] = {}
            for item in scored:
                key = item[2]["key"]
                prev = best.get(key)
                if prev is None or item[0] > prev[0]:
                    best[key] = item
            ranked = list(best.values())
            ranked.sort(key=lambda x: (-x[0], _exp_dist(x[1]), x[1], x[2]["tradingsymbol"]))

            # When user named an expiry date, only show that expiry (accurate dropdown).
            # If missing, show the nearest few with a clear fallback hint later.
            if want_exp:
                exact = [x for x in ranked if x[1] == want_exp]
                if exact:
                    ranked = exact
                else:
                    ranked = ranked[: min(5, max(limit, 3))]
            opt_hits = [x[2] for x in ranked[: max(limit, 12)]]
        except Exception as exc:
            search_err = str(exc)
            opt_hits = []

    merged: List[Dict[str, Any]] = []
    seen = set()

    def _add(row: Dict[str, Any]) -> None:
        key = str(row.get("key") or row.get("symbol") or "").upper()
        if not key or key in seen:
            return
        seen.add(key)
        if "kind" not in row:
            row = dict(row)
            row["kind"] = "index" if key in _INDEX else "equity"
            row["key"] = key
            row["display"] = row.get("symbol") or key
        merged.append(row)

    if not q:
        for c in chips:
            _add(c)
    elif option_query:
        for o in opt_hits:
            _add(o)
    else:
        for c in chips:
            _add(c)
        for o in opt_hits:
            _add(o)
        # Equity catalog only for non-option queries
        catalog_q = q
        try:
            base = instrument_search.search(catalog_q, limit=limit)
            for r in list(base.get("results") or []):
                _add(r if isinstance(r, dict) else {"symbol": str(r), "key": str(r)})
        except Exception as exc:
            search_err = search_err or str(exc)

    hint = "Type e.g. NIFTY 23 Nov 25450 Call — pick a row to load the chart."
    want_exp = str((parsed or {}).get("expiry") or "")[:10] or None
    if option_query and not merged:
        hint = (
            "No option match in cache. Try NIFTY26NOV25450CE, or refresh Kite instruments."
            + (f" ({search_err})" if search_err else "")
        )
    elif option_query and want_exp and merged:
        if str(merged[0].get("expiry") or "")[:10] == want_exp:
            hint = f"Exact expiry {want_exp} — pick to load."
        else:
            hint = (
                f"No contract for {want_exp}; nearest shown. "
                "Refresh Kite instruments if the weekly is missing."
            )

    return {
        "available": True,
        "query": q,
        "parsed": {
            k: parsed.get(k)
            for k in ("underlying", "strike", "side", "expiry", "exp_day", "exp_month", "exp_year")
            if parsed.get(k) is not None
        },
        "results": merged[:limit],
        "hint": hint,
        "scope": "scalper",
        "error": search_err,
    }
