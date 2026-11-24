"""Dummy LIVE session test — FINAL 3 books · one-page UI · accuracy-tag notifies.

Shows how NIFTY F&O would look on live sessions:
  - All possible UI calls on **one page** (no blocked entries)
  - Notification = **accuracy_tag only** + Option Chain links
  - Books: P2F day/cap2 · P2G 10m · CHAMP_PLUS (nothing else)

  python -u prod_live/tests/builders/dummy_live_session_final_3books.py
  python -u prod_live/tests/builders/dummy_live_session_final_3books.py --emit   # real toasts
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[3]
BUILDERS = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BUILDERS))
sys.path.insert(0, str(ROOT / "prod_live"))
import path_setup  # noqa: F401,E402

from accuracy_max_6m import _champ_floor  # noqa: E402
from research_100pct_deeper_more_calls import gap_map, union_unique_days  # noqa: E402
from research_confirm_dual_tf_deep import _clip  # noqa: E402
import research_nifty_final_stack_2y as fs  # noqa: E402
from prod_live.logic.accurate_desks import build_all_accurate_desks  # noqa: E402
from prod_live.logic.combined_live_book import (  # noqa: E402
    call_key,
    combine_live_rows,
    final_book_registry,
)
from prod_live.logic.champ_plus_live import load_held_calls  # noqa: E402
from prod_live.logic.p2f_day_live import (  # noqa: E402
    LIVE_DAY_DESKS,
    WINDOW_1Y as P2F_1Y,
    build_p2f_day_desks,
    load_phase2f_day_recipes,
)
from prod_live.logic.p2f_cap2_live import (  # noqa: E402
    LIVE_CAP2_DESKS,
    build_p2f_cap2_desks,
    load_phase2f_cap2_recipes,
)
from prod_live.logic.p2g_10m import BASE_KEY_BY_DESK, HARD_GATES, WINDOW_5Y  # noqa: E402
from prod_live.logic.p2g_10m_live import LIVE_P2G_DESKS, load_phase2g_recipes, stamp_live  # noqa: E402
from prod_live.logic.accuracy_notify import (  # noqa: E402
    build_notifies_for_ui_calls,
    emit_accuracy_notify,
)
from research_acc_phase2g_10m_1y import desk_ok, load_d10, mine_streams, universes_p2g  # noqa: E402
from prod_live.holding_accurate.rebuild_streams import rebuild_all_tags  # noqa: E402

OUT_DIR = ROOT / "prod_live" / "reports" / "1y"
OUT_HTML = OUT_DIR / "DUMMY_LIVE_SESSION_FINAL_3BOOKS.html"
OUT_JSON = OUT_DIR / "DUMMY_LIVE_SESSION_FINAL_3BOOKS.json"
OUT_MD = OUT_DIR / "DUMMY_LIVE_SESSION_FINAL_3BOOKS.md"
LEDGER = ROOT / "stock_signal_data/fno_validate/research"
CACHE_DUAL = LEDGER / "_cache_dual15_dual5_10y.json"
CACHE_PATH = LEDGER / "_cache_path_trusted_10y.json"

# Live-session window to demo (recent tape)
SESSION_START = "2026-11-01"
SESSION_END = "2026-11-15"


def clip_incl(rows: List[dict], a: str, b: str) -> List[dict]:
    return [r for r in rows if a <= str(r.get("day") or "") <= b]


def rebuild_held_p2g(seed, tags, by_tag, floor):
    cur = list(seed)
    if not desk_ok(cur, floor):
        cur = []
    for tag in tags:
        rows = by_tag.get(tag)
        if rows:
            cur = union_unique_days(cur, rows)
    return cur


def esc(s: Any) -> str:
    return (
        str(s or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def render_html(
    *,
    ui: List[dict],
    notifies: List[dict],
    meta: Dict[str, Any],
) -> str:
    by_day: Dict[str, List[dict]] = defaultdict(list)
    for r in ui:
        by_day[str(r.get("day") or "")].append(r)

    notify_by_key = {
        (n.get("day"), n.get("decision"), n.get("hm")): n for n in notifies
    }

    rows_html = []
    for day in sorted(by_day):
        rows_html.append(f'<h2 class="day">{esc(day)}</h2>')
        rows_html.append('<div class="calls">')
        for r in sorted(by_day[day], key=lambda x: (x.get("hm") or "", x.get("decision") or "")):
            side = str(r.get("decision") or "")
            acc = esc(r.get("accuracy_tag") or "")
            desks = r.get("desks_satisfied") or []
            tags = [t for t in (r.get("tags") or []) if str(t).startswith("ACC_RANGE_")]
            # show all ACC_RANGE tags on card
            tag_pills = "".join(f'<span class="pill acc">{esc(t)}</span>' for t in tags)
            desk_pills = "".join(
                f'<span class="pill desk">{esc(d)}</span>' for d in desks
            )
            n = notify_by_key.get((r.get("day"), side, r.get("hm"))) or {}
            links = ((n.get("option_chain_links") or {}))
            opt = n.get("option") or {}
            oc_btns = []
            if links.get("desk_option_chain"):
                oc_btns.append(
                    f'<a class="btn" href="{esc(links["desk_option_chain"])}" target="_blank" rel="noopener">Desk Option Chain</a>'
                )
            if links.get("nse_option_chain"):
                oc_btns.append(
                    f'<a class="btn ghost" href="{esc(links["nse_option_chain"])}" target="_blank" rel="noopener">NSE Option Chain</a>'
                )
            if links.get("groww_chart"):
                oc_btns.append(
                    f'<a class="btn groww" href="{esc(links["groww_chart"])}" target="_blank" rel="noopener">Groww chart</a>'
                )
            if links.get("api_contracts"):
                oc_btns.append(
                    f'<a class="btn ghost" href="{esc(links["api_contracts"])}" target="_blank" rel="noopener">API /fno/contracts</a>'
                )
            multi = " multi" if r.get("multi_desk") else ""
            rows_html.append(
                f"""
<article class="card{multi}">
  <header>
    <div class="side {esc(side.lower())}">{esc(side)}</div>
    <div class="hm">{esc(r.get('hm'))}</div>
    <div class="acc-main">{acc}</div>
  </header>
  <div class="levels">
    entry <b>{esc(r.get('entry'))}</b>
    · SL <b>{esc(r.get('stop_loss'))}</b>
    · T <b>{esc(r.get('target_1'))}</b>
    · win <b>{'W' if r.get('win') else 'L' if r.get('win') is False else '—'}</b>
  </div>
  <div class="pills">{tag_pills}{desk_pills}</div>
  <div class="notify">
    <div class="toast-title">NOTIFY · {acc}</div>
    <div class="toast-body">{esc(n.get('message') or '')}</div>
    <div class="oc">ATM {esc(opt.get('right'))} {esc(opt.get('strike'))}
    {(' · ' + esc(opt.get('tradingsymbol'))) if opt.get('tradingsymbol') else ''}</div>
    <div class="actions">{''.join(oc_btns)}</div>
  </div>
</article>
"""
            )
        rows_html.append("</div>")

    notify_list = []
    for n in notifies:
        notify_list.append(
            f"<li><code>{esc(n.get('title'))}</code> — {esc(n.get('message'))}</li>"
        )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Dummy LIVE · FINAL 3 books · NIFTY F&O</title>
<style>
  :root {{
    --bg: #0f1419;
    --panel: #171d25;
    --line: #2a3441;
    --text: #e7eef7;
    --muted: #8b9bb0;
    --buy: #1f9d63;
    --sell: #d4534a;
    --acc: #3d8bfd;
    --desk: #6b7c93;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; font-family: "Segoe UI", system-ui, sans-serif;
    background: var(--bg); color: var(--text); line-height: 1.45;
  }}
  .wrap {{ max-width: 1100px; margin: 0 auto; padding: 28px 18px 80px; }}
  h1 {{ font-size: 1.55rem; font-weight: 650; margin: 0 0 6px; letter-spacing: -0.02em; }}
  .sub {{ color: var(--muted); margin-bottom: 22px; font-size: 0.95rem; }}
  .stats {{
    display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
    gap: 10px; margin-bottom: 28px;
  }}
  .stat {{
    background: var(--panel); border: 1px solid var(--line); border-radius: 10px;
    padding: 12px 14px;
  }}
  .stat b {{ display: block; font-size: 1.25rem; }}
  .stat span {{ color: var(--muted); font-size: 0.8rem; }}
  .banner {{
    border: 1px solid var(--line); background: #132033; border-radius: 10px;
    padding: 12px 14px; margin-bottom: 24px; color: #c5d7ef; font-size: 0.9rem;
  }}
  h2.day {{
    margin: 28px 0 12px; font-size: 1.05rem; color: var(--muted);
    border-bottom: 1px solid var(--line); padding-bottom: 6px;
  }}
  .calls {{ display: grid; gap: 12px; }}
  .card {{
    background: var(--panel); border: 1px solid var(--line); border-radius: 12px;
    padding: 14px 16px;
  }}
  .card.multi {{ border-color: #3a5a8a; }}
  header {{
    display: flex; flex-wrap: wrap; gap: 10px; align-items: baseline; margin-bottom: 8px;
  }}
  .side {{
    font-weight: 700; font-size: 0.95rem; padding: 2px 8px; border-radius: 6px;
  }}
  .side.buy {{ background: rgba(31,157,99,.18); color: #5ddea3; }}
  .side.sell {{ background: rgba(212,83,74,.18); color: #f0a29c; }}
  .hm {{ color: var(--muted); font-variant-numeric: tabular-nums; }}
  .acc-main {{
    margin-left: auto; font-weight: 700; color: #9ec1ff; font-size: 0.95rem;
  }}
  .levels {{ color: var(--muted); font-size: 0.88rem; margin-bottom: 8px; }}
  .levels b {{ color: var(--text); font-weight: 600; }}
  .pills {{ display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 10px; }}
  .pill {{
    font-size: 0.72rem; padding: 3px 8px; border-radius: 999px; border: 1px solid var(--line);
  }}
  .pill.acc {{ background: rgba(61,139,253,.15); color: #9ec1ff; border-color: #2e4f7a; }}
  .pill.desk {{ color: #b7c3d4; }}
  .notify {{
    margin-top: 8px; padding-top: 10px; border-top: 1px dashed var(--line);
  }}
  .toast-title {{
    font-size: 0.78rem; letter-spacing: 0.04em; color: #9ec1ff; font-weight: 700;
    margin-bottom: 4px;
  }}
  .toast-body {{ font-size: 0.9rem; margin-bottom: 4px; }}
  .oc {{ color: var(--muted); font-size: 0.82rem; margin-bottom: 8px; }}
  .actions {{ display: flex; flex-wrap: wrap; gap: 8px; }}
  .btn {{
    display: inline-block; text-decoration: none; color: #041018; background: #3d8bfd;
    padding: 6px 10px; border-radius: 8px; font-size: 0.8rem; font-weight: 600;
  }}
  .btn.ghost {{ background: transparent; color: #9ec1ff; border: 1px solid #2e4f7a; }}
  .btn.groww {{ background: #00b386; color: #041018; }}
  .notify-log {{
    margin-top: 36px; background: var(--panel); border: 1px solid var(--line);
    border-radius: 12px; padding: 16px;
  }}
  .notify-log h2 {{ margin: 0 0 10px; font-size: 1rem; }}
  .notify-log ul {{ margin: 0; padding-left: 18px; color: var(--muted); font-size: 0.88rem; }}
  code {{ color: #9ec1ff; }}
</style>
</head>
<body>
<div class="wrap">
  <h1>NIFTY F&amp;O · Dummy LIVE session</h1>
  <p class="sub">
    Final 3 books only · {esc(meta.get('session_start'))} → {esc(meta.get('session_end'))} ·
    same (day,side,hm) → 1 call · accuracy-tag notify · Option Chain links ·
    <b>blocked = {esc(meta.get('blocked_distinct'))}</b>
  </p>
  <div class="banner">
    Books: <b>P2F</b> (day+cap2) · <b>P2G 10m</b> · <b>CHAMP_PLUS_T30SL30_CAP4</b>.
    Excluded: STACK / AGREE. Notification title = <b>accuracy_tag only</b> (ACC_RANGE_*).
  </div>
  <div class="stats">
    <div class="stat"><b>{esc(meta.get('n_ui'))}</b><span>UI calls (1 page)</span></div>
    <div class="stat"><b>{esc(meta.get('n_raw'))}</b><span>Raw desk firings</span></div>
    <div class="stat"><b>{esc(meta.get('n_multi'))}</b><span>Multi-desk combined</span></div>
    <div class="stat"><b>{esc(meta.get('n_notify'))}</b><span>Accuracy notifies</span></div>
    <div class="stat"><b>{esc(meta.get('blocked_distinct'))}</b><span>Blocked distinct</span></div>
  </div>
  {''.join(rows_html)}
  <section class="notify-log">
    <h2>Notification feed (accuracy_tag title only)</h2>
    <ul>{''.join(notify_list) if notify_list else '<li>(none)</li>'}</ul>
  </section>
</div>
</body>
</html>
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--emit", action="store_true", help="Fire real desktop notifies")
    ap.add_argument("--start", default=SESSION_START)
    ap.add_argument("--end", default=SESSION_END)
    args = ap.parse_args()
    start, end = args.start, args.end
    dry = not args.emit
    t0 = time.time()
    print(f"DUMMY LIVE session {start} → {end} · dry_run={dry}", flush=True)

    # ---- CHAMP (fast held) ----
    print("  CHAMP_PLUS…", flush=True)
    champ_all = load_held_calls()
    champ = clip_incl(champ_all, start, end)

    # ---- shared caches ----
    dual = json.loads(CACHE_DUAL.read_text(encoding="utf-8"))
    path_u = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    gaps = gap_map()
    sessions_all, _, _ = fs._prod2(5000)
    sess_1y = [d for d in sessions_all if P2F_1Y["start"] < d <= P2F_1Y["end"]]
    active_1y = fs._active_days(sess_1y, fs._load_daily()) if sess_1y else set()
    proven = [dict(r, track="proven_100") for r in dual["dual15"]["proven_100"]]
    champ_rows = _champ_floor([dict(r, track="champion") for r in dual["dual15"]["champion"]])
    dual15 = proven + dual["dual15"]["champion"]
    dual5 = dual["dual5"]["proven_100"] + dual["dual5"]["champion"]
    champ_native = path_u.get("champ_native") or champ_rows

    # ---- P2F ----
    print("  P2F rebuild…", flush=True)
    phase1_1y = build_all_accurate_desks(
        proven15=proven,
        dual15=dual15,
        dual5=dual5,
        crown_by_risk=path_u.get("crown_by_risk") or {},
        good_by_risk=path_u.get("good_by_risk") or {},
        champ_rows=champ_native,
        gap_pct_by_day=gaps,
        htf_days=active_1y,
    )
    recipes_f = load_phase2f_day_recipes()
    recipes_c = load_phase2f_cap2_recipes()
    all_tags: List[str] = []
    seen = set()
    for desk in list(LIVE_DAY_DESKS) + list(LIVE_CAP2_DESKS):
        meta = recipes_f.get(desk) or recipes_c.get(desk) or {}
        for t in meta.get("stream_tags_research") or []:
            if t not in seen:
                seen.add(t)
                all_tags.append(t)
    by_tag = rebuild_all_tags(
        all_tags, path_u, gaps, active_1y, dual15, dual5, proven, champ_rows
    )
    p2f_day_full = build_p2f_day_desks(phase1_1y, by_tag)
    p2f_cap2_full = build_p2f_cap2_desks(phase1_1y, by_tag)
    p2f_day = {d: clip_incl(p2f_day_full.get(d) or [], start, end) for d in LIVE_DAY_DESKS}
    p2f_cap2 = {d: clip_incl(p2f_cap2_full.get(d) or [], start, end) for d in LIVE_CAP2_DESKS}

    # ---- P2G ----
    print("  P2G rebuild…", flush=True)
    sess_5y = [d for d in sessions_all if WINDOW_5Y["start"] < d <= WINDOW_5Y["end"]]
    active_5y = fs._active_days(sess_5y, fs._load_daily()) if sess_5y else set()
    phase1_5y = build_all_accurate_desks(
        proven15=proven,
        dual15=dual15,
        dual5=dual5,
        crown_by_risk=path_u.get("crown_by_risk") or {},
        good_by_risk=path_u.get("good_by_risk") or {},
        champ_rows=champ_native,
        gap_pct_by_day=gaps,
        htf_days=active_5y,
    )
    d10 = load_d10()
    univ = universes_p2g(path_u, d10, champ_native)
    streams_all = mine_streams(univ, gaps, active_5y, floor_min=82.71)
    by_tag_g = {t: rows for t, rows in streams_all}
    recipes_g = load_phase2g_recipes()
    p2g: Dict[str, List[dict]] = {}
    for desk in LIVE_P2G_DESKS:
        floor = HARD_GATES[desk]
        meta = recipes_g.get(desk) or {}
        tags = list(meta.get("stream_tags_research") or [])
        seed = list(phase1_5y.get(BASE_KEY_BY_DESK[desk]) or [])
        rows = stamp_live(rebuild_held_p2g(seed, tags, by_tag_g, floor), desk)
        p2g[desk] = clip_incl(rows, start, end)

    # ---- Combine (never block) ----
    print("  combine…", flush=True)
    combined = combine_live_rows(
        p2f_day=p2f_day,
        p2f_cap2=p2f_cap2,
        p2g_10m=p2g,
        champ_plus=champ,
    )
    ui = combined["ui_rows"]
    blocked = int(combined.get("blocked_distinct") or 0)
    assert blocked == 0, f"blocked_distinct={blocked}"

    raw_keys = {call_key(r) for r in combined["raw_rows"] if all(call_key(r))}
    ui_keys = {call_key(r) for r in ui}
    missing = raw_keys - ui_keys
    assert not missing, f"missing UI keys {len(missing)}"

    # ---- Accuracy notifies ----
    notifies = build_notifies_for_ui_calls(ui, dry_run=dry)
    emitted = 0
    if not dry:
        for n in notifies:
            n["dry_run"] = False
            if emit_accuracy_notify(n):
                emitted += 1

    meta = {
        "session_start": start,
        "session_end": end,
        "n_ui": len(ui),
        "n_raw": combined["n_raw"],
        "n_multi": combined["n_multi_desk"],
        "n_notify": len(notifies),
        "blocked_distinct": blocked,
        "emitted": emitted,
        "dry_run": dry,
        "registry": final_book_registry(),
        "policy": combined.get("policy"),
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    html = render_html(ui=ui, notifies=notifies, meta=meta)
    OUT_HTML.write_text(html, encoding="utf-8")

    # compact JSON
    OUT_JSON.write_text(
        json.dumps(
            {
                "meta": meta,
                "ui_calls": [
                    {
                        "day": r.get("day"),
                        "hm": r.get("hm"),
                        "side": r.get("decision"),
                        "accurate_tag": r.get("accurate_tag"),
                        "accuracy_tag": r.get("accuracy_tag"),
                        "desks_satisfied": r.get("desks_satisfied"),
                        "tags": r.get("tags"),
                        "entry": r.get("entry"),
                        "stop_loss": r.get("stop_loss"),
                        "target_1": r.get("target_1"),
                        "win": r.get("win"),
                        "multi_desk": r.get("multi_desk"),
                    }
                    for r in ui
                ],
                "notifications": notifies,
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )

    lines = [
        "# Dummy LIVE session — FINAL 3 books",
        "",
        f"**Window:** `{start}` → `{end}`",
        f"**UI calls:** {len(ui)} · raw {combined['n_raw']} · multi-desk {combined['n_multi_desk']}",
        f"**Blocked distinct:** **{blocked}**",
        f"**Notifies:** {len(notifies)} (accuracy_tag title only) · emitted={emitted} · dry_run={dry}",
        "",
        f"Open one-page UI: `{OUT_HTML}`",
        "",
        "## Sample notifications",
        "",
    ]
    for n in notifies[:12]:
        lines.append(
            f"- **{n.get('title')}** — {n.get('message')}  "
            f"  \n  OC: `{((n.get('option_chain_links') or {}).get('desk_option_chain'))}`"
        )
    lines.extend(["", "## All UI calls", ""])
    lines.append("| Day | HM | Side | accuracy_tag | desks | Entry | SL | T |")
    lines.append("|---|---|---|---|---|---:|---:|---:|")
    for r in ui:
        lines.append(
            f"| {r.get('day')} | {r.get('hm')} | {r.get('decision')} | "
            f"`{r.get('accuracy_tag')}` | {len(r.get('desks_satisfied') or [])} | "
            f"{r.get('entry')} | {r.get('stop_loss')} | {r.get('target_1')} |"
        )
    elapsed = round(time.time() - t0, 1)
    lines.extend(["", f"Elapsed {elapsed}s", ""])
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"  UI={len(ui)} raw={combined['n_raw']} multi={combined['n_multi_desk']} blocked={blocked}", flush=True)
    print(f"Wrote {OUT_HTML}", flush=True)
    print(f"Wrote {OUT_JSON}", flush=True)
    print(f"Wrote {OUT_MD}", flush=True)
    print("VERDICT PASS · no blocked calls · accuracy-tag notifies ready", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
