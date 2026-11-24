"""Free Telegram desk alerts (easy setup, no Meta / Twilio).

Setup (~5 minutes):
  1. Open Telegram → search @BotFather → /newbot → copy the bot token
  2. Open your new bot → press Start
  3. Open https://api.telegram.org/bot<TOKEN>/getUpdates
     and copy "chat":{"id": ........}
  4. Set env (or put in .env loaded by the API process):
       TELEGRAM_NOTIFY=1
       TELEGRAM_BOT_TOKEN=123456:ABC...
       TELEGRAM_CHAT_ID=987654321
  5. Restart stock_signal_ml.py
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional


def enabled() -> bool:
    return os.environ.get("TELEGRAM_NOTIFY", "").strip().lower() in ("1", "true", "yes")


def status() -> Dict[str, Any]:
    return {
        "enabled": enabled(),
        "token_configured": bool(os.environ.get("TELEGRAM_BOT_TOKEN")),
        "chat_configured": bool(os.environ.get("TELEGRAM_CHAT_ID")),
        "setup": [
            "Telegram → @BotFather → /newbot → copy token",
            "Open your bot → Start",
            "Open api.telegram.org/bot<TOKEN>/getUpdates → copy chat.id",
            "Set TELEGRAM_NOTIFY=1 TELEGRAM_BOT_TOKEN=… TELEGRAM_CHAT_ID=…",
            "Restart the API",
        ],
        "cost": "Free",
    }


def _num(v: Any) -> Optional[float]:
    try:
        if v is None or v == "":
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _px(v: Any) -> str:
    n = _num(v)
    return f"₹{n:.2f}" if n is not None else ""


def _esc(s: str) -> str:
    return (
        str(s or "")
        .replace("\\", "\\\\")
        .replace("_", "\\_")
        .replace("*", "\\*")
        .replace("[", "\\[")
        .replace("`", "\\`")
    )


def _build_text(
    *,
    title: str,
    message: str,
    stock: Optional[str],
    kind: str,
    decision: Optional[str],
    payload: Optional[dict],
) -> str:
    p = payload if isinstance(payload, dict) else {}
    action = str(p.get("action") or "").upper()
    ts = str(p.get("tradingsymbol") or "")
    right = str(p.get("right") or "").upper()
    leg = "CE (call)" if right == "CE" else ("PE (put)" if right == "PE" else right)
    groww = str(p.get("groww_url") or p.get("groww_chart") or "")
    # Option premium levels only when a contract is attached (never index points).
    if ts:
        buy = _num(p.get("premium_buy") if p.get("premium_buy") is not None else p.get("entry"))
        prem_sl = _num(p.get("premium_sl") if p.get("premium_sl") is not None else p.get("stop_loss"))
        prem_tgt = _num(
            p.get("premium_exit_book")
            if p.get("premium_exit_book") is not None
            else (p.get("premium_target") if p.get("premium_target") is not None else p.get("target"))
        )
    else:
        buy = prem_sl = prem_tgt = None
    strike = p.get("strike")
    expiry = p.get("expiry")

    lines = [f"*{_esc(title)}*"]
    if stock:
        lines.append(
            f"`{_esc(str(stock).upper())}`"
            + (f" · `{_esc(decision)}`" if decision else "")
            + (f" · {_esc(leg)}" if leg else "")
        )

    # Keep core desk detail (first lines of message), but avoid duplicating option lines
    core = []
    for raw in str(message or "").split("\n"):
        t = raw.strip()
        if not t:
            continue
        low = t.lower()
        if low.startswith("contract:") or low.startswith("buy premium") or low.startswith("option "):
            continue
        if low.startswith("book / exit") or low.startswith("open on groww") or low.startswith("(bought"):
            continue
        if low.startswith("exit now ·"):
            continue
        core.append(t)
    if core:
        lines.append(_esc("\n".join(core[:3])))

    if action == "DROP":
        lines.append("*Action:* EXIT / DROP now")
        if ts:
            lines.append(f"Contract: `{_esc(ts)}`")
    elif action == "BOOK":
        lines.append("*Action:* BOOK PROFIT — square off")
        if ts:
            lines.append(f"Contract: `{_esc(ts)}`" + (f" · {_esc(leg)}" if leg else ""))
        if prem_tgt is not None:
            lines.append(f"*Exit premium (book near):* `{_px(prem_tgt)}`")
        elif buy is not None:
            lines.append(f"Exit on Groww now (guide buy was `{_px(buy)}`)")
        if buy is not None and prem_tgt is not None:
            lines.append(f"Guide buy was `{_px(buy)}` → book near `{_px(prem_tgt)}`")
    elif action == "CLOSE":
        lines.append("*Action:* CALL CLOSED")
        if ts:
            lines.append(f"Contract: `{_esc(ts)}`")
    elif action == "NEW" or action == "" or "indication" in str(kind or "").lower() or (
        "call" in str(kind or "").lower() and "close" not in str(kind or "").lower()
    ):
        lines.append("*Action:* BUY the option" if ts else "*Action:* NEW CALL")
        if ts:
            lines.append(f"Contract: `{_esc(ts)}`" + (f" · {_esc(leg)}" if leg else ""))
        if strike is not None or expiry:
            bits = []
            if strike is not None:
                bits.append(f"strike {strike}")
            if expiry:
                bits.append(f"exp {expiry}")
            lines.append(_esc(" · ".join(bits)))
        if buy is not None:
            lines.append(f"*Buy premium around:* `{_px(buy)}`")
        if prem_sl is not None:
            lines.append(f"*Option stop-loss:* `{_px(prem_sl)}`")
        if prem_tgt is not None:
            lines.append(f"*Option target / book near:* `{_px(prem_tgt)}`")

    if groww:
        lines.append(f"[Open on Groww]({groww})")
    return "\n".join(lines)


def maybe_send(
    *,
    title: str,
    message: str,
    stock: Optional[str] = None,
    kind: str = "alert",
    decision: Optional[str] = None,
    payload: Optional[dict] = None,
) -> bool:
    if not enabled():
        return False
    token = (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
    chat_id = (os.environ.get("TELEGRAM_CHAT_ID") or "").strip()
    if not token or not chat_id:
        print("[telegram] enabled but TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID missing")
        return False

    text = _build_text(
        title=title,
        message=message,
        stock=stock,
        kind=kind,
        decision=decision,
        payload=payload,
    )
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    body = {
        "chat_id": chat_id,
        "text": text[:3900],
        "parse_mode": "Markdown",
        "disable_web_page_preview": False,
    }
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        data = json.loads(raw or "{}")
        return bool(data.get("ok"))
    except urllib.error.HTTPError as exc:
        err = exc.read().decode("utf-8", errors="replace")
        if "can't parse" in err.lower() or exc.code == 400:
            plain = _build_text(
                title=title,
                message=message,
                stock=stock,
                kind=kind,
                decision=decision,
                payload=payload,
            )
            # Strip Markdown markers only; keep normal parentheses in CE/PE labels.
            plain = plain.replace("*", "").replace("`", "")
            if "[Open on Groww](" in plain:
                plain = plain.replace("[Open on Groww](", "Groww: ")
                if plain.endswith(")"):
                    plain = plain[:-1]
            return _send_plain(token, chat_id, plain)
        print(f"[telegram] send failed: {exc.code} {err}")
        return False
    except Exception as exc:
        print(f"[telegram] send failed: {exc}")
        return False


def _send_plain(token: str, chat_id: str, text: str) -> bool:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    body = urllib.parse.urlencode({"chat_id": chat_id, "text": text[:3900]}).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    with urllib.request.urlopen(req, timeout=15) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    return bool(json.loads(raw or "{}").get("ok"))
