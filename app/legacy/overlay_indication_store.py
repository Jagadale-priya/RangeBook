"""Separate SQLite history for 15m overlay indication signals (parallel to model)."""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional


def default_db_path() -> str:
    import knowledge_db

    return knowledge_db.ensure_db_dir()


def ensure_tables(db_path: Optional[str] = None) -> str:
    path = db_path or default_db_path()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS overlay_indication_calls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock TEXT NOT NULL,
            session_date TEXT NOT NULL,
            bar_time TEXT NOT NULL,
            decision TEXT NOT NULL,
            status TEXT NOT NULL,
            entry REAL,
            stop_loss REAL,
            target_1 REAL,
            best_acc REAL,
            accuracy_label TEXT,
            rule_ids_json TEXT,
            tags_json TEXT,
            payload_json TEXT,
            taken_at TEXT,
            closed_at TEXT,
            status_plain TEXT,
            notify_sent INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(stock, bar_time, decision)
        );
        CREATE INDEX IF NOT EXISTS idx_overlay_ind_day
            ON overlay_indication_calls(session_date, stock);
        CREATE INDEX IF NOT EXISTS idx_overlay_ind_open
            ON overlay_indication_calls(stock, status);
        """
    )
    conn.commit()
    conn.close()
    return path


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _plain(status: str) -> str:
    return {
        "open": "Open",
        "t1_before_sl": "Hit first target",
        "sl_before_t1": "Hit stop",
        "booked": "Booked (exit rule)",
        "stopped": "Stopped (exit rule)",
        "expired": "Favour window done",
        "cancelled": "Cancelled",
    }.get(status, status)


def upsert_signal(sig: Dict[str, Any], *, db_path: Optional[str] = None) -> Dict[str, Any]:
    """Overlay indication channel retired — never insert new rows."""
    return {
        "ok": False,
        "created": False,
        "notify": False,
        "reason": "overlay_indication_disabled",
    }
    # --- retired ---
    path = ensure_tables(db_path)
    stock = str(sig.get("symbol") or "").upper()
    bar_time = str(sig.get("bar_time") or "")
    decision = str(sig.get("decision") or sig.get("side") or "")
    if not stock or not bar_time or decision not in ("BUY", "SELL"):
        return {"ok": False, "reason": "bad_payload"}
    session_date = bar_time[:10]
    now = _now()
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.execute(
            "SELECT id, status FROM overlay_indication_calls WHERE stock=? AND bar_time=? AND decision=?",
            (stock, bar_time, decision),
        )
        row = cur.fetchone()
        if row:
            return {"ok": True, "created": False, "id": row["id"], "status": row["status"]}
        payload = json.dumps(sig, default=str)
        tags = json.dumps(sig.get("accuracy_tags") or [], default=str)
        rules = json.dumps(sig.get("rule_ids") or [], default=str)
        cur = conn.execute(
            """
            INSERT INTO overlay_indication_calls (
                stock, session_date, bar_time, decision, status,
                entry, stop_loss, target_1, best_acc, accuracy_label,
                rule_ids_json, tags_json, payload_json,
                taken_at, closed_at, status_plain, notify_sent,
                created_at, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                stock,
                session_date,
                bar_time,
                decision,
                "open",
                sig.get("entry"),
                sig.get("stop_loss"),
                sig.get("target_1"),
                sig.get("best_acc_1m"),
                sig.get("accuracy_label"),
                rules,
                tags,
                payload,
                now,
                None,
                _plain("open"),
                0,
                now,
                now,
            ),
        )
        conn.commit()
        return {"ok": True, "created": True, "id": cur.lastrowid, "status": "open", "notify": False}
    finally:
        conn.close()


def list_today(stock: str, *, db_path: Optional[str] = None, day: Optional[str] = None) -> List[Dict[str, Any]]:
    path = ensure_tables(db_path)
    if day is None:
        # IST-ish: local date is fine for India desk machines
        day = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT * FROM overlay_indication_calls
            WHERE stock=? AND session_date=?
            ORDER BY bar_time ASC, id ASC
            """,
            (str(stock).upper(), day),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def list_history(
    stock: str,
    *,
    db_path: Optional[str] = None,
    limit: int = 200,
    exclude_today: bool = True,
) -> List[Dict[str, Any]]:
    path = ensure_tables(db_path)
    today = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        if exclude_today:
            rows = conn.execute(
                """
                SELECT * FROM overlay_indication_calls
                WHERE stock=? AND session_date < ?
                ORDER BY session_date DESC, bar_time DESC
                LIMIT ?
                """,
                (str(stock).upper(), today, int(limit)),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT * FROM overlay_indication_calls
                WHERE stock=?
                ORDER BY session_date DESC, bar_time DESC
                LIMIT ?
                """,
                (str(stock).upper(), int(limit)),
            ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def list_open(stock: Optional[str] = None, *, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    path = ensure_tables(db_path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        if stock:
            rows = conn.execute(
                "SELECT * FROM overlay_indication_calls WHERE status='open' AND stock=? ORDER BY id",
                (str(stock).upper(),),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM overlay_indication_calls WHERE status='open' ORDER BY id"
            ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def mark_notify_sent(row_id: int, *, db_path: Optional[str] = None) -> None:
    path = ensure_tables(db_path)
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            "UPDATE overlay_indication_calls SET notify_sent=1, updated_at=? WHERE id=?",
            (_now(), int(row_id)),
        )
        conn.commit()
    finally:
        conn.close()


def claim_notify_sent(row_id: int, *, db_path: Optional[str] = None) -> bool:
    """Atomically claim the NEW-call toast slot. True only for the first claimant."""
    path = ensure_tables(db_path)
    conn = sqlite3.connect(path)
    try:
        cur = conn.execute(
            "UPDATE overlay_indication_calls SET notify_sent=1, updated_at=? "
            "WHERE id=? AND notify_sent=0",
            (_now(), int(row_id)),
        )
        conn.commit()
        return int(cur.rowcount or 0) > 0
    finally:
        conn.close()


def release_notify_sent(row_id: int, *, db_path: Optional[str] = None) -> None:
    """Allow catch-up retry if the claimed toast failed to send."""
    path = ensure_tables(db_path)
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            "UPDATE overlay_indication_calls SET notify_sent=0, updated_at=? WHERE id=?",
            (_now(), int(row_id)),
        )
        conn.commit()
    finally:
        conn.close()


# Fallback book floors when signal payload has no research med_favour_pts.
# Research (overlay_favour_bars_5m_1m): MFE@6×5m med — NIFTY ~23–25, BN ~56–67, SX ~54–68.
BOOK_FAVOUR_PTS = {"NIFTY": 24.0, "BANKNIFTY": 60.0, "SENSEX": 60.0}
# Legacy absolute floor; live early-kill uses research favour_horizon (6×5m=30m).
EARLY_KILL_MINUTES = 30
DEFAULT_FAVOUR_HORIZON_BARS = 6  # research MFE@6 window
# No favour-book / early-drop / live BOOK-DROP alerts until the call has been
# listed this long. Prevents NEW→BOOK/DROP within seconds from bar-clock bugs.
OVERLAY_MANAGE_GRACE_MIN = 3


def _parse_naive_ts(raw: Any) -> Optional[datetime]:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    try:
        ts = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception:
        return None
    if ts.tzinfo is not None:
        ts = ts.replace(tzinfo=None)
    return ts


def early_kill_elapsed_minutes(row: Dict[str, Any], *, asof: Optional[datetime] = None) -> float:
    """Minutes since the overlay call was *listed*, not since the signal bar open.

    Overlay evaluates the closed 15m bar, so `bar_time` is already ~15m old when
    NEW fires. Measuring early-kill from bar_time caused NEW → DROP within seconds
    (elapsed already ≥ 15m at toast time).
    """
    now = asof or datetime.now()
    if getattr(now, "tzinfo", None) is not None:
        now = now.replace(tzinfo=None)
    listed = (
        _parse_naive_ts((row or {}).get("created_at"))
        or _parse_naive_ts((row or {}).get("taken_at"))
        or _parse_naive_ts((row or {}).get("bar_time"))
    )
    if listed is None:
        return 0.0
    return max(0.0, (now - listed).total_seconds() / 60.0)


def record_path_extremes(
    row_id: int,
    *,
    high: float,
    low: float,
    last: float,
    db_path: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Accumulate path high/low/last on open overlay rows (for favour book / early drop)."""
    path = ensure_tables(db_path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT * FROM overlay_indication_calls WHERE id=?", (int(row_id),)
        ).fetchone()
        if not row or row["status"] != "open":
            return _row_to_dict(row) if row else None
        try:
            payload = json.loads(row["payload_json"] or "{}")
        except Exception:
            payload = {}
        entry = float(row["entry"] or last)
        prev_hi = float(payload.get("path_high") or entry)
        prev_lo = float(payload.get("path_low") or entry)
        # Favour path follows live LTP only. Feeding the signal bar's OHLC
        # includes pre-entry prints and falsely inflates MFE (e.g. SENSEX
        # SELL "BOOK +404" while price was already against the trade).
        last_f = float(last)
        payload["path_high"] = max(prev_hi, last_f, entry)
        payload["path_low"] = min(prev_lo, last_f, entry)
        payload["path_last"] = last_f
        stamp = _now()
        conn.execute(
            """
            UPDATE overlay_indication_calls
            SET payload_json=?, updated_at=?
            WHERE id=?
            """,
            (json.dumps(payload, default=str), stamp, int(row_id)),
        )
        conn.commit()
        row2 = conn.execute(
            "SELECT * FROM overlay_indication_calls WHERE id=?", (int(row_id),)
        ).fetchone()
        return _row_to_dict(row2)
    finally:
        conn.close()


def _favour_from_payload(side: str, entry: float, payload: Dict[str, Any]) -> tuple:
    hi = float(payload.get("path_high") or entry)
    lo = float(payload.get("path_low") or entry)
    last = float(payload.get("path_last") or entry)
    if str(side).upper() == "BUY":
        return hi - entry, last - entry
    return entry - lo, entry - last


def _payload_favour(payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    fav = payload.get("favour")
    return fav if isinstance(fav, dict) else {}


def research_favour_hint(stock: str, side: str) -> Dict[str, Any]:
    """Research live-hint from overlay_favour_bars_5m_1m (FAVOUR_FALLBACK)."""
    try:
        import fno_overlay_indication as foi

        block = (foi.FAVOUR_FALLBACK or {}).get(str(stock).upper()) or {}
        hint = block.get(str(side).upper()) or {}
        return hint if isinstance(hint, dict) else {}
    except Exception:
        return {}


def book_favour_threshold(
    stock: str,
    *,
    side: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
) -> float:
    """Book floor = research med favour pts (MFE@6×5m), not a flat desk guess."""
    fav = _payload_favour(payload)
    for key in ("med_favour_pts", "med_favour", "favour_pts"):
        raw = None
        if payload and payload.get(key) is not None:
            raw = payload.get(key)
        elif fav.get(key) is not None:
            raw = fav.get(key)
        if raw is not None:
            try:
                val = float(raw)
                if val > 0:
                    return val
            except (TypeError, ValueError):
                pass
    hint = research_favour_hint(stock, str(side or "BUY"))
    if hint.get("med_favour_pts") is not None:
        try:
            return float(hint["med_favour_pts"])
        except (TypeError, ValueError):
            pass
    return float(BOOK_FAVOUR_PTS.get(str(stock).upper(), 24.0))


def early_kill_minutes_for(
    stock: str,
    *,
    side: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
) -> float:
    """Minutes before early-drop. Research measured med favour at 6×5m (=30m)."""
    fav = _payload_favour(payload)
    horizon = None
    if payload and payload.get("favour_horizon_bars") is not None:
        horizon = payload.get("favour_horizon_bars")
    elif fav.get("favour_horizon_bars") is not None:
        horizon = fav.get("favour_horizon_bars")
    if horizon is None:
        hint = research_favour_hint(stock, str(side or "BUY"))
        horizon = hint.get("favour_horizon_bars")
    try:
        bars = int(horizon) if horizon is not None else DEFAULT_FAVOUR_HORIZON_BARS
    except (TypeError, ValueError):
        bars = DEFAULT_FAVOUR_HORIZON_BARS
    mins = max(1, bars) * 5
    return float(max(EARLY_KILL_MINUTES, mins))


def update_path(
    row_id: int,
    *,
    high: float,
    low: float,
    db_path: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Legacy T1/SL path close — skipped when levels are null (favour-bars mode)."""
    path = ensure_tables(db_path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT * FROM overlay_indication_calls WHERE id=?", (int(row_id),)
        ).fetchone()
        if not row or row["status"] != "open":
            return _row_to_dict(row) if row else None
        sl = row["stop_loss"]
        t1 = row["target_1"]
        # Favour-bars mode: no fixed SL/T1 — do not close on price path
        if sl is None or t1 is None:
            return _row_to_dict(row)
        side = row["decision"]
        hit = None
        if side == "BUY":
            t1_hit = high >= float(t1)
            sl_hit = low <= float(sl)
        else:
            t1_hit = low <= float(t1)
            sl_hit = high >= float(sl)
        if t1_hit and sl_hit:
            hit = "sl_before_t1"
        elif t1_hit:
            hit = "t1_before_sl"
        elif sl_hit:
            hit = "sl_before_t1"
        if not hit:
            return _row_to_dict(row)
        now = _now()
        conn.execute(
            """
            UPDATE overlay_indication_calls
            SET status=?, status_plain=?, closed_at=?, updated_at=?
            WHERE id=?
            """,
            (hit, _plain(hit), now, now, int(row_id)),
        )
        conn.commit()
        row2 = conn.execute(
            "SELECT * FROM overlay_indication_calls WHERE id=?", (int(row_id),)
        ).fetchone()
        return _row_to_dict(row2)
    finally:
        conn.close()


def close_by_exit_rule(
    row_id: int,
    *,
    status: str,
    detail: Optional[str] = None,
    db_path: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Close open indication via book/stop RULE (not price levels)."""
    if status not in ("booked", "stopped"):
        return None
    path = ensure_tables(db_path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT * FROM overlay_indication_calls WHERE id=?", (int(row_id),)
        ).fetchone()
        if not row or row["status"] != "open":
            return _row_to_dict(row) if row else None
        stamp = _now()
        plain = _plain(status)
        if detail:
            plain = f"{plain} · {detail}"
        # Keep payload; fold exit detail into tags_json note if useful
        conn.execute(
            """
            UPDATE overlay_indication_calls
            SET status=?, status_plain=?, closed_at=?, updated_at=?
            WHERE id=?
            """,
            (status, plain, stamp, stamp, int(row_id)),
        )
        conn.commit()
        row2 = conn.execute(
            "SELECT * FROM overlay_indication_calls WHERE id=?", (int(row_id),)
        ).fetchone()
        return _row_to_dict(row2)
    finally:
        conn.close()


def maybe_exit_by_rules(
    row_id: int,
    df: Any,
    *,
    db_path: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Evaluate book/stop rules on latest bar; close if either fires."""
    import fno_overlay_indication as foi

    path = ensure_tables(db_path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT * FROM overlay_indication_calls WHERE id=?", (int(row_id),)
        ).fetchone()
        if not row or row["status"] != "open":
            return _row_to_dict(row) if row else None
        d = _row_to_dict(row)
    finally:
        conn.close()

    payload = d.get("payload") or {}
    side = str(d.get("decision") or "")
    book = payload.get("book_profit_rule") or d.get("book_profit_rule")
    stop = payload.get("stop_rule") or d.get("stop_rule")
    if not book and not stop:
        exits = foi.exit_rules_for(str(d.get("stock") or "NIFTY"), side)
        book = exits.get("book_profit_rule")
        stop = exits.get("stop_rule")
    ev = foi.evaluate_exit_on_bar(
        df,
        side=side,
        book_rule=book,
        stop_rule=stop,
        symbol=str(d.get("stock") or ""),
    )
    if not ev or not ev.get("status"):
        return d
    detail = (
        ev.get("stop_label")
        if ev["status"] == "stopped"
        else ev.get("book_label")
    )
    return close_by_exit_rule(
        int(row_id), status=str(ev["status"]), detail=detail, db_path=db_path
    )


def manage_open_trade(
    row_id: int,
    df: Any,
    *,
    high: float,
    low: float,
    last: float,
    db_path: Optional[str] = None,
    asof: Optional[datetime] = None,
) -> Optional[Dict[str, Any]]:
    """Path update + book/stop rules + favour book + early drop. Returns closed row or open.

    Alert kinds (for caller notify):
      booked_rule / booked_favour / stopped_rule / stopped_early / expired
    """
    d = record_path_extremes(
        int(row_id), high=high, low=low, last=last, db_path=db_path
    )
    if not d or d.get("status") != "open":
        return d

    elapsed = early_kill_elapsed_minutes(d, asof=asof)
    # Grace after listing: no BOOK/DROP of any kind in the first minutes
    # (fixes NEW→DROP/BOOK within ~1m from bar-clock / same-bar atoms).
    if elapsed < OVERLAY_MANAGE_GRACE_MIN:
        return d

    closed = maybe_exit_by_rules(int(row_id), df, db_path=db_path)
    if closed and closed.get("status") in ("booked", "stopped"):
        closed["alert_kind"] = (
            "booked_rule" if closed["status"] == "booked" else "stopped_rule"
        )
        return closed

    payload = (closed or d).get("payload") or {}
    side = str((closed or d).get("decision") or "")
    entry = float((closed or d).get("entry") or last)
    stock = str((closed or d).get("stock") or "NIFTY")
    mfe, cur = _favour_from_payload(side, entry, payload)
    thr = book_favour_threshold(stock, side=side, payload=payload)
    kill_mins = early_kill_minutes_for(stock, side=side, payload=payload)

    # Book when research med-favour floor hit (desk shortcut)
    if mfe >= thr and cur >= thr * 0.35:
        out = close_by_exit_rule(
            int(row_id),
            status="booked",
            detail=f"Favour ≥{thr:.0f} pts (MFE {mfe:.0f}) — book now",
            db_path=db_path,
        )
        if out:
            out["alert_kind"] = "booked_favour"
            out["favour_pts"] = round(mfe, 1)
        return out

    # Early drop only after research favour-horizon (default 6×5m=30m).
    if elapsed >= kill_mins and mfe < thr and cur < 0:
        out = close_by_exit_rule(
            int(row_id),
            status="stopped",
            detail=f"No favour in {kill_mins:.0f}m (MFE {mfe:.0f}) — drop",
            db_path=db_path,
        )
        if out:
            out["alert_kind"] = "stopped_early"
            out["favour_pts"] = round(cur, 1)
        return out

    expired = maybe_expire_favour(int(row_id), asof=asof, db_path=db_path)
    if expired and expired.get("status") == "expired":
        expired["alert_kind"] = "expired"
        expired["favour_pts"] = round(cur, 1)
        return expired
    return closed or d


def maybe_expire_favour(
    row_id: int,
    *,
    asof: Optional[datetime] = None,
    db_path: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Close open indication after research favour window (bars × 5m) elapses."""
    path = ensure_tables(db_path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT * FROM overlay_indication_calls WHERE id=?", (int(row_id),)
        ).fetchone()
        if not row or row["status"] != "open":
            return _row_to_dict(row) if row else None
        d = _row_to_dict(row)
        payload = d.get("payload") or {}
        mins = payload.get("favour_minutes")
        if mins is None:
            bars = payload.get("favour_bars") or (payload.get("favour") or {}).get("favour_bars")
            mins = int(bars or 12) * 5
        mins = int(mins)
        # Favour window starts at listing (created_at), not bar open — same
        # clock class as early-kill (bar open is already ~15m old at NEW).
        elapsed_min = early_kill_elapsed_minutes(d, asof=asof)
        if elapsed_min < mins:
            return d
        stamp = _now()
        conn.execute(
            """
            UPDATE overlay_indication_calls
            SET status=?, status_plain=?, closed_at=?, updated_at=?
            WHERE id=?
            """,
            ("expired", _plain("expired"), stamp, stamp, int(row_id)),
        )
        conn.commit()
        row2 = conn.execute(
            "SELECT * FROM overlay_indication_calls WHERE id=?", (int(row_id),)
        ).fetchone()
        return _row_to_dict(row2)
    finally:
        conn.close()


def ui_alert_for_row(
    d: Dict[str, Any],
    *,
    last_price: Optional[float] = None,
    asof: Optional[datetime] = None,
) -> Optional[Dict[str, Any]]:
    """Per-call UI alert for Today tab (drop=red, book=green, warn=amber)."""
    if not d:
        return None
    status = str(d.get("status") or "")
    side = str(d.get("decision") or "")
    stock = str(d.get("stock") or "NIFTY")
    plain = str(d.get("status_plain") or status)
    if status == "stopped":
        return {
            "level": "drop",
            "title": "DROP",
            "detail": plain or "Stop / invalidate — exit this trade",
            "decision": side,
        }
    if status == "booked":
        return {
            "level": "book",
            "title": "BOOKED",
            "detail": plain or "Book profit rule hit",
            "decision": side,
        }
    if status != "open":
        return None

    payload = d.get("payload") if isinstance(d.get("payload"), dict) else {}
    try:
        entry = float(d.get("entry"))
    except (TypeError, ValueError):
        return None
    # Refresh last into path for live colouring
    if last_price is not None:
        payload = dict(payload)
        payload["path_last"] = float(last_price)
        if side == "BUY":
            payload["path_high"] = max(float(payload.get("path_high") or entry), float(last_price))
            payload["path_low"] = min(float(payload.get("path_low") or entry), float(last_price))
        else:
            payload["path_high"] = max(float(payload.get("path_high") or entry), float(last_price))
            payload["path_low"] = min(float(payload.get("path_low") or entry), float(last_price))
    mfe, cur = _favour_from_payload(side, entry, payload)
    thr = book_favour_threshold(stock, side=side, payload=payload)
    kill_mins = early_kill_minutes_for(stock, side=side, payload=payload)
    elapsed = early_kill_elapsed_minutes(d, asof=asof)

    # Align with manage_open_trade booked_favour: need MFE floor AND still in favour.
    # Suppress BOOK/DROP live alerts during listing grace (avoids NEW→alert spam).
    if elapsed >= OVERLAY_MANAGE_GRACE_MIN and mfe >= thr and cur >= thr * 0.35:
        return {
            "level": "book",
            "title": "BOOK NOW",
            "detail": f"Favour ~{mfe:.0f} pts (floor {thr:.0f}) — take profit on this trade",
            "decision": side,
            "favour_pts": round(mfe, 1),
        }
    if elapsed >= kill_mins and mfe < thr and cur < 0:
        return {
            "level": "drop",
            "title": "DROP NOW",
            "detail": f"No favour in {kill_mins:.0f}m · underwater {cur:.0f} pts — exit this trade",
            "decision": side,
            "favour_pts": round(cur, 1),
        }
    if cur < 0:
        return {
            "level": "warn",
            "title": "UNDERWATER",
            "detail": f"Against you ~{abs(cur):.0f} pts · watch stop rule on this trade",
            "decision": side,
            "favour_pts": round(cur, 1),
        }
    return {
        "level": "ok",
        "title": "OPEN",
        "detail": f"Favour ~{mfe:.0f} pts · hold / watch book+stop rules",
        "decision": side,
        "favour_pts": round(mfe, 1),
    }


def enrich_ui_alerts(
    rows: List[Dict[str, Any]],
    *,
    last_price: Optional[float] = None,
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for r in rows or []:
        d = dict(r)
        alert = ui_alert_for_row(d, last_price=last_price)
        if alert:
            d["ui_alert"] = alert
        out.append(d)
    return out


def _row_to_dict(row: Any) -> Dict[str, Any]:
    if row is None:
        return {}
    d = dict(row)
    try:
        d["rule_ids"] = json.loads(d.get("rule_ids_json") or "[]")
    except Exception:
        d["rule_ids"] = []
    try:
        d["accuracy_tags"] = json.loads(d.get("tags_json") or "[]")
    except Exception:
        d["accuracy_tags"] = []
    try:
        d["payload"] = json.loads(d.get("payload_json") or "{}")
    except Exception:
        d["payload"] = {}
    d["overlay_indication"] = True
    d["open"] = d.get("status") == "open"
    d["n"] = d.get("id")
    payload = d.get("payload") or {}
    for key in (
        "favour_bars",
        "favour_minutes",
        "med_favour_pts",
        "med_peak_pts",
        "favour_label",
        "levels_mode",
        "book_profit_rule",
        "book_profit_label",
        "stop_rule",
        "stop_label",
        "book_alt_rule",
        "book_alt_label",
        "stop_alt_rule",
        "stop_alt_label",
    ):
        if d.get(key) is None and payload.get(key) is not None:
            d[key] = payload.get(key)
    return d
