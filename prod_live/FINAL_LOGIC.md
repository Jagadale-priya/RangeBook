# Finalized logic — Lane A LIVE (prod sessions)

## Morning (before 9:15) — LIVE

**Tag:** `MORNING_CALIBRATED_V1` · job `morning_pre915_context` · UI Morning tab  
**Inputs:** live news + global overnight + prior-day TA (no cash open)  
**Guaranteed:** expected high/low ~96%+ · bias ≥70% when HIGH (US+Asia agree & |SPX|≥1.5%)  
**Gap:** lean only (not guaranteed) · **No BUY/SELL**  
Doc: `MORNING_CONTEXT_LOGIC.md`

---

## NIFTY F&O — FINAL (HELD)

**Status:** `HELD` · **Calls board:** CHAMP_PLUS ticket-fill  
**Flag:** `SUPPRESS_DUAL_LIST=1` (default) — dual proven/champion scores/annotates but **does not list**.  
**Measured live replay:** 1y board **377 @ 99.2%** · Nov MTD **14 @ 90%** settled — `reports/1y/NIFTY_LIVE_LOGIC_1Y_AND_MONTH.md`

**Nothing else may emit NIFTY F&O BUY/SELL on the Calls board.**  
Excluded: dual proven_100/champion listing · `STACK_PLUS_CROWN_HTF_CAP2` · `AGREE_15M_ANY5` · ExtraTrees single.

| # | Book | accurate_tag family | Brackets | Mode |
|---:|---|---|---|---|
| 1 | **P2F** | `ACC100_MULTI_V11` … `ACC_WIDE_P75_P2F` (+ Cap2) | ±30 | annotate / UI merge |
| 2 | **P2G 10m** | `ACC100_MULTI_V12_P2G_10M` … `ACC_WIDE_P75_P2G_10M` | ±30 | annotate / UI merge |
| 3 | **CHAMP_PLUS** | `CHAMP_PLUS_T30SL30_CAP6` | ±30 | cap6 · **live Calls ticket-fill** |

### UI combine (no blocked calls)

- Key = `(day, side, hm)`
- Same key from multiple desks → **1 UI call**
- Merge **all** tags; **highest-accuracy desk first** (`accurate_tag` + `accuracy_tag`)
- Distinct keys are **never** dropped

Code: `logic/combined_live_book.py` · `collapse_to_ui_calls` · `combine_live_rows`

### Desk priority (high → low)

See `DESK_ACCURACY_ORDER` in `combined_live_book.py`  
(P2F V11 / Cap2 V5 → P2G V12 → CHAMP_PLUS → … → P75 ladders)

### Accuracy tags (must cover measured ranges)

**P2F** (unchanged promoted ranges):

| accurate_tag | accuracy_tag |
|---|---|
| `ACC100_MULTI_V11` | `ACC_RANGE_98_100` |
| `ACC_WIDE_P92_P2F` | `ACC_RANGE_91_100` |
| `ACC_WIDE_P90_P2F` | `ACC_RANGE_89_96` |
| `ACC_WIDE_P85_P2F` | `ACC_RANGE_84_90` |
| `ACC_WIDE_P85B_P2F` | `ACC_RANGE_81_89` |
| `ACC_WIDE_P80_P2F` | `ACC_RANGE_76_85` |
| `ACC_WIDE_P75_P2F` | `ACC_RANGE_75_83` |
| Cap2 twins | same ranges as day family |

**P2G 10m** (measured 1y·3y·5y·extra_2y):

| accurate_tag | accuracy_tag | Lo–Hi | 5y OK |
|---|---|---|---|
| `ACC100_MULTI_V12_P2G_10M` | `ACC_RANGE_94_100` | 94.51–100 | N |
| `ACC_WIDE_P92_P2G_10M` | `ACC_RANGE_83_100` | 83.08–100 | N |
| `ACC_WIDE_P90_P2G_10M` | `ACC_RANGE_92_100` | 92.92–100 | N |
| `ACC_WIDE_P85_P2G_10M` | `ACC_RANGE_86_97` | 86.17–96.72 | Y |
| `ACC_WIDE_P85B_P2G_10M` | `ACC_RANGE_88_95` | 88.41–94.23 | Y |
| `ACC_WIDE_P80_P2G_10M` | `ACC_RANGE_81_85` | 81.37–84.81 | N |
| `ACC_WIDE_P75_P2G_10M` | `ACC_RANGE_81_84` | 81.46–83.49 | N |

**CHAMP_PLUS:**

| accurate_tag | accuracy_tag | Lo–Hi (5y→3y) |
|---|---|---|
| `CHAMP_PLUS_T30SL30_CAP6` | `ACC_RANGE_93_100` | 93.19–99.61 |

### Locked golden numbers

| Book | Window | N @ hit |
|---|---|---|
| CHAMP_PLUS Cap6 (causal=live) | 1y | **467 @ 75.16%** |
| CHAMP_PLUS Cap6 (causal=live) | 1m candles | **24 @ 79.17%** |
| P2G desks | 5y | see `reports/5y/ACC_PHASE2G_10M_5Y.md` |
| P2F day/cap2 | 1y | see `P2F_*_LIVE_1Y_CONFIRM` |

### Confirm (exact N + hit must match)

```bash
python -u prod_live/tests/confirm_final_nifty_3books.py
```

Also: `confirm_p2f_day_live_1y.py` · `confirm_p2f_cap2_live_1y.py`

### Code map

| Module | Role |
|---|---|
| `logic/p2f_day_live.py` | P2F day LIVE |
| `logic/p2f_cap2_live.py` | P2F Cap2 LIVE |
| `logic/p2g_10m_live.py` | P2G 10m LIVE stamps |
| `logic/champ_plus_live.py` | CHAMP_PLUS LIVE stamps |
| `logic/combined_live_book.py` | 3-book combine · no block |
| `adapters/live_session_final.py` | Session annotate |

---

## Cutover

NIFTY F&O session annotate uses `final_nifty_fno` snapshot (not volume-primary).  
Flags / loaders: `prod_live.paths` · branch notes in `BRANCH.md`.
