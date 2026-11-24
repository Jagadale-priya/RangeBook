"""Today's F&O / Intraday call tickets — list for the UI and rows in knowledge.db."""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional

STATUS_PLAIN = {
    "open": "Open",
    "t1_before_sl": "Hit first target",
    "sl_before_t1": "Hit stop",
    "same_bar_both": "Stop and target same bar (counts as stop)",
    "expired": "Expired without target or stop",
    "expired_unobserved": "Closed at session end; outcome was not observed",
    "cancelled": "Cancelled",
    "early_drop": "Early drop (never ran)",
    "superseded_by_model": "Replaced by model call",
}


def default_db_path() -> str:
    import knowledge_db

    return knowledge_db.ensure_db_dir()


def ensure_tables(db_path: str) -> None:
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS session_calls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock TEXT NOT NULL,
            product TEXT NOT NULL DEFAULT 'fno',
            session_date TEXT NOT NULL,
            ticket_n INTEGER NOT NULL,
            decision TEXT NOT NULL,
            status TEXT NOT NULL,
            entry REAL,
            stop_loss REAL,
            target_1 REAL,
            target_2 REAL,
            p_t1 REAL,
            p_meta REAL,
            regime TEXT,
            taken_at TEXT,
            closed_at TEXT,
            status_plain TEXT,
            payload_json TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(stock, product, session_date, ticket_n)
        );
        CREATE INDEX IF NOT EXISTS idx_session_calls_day
            ON session_calls(session_date, stock, product);
        """
    )
    conn.commit()
    conn.close()


def status_plain(status: Optional[str]) -> str:
    key = str(status or "open").strip().lower()
    return STATUS_PLAIN.get(key, key.replace("_", " "))


def _clock(ts: Any) -> str:
    if ts is None:
        return ""
    s = str(ts)
    if "T" in s:
        return s[11:16]
    if " " in s:
        return s.split(" ")[-1][:5]
    return s[:5]


def ticket_rows(session_ticket: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Closed history plus the open ticket, in call order (#1, #2, …)."""
    if not session_ticket:
        return []
    import fno_session_rules as fsrules

    day = str(session_ticket.get("session_date") or "")
    hist = list(session_ticket.get("history") or [])
    rows: List[Dict[str, Any]] = []
    for i, h in enumerate(hist, 1):
        rows.append(_normalize_row(h, i, day, closed=True))
    live = fsrules.open_ticket(session_ticket)
    if live:
        n = max(int(session_ticket.get("tickets") or 1), len(hist) + 1)
        rows.append(_normalize_row(live, n, day, closed=False))
    return rows


def session_ticket_from_db(
    db_path: str,
    stock: str,
    *,
    session_date: Any,
    product: str = "fno",
) -> Optional[Dict[str, Any]]:
    """Rebuild today's ticket state from the saved rows. The live state is kept
    in memory; a restart must not forget a call that already hit the stop, or the
    one-ticket rule and the opening-drive guard would reset mid-session."""
    day = str(session_date or "")[:10]
    if not day:
        return None
    expire_open_before(db_path, stock, product=product, before_day=day)
    rows = [
        r for r in list_recent(db_path, stock, product, limit=40)
        if str(r.get("session_date") or "")[:10] == day
    ]
    if not rows:
        return None
    rows.sort(key=lambda r: int(r.get("ticket_n") or r.get("n") or 0))
    history: List[Dict[str, Any]] = []
    live: Optional[Dict[str, Any]] = None
    for r in rows:
        item = {
            "decision": r.get("decision"),
            "entry": r.get("entry"),
            "stop_loss": r.get("stop_loss"),
            "target_1": r.get("target_1"),
            "target_2": r.get("target_2"),
            "p_t1": r.get("p_t1"),
            "p_meta": r.get("p_meta") or r.get("p_t1"),
            "regime": r.get("regime"),
            "taken_at": r.get("taken_at"),
            "closed_at": r.get("closed_at"),
            "status": str(r.get("status") or ""),
            "readings": r.get("readings"),
            "exit_price": r.get("exit_price"),
            "exit_source": r.get("exit_source"),
            "points": r.get("points"),
        }
        if item["status"] == "open":
            live = item
        else:
            history.append(item)
    ticket: Dict[str, Any] = {
        "session_date": day,
        "tickets": max(len(history) + (1 if live else 0), int(rows[-1].get("ticket_n") or 0)),
        "history": history,
        "decision": "HOLD",
        "status": history[-1]["status"] if history else "",
        "entry": None,
        "stop_loss": None,
        "target_1": None,
        "target_2": None,
    }
    if live:
        ticket.update({
            "decision": live["decision"],
            "status": "open",
            "entry": live["entry"],
            "stop_loss": live["stop_loss"],
            "target_1": live["target_1"],
            "target_2": live["target_2"],
            "p_t1": live["p_t1"],
            "p_meta": live["p_meta"],
            "regime": live["regime"],
            "taken_at": live["taken_at"],
            "readings": live["readings"],
        })
    return ticket


def expire_open_before(db_path: str, stock: str, *, product: str, before_day: str) -> int:
    """A prior-session call cannot remain live after a restart.

    Its barrier outcome is deliberately left unknown because no point-in-time
    tape was available to establish whether target or stop came first.
    """
    if not db_path or not os.path.isfile(db_path):
        return 0
    key = str(stock or "").strip().upper()
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            """SELECT id, session_date, payload_json FROM session_calls
               WHERE stock = ? AND product = ? AND status = 'open' AND session_date < ?""",
            (key, product, str(before_day)[:10]),
        ).fetchall()
        now = datetime.now().isoformat()
        for row_id, session_day, payload_json in rows:
            try:
                payload = json.loads(payload_json or "{}")
            except (TypeError, ValueError, json.JSONDecodeError):
                payload = {}
            closed_at = f"{str(session_day)[:10]}T15:30:00+05:30"
            payload.update(status="expired_unobserved", closed_at=closed_at,
                           exit_source="session_end_after_restart")
            conn.execute(
                """UPDATE session_calls SET status = ?, closed_at = ?, status_plain = ?,
                   payload_json = ?, updated_at = ? WHERE id = ?""",
                ("expired_unobserved", closed_at, status_plain("expired_unobserved"),
                 json.dumps(payload, default=str), now, row_id),
            )
        conn.commit()
        return len(rows)
    except sqlite3.OperationalError:
        return 0
    finally:
        conn.close()


def is_live_confluence_row(row: Optional[Dict[str, Any]]) -> bool:
    """True for lower-priority live-indication clips (not model history)."""
    if not isinstance(row, dict):
        return False
    if row.get("history_eligible") is False:
        return True
    if row.get("live_confluence") is True:
        return True
    readings = row.get("readings") if isinstance(row.get("readings"), dict) else {}
    track = str(row.get("track") or readings.get("track") or row.get("source") or readings.get("source") or "")
    if track == "live_confluence":
        return True
    if readings.get("live_confluence") or readings.get("history_eligible") is False:
        return True
    if str(row.get("regime") or readings.get("setup_type") or "") == "live_confluence":
        return True
    label = str(row.get("accuracy_label") or readings.get("accuracy_label") or "").lower()
    if "live confluence" in label:
        return True
    tags = row.get("accuracy_tags") or readings.get("accuracy_tags") or []
    if isinstance(tags, list):
        for t in tags:
            if not isinstance(t, dict):
                continue
            blob = f"{t.get('code') or ''} {t.get('label') or ''}".lower()
            if "live_confluence" in blob or "live confluence" in blob:
                return True
    return False


def is_history_eligible_row(row: Optional[Dict[str, Any]]) -> bool:
    """Model / dual-track rows only — live confluence never goes to History."""
    if not isinstance(row, dict) or is_live_confluence_row(row):
        return False
    if row.get("history_eligible") is False:
        return False
    readings = row.get("readings") if isinstance(row.get("readings"), dict) else {}
    if row.get("dual_track") or readings.get("dual_track"):
        return True
    track = str(row.get("track") or readings.get("track") or row.get("source") or "")
    if track in ("proven_100", "champion", "baseline"):
        return True
    if row.get("history_eligible") is True and track and track != "live_confluence":
        return True
    # Legacy untagged model tickets.
    if not track and row.get("history_eligible") is not False:
        return True
    return False


def split_live(rows: Optional[List[Dict[str, Any]]]) -> Dict[str, Any]:
    items = list(rows or [])
    active = next((r for r in items if r.get("open") or str(r.get("status") or "") == "open"), None)
    # Full closed list (Today can show live clips). History consumers should
    # filter with is_history_eligible_row.
    history = [r for r in items if r is not active]
    history_model = [r for r in history if is_history_eligible_row(r)]
    return {
        "active": active,
        "history": history,
        "history_model": history_model,
        "all": items,
    }


def list_recent(
    db_path: str,
    stock: Optional[str] = None,
    product: str = "fno",
    limit: int = 40,
) -> List[Dict[str, Any]]:
    if not os.path.isfile(db_path):
        return []
    ensure_tables(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    if stock:
        rows = conn.execute(
            """
            SELECT * FROM session_calls
            WHERE stock = ? AND product = ?
            ORDER BY session_date DESC, ticket_n DESC
            LIMIT ?
            """,
            (stock.strip().upper(), product, int(limit)),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT * FROM session_calls
            WHERE product = ?
            ORDER BY session_date DESC, ticket_n DESC
            LIMIT ?
            """,
            (product, int(limit)),
        ).fetchall()
    conn.close()
    out = []
    for r in rows:
        out.append(_row_from_db(r))
    out.reverse()
    return out


def _normalize_row(raw: Dict[str, Any], n: int, day: str, *, closed: bool) -> Dict[str, Any]:
    status = str(raw.get("status") or ("open" if not closed else ""))
    if not status:
        status = "open" if not closed else "expired"
    taken = raw.get("taken_at")
    readings = raw.get("readings") if isinstance(raw.get("readings"), dict) else None
    tags = None
    model_view = None
    accuracy_label = None
    if readings:
        tags = readings.get("accuracy_tags")
        model_view = readings.get("model_view")
        accuracy_label = readings.get("accuracy_label")
    track = None
    source = None
    live_confluence = False
    history_eligible = True
    if readings:
        track = readings.get("track")
        source = readings.get("source") or track
        live_confluence = bool(readings.get("live_confluence") or track == "live_confluence")
        if readings.get("history_eligible") is not None:
            history_eligible = bool(readings.get("history_eligible"))
        elif live_confluence:
            history_eligible = False
    risk_src = readings or {}
    return {
        "n": n,
        "session_date": day,
        "decision": str(raw.get("decision") or "HOLD"),
        "status": status,
        "status_plain": status_plain(status),
        "entry": raw.get("entry"),
        "stop_loss": raw.get("stop_loss"),
        "target_1": raw.get("target_1"),
        "target_2": raw.get("target_2"),
        "p_t1": raw.get("p_t1"),
        "p_meta": raw.get("p_meta") or raw.get("p_t1"),
        "p_sl": (readings or {}).get("p_sl") if readings else None,
        "regime": raw.get("regime"),
        "taken_at": taken,
        "taken_clock": _clock(taken),
        "closed_at": raw.get("closed_at") if closed else None,
        "closed_clock": _clock(raw.get("closed_at")) if closed else "",
        "exit_price": raw.get("exit_price") if closed else None,
        "exit_source": raw.get("exit_source") if closed else None,
        "points": raw.get("points") if closed else None,
        "open": not closed,
        "readings": readings or None,
        "accuracy_tags": tags,
        "model_view": model_view,
        "accuracy_label": accuracy_label,
        "dual_track": bool((readings or {}).get("dual_track")) if readings else False,
        "track": track,
        "source": source,
        "live_confluence": live_confluence,
        "history_eligible": history_eligible,
        "risk_tier": risk_src.get("risk_tier") or (model_view or {}).get("risk_tier"),
        "risk_label": risk_src.get("risk_label") or (model_view or {}).get("risk_label"),
        "risk_action": risk_src.get("risk_action") or (model_view or {}).get("risk_action"),
        "risk_flags": risk_src.get("risk_flags") or (model_view or {}).get("risk_flags"),
        "expected_sl_pct": risk_src.get("expected_sl_pct") or (model_view or {}).get("expected_sl_pct"),
    }


def _row_from_db(r: Any) -> Dict[str, Any]:
    item = dict(r)
    payload: Dict[str, Any] = {}
    raw = item.pop("payload_json", None)
    if raw:
        try:
            payload = json.loads(raw)
        except (TypeError, ValueError, json.JSONDecodeError):
            payload = {}
    for key in ("entry", "stop_loss", "target_1", "target_2", "p_t1", "p_meta", "regime",
                "exit_price", "exit_source", "points"):
        if item.get(key) is None and payload.get(key) is not None:
            item[key] = payload[key]
    item["status_plain"] = item.get("status_plain") or status_plain(item.get("status"))
    item["n"] = item.get("ticket_n")
    item["open"] = str(item.get("status") or "") == "open"
    item["taken_clock"] = _clock(item.get("taken_at"))
    item["closed_clock"] = _clock(item.get("closed_at"))
    if payload.get("readings"):
        item["readings"] = payload["readings"]
    readings = item.get("readings") if isinstance(item.get("readings"), dict) else None
    if readings:
        if item.get("accuracy_tags") is None and readings.get("accuracy_tags") is not None:
            item["accuracy_tags"] = readings.get("accuracy_tags")
        if item.get("model_view") is None and readings.get("model_view") is not None:
            item["model_view"] = readings.get("model_view")
        if item.get("accuracy_label") is None and readings.get("accuracy_label") is not None:
            item["accuracy_label"] = readings.get("accuracy_label")
        if readings.get("p_sl") is not None and item.get("p_sl") is None:
            item["p_sl"] = readings.get("p_sl")
        item["dual_track"] = bool(readings.get("dual_track"))
        item["track"] = readings.get("track") or item.get("track")
        item["source"] = readings.get("source") or item.get("track") or item.get("source")
        item["live_confluence"] = bool(
            readings.get("live_confluence")
            or item.get("track") == "live_confluence"
            or readings.get("track") == "live_confluence"
        )
        if readings.get("history_eligible") is not None:
            item["history_eligible"] = bool(readings.get("history_eligible"))
        else:
            item["history_eligible"] = not item["live_confluence"]
        mv = readings.get("model_view") if isinstance(readings.get("model_view"), dict) else {}
        for rk in ("risk_tier", "risk_label", "risk_action", "risk_flags", "expected_sl_pct", "sell_flag_n"):
            if item.get(rk) is None:
                item[rk] = readings.get(rk) if readings.get(rk) is not None else mv.get(rk)
    elif item.get("history_eligible") is None:
        item["history_eligible"] = True
    return item


def _existing_payload(db_path: str, stock: str, product: str, day: str, n: int) -> Dict[str, Any]:
    if not os.path.isfile(db_path):
        return {}
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            """
            SELECT payload_json FROM session_calls
            WHERE stock = ? AND product = ? AND session_date = ? AND ticket_n = ?
            """,
            (stock, product, day, n),
        ).fetchone()
    except sqlite3.OperationalError:
        return {}
    finally:
        conn.close()
    if not row or not row[0]:
        return {}
    try:
        payload = json.loads(row[0])
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _merge_readings(old: Any, new: Any) -> Optional[Dict[str, Any]]:
    """Keep the snapshot taken when the call opened. Fill only what was missing."""
    old_d = dict(old) if isinstance(old, dict) else {}
    new_d = dict(new) if isinstance(new, dict) else {}
    if not old_d and not new_d:
        return None
    merged = dict(old_d)
    for key, value in new_d.items():
        if merged.get(key) in (None, "", {}, []):
            merged[key] = value
    return merged or None


def _num(value: Any, places: int = 4) -> Optional[float]:
    try:
        if value is None:
            return None
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:
        return None
    return round(number, places)


def live_readings(
    *,
    fno_head: Optional[Dict[str, Any]] = None,
    live_context: Optional[Dict[str, Any]] = None,
    candlestick: Optional[Dict[str, Any]] = None,
    derivatives: Optional[Dict[str, Any]] = None,
    news_delta: float = 0.0,
    vix_level: float = 0.0,
    setup_type: Optional[str] = None,
    core_decision: Optional[str] = None,
) -> Dict[str, Any]:
    """Readings known at the moment a live call is given. Stored with that call."""
    head = fno_head or {}
    feat = head.get("features") if isinstance(head.get("features"), dict) else {}
    micro = (live_context or {}).get("microstructure") or {}
    orb = micro.get("opening_range") if isinstance(micro.get("opening_range"), dict) else {}
    candle = candlestick or {}
    names = []
    for pattern in (candle.get("patterns") or [])[:6]:
        if isinstance(pattern, dict):
            text = str(pattern.get("name") or pattern.get("pattern") or "")
        else:
            text = str(pattern)
        if text:
            names.append(text[:80])
    deriv = derivatives or {}
    gex = deriv.get("gex") if isinstance(deriv.get("gex"), dict) else {}
    regime = head.get("regime") if isinstance(head.get("regime"), dict) else {}
    align = head.get("alignment") if isinstance(head.get("alignment"), dict) else {}
    return {
        "p_t1": _num(head.get("p_t1")),
        "p_rule": _num(head.get("p_rule")),
        "p_runner": _num(head.get("p_runner")),
        "p_up": _num(head.get("p_up")),
        "buy_p": _num(head.get("buy_p")),
        "source": head.get("source"),
        "side": head.get("side"),
        "first_clip": bool(head.get("first_clip")),
        "reclaim": bool(head.get("reclaim")),
        "continue_ok": bool(head.get("continue_ok")),
        "flow_adjust": _num(head.get("flow_adjust")),
        "regime": regime.get("name"),
        "five_min_conflict": bool(micro.get("five_min_conflict")),
        "micro_score": _num(micro.get("micro_score"), 1),
        "or_high": _num(orb.get("or_high"), 2),
        "or_low": _num(orb.get("or_low"), 2),
        "or_bias": orb.get("bias"),
        "news_delta": _num(news_delta),
        "vix_level": _num(vix_level, 2),
        "pcr": _num(deriv.get("pcr")),
        "daily_decision": core_decision,
        "setup_type": setup_type,
        "alignment": align.get("note"),
        "candle_bias": candle.get("bias"),
        "candle_patterns": names,
        "gex_flip": _num(gex.get("flip")) if gex.get("available") else None,
        "features": {name: _num(value) for name, value in feat.items()},
    }


def upsert_call(
    db_path: str,
    *,
    stock: str,
    product: str,
    row: Dict[str, Any],
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    ensure_tables(db_path)
    key = (stock or "").strip().upper()
    if not key or row.get("decision") in (None, "HOLD"):
        return
    day = str(row.get("session_date") or datetime.now().strftime("%Y-%m-%d"))[:10]
    n = int(row.get("n") or 1)
    now = datetime.now().isoformat()
    # The option order text stays off the row. The readings snapshot, including the
    # contract that was shown, is kept so a later review can see why the call was given.
    dropped = {"option_order", "order_line", "tradingsymbol", "why", "guide_only"}
    stored = {k: v for k, v in (row or {}).items() if k not in dropped}
    extra_stored = {k: v for k, v in (extra or {}).items() if k not in dropped}
    prior = _existing_payload(db_path, key, product, day, n)
    stored["readings"] = _merge_readings(prior.get("readings"), stored.get("readings"))
    payload = json.dumps({**stored, **extra_stored}, default=str)
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        INSERT INTO session_calls (
            stock, product, session_date, ticket_n, decision, status,
            entry, stop_loss, target_1, target_2, p_t1, p_meta, regime,
            taken_at, closed_at, status_plain, payload_json, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(stock, product, session_date, ticket_n) DO UPDATE SET
            decision=excluded.decision,
            status=excluded.status,
            entry=COALESCE(excluded.entry, session_calls.entry),
            stop_loss=COALESCE(excluded.stop_loss, session_calls.stop_loss),
            target_1=COALESCE(excluded.target_1, session_calls.target_1),
            target_2=COALESCE(excluded.target_2, session_calls.target_2),
            p_t1=excluded.p_t1,
            p_meta=excluded.p_meta,
            regime=excluded.regime,
            taken_at=COALESCE(excluded.taken_at, session_calls.taken_at),
            closed_at=CASE WHEN excluded.status = 'open' THEN NULL
                           ELSE COALESCE(excluded.closed_at, session_calls.closed_at) END,
            status_plain=excluded.status_plain,
            payload_json=excluded.payload_json,
            updated_at=excluded.updated_at
        """,
        (
            key,
            product,
            day,
            n,
            str(row.get("decision")),
            str(row.get("status") or "open"),
            row.get("entry"),
            row.get("stop_loss"),
            row.get("target_1"),
            row.get("target_2"),
            row.get("p_t1"),
            row.get("p_meta"),
            row.get("regime"),
            row.get("taken_at"),
            row.get("closed_at"),
            status_plain(row.get("status")),
            payload,
            now,
            now,
        ),
    )
    conn.commit()
    conn.close()


def sync_session(
    db_path: str,
    *,
    stock: str,
    product: str,
    session_ticket: Optional[Dict[str, Any]],
    extra: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    rows = ticket_rows(session_ticket)
    for row in rows:
        upsert_call(db_path, stock=stock, product=product, row=row, extra=extra)
    return rows


def note_option(
    db_path: str,
    *,
    stock: str,
    product: str,
    session_ticket: Optional[Dict[str, Any]],
    order: Optional[Dict[str, Any]],
) -> None:
    """Remember the call or put that was shown for this open ticket."""
    if not session_ticket or not isinstance(order, dict) or not order.get("available"):
        return
    guide = {
        key: order.get(key)
        for key in (
            "right",
            "tradingsymbol",
            "expiry",
            "strike",
            "entry",
            "stop_loss",
            "target",
            "delta",
            "lot_size",
            "groww_url",
            "groww_chart",
        )
        if order.get(key) is not None
    }
    if not guide.get("right"):
        return
    if guide.get("tradingsymbol") and not guide.get("groww_url"):
        try:
            import groww_option_links

            url = groww_option_links.option_chart_url(stock, guide.get("tradingsymbol"))
            if url:
                guide["groww_url"] = url
                guide["groww_chart"] = url
        except Exception:
            pass
    readings = dict(session_ticket.get("readings") or {})
    if not readings.get("option"):
        readings["option"] = guide
        session_ticket["readings"] = readings
    day = str(session_ticket.get("session_date") or "")[:10]
    n = int(session_ticket.get("tickets") or 1)
    if not day:
        return
    prior = _existing_payload(db_path, stock.strip().upper(), product, day, n)
    if not prior:
        return
    merged = _merge_readings(prior.get("readings"), {"option": guide})
    prior["readings"] = merged
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        UPDATE session_calls SET payload_json = ?, updated_at = ?
        WHERE stock = ? AND product = ? AND session_date = ? AND ticket_n = ?
        """,
        (
            json.dumps(prior, default=str),
            datetime.now().isoformat(),
            stock.strip().upper(),
            product,
            day,
            n,
        ),
    )
    conn.commit()
    conn.close()


def list_calls(
    db_path: str,
    stock: Optional[str] = None,
    session_date: Optional[str] = None,
    product: str = "fno",
) -> List[Dict[str, Any]]:
    if not os.path.isfile(db_path):
        return []
    ensure_tables(db_path)
    day = (session_date or datetime.now().strftime("%Y-%m-%d"))[:10]
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    if stock:
        rows = conn.execute(
            """
            SELECT * FROM session_calls
            WHERE stock = ? AND session_date = ? AND product = ?
            ORDER BY ticket_n ASC
            """,
            (stock.strip().upper(), day, product),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT * FROM session_calls
            WHERE session_date = ? AND product = ?
            ORDER BY stock, ticket_n
            """,
            (day, product),
        ).fetchall()
    conn.close()
    return [_row_from_db(r) for r in rows]
