"""Optional WhatsApp desk alerts (off by default).

Research summary (2026):
- Official path only for reliable trading alerts: Meta WhatsApp Cloud API
  (or a BSP on top: Twilio / Gupshup / 360dialog). On-premise API is deprecated.
- Business-initiated alerts (BOOK / DROP / NEW CALL) MUST use pre-approved
  message templates + explicit user opt-in. Free-form text only works inside a
  24h window after the user messages you first.
- Unofficial WhatsApp-Web / QR gateways are fast to prototype but can get the
  number restricted — do not use as the only channel for money alerts.
- India: Gupshup / Twilio are common BSPs; Cloud API direct is cheapest if you
  can manage Meta Business Manager + template approval yourself.

Env (all optional; nothing sends until enabled):
  WHATSAPP_NOTIFY=1
  WHATSAPP_PROVIDER=cloud|twilio|log
  WHATSAPP_TO=+91XXXXXXXXXX
  WHATSAPP_TOKEN=...          # Cloud API access token or Twilio auth
  WHATSAPP_PHONE_ID=...       # Cloud API phone number id
  WHATSAPP_TEMPLATE=desk_alert  # approved template name
  WHATSAPP_TEMPLATE_LANG=en
  TWILIO_ACCOUNT_SID=...
  TWILIO_AUTH_TOKEN=...
  TWILIO_WHATSAPP_FROM=whatsapp:+14155238886

Recommended templates (submit in Meta / BSP):
  1) desk_new_call   — {{1}}=stock {{2}}=side {{3}}=detail
  2) desk_book       — {{1}}=stock {{2}}=side {{3}}=detail
  3) desk_drop       — {{1}}=stock {{2}}=side {{3}}=detail
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict, Optional


def enabled() -> bool:
    return os.environ.get("WHATSAPP_NOTIFY", "").strip().lower() in ("1", "true", "yes")


def status() -> Dict[str, Any]:
    provider = (os.environ.get("WHATSAPP_PROVIDER") or "log").strip().lower()
    return {
        "enabled": enabled(),
        "provider": provider,
        "to_configured": bool(os.environ.get("WHATSAPP_TO")),
        "template": os.environ.get("WHATSAPP_TEMPLATE") or "desk_alert",
        "research": {
            "official": "Meta WhatsApp Cloud API or BSP (Twilio/Gupshup/360dialog)",
            "requires": [
                "Meta Business verification",
                "Pre-approved templates for BOOK/DROP/NEW",
                "User opt-in to WhatsApp alerts",
            ],
            "avoid_for_money_alerts": "Unofficial WhatsApp Web / QR gateways",
            "docs": [
                "https://developers.facebook.com/docs/whatsapp/cloud-api",
                "https://www.twilio.com/docs/whatsapp/api",
            ],
        },
    }


def _template_for_kind(kind: str) -> str:
    k = (kind or "").lower()
    override = os.environ.get("WHATSAPP_TEMPLATE")
    if override:
        return override
    if "book" in k:
        return "desk_book"
    if "drop" in k:
        return "desk_drop"
    if k in ("model_call", "overlay_indication"):
        return "desk_new_call"
    return "desk_alert"


def maybe_send(
    *,
    title: str,
    message: str,
    stock: Optional[str] = None,
    kind: str = "alert",
    decision: Optional[str] = None,
    payload: Optional[dict] = None,
) -> bool:
    """Send WhatsApp if enabled. Never raises to callers."""
    if not enabled():
        return False
    to = (os.environ.get("WHATSAPP_TO") or "").strip()
    if not to:
        return False
    provider = (os.environ.get("WHATSAPP_PROVIDER") or "log").strip().lower()
    body = {
        "title": title,
        "message": message,
        "stock": stock,
        "kind": kind,
        "decision": decision,
        "payload": payload or {},
        "template": _template_for_kind(kind),
    }
    try:
        if provider == "cloud":
            return _send_cloud(to, body)
        if provider == "twilio":
            return _send_twilio(to, body)
        # Default safe mode: log only (proves wiring without Meta fees).
        print(f"[whatsapp:log] to={to} template={body['template']} {title}: {message.replace(chr(10), ' · ')}")
        return True
    except Exception as exc:
        print(f"[whatsapp] send failed: {exc}")
        return False


def _send_cloud(to: str, body: Dict[str, Any]) -> bool:
    token = (os.environ.get("WHATSAPP_TOKEN") or "").strip()
    phone_id = (os.environ.get("WHATSAPP_PHONE_ID") or "").strip()
    if not token or not phone_id:
        raise RuntimeError("WHATSAPP_TOKEN and WHATSAPP_PHONE_ID required for cloud provider")
    lang = os.environ.get("WHATSAPP_TEMPLATE_LANG") or "en"
    # Template variables: stock, side/decision, compact detail
    detail = str(body.get("message") or "").replace("\n", " · ")[:200]
    payload = {
        "messaging_product": "whatsapp",
        "to": to.lstrip("+"),
        "type": "template",
        "template": {
            "name": body["template"],
            "language": {"code": lang},
            "components": [
                {
                    "type": "body",
                    "parameters": [
                        {"type": "text", "text": str(body.get("stock") or "INDEX")},
                        {"type": "text", "text": str(body.get("decision") or body.get("title") or "ALERT")},
                        {"type": "text", "text": detail},
                    ],
                }
            ],
        },
    }
    req = urllib.request.Request(
        f"https://graph.facebook.com/v20.0/{phone_id}/messages",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            resp.read()
            return 200 <= getattr(resp, "status", 200) < 300
    except urllib.error.HTTPError as exc:
        err = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Cloud API {exc.code}: {err}") from exc


def _send_twilio(to: str, body: Dict[str, Any]) -> bool:
    import base64
    import urllib.parse

    sid = (os.environ.get("TWILIO_ACCOUNT_SID") or "").strip()
    token = (os.environ.get("TWILIO_AUTH_TOKEN") or os.environ.get("WHATSAPP_TOKEN") or "").strip()
    frm = (os.environ.get("TWILIO_WHATSAPP_FROM") or "").strip()
    if not sid or not token or not frm:
        raise RuntimeError("TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_FROM required")
    # Free-form only works in 24h session; for alerts prefer ContentSid templates later.
    text = f"{body.get('title')}: {str(body.get('message') or '').replace(chr(10), ' · ')}"
    data = urllib.parse.urlencode(
        {
            "From": frm if frm.startswith("whatsapp:") else f"whatsapp:{frm}",
            "To": to if to.startswith("whatsapp:") else f"whatsapp:{to}",
            "Body": text[:1500],
        }
    ).encode("utf-8")
    auth = base64.b64encode(f"{sid}:{token}".encode()).decode()
    req = urllib.request.Request(
        f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
        data=data,
        headers={
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        resp.read()
        return True
