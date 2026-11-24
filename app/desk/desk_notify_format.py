"""Canonical desk alert copy for toast + hamburger + WhatsApp.

Format (body):
  {STOCK} {SIDE} · {channel}
  {action line}

Title is a short action label: BOOK PROFIT / DROP TRADE / NEW CALL / CALL CLOSED.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None  # type: ignore

IST = ZoneInfo("Asia/Kolkata") if ZoneInfo else None

ACTION_BOOK = "BOOK"
ACTION_DROP = "DROP"
ACTION_NEW = "NEW"
ACTION_CLOSE = "CLOSE"
ACTION_WATCH = "WATCH"


def now_ist_label(when: Optional[Any] = None) -> str:
    if when is None:
        ts = datetime.now(IST) if IST else datetime.now()
    else:
        try:
            ts = datetime.fromisoformat(str(when).replace("Z", "+00:00"))
        except Exception:
            return str(when)[:16]
        if IST and ts.tzinfo is None:
            ts = ts.replace(tzinfo=IST)
        elif IST and ts.tzinfo is not None:
            ts = ts.astimezone(IST)
    return ts.strftime("%d %b · %H:%M")


def _num(v: Any) -> Optional[float]:
    try:
        if v is None or v == "":
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _side(decision: Any) -> str:
    s = str(decision or "").upper()
    if "BUY" in s:
        return "BUY"
    if "SELL" in s:
        return "SELL"
    return s or "CALL"


def pack(
    *,
    action: str,
    title: str,
    stock: str,
    decision: Any = None,
    channel: str = "Desk",
    detail: str,
    entry: Any = None,
    stop: Any = None,
    target: Any = None,
    favour_pts: Any = None,
    when: Any = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build title/message/payload for desk_notifications + toast."""
    sym = str(stock or "").upper()
    side = _side(decision)
    when_label = now_ist_label(when)
    bits = [f"{sym} {side}".strip(), channel]
    line1 = " · ".join(b for b in bits if b)
    line2 = (detail or "").strip()
    extras = []
    e = _num(entry)
    s = _num(stop)
    t = _num(target)
    f = _num(favour_pts)
    if e is not None:
        extras.append(f"entry {e:g}")
    if s is not None:
        extras.append(f"SL {s:g}")
    if t is not None:
        extras.append(f"T1 {t:g}")
    if f is not None:
        extras.append(f"favour ~{f:.0f} pts")
    if extras:
        line2 = f"{line2} · " + " · ".join(extras) if line2 else " · ".join(extras)
    message = f"{line1}\n{line2}".strip() if line2 else line1
    payload = {
        "action": str(action or "").upper(),
        "channel": channel,
        "when_label": when_label,
        "detail": detail,
        "favour_pts": f,
        **(extra or {}),
    }
    return {
        "title": title,
        "message": message,
        "stock": sym,
        "decision": side,
        "entry": e,
        "stop_loss": s,
        "target_1": t,
        "kind": payload.get("kind") or str(action or "alert").lower(),
        "payload": payload,
        "action": payload["action"],
        "when_label": when_label,
    }
