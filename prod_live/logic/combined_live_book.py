"""Final NIFTY F&O LIVE combine — P2F + P2G 10m + CHAMP_PLUS only.

UI rule: one physical entry `(day, side, hm)` → **one call** with all
satisfying desk tags merged. Highest-accuracy desk displays first.

Distinct entries (different day/side/hm) are **never** blocked or dropped.
No volume stack / AGREE — those are not part of the final NIFTY F&O books.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional, Sequence, Tuple

from prod_live.logic.p2f_day_live import (
    ACCURACY_TAG_BY_DESK as DAY_ACC,
    HARD_GATES as DAY_GATES,
    LIVE_DAY_DESKS,
)
from prod_live.logic.p2f_cap2_live import (
    ACCURACY_TAG_BY_DESK as CAP2_ACC,
    HARD_GATES as CAP2_GATES,
    LIVE_CAP2_DESKS,
)
from prod_live.logic.p2g_10m import (
    ACCURACY_TAG_BY_DESK as P2G_ACC,
    HARD_GATES as P2G_GATES,
)
from prod_live.logic.p2g_10m_live import (
    EXPECTED_5Y as P2G_EXP_5Y,
    LIVE_P2G_DESKS,
)
from prod_live.logic.champ_plus_live import (
    ACCURACY_TAG as CHAMP_ACC,
    DESK as CHAMP_DESK,
    EXPECTED as CHAMP_EXPECTED,
)

NOTIFY_ALREADY = "ALREADY_OPEN_OTHER_DESK"

# Highest accuracy first (UI display / primary desk order)
# Ranked by measured accuracy_lo / P2F range floors (high → low).
DESK_ACCURACY_ORDER: List[str] = [
    # P2F perfect band
    "ACC100_MULTI_V11",
    "ACC100_MULTI_V5_CAP2_P2F",
    # P2G / CHAMP high-90 measured
    "ACC100_MULTI_V12_P2G_10M",  # 94.51–100
    "CHAMP_PLUS_T30SL30_CAP6",  # Cap6 final · ~99.5% 1y
    "CHAMP_PLUS_T30SL30_CAP4",  # legacy Cap4 tag compat
    "ACC_WIDE_P90_P2G_10M",  # 92.92–100
    # P2F P92
    "ACC_WIDE_P92_P2F",
    "ACC_WIDE_P92_CAP2_P2F",
    # P2F P90
    "ACC_WIDE_P90_P2F",
    "ACC_WIDE_P90_CAP2_P2F",
    # P2G mid
    "ACC_WIDE_P85B_P2G_10M",  # 88.41–94.23
    "ACC_WIDE_P85_P2G_10M",  # 86.17–96.72
    # P2F P85
    "ACC_WIDE_P85_P2F",
    "ACC_WIDE_P85_CAP2_P2F",
    "ACC_WIDE_P85B_P2F",
    # P2G / P2F vol
    "ACC_WIDE_P92_P2G_10M",  # 83.08–100 (wide; lower lo)
    "ACC_WIDE_P80_P2F",
    "ACC_WIDE_P80_P2G_10M",
    "ACC_WIDE_P75_P2F",
    "ACC_WIDE_P75_P2G_10M",
]

_ACC_RANGE_ORDER = [
    "ACC_RANGE_98_100",
    "ACC_RANGE_94_100",
    "ACC_RANGE_93_100",
    "ACC_RANGE_92_100",
    "ACC_RANGE_91_100",
    "ACC_RANGE_89_96",
    "ACC_RANGE_88_95",
    "ACC_RANGE_86_97",
    "ACC_RANGE_84_90",
    "ACC_RANGE_83_100",
    "ACC_RANGE_81_89",
    "ACC_RANGE_81_85",
    "ACC_RANGE_81_84",
    "ACC_RANGE_76_85",
    "ACC_RANGE_75_83",
]

_FLOOR = {**DAY_GATES, **CAP2_GATES, **P2G_GATES}
_ACC = {**DAY_ACC, **CAP2_ACC, **P2G_ACC, CHAMP_DESK: CHAMP_ACC}

FINAL_BOOKS = ("p2f_day", "p2f_cap2", "p2g_10m", "champ_plus")


def _side(r: dict) -> str:
    return str(r.get("decision") or r.get("side") or "").upper()


def _hm(r: dict) -> str:
    return str(r.get("hm") or "")


def call_key(r: dict) -> Tuple[str, str, str]:
    return (str(r.get("day") or ""), _side(r), _hm(r))


def desk_rank(desk_tag: str) -> int:
    """Lower = higher accuracy / display priority."""
    if desk_tag in DESK_ACCURACY_ORDER:
        return DESK_ACCURACY_ORDER.index(desk_tag)
    floor = _FLOOR.get(desk_tag)
    if floor is not None:
        return 50 + int(1000 - floor * 10)
    return 900


def desk_priority(desk_tag: str, *, book: str = "") -> int:
    return desk_rank(desk_tag)


def _tag_rank(tag: str) -> int:
    if tag in DESK_ACCURACY_ORDER:
        return DESK_ACCURACY_ORDER.index(tag)
    if tag in _ACC_RANGE_ORDER:
        return 100 + _ACC_RANGE_ORDER.index(tag)
    if tag.startswith("ACC_FLOOR_"):
        return 200
    if tag.startswith("ACC_BAND_"):
        return 300
    if tag.startswith("LOGIC_"):
        return 400
    if tag in ("LANE_LIVE", "MODE_CAP2", "MODE_CAP4", "MODE_CAP6"):
        return 500
    return 600


def ordered_unique(items: List[str]) -> List[str]:
    seen = set()
    out = []
    for t in sorted([x for x in items if x], key=_tag_rank):
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def _collect_raw(
    *,
    p2f_day: Optional[Dict[str, List[dict]]] = None,
    p2f_cap2: Optional[Dict[str, List[dict]]] = None,
    p2g_10m: Optional[Dict[str, List[dict]]] = None,
    champ_plus: Optional[Sequence[dict]] = None,
    # deprecated — ignored (volume/agree removed from final NIFTY F&O)
    volume_rows: Optional[Sequence[dict]] = None,
) -> List[dict]:
    del volume_rows  # explicit: final books only
    all_rows: List[dict] = []
    for desk, rows in (p2f_day or {}).items():
        for r in rows:
            rr = dict(r)
            rr["book"] = "p2f_day"
            rr["source_desk"] = desk
            rr["desk_tag"] = desk
            if not rr.get("decision"):
                rr["decision"] = _side(rr)
            all_rows.append(rr)
    for desk, rows in (p2f_cap2 or {}).items():
        for r in rows:
            rr = dict(r)
            rr["book"] = "p2f_cap2"
            rr["source_desk"] = desk
            rr["desk_tag"] = desk
            if not rr.get("decision"):
                rr["decision"] = _side(rr)
            all_rows.append(rr)
    for desk, rows in (p2g_10m or {}).items():
        for r in rows:
            rr = dict(r)
            rr["book"] = "p2g_10m"
            rr["source_desk"] = desk
            rr["desk_tag"] = desk
            if not rr.get("decision"):
                rr["decision"] = _side(rr)
            all_rows.append(rr)
    for r in champ_plus or []:
        rr = dict(r)
        rr["book"] = "champ_plus"
        rr["source_desk"] = rr.get("source_desk") or CHAMP_DESK
        rr["desk_tag"] = rr.get("desk_tag") or CHAMP_DESK
        if not rr.get("decision"):
            rr["decision"] = _side(rr)
        all_rows.append(rr)
    return all_rows


def collapse_to_ui_calls(raw_rows: Sequence[dict]) -> List[dict]:
    """One UI call per (day, side, hm); merge all desk tags (accuracy-first)."""
    by_key: Dict[Tuple[str, str, str], List[dict]] = defaultdict(list)
    for r in raw_rows:
        k = call_key(r)
        if not k[0] or not k[1] or not k[2]:
            continue
        by_key[k].append(r)

    ui: List[dict] = []
    for key in sorted(by_key):
        group = by_key[key]
        desk_meta = []
        for r in group:
            desk = str(r.get("source_desk") or r.get("desk_tag") or "")
            desk_meta.append((desk_rank(desk), desk, r))
        desk_meta.sort(key=lambda x: (x[0], x[1]))
        best = desk_meta[0][2]
        desks_ordered: List[str] = []
        seen_d = set()
        for _, desk, _ in desk_meta:
            if desk and desk not in seen_d:
                seen_d.add(desk)
                desks_ordered.append(desk)

        all_tags: List[str] = []
        books: List[str] = []
        tracks: List[str] = []
        for r in group:
            all_tags.extend(str(t) for t in (r.get("tags") or []) if t)
            desk = str(r.get("source_desk") or r.get("desk_tag") or "")
            if desk:
                all_tags.append(desk)
            ar = r.get("accuracy_tag") or r.get("accuracy_range_tag") or _ACC.get(desk)
            if ar:
                all_tags.append(str(ar))
            b = str(r.get("book") or "")
            if b and b not in books:
                books.append(b)
            tr = str(r.get("track") or "")
            if tr and tr not in tracks:
                tracks.append(tr)

        primary_desk = desks_ordered[0]
        primary_acc = _ACC.get(primary_desk) or best.get("accuracy_tag") or best.get(
            "accuracy_range_tag"
        )
        tags = ordered_unique(all_tags)
        lead = [primary_desk]
        if primary_acc:
            lead.append(str(primary_acc))
        tags = ordered_unique(lead + tags)
        # strip legacy volume/agree/research lane noise
        tags = [
            t
            for t in tags
            if t
            not in (
                "STACK_PLUS_CROWN_HTF_CAP2",
                "AGREE_15M_ANY5",
                "BOOK_VOLUME",
                "LIVE_AGREE",
                "LANE_RESEARCH",
            )
        ]
        if "LANE_LIVE" not in tags:
            tags.append("LANE_LIVE")

        ui_row = dict(best)
        ui_row["day"] = key[0]
        ui_row["decision"] = key[1]
        ui_row["hm"] = key[2]
        ui_row["ui_combined"] = True
        ui_row["desks_satisfied"] = desks_ordered
        ui_row["also_satisfies"] = desks_ordered[1:]
        ui_row["books"] = books
        ui_row["tracks"] = tracks
        ui_row["source_desk"] = primary_desk
        ui_row["desk_tag"] = primary_desk
        ui_row["accurate_tag"] = primary_desk
        ui_row["accuracy_tag"] = primary_acc
        ui_row["accuracy_range_tag"] = primary_acc
        ui_row["hard_gate"] = _FLOOR.get(primary_desk)
        ui_row["tags"] = tags
        ui_row["accuracy_tags"] = tags
        ui_row["tag_count"] = len(tags)
        ui_row["desk_count"] = len(desks_ordered)
        ui_row["is_primary"] = True
        ui_row["is_ui_call"] = True
        ui_row["notify_code"] = None
        ui_row["notify_msg"] = None
        ui_row["override_of"] = None
        if len(desks_ordered) > 1:
            ui_row["multi_desk"] = True
            ui_row["notify_code"] = "MULTI_DESK_COMBINED"
            ui_row["notify_msg"] = (
                f"Combined {len(desks_ordered)} desks into 1 UI call; "
                f"primary={primary_desk}; also={desks_ordered[1:]}"
            )
        else:
            ui_row["multi_desk"] = False
        ui_row["win"] = best.get("win")
        ui_row["points"] = best.get("points")
        ui_row["p_t1"] = best.get("p_t1")
        ui_row["track"] = best.get("track") or (tracks[0] if tracks else None)
        ui_row["book"] = "combined" if len(books) > 1 else (books[0] if books else best.get("book"))
        ui_row["lane"] = "LIVE"
        ui.append(ui_row)

    ui.sort(key=lambda r: (str(r.get("day") or ""), _hm(r), _side(r)))
    return ui


def combine_live_rows(
    *,
    p2f_day: Optional[Dict[str, List[dict]]] = None,
    p2f_cap2: Optional[Dict[str, List[dict]]] = None,
    p2g_10m: Optional[Dict[str, List[dict]]] = None,
    champ_plus: Optional[Sequence[dict]] = None,
    volume_rows: Optional[Sequence[dict]] = None,  # ignored
) -> Dict[str, Any]:
    """Build raw desk firings + UI-collapsed calls (1 per day/side/hm)."""
    raw = _collect_raw(
        p2f_day=p2f_day,
        p2f_cap2=p2f_cap2,
        p2g_10m=p2g_10m,
        champ_plus=champ_plus,
        volume_rows=volume_rows,
    )
    ui = collapse_to_ui_calls(raw)

    raw_keys = {call_key(r) for r in raw if call_key(r)[0] and call_key(r)[1] and call_key(r)[2]}
    ui_keys = {call_key(r) for r in ui}
    blocked_distinct = len(raw_keys - ui_keys)

    multi_n = sum(1 for r in ui if r.get("multi_desk"))
    return {
        "raw_rows": raw,
        "all_rows": ui,
        "ui_rows": ui,
        "primary_rows": ui,
        "n_raw": len(raw),
        "n_all": len(ui),
        "n_ui": len(ui),
        "n_primary": len(ui),
        "n_multi_desk": multi_n,
        "overlap_days": len({r["day"] for r in ui if r.get("multi_desk")}),
        "blocked": 0,
        "blocked_distinct": blocked_distinct,
        "policy": "final_3books_collapse_same_entry_tags_accuracy_first_never_block",
        "final_books": list(FINAL_BOOKS),
        "excluded_books": ["STACK_PLUS_CROWN_HTF_CAP2", "AGREE_15M_ANY5"],
    }


def final_book_registry() -> Dict[str, Any]:
    """Machine snapshot of the only NIFTY F&O live logics."""
    return {
        "status": "FINAL",
        "lane": "LIVE",
        "nifty_fno_books_only": [
            {
                "book": "p2f",
                "modes": ["day", "cap2"],
                "day_desks": list(LIVE_DAY_DESKS),
                "cap2_desks": list(LIVE_CAP2_DESKS),
            },
            {
                "book": "p2g_10m",
                "modes": ["day"],
                "desks": list(LIVE_P2G_DESKS),
                "expected_5y": dict(P2G_EXP_5Y),
            },
            {
                "book": "champ_plus",
                "modes": ["cap6"],
                "desks": [CHAMP_DESK],
                "accuracy_tag": CHAMP_ACC,
                "expected": dict(CHAMP_EXPECTED),
            },
        ],
        "excluded": ["STACK_PLUS_CROWN_HTF_CAP2", "AGREE_15M_ANY5"],
        "ui": "same (day,side,hm) → 1 call · all tags · highest accuracy desk first · never block",
        "desk_priority": list(DESK_ACCURACY_ORDER),
    }
