# NIFTY F&O — all call logics (inventory + measured results)

**As of:** 2026-11-19  
**Scope:** every path that can produce or stamp a NIFTY F&O BUY/SELL (live board + research futures modules).  
**Cost convention (research):** 1.0 pt unless noted.

---

## A · Live board (what actually lists Calls)

Two layers run together:

1. **Listing** — `USE_DUAL_TRACK=1` scores dual packs; **`SUPPRESS_DUAL_LIST=1` (default)** blocks proven_100 → champion from the Calls board so **CHAMP_PLUS / crown fill** when empty. Set `SUPPRESS_DUAL_LIST=0` to restore dual-first listing.
2. **Annotate** — `ENABLE_P2F_LIVE_ACCURATE=1` (default). FINAL 3 books stamp accuracy tags; UI merges same `(day, side, hm)`.

| Flag | Default | Effect |
|---|---|---|
| `USE_DUAL_TRACK` | ON | Dual proven/champion **evaluation** (annotate / debug) |
| `SUPPRESS_DUAL_LIST` | **ON** | Do **not** list dual proven/champion; fill via CHAMP_PLUS / crown |
| `ENABLE_P2F_LIVE_ACCURATE` | ON | P2F + P2G + CHAMP_PLUS annotate |
| `ENABLE_EXTRA_TREES_SINGLE` | **OFF** | ExtraTrees single listing disabled |
| `ENABLE_STACKED_CALLS` | OFF | Research stack_plus / good channel |
| `ENABLE_PRE_DUAL_SINGLE` | OFF | Pre-dual single path |

**Docs:** `prod_live/FINAL_LOGIC.md` · `prod_live/holding_accurate/LIVE_CHANNELS.md` · `app/fno/fno_live_config.py`

---

### A1 · `proven_100` — dual track (suppressed list by default)

| | |
|---|---|
| **Tag / track** | `proven_100` · source `nifty_dual_track_proven_100` |
| **Code** | `app/fno/nifty_live_dual_track.py` |
| **TF** | 15m packs (BUY / SELL / SELL_CONT_Q) |
| **BUY gates** | regime ∈ {range, mixed} · p ≥ **0.62** · OR extension ≤ **0.10** · before **13:00** |
| **SELL gates** | regime ∈ {trend} · p ≥ **0.58** |
| **Brackets** | research ±30 (session rules) |
| **Priority** | highest dual channel |

---

### A2 · `champion` — dual track (suppressed list by default)

| | |
|---|---|
| **Tag / track** | `champion` · source `nifty_dual_track_champion` |
| **Code** | `app/fno/nifty_live_dual_track.py` |
| **TF** | same 15m packs |
| **BUY floor** | p ≥ **0.55** (raised from 0.50; 3y research: p&lt;0.55 ~21% hit) |
| **SELL floor** | p ≥ **0.58** |
| **Live clip** | **SL20 / T30** via `champion_clip_pts()` (env overrideable; research ±30 kept as base) |
| **Priority** | after proven_100 |

---

### A3 · CHAMP_PLUS fill (primary list when dual suppressed / dual silent)

| | |
|---|---|
| **accurate_tag** | `CHAMP_PLUS_T30SL30_CAP4` |
| **accuracy_tag** | `ACC_RANGE_93_100` (measured 93.19–99.61) |
| **Code** | `prod_live/logic/champ_plus_live.py` · dual modal fill path |
| **Brackets** | ±30 · **cap 4** same-side |
| **Mode** | live ticket-fill when dual quiet |
| **Locked N@hit** | 1y **374 @ 99.47%** · 3y **1028 @ 99.61%** · 5y **1689 @ 93.19%** |

---

### A4 · FINAL book · P2F (annotate)

| | |
|---|---|
| **Family** | day + Cap2 |
| **Code** | `logic/p2f_day_live.py` · `logic/p2f_cap2_live.py` |
| **Brackets** | ±30 |
| **Role** | stamps `accurate_tag` / `accuracy_tag`; UI merge via `combined_live_book.py` |

**Day desks (priority high → low):**

| accurate_tag | accuracy_tag | Floor |
|---|---|---:|
| `ACC100_MULTI_V11` | `ACC_RANGE_98_100` | 100 |
| `ACC_WIDE_P92_P2F` | `ACC_RANGE_91_100` | 99.24 |
| `ACC_WIDE_P90_P2F` | `ACC_RANGE_89_96` | 95.4 |
| `ACC_WIDE_P85_P2F` | `ACC_RANGE_84_90` | 89.69 |
| `ACC_WIDE_P85B_P2F` | `ACC_RANGE_81_89` | 88.4 |
| `ACC_WIDE_P80_P2F` | `ACC_RANGE_76_85` | 84.72 |
| `ACC_WIDE_P75_P2F` | `ACC_RANGE_75_83` | 82.71 |

Cap2 twins: `ACC100_MULTI_V5_CAP2_P2F` … `ACC_WIDE_P85_CAP2_P2F` (same ranges as day).

Confirm: `python -u prod_live/tests/confirm_p2f_day_live_1y.py` · `confirm_p2f_cap2_live_1y.py`

---

### A5 · FINAL book · P2G 10m (annotate)

| | |
|---|---|
| **Family** | `*_P2G_10M` |
| **Code** | `logic/p2g_10m_live.py` |
| **Brackets** | ±30 day |

| accurate_tag | accuracy_tag | Lo–Hi | 5y OK |
|---|---|---|---|
| `ACC100_MULTI_V12_P2G_10M` | `ACC_RANGE_94_100` | 94.51–100 | N |
| `ACC_WIDE_P90_P2G_10M` | `ACC_RANGE_92_100` | 92.92–100 | N |
| `ACC_WIDE_P85B_P2G_10M` | `ACC_RANGE_88_95` | 88.41–94.23 | Y |
| `ACC_WIDE_P85_P2G_10M` | `ACC_RANGE_86_97` | 86.17–96.72 | Y |
| `ACC_WIDE_P92_P2G_10M` | `ACC_RANGE_83_100` | 83.08–100 | N |
| `ACC_WIDE_P80_P2G_10M` | `ACC_RANGE_81_85` | 81.37–84.81 | N |
| `ACC_WIDE_P75_P2G_10M` | `ACC_RANGE_81_84` | 81.46–83.49 | N |

Confirm: `python -u prod_live/tests/confirm_final_nifty_3books.py`

---

### A6 · Morning context (no BUY/SELL)

| | |
|---|---|
| **Tag** | `MORNING_CALIBRATED_V1` |
| **Job** | `morning_pre915_context` |
| **Outputs** | expected H/L (~96%+), bias (≥70% when HIGH), gap lean |
| **Doc** | `MORNING_CONTEXT_LOGIC.md` |

---

### A7 · Explicitly OFF / excluded from NIFTY BUY/SELL emit

- `STACK_PLUS_CROWN_HTF_CAP2`
- `AGREE_15M_ANY5`
- ExtraTrees single (`ENABLE_EXTRA_TREES_SINGLE=0`)
- Baseline dual track (retired; proven + champion only)

---

## B · Research futures logics (modules ready; not LIVE emit yet)

These live under `prod_live/logic/`. Each has **baseline** + **accurate** profiles. They do **not** replace dual/FINAL listing unless wired later.

---

### B1 · ORB30 VWAP futures

| | |
|---|---|
| **Module** | `prod_live/logic/nifty_orb30_vwap_fut.py` |
| **TF** | 5m |
| **Idea** | 09:15–09:45 OR · VWAP confirm · break within extension · fill at level |

**baseline rule**

- Width **30–90** · signal close within **10** of ORH/ORL + VWAP side
- Entry: trade ORH/ORL if next bar still has it (`at_level`); else ≤10 past (`next_trade`)
- Stop **12** through level (ORH−12 / ORL+12) · Target **20** from fill · flat 14:45
- One live trade/day; failed fill keeps scanning; stop never reverses
- Prob gate 0.60 when model cols present

**accurate profile**

- Width **40–100** · entry within **5** of ORH/ORL

**Measured (kite 5m, cost 1.0)** — from `NIFTY_ACCURATE_PROFILES_TEST.md` / last-10 report:

| Profile | Window | N | Hit | Net |
|---|---:|---:|---:|---:|
| baseline | 10d | 0 | — | 0 (width out on all recent) |
| accurate | 10d | 2 | 50% | +2.45 |
| baseline | 40d | 9 | 66.7% | +51.70 |
| accurate | 40d | 9 | 66.7% | +68.55 |
| accurate | 60d | 24 | 58.3% | +99.40 |
| accurate | 80d | 33 | 54.5% | +114.40 |

**Reports:** `NIFTY_ORB30_VWAP_FUT_LAST10D.md` · `NIFTY_ACCURATE_PROFILES_TEST.md` · `NIFTY_TREND_ORB_ACCURACY_SEARCH.md`

---

### B2 · Trend-stay pullback

| | |
|---|---|
| **Module** | `prod_live/logic/nifty_trend_stay.py` |
| **TF** | 5m (+15m trail) |
| **Idea** | IB 09:15–10:15 break + VWAP · enter on pullback touch, not the break |

**baseline rule**

- Balance width **25–160**
- 15m close beyond IBH/IBL + same VWAP side
- Entry = first pullback touch + close back in break direction
- Chase &gt;25 without touch → no call · initial stop 15 inside · reject risk &gt;40
- Trail post-entry 15m swing · VWAP close exit · flat 14:45 · no reverse

**accurate profile**

- **SELL only** · signal before **12:00** · risk≤30 · entry_ext≤15 · chase≤20

**Measured:**

| Profile | Window | N | Hit | AvgW / AvgL | Net |
|---|---:|---:|---:|---|---:|
| baseline | 10d | 2 | 50% | 86 / −28.85 | +57.15 |
| accurate | 10d | 0 | — | — | 0 |
| baseline | 40d | 9 | 55.6% | — | +94.50 |
| accurate | 40d | 2 | **100%** | 37 / — | +74.00 |
| accurate | 60d | 8 | 62.5% | — | +96.95 |
| baseline | 80d | 27 | 37% | — | +117.00 |
| accurate | 80d | 11 | 45.5% | — | +85.95 |

**Verdict:** prefer trend **baseline** (or accurate SELL) for large winners; hit stays lower than ORB.

**Reports:** `NIFTY_TREND_STAY_LAST10D.md` · `NIFTY_ACCURATE_PROFILES_TEST.md`

---

### B3 · State-conditional (1m)

| | |
|---|---|
| **Module** | `prod_live/logic/nifty_state_conditional.py` |
| **TF** | 1m |
| **Idea** | trade a bar-state only when prior analogs hit target before stop often enough |

**State dims:** VIX bucket · auction · VWAP side · swing · time bucket  
**Memory:** prior sessions only · gates use rolling last **80** analogs  
**Risk:** stop 0.6 ATR clipped 12–25 · target **1.7×** stop · hold ≤60 bars · flat 14:45  
**Prob gate:** direction p ≥ **0.60** when present  
**VIX:** proxy from realized vol when `india_vix` missing

**baseline:** analogs≥20 · hit≥0.52 · max **3**/day  
**accurate (`n22_h54_c1`):** analogs≥22 · hit≥0.54 · max **1**/day

**Last 1 month (2026-10-19 → 2026-11-18, 22 sessions, warm 752):**

| Profile | Month N | Hit | Net | Warm N/hit/net |
|---|---:|---:|---:|---|
| baseline | 6 | 66.7% | +51.60 | 50 / 46% / +101.60 |
| **accurate** | **4** | **75.0%** | **+45.20** | 35 / 40% / +5.00 |

Accurate month exits: 3 target / 1 stop. Days with calls: 10-27 sell, 10-30 buy, (+2 more in report).

**Reports:** `NIFTY_STATE_CONDITIONAL_1M.md` · freeze/holdout notes in module header

---

## C · UI combine rule (FINAL books)

```
key = (day, side, hm)
same key → 1 UI call
tags = all satisfying desks (accuracy-first)
never drop a distinct key
```

Code: `prod_live/logic/combined_live_book.py` · `collapse_to_ui_calls` · `combine_live_rows`  
Desk order: `DESK_ACCURACY_ORDER` (P2F V11/Cap2 → P2G V12 → CHAMP_PLUS → … → P75)

---

## D · Confirm / research runners

```bash
# FINAL 3 books locked numbers
python -u prod_live/tests/confirm_final_nifty_3books.py

# Futures research
python -u prod_live/tests/research_nifty_orb30_vwap_fut.py
python -u prod_live/tests/research_nifty_trend_stay.py
python -u prod_live/tests/research_nifty_state_conditional.py
python -u prod_live/tests/research_nifty_accurate_profiles.py
```

---

## E · Quick map — “what should I watch?”

| Goal | Use |
|---|---|
| Live tickets on Calls board | **CHAMP_PLUS / crown fill** (dual proven/champion list suppressed by default) |
| Accuracy tags / desk provenance | FINAL **P2F / P2G / CHAMP_PLUS** annotate |
| Restore dual-first listing | `SUPPRESS_DUAL_LIST=0` · see `NIFTY_NO_DUAL_FIRST_1Y.md` |
| Higher-hit short ORB-style futures | **ORB accurate** (entry_ext≤5) |
| Larger winners, fewer high-hit days | **Trend baseline** (or accurate SELL) |
| Sparse high-hit 1m state trades | **State accurate** (max 1/day, ≥22 @ ≥54%) |
| Pre-open bias only | Morning `MORNING_CALIBRATED_V1` |

---

*This file is the desk inventory. Canvas companion: `nifty-fno-live-logic-map.canvas.tsx`.*
