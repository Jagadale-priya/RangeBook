"""Accuracy-tag-only notifications for FINAL NIFTY F&O calls.

Notify content shows **accuracy_tag** (ACC_RANGE_*) as the headline signal —
not volume/agree noise. Includes Option Chain deep-links (desk + Groww + NSE).

Never blocks a call: one notify payload per UI call (day/side/hm).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from urllib.parse import quote

STOCK = "NIFTY"
NSE_OC = "https://www.nseindia.com/option-chain"
DESK_OC_PATH = "/dashboard/?stock=NIFTY&tab=fno&sub=contracts"


def _side(r: dict) -> str:
    return str(r.get("decision") or r.get("side") or "").upper()


def _acc_only_tags(tags: List[Any]) -> List[str]:
    """Keep accuracy_tag family only (ACC_RANGE_*)."""
    out = []
    seen = set()
    for t in tags or []:
        s = str(t or "")
        if not s.startswith("ACC_RANGE_"):
            continue
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


def option_right(side: str) -> str:
    s = str(side or "").upper()
    if s == "BUY":
        return "CE"
    if s == "SELL":
        return "PE"
    return ""


def atm_strike(entry: Optional[float], step: float = 50.0) -> Optional[float]:
    if entry is None:
        return None
    try:
        px = float(entry)
    except (TypeError, ValueError):
        return None
    return round(px / step) * step


def resolve_option_hint(call: dict) -> Dict[str, Any]:
    """Best-effort ATM CE/PE hint + links (works without live Kite cache)."""
    side = _side(call)
    right = option_right(side)
    entry = call.get("entry")
    try:
        entry_f = float(entry) if entry is not None else None
    except (TypeError, ValueError):
        entry_f = None
    strike = atm_strike(entry_f)
    spot_q = f"{entry_f:.2f}" if entry_f is not None else ""

    # Desk Option Chain (opens F&O Contracts sub-tab with spot)
    desk_oc = DESK_OC_PATH
    if spot_q:
        desk_oc = f"{DESK_OC_PATH}&spot={quote(spot_q)}"

    # NSE public option chain
    nse_oc = NSE_OC

    # Groww chart — prefer resolved tradingsymbol; else leave template
    tradingsymbol = call.get("tradingsymbol") or call.get("option_symbol")
    groww_url = call.get("groww_url") or call.get("groww_chart")
    if not groww_url and tradingsymbol:
        try:
            import groww_option_links

            groww_url = groww_option_links.option_chart_url(STOCK, tradingsymbol)
        except Exception:
            groww_url = None

    # Try live instrument cache for ATM CE/PE
    ce = pe = None
    if entry_f is not None:
        try:
            import fno_instruments

            con = fno_instruments.resolve_contracts(STOCK, float(entry_f)) or {}
            ce = con.get("atm_ce") or con.get("ce")
            pe = con.get("atm_pe") or con.get("pe")
            pick = ce if right == "CE" else pe if right == "PE" else None
            if isinstance(pick, dict):
                tradingsymbol = pick.get("tradingsymbol") or tradingsymbol
                strike = float(pick.get("strike") or strike or 0) or strike
                if not groww_url and tradingsymbol:
                    try:
                        import groww_option_links

                        groww_url = groww_option_links.option_chart_url(
                            STOCK, tradingsymbol
                        )
                    except Exception:
                        pass
        except Exception:
            pass

    api_oc = f"/fno/contracts/{STOCK}"
    if spot_q:
        api_oc = f"{api_oc}?spot={quote(spot_q)}"

    return {
        "underlying": STOCK,
        "right": right,
        "strike": strike,
        "tradingsymbol": tradingsymbol,
        "entry_spot": entry_f,
        "atm_ce": ce,
        "atm_pe": pe,
        "links": {
            "desk_option_chain": desk_oc,
            "api_contracts": api_oc,
            "nse_option_chain": nse_oc,
            "groww_chart": groww_url,
        },
    }


def build_accuracy_notify(call: dict, *, dry_run: bool = True) -> Dict[str, Any]:
    """One accuracy-tag-only notification for a UI-combined call.

    Title uses primary accuracy_tag only.
    Body: side · hm · SL/T1 · Option Chain links.
    """
    side = _side(call)
    acc = str(call.get("accuracy_tag") or call.get("accuracy_range_tag") or "")
    # Prefer ACC_RANGE from tags if primary missing
    acc_tags = _acc_only_tags(list(call.get("accuracy_tags") or call.get("tags") or []))
    if not acc and acc_tags:
        acc = acc_tags[0]
    if acc and acc not in acc_tags:
        acc_tags = [acc] + acc_tags

    desk = str(call.get("accurate_tag") or call.get("desk_tag") or "")
    opt = resolve_option_hint(call)
    links = opt.get("links") or {}

    title = acc or "ACC_RANGE_?"
    # Accuracy tag ONLY in title — user ask
    detail_bits = [
        f"NIFTY {side}",
        str(call.get("hm") or ""),
        f"day {call.get('day')}",
    ]
    if call.get("entry") is not None:
        detail_bits.append(f"entry {call.get('entry')}")
    if call.get("stop_loss") is not None:
        detail_bits.append(f"SL {call.get('stop_loss')}")
    if call.get("target_1") is not None:
        detail_bits.append(f"T {call.get('target_1')}")
    if opt.get("right") and opt.get("strike"):
        detail_bits.append(f"ATM {opt['right']} {opt['strike']}")
    if opt.get("tradingsymbol"):
        detail_bits.append(str(opt["tradingsymbol"]))

    message = " · ".join(x for x in detail_bits if x)
    oc_line = (
        f"Option Chain: desk {links.get('desk_option_chain')} · "
        f"NSE {links.get('nse_option_chain')}"
    )
    if links.get("groww_chart"):
        oc_line += f" · Groww {links.get('groww_chart')}"

    payload = {
        "kind": "accuracy_call",
        "channel": "FINAL_NIFTY_3BOOKS",
        "stock": STOCK,
        "day": call.get("day"),
        "hm": call.get("hm"),
        "decision": side,
        "accuracy_tag": acc,
        "accuracy_tags_only": acc_tags,
        "accurate_tag": desk,
        "desks_satisfied": list(call.get("desks_satisfied") or []),
        "multi_desk": bool(call.get("multi_desk")),
        "entry": call.get("entry"),
        "stop_loss": call.get("stop_loss"),
        "target_1": call.get("target_1"),
        "option": opt,
        "option_chain_links": links,
        "title": title,
        "message": message,
        "message_with_oc": f"{message}\n{oc_line}",
        "dedupe_key": f"acc:{STOCK}:{call.get('day')}:{side}:{call.get('hm')}:{acc}",
        "blocked": False,
        "dry_run": dry_run,
    }
    return payload


def build_notifies_for_ui_calls(
    ui_calls: List[dict], *, dry_run: bool = True
) -> List[Dict[str, Any]]:
    """One notify per UI call — never drop / never block."""
    out = []
    for r in ui_calls:
        out.append(build_accuracy_notify(r, dry_run=dry_run))
    return out


def emit_accuracy_notify(payload: Dict[str, Any]) -> bool:
    """Fire desktop/telegram via desk notify (optional live)."""
    if payload.get("dry_run"):
        return False
    try:
        import desktop_notify

        opt = payload.get("option") or {}
        links = payload.get("option_chain_links") or {}
        option = {
            "tradingsymbol": opt.get("tradingsymbol"),
            "right": opt.get("right"),
            "strike": opt.get("strike"),
            "groww_url": links.get("groww_chart"),
        }
        return bool(
            desktop_notify.notify(
                title=str(payload.get("title") or "ACC"),
                message=str(payload.get("message_with_oc") or payload.get("message") or ""),
                stock=STOCK,
                kind="accuracy_call",
                decision=payload.get("decision"),
                entry=payload.get("entry"),
                stop_loss=payload.get("stop_loss"),
                target_1=payload.get("target_1"),
                dedupe_key=payload.get("dedupe_key"),
                product="fno",
                payload={
                    "accuracy_tag": payload.get("accuracy_tag"),
                    "accuracy_tags_only": payload.get("accuracy_tags_only"),
                    "option_chain_links": links,
                    "option": option,
                    "channel": "FINAL_NIFTY_3BOOKS",
                },
            )
        )
    except Exception:
        return False
