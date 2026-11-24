"""Saved watchlists for the desk. At most five. The first list holds the built-in book."""

from __future__ import annotations

import json
import os
import re
import threading
from typing import Any, Dict, List, Optional

MAX_LISTS = 5
DEFAULT_ID = "all"


def default_base() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "stock_signal_data")
_LOCK = threading.Lock()
_CACHE: Dict[str, Any] = {"mtime": None, "symbols": frozenset()}
_SYMBOL = re.compile(r"^[A-Z][A-Z0-9&-]{0,19}$")


def store_path(base_dir: str) -> str:
    return os.path.join(base_dir, "watchlists.json")


def _blank(symbols: List[str]) -> Dict[str, Any]:
    clean = _symbols(symbols)
    return {
        "active_id": DEFAULT_ID,
        "lists": [{"id": DEFAULT_ID, "name": "All", "symbols": clean}],
    }


def _symbols(values: List[str]) -> List[str]:
    out: List[str] = []
    for raw in values:
        sym = str(raw or "").strip().upper()
        if not _SYMBOL.match(sym) or sym in out:
            continue
        out.append(sym)
    return out


def _read(base_dir: str, defaults: List[str]) -> Dict[str, Any]:
    path = store_path(base_dir)
    if not os.path.isfile(path):
        book = _blank(defaults)
        _write(base_dir, book)
        return book
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict) or not isinstance(data.get("lists"), list) or not data["lists"]:
        book = _blank(defaults)
        _write(base_dir, book)
        return book
    return data


def _write(base_dir: str, book: Dict[str, Any]) -> None:
    os.makedirs(base_dir, exist_ok=True)
    path = store_path(base_dir)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(book, handle, indent=2)
    _CACHE["mtime"] = None


def ensure(base_dir: str, defaults: List[str]) -> Dict[str, Any]:
    with _LOCK:
        return _read(base_dir, defaults)


def known_symbols(base_dir: str) -> frozenset:
    path = store_path(base_dir)
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return frozenset()
    if _CACHE.get("mtime") == mtime:
        return _CACHE["symbols"]
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return frozenset()
    found = []
    for row in data.get("lists") or []:
        found.extend(_symbols(list(row.get("symbols") or [])))
    symbols = frozenset(found)
    _CACHE["mtime"] = mtime
    _CACHE["symbols"] = symbols
    return symbols


def contains(base_dir: str, symbol: str) -> bool:
    return str(symbol or "").strip().upper() in known_symbols(base_dir)


def _list(book: Dict[str, Any], list_id: Optional[str]) -> Optional[Dict[str, Any]]:
    want = list_id or book.get("active_id") or DEFAULT_ID
    for row in book["lists"]:
        if row.get("id") == want:
            return row
    return book["lists"][0]


def as_rows(base_dir: str, defaults: List[str], list_id: Optional[str] = None) -> List[Dict[str, str]]:
    book = ensure(base_dir, defaults)
    row = _list(book, list_id)
    return [
        {"symbol": sym, "name": sym, "sector": ""}
        for sym in _symbols(list(row.get("symbols") or []))
    ]


def public_view(base_dir: str, defaults: List[str]) -> Dict[str, Any]:
    book = ensure(base_dir, defaults)
    return {
        "max_lists": MAX_LISTS,
        "active_id": book.get("active_id") or DEFAULT_ID,
        "lists": [
            {
                "id": row.get("id"),
                "name": row.get("name") or row.get("id"),
                "symbols": _symbols(list(row.get("symbols") or [])),
                "locked": row.get("id") == DEFAULT_ID,
            }
            for row in book["lists"]
        ],
    }


def set_active(base_dir: str, defaults: List[str], list_id: str) -> Dict[str, Any]:
    with _LOCK:
        book = _read(base_dir, defaults)
        if not any(row.get("id") == list_id for row in book["lists"]):
            raise ValueError("That watchlist does not exist.")
        book["active_id"] = list_id
        _write(base_dir, book)
    return public_view(base_dir, defaults)


def create_list(base_dir: str, defaults: List[str], name: str) -> Dict[str, Any]:
    title = " ".join(str(name or "").split())
    if not title:
        raise ValueError("Name the watchlist.")
    with _LOCK:
        book = _read(base_dir, defaults)
        if len(book["lists"]) >= MAX_LISTS:
            raise ValueError("Five watchlists is the limit.")
        used = {row.get("id") for row in book["lists"]}
        n = 2
        while f"w{n}" in used:
            n += 1
        book["lists"].append({"id": f"w{n}", "name": title[:32], "symbols": []})
        book["active_id"] = f"w{n}"
        _write(base_dir, book)
    return public_view(base_dir, defaults)


def delete_list(base_dir: str, defaults: List[str], list_id: str) -> Dict[str, Any]:
    if list_id == DEFAULT_ID:
        raise ValueError("The All list stays.")
    with _LOCK:
        book = _read(base_dir, defaults)
        book["lists"] = [row for row in book["lists"] if row.get("id") != list_id]
        if not book["lists"]:
            book = _blank(defaults)
        if book.get("active_id") == list_id:
            book["active_id"] = DEFAULT_ID
        _write(base_dir, book)
    return public_view(base_dir, defaults)


def add_symbol(base_dir: str, defaults: List[str], list_id: str, symbol: str) -> Dict[str, Any]:
    sym = str(symbol or "").strip().upper()
    if not _SYMBOL.match(sym):
        raise ValueError("Use the NSE symbol, such as TATAMOTORS.")
    with _LOCK:
        book = _read(base_dir, defaults)
        target = next((item for item in book["lists"] if item.get("id") == list_id), None)
        if target is None:
            raise ValueError("That watchlist does not exist.")
        symbols = _symbols(list(target.get("symbols") or []))
        if sym not in symbols:
            symbols.append(sym)
        target["symbols"] = symbols
        book["active_id"] = list_id
        _write(base_dir, book)
    return public_view(base_dir, defaults)


def remove_symbol(base_dir: str, defaults: List[str], list_id: str, symbol: str) -> Dict[str, Any]:
    if list_id == DEFAULT_ID:
        raise ValueError("Symbols on the All watchlist cannot be removed. Switch to your own list to edit it.")
    sym = str(symbol or "").strip().upper()
    with _LOCK:
        book = _read(base_dir, defaults)
        if not any(item.get("id") == list_id for item in book["lists"]):
            raise ValueError("That watchlist does not exist.")
        target = next(item for item in book["lists"] if item.get("id") == list_id)
        target["symbols"] = [s for s in _symbols(list(target.get("symbols") or [])) if s != sym]
        _write(base_dir, book)
    return public_view(base_dir, defaults)
