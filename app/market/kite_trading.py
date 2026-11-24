"""Kite Connect trading APIs — orders, portfolio, GTT, margins (gated by KITE_ALLOW_LIVE_ORDERS)."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

import kite_data


def _live_orders_allowed() -> bool:
    return os.environ.get("KITE_ALLOW_LIVE_ORDERS", "0").strip().lower() in ("1", "true", "yes")


def _require_kite() -> Tuple[Any, Optional[str]]:
    kite, err = kite_data._get_kite()
    if err or not kite:
        return None, err or "Kite unavailable"
    return kite, None


def trading_status() -> Dict[str, Any]:
    return {
        "live_orders_allowed": _live_orders_allowed(),
        "env_flag": "KITE_ALLOW_LIVE_ORDERS=1 required for POST orders/GTT",
        "note": "Connect plan: market data. Order placement needs appropriate Kite app permissions.",
    }


def get_profile() -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    kite, err = _require_kite()
    if err:
        return None, err
    try:
        return kite.profile(), None
    except Exception as exc:
        return None, str(exc)


def get_margins(segment: Optional[str] = None) -> Tuple[Optional[Any], Optional[str]]:
    kite, err = _require_kite()
    if err:
        return None, err
    try:
        if segment:
            return kite.margins(segment=segment), None
        return kite.margins(), None
    except Exception as exc:
        return None, str(exc)


def get_holdings() -> Tuple[Optional[List[Any]], Optional[str]]:
    kite, err = _require_kite()
    if err:
        return None, err
    try:
        return kite.holdings(), None
    except Exception as exc:
        return None, str(exc)


def get_positions() -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    kite, err = _require_kite()
    if err:
        return None, err
    try:
        return kite.positions(), None
    except Exception as exc:
        return None, str(exc)


def list_orders() -> Tuple[Optional[List[Any]], Optional[str]]:
    kite, err = _require_kite()
    if err:
        return None, err
    try:
        return kite.orders(), None
    except Exception as exc:
        return None, str(exc)


def get_order(order_id: str) -> Tuple[Optional[Any], Optional[str]]:
    kite, err = _require_kite()
    if err:
        return None, err
    try:
        return kite.order_history(order_id), None
    except Exception as exc:
        return None, str(exc)


def place_order(payload: Dict[str, Any], *, dry_run: bool = True) -> Tuple[Optional[Any], Optional[str]]:
    if dry_run or not _live_orders_allowed():
        return {
            "dry_run": True,
            "would_place": payload,
            "hint": "Send dry_run=false and set KITE_ALLOW_LIVE_ORDERS=1 to execute",
        }, None
    kite, err = _require_kite()
    if err:
        return None, err
    required = ("exchange", "tradingsymbol", "transaction_type", "quantity", "product", "order_type")
    missing = [k for k in required if not payload.get(k)]
    if missing:
        return None, f"Missing fields: {', '.join(missing)}"
    try:
        order_id = kite.place_order(
            variety=payload.get("variety", kite.VARIETY_REGULAR),
            exchange=payload["exchange"],
            tradingsymbol=payload["tradingsymbol"],
            transaction_type=payload["transaction_type"],
            quantity=int(payload["quantity"]),
            product=payload["product"],
            order_type=payload["order_type"],
            price=payload.get("price"),
            trigger_price=payload.get("trigger_price"),
            validity=payload.get("validity", kite.VALIDITY_DAY),
            disclosed_quantity=payload.get("disclosed_quantity"),
            tag=payload.get("tag"),
        )
        return {"order_id": order_id, "status": "submitted"}, None
    except Exception as exc:
        return None, str(exc)


def cancel_order(variety: str, order_id: str, *, dry_run: bool = True) -> Tuple[Optional[Any], Optional[str]]:
    if dry_run or not _live_orders_allowed():
        return {"dry_run": True, "would_cancel": {"variety": variety, "order_id": order_id}}, None
    kite, err = _require_kite()
    if err:
        return None, err
    try:
        return kite.cancel_order(variety=variety, order_id=order_id), None
    except Exception as exc:
        return None, str(exc)


def list_gtts() -> Tuple[Optional[List[Any]], Optional[str]]:
    kite, err = _require_kite()
    if err:
        return None, err
    try:
        return kite.get_gtts(), None
    except Exception as exc:
        return None, str(exc)


def place_gtt(payload: Dict[str, Any], *, dry_run: bool = True) -> Tuple[Optional[Any], Optional[str]]:
    if dry_run or not _live_orders_allowed():
        return {"dry_run": True, "would_place_gtt": payload}, None
    kite, err = _require_kite()
    if err:
        return None, err
    try:
        trigger_id = kite.place_gtt(
            trigger_type=payload["trigger_type"],
            tradingsymbol=payload["tradingsymbol"],
            exchange=payload["exchange"],
            trigger_values=payload["trigger_values"],
            last_price=float(payload["last_price"]),
            orders=payload["orders"],
        )
        return {"trigger_id": trigger_id}, None
    except Exception as exc:
        return None, str(exc)


def delete_gtt(trigger_id: int, *, dry_run: bool = True) -> Tuple[Optional[Any], Optional[str]]:
    if dry_run or not _live_orders_allowed():
        return {"dry_run": True, "would_delete_gtt": trigger_id}, None
    kite, err = _require_kite()
    if err:
        return None, err
    try:
        return kite.delete_gtt(trigger_id), None
    except Exception as exc:
        return None, str(exc)


def order_margins(orders: List[Dict[str, Any]]) -> Tuple[Optional[Any], Optional[str]]:
    kite, err = _require_kite()
    if err:
        return None, err
    try:
        return kite.order_margins(orders), None
    except Exception as exc:
        return None, str(exc)
