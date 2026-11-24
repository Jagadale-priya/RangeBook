"""AGREE_15M_ANY5 — issued 15m ∩ any 5m, take best-p 5m entry."""
from __future__ import annotations

from collections import defaultdict
from typing import Dict, Iterable, List, Set, Tuple

AGREE_TAG = "AGREE_15M_ANY5"


def _side(r: dict) -> str:
    return str(r.get("decision") or "").upper()


def _p(r: dict) -> float:
    for k in ("p_t1", "score", "p"):
        if r.get(k) is not None:
            try:
                return float(r[k])
            except Exception:
                pass
    return 0.0


def _hm(r: dict) -> str:
    return str(r.get("hm") or "")


def build_agree_rows(
    good_prod2: Iterable[dict],
    proven: Iterable[dict],
    champion: Iterable[dict],
    crown_htf: Iterable[dict],
) -> List[dict]:
    """One call per agreeing day+side; entry = 5m with highest p_t1."""
    good_ix: Dict[Tuple[str, str], List[dict]] = defaultdict(list)
    for r in good_prod2:
        good_ix[(r["day"], _side(r))].append(r)

    five_ix: Dict[Tuple[str, str], List[dict]] = defaultdict(list)
    for rows, track in (
        (proven, "proven_100"),
        (champion, "champion"),
        (crown_htf, "crown_5m"),
    ):
        for r in rows:
            rr = dict(r, track=track)
            five_ix[(rr["day"], _side(rr))].append(rr)

    out: List[dict] = []
    for key, grows in good_ix.items():
        frows = five_ix.get(key) or []
        if not frows:
            continue
        best5 = max(frows, key=lambda x: (_p(x), -len(_hm(x))))
        g = sorted(grows, key=lambda x: _hm(x))[0]
        out.append(
            dict(
                best5,
                accurate=True,
                accurate_tag=AGREE_TAG,
                agree_15m_hm=g.get("hm"),
                tag=AGREE_TAG,
            )
        )
    return out


def build_agree_keys(
    good_prod2: Iterable[dict],
    proven: Iterable[dict],
    champion: Iterable[dict],
    crown_htf: Iterable[dict],
) -> Set[Tuple[str, str, str]]:
    rows = build_agree_rows(good_prod2, proven, champion, crown_htf)
    return {(r["day"], _side(r), _hm(r)) for r in rows}
