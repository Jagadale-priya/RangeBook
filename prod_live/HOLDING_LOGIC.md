# Holding logic — Lane B

**Status:** Empty-fill / pre-promote expand remain `HOLDING` / `not_live`.  
**Promoted to LIVE:** Phase-2F **day** + **Cap2** desks — `FINAL_LOGIC.md` · `logic/p2f_day_live.py` · `logic/p2f_cap2_live.py`.  
**Lane A LIVE volume** (unchanged): `STACK_PLUS_CROWN_HTF_CAP2` + `AGREE_15M_ANY5`.  
**Master map:** `ALL_LOGIC.md`

This lane still holds: empty-day fill · Phase-1 nested copies used as seeds.  
Holding tags use `lane=HOLDING` (never overwrite live AGREE / P2F LIVE stamps).

> **Keep all ACC100 desks:** `V1` ⊂ `V2` ⊂ `V3` ⊂ `V4` ⊂ `V5`. Do not discard earlier versions.

---

## Holding desk name

`STACK_PLUS_EMPTY_FILL_GAP055_T35`  
(= frozen `STACK_PLUS_CROWN_HTF_CAP2` + holding empty fill)

Accurate channel stays exactly:

`AGREE_15M_ANY5` (stamp only — never invent OR / never stamp structure fills)

Desk combo while holding:

`STACK_PLUS_EMPTY_FILL_GAP055_T35` + `AGREE_15M_ANY5` stamps

---

## Layers (same as final, plus fill)

### 1. Volume stack — **FINALIZED** (unchanged)

`STACK_PLUS_CROWN_HTF_CAP2`

1. Collect `PROVEN_100`, `GOOD_PROD2`, `CHAMPION`, `CROWN_DUAL_HTF`
2. Priority: **proven > good > champ > crown**
3. Day cap **2**, **same side** only
4. Crown only on `HTF_ACTIVE_DAY`
5. NSE mid **OFF**

### 2. Accurate tag — **FINALIZED** (unchanged)

`AGREE_15M_ANY5`

1. Issued 15m `GOOD_PROD2` ∩ any 5m (proven ∪ champ ∪ crown_htf) same **day + side**
2. Entry = **5m** with highest `p_t1`
3. Stamp `accurate_tag=AGREE_15M_ANY5` only on **exact** stack row match `(day, side, hm)`
4. Optional agree extra if not already in stack

**Rules for accuracy integrity**

- Empty fills are **never** stamped `AGREE_15M_ANY5`
- Empty fills set `accurate=false`, `holding_tag=EMPTY_FILL_FADE1030_GAP055_T35`
- Agree extras remain the only additive accurate parallel

### 3. Empty fill — **HOLDING** (new)

`EMPTY_FILL_FADE1030_GAP055_T35`

1. Day must be **stack-silent** (0 calls from volume stack after cap2)
2. `|gap_pct| ≥ 0.55` where `gap_pct = (open − prior_close) / prior_close × 100`
3. Entry at **10:30** IST (5m close)
4. Side = **fade the open** (close ≥ open → SELL, else BUY)
5. Risk **T35 / S35** (V2 — improved vs T25 on Nov + 3y points)
6. Max **1** fill per empty day; merge with stack under same-side cap2
7. Track: `empty_fade_gap055_t35` · priority **5** (after crown)

---

## Session algorithm (holding)

```
1. Score PROVEN / GOOD / CHAMP / CROWN(HTF)
2. Build STACK_PLUS_CROWN_HTF_CAP2 (cap2 same side)
3. Build AGREE_15M_ANY5 keys; stamp accurate_tag on matching stack rows
4. IF stack has 0 calls today:
      IF |gap| >= 0.55:
         emit EMPTY_FILL @ 10:30 fade T35
         accurate_tag = null
5. Merge stack + fill (cap2); agree extras additive as today
6. Output holding desk listing
```

---

## Confirmation snapshot (research)

| Book | Window | N | Hit | Points | Status |
|---|---|---:|---:|---:|---|
| Stack alone (final) | 1y | 229 | 75.11% | 3404 | FINALIZED |
| Agree tagged on stack | 1y | 54 | 90.74% | — | FINALIZED |
| Stack + fill T25 (V1) | 3y | 652 | 75.92% | 9638 | superseded |
| **Stack + fill T35 (V2 holding)** | 3y | 652 | 75.46% | **9658** | **HOLDING** |
| **V2** | 1y | ~250 | ~74.8–75.6% | ~3719–3729 | HOLDING |
| **V2 Nov 2026** | Nov1–14 | 6 | **83.3%** | 122 | overlay |

Oct 2026: fill did not fire (no empty+|gap| days); stack alone **29 @ 100% · 785 pts**.

---

### 4. 100% confirm expand — **HOLDING** (new)

`PROVEN15_PLUS_CONFIRM_T30`  
(= prod `PROVEN_100` ∪ timed dual15∩dual5 confirms on non-proven days)

1. Keep live **15m dual proven** as-is (already FINALIZED in stack)
2. Research-only: replay dual packs on **5m** OR-break (not a 5m proven pack)
3. Confirm when 15m dual any ∩ 5m dual same side and `|hm15−hm5| ≤ 30`
4. Add confirm **only if that day has no proven_100**
5. Confirm entry / P&L = **5m** ticket · tag `CONFIRM_DUAL15_DUAL5_TIME30`

**3y:** 49 @ **100%** · 2070 pts (41 proven + 8 confirms)  
**1y:** 28 @ **100%** · Nov: 0 fires

Pure confirm alone (no proven merge): 11 @ 100% (3 overlap proven days + 8 new).

Crown timed-agree with dual15 @ ±30m = **0** — do not use crown as that confirm entry.

### 5. Multi-stream 100% desk — **HOLDING** (deeper expand)

`ACC100_MULTI_V1` (= proven ∪ confirm T30 ∪ crown BUY am ∪ good BUY late-mid)

| Stream | Rule | Risk | 3y n |
|---|---|---|---:|
| Proven | prod 15m dual proven | native | 41 |
| Confirm | dual15∩dual5 ±30m, non-proven days | 5m dual | +8 |
| Crown | first **BUY** crown · 09:15–11:30 | **T20 only** | +12 |
| Good | first **BUY** good · 10:30–14:00 · `|gap|≥0.45` | **T30 fixed path** | +9 |
| **Desk** | day-dedupe in that priority | — | **70 @ 100%** |

**Fragility (must keep):**
- Crown add-on breaks at T25 (~83%) — lock **T20**
- Good add-on fails on native prod2 brackets — lock **fixed T30 path**
- Good gap 0.35 fails — lock **|gap|≥0.45**

**1y:** 31 @ 100% · Nov: crown stream fired (2026-11-06 BUY)

### 6. Multi-stream 100% desk V2 — **HOLDING** (expand beyond V1)

`ACC100_MULTI_V2` = **V1 ∪ 10 more path-true streams**

| | 3y | 1y | Nov |
|---|---:|---:|---:|
| V1 (locked) | 70 @ 100% | 31 @ 100% | — |
| **V2** | **112 @ 100%** | **46 @ 100%** | 1 @ 100% |

**+42 calls** vs V1 · ~3861 pts · report `ACC100_EXPAND_FROM_V1.md`

Expand streams (day-deduped onto V1): good T40 mid gap040 · crown T20 pm HTF gap-down · crown T20 SELL p62 pm · **champ BUY p≥0.70 am** · good T30 p57 am · crown T35 am HTF · crown T40 SELL am gap · good T35 sell/buy mid · crown T20 p60 am first.

Each stream locks its own path risk — do not mix brackets.

**Long-horizon check (V2):** `reports/1y/ACC100_MULTI_V2_5Y_10Y.md`

| Window | N | Hit | Perfect |
|---|---:|---:|---|
| 3y | 118 | 100% | yes |
| 5y | 171 | 100% | yes |
| 10y | 227 | **97.8%** | no |

Crown streams only from ~2024-05 (pool). 10y is not perfect — review before promote.

### 7. Multi-stream 100% desk V3 — **HOLDING** (keep with V1+V2)

`ACC100_MULTI_V3` = **V2 ∪ 5 more path-true streams** (3y+5y perfect gate)

| | 3y | 5y | 1y |
|---|---:|---:|---:|
| V2 | 118 @ 100% | 171 @ 100% | — |
| **V3** | **122 @ 100%** | **181 @ 100%** | 49 @ 100% |

**+4 / +10** vs V2 · report `ACC100_EXPAND_FROM_V2.md`

### 8. Multi-stream 100% desk V4/V5 + wide ladder — **HOLDING** (keep all)

| Desk | Floor | Mode | 3y | 5y |
|---|---:|---|---:|---:|
| V3 | 100 | day | 122 @ 100% | 181 @ 100% |
| V4 | 100 | day | 123 @ 100% | 182 @ 100% |
| **V5** | **100** | day | **141 @ 100%** | **202 @ 100%** |
| `ACC_WIDE_P92` | 92 | day | 131 @ 99.2% | 199 @ 97.5% |
| `ACC_WIDE_P90` | 90 | day | 174 @ 95.4% | 259 @ 95.0% |
| `ACC_WIDE_P85` | 85 | day | 223 @ 89.7% | 326 @ 89.9% |
| **`P85B`** | 85 | day | **250 @ 88.4%** | 364 @ 88.2% |
| **`P80`** | 80 | day | **301 @ 84.7%** | 442 @ 83.5% |
| **`P75`** | 75 | day | **347 @ 82.7%** | 514 @ 81.7% |
| **`P80_CAP2`** | 80 | cap2 | **525 @ 86.3%** | 770 @ 84.9% |
| **`P75_CAP2`** | 75 | cap2 | **626 @ 83.4%** | 933 @ 82.2% |

Nested day ladder: V1⊂…⊂V5 and P92⊂…⊂P75. Cap2 desks branch from P85.  
Reports: `ACC_MULTI_TIER_EXPAND.md` · `ACC_MULTI_TIER_EXPAND2.md` · **`ACC_ALL_DESKS_10Y.md`**

### 9. Long-horizon hold check (10y) — **HOLDING keep all**

| Desk | 3y | 5y | 10y |
|---|---:|---:|---:|
| V1 | 70 @ 100% | 104 @ 100% | 148 @ 96.6% |
| V2 | 118 @ 100% | 171 @ 100% | 227 @ 97.8% |
| V3 | 122 @ 100% | 181 @ 100% | 238 @ 97.9% |
| V4 | 123 @ 100% | 182 @ 100% | 240 @ 97.9% |
| **V5** | **141 @ 100%** | **202 @ 100%** | **273 @ 98.2%** |
| P92 | 131 @ 99.2% | 199 @ 97.5% | 292 @ 91.1% |
| P90 | 174 @ 95.4% | 259 @ 95.0% | 405 @ 89.9% |
| P85 | 223 @ 89.7% | 326 @ 89.9% | 525 @ 84.0% |
| P85B | 250 @ 88.4% | 364 @ 88.2% | 598 @ 81.1% |
| P80 | 301 @ 84.7% | 442 @ 83.5% | 723 @ 76.6% |
| P75 | 347 @ 82.7% | 514 @ 81.7% | 833 @ 75.2% |
| P80_CAP2 | 525 @ 86.3% | 770 @ 84.9% | 1278 @ 77.7% |
| P75_CAP2 | 626 @ 83.4% | 933 @ 82.2% | 1510 @ 75.5% |

V1–V5 share the same **5** old 10y losses (pre-window proven/confirm). Crown denser from ~2024-05.

### 10. Last-1y to today — **HOLDING**

Window `2025-11-14` → `2026-11-14` · report **`ACC_ALL_DESKS_1Y_TODAY.md`**

| Desk | N | Hit |
|---|---:|---:|
| V5 | 54 | **100%** |
| P92 / P90 | 52 / 65 | **100%** |
| P85 | 86 | 94.2% |
| P75 | 116 | 88.8% |
| P75_CAP2 | 218 | 90.4% |

---

## Tags

| Tag | Kind | Status |
|---|---|---|
| `STACK_PLUS_CROWN_HTF_CAP2` | volume_desk | FINALIZED |
| `AGREE_15M_ANY5` | accurate_tag | FINALIZED |
| `EMPTY_FILL_FADE1030_GAP055_T35` | empty_fill | **HOLDING** |
| `STACK_PLUS_EMPTY_FILL_GAP055_T35` | holding_desk | **HOLDING** |
| `CONFIRM_DUAL15_DUAL5_TIME30` | confirm_accurate | **HOLDING** |
| `PROVEN15_PLUS_CONFIRM_T30` | holding_accurate_desk | **HOLDING** |
| `ACC100_CROWN_BUY_AM1130_T20` | acc100_stream | **HOLDING** |
| `ACC100_GOOD_BUY_LATEMID_GAP045_T30` | acc100_stream | **HOLDING** |
| `ACC100_MULTI_V1` | holding_accurate_desk | **HOLDING keep** |
| `ACC100_MULTI_V2` | holding_accurate_desk | **HOLDING keep** |
| `ACC100_MULTI_V3` | holding_accurate_desk | **HOLDING keep** |
| `ACC100_MULTI_V4` | holding_accurate_desk | **HOLDING keep** |
| `ACC100_MULTI_V5` | holding_accurate_desk | **HOLDING keep** |
| `ACC_WIDE_P92`…`P75` | holding_wide_desk | **HOLDING keep** |
| `ACC_WIDE_P80_CAP2` / `P75_CAP2` | holding_wide_desk | **HOLDING keep** |

---

## Accurate hold folder (Phase-1 + Phase-2c)

**`holding_accurate/`** — both layers in one place (not live):

- Phase-1 **LOCKED** → `logic/accurate_desks.py` (indexed under `holding_accurate/phase1/`)
- Phase-2c **HELD** → `holding_accurate/recipes.json` + `phase2c/` (V8 / P*_P2C / CAP2_P2C)
- More research → Phase-2d (`research_acc_phase2d_keep_going.py`)

See `ACCURATE_LOGIC.md` · `holding_accurate/LOGIC.md`.

## Code map

| Module | Role |
|---|---|
| `logic/stack.py` | Cap2 union, agree stamp, agree merge (**unchanged**) |
| `logic/agree_accurate.py` | Agree keys (**unchanged**) |
| `logic/htf_active.py` | HTF gate (**unchanged**) |
| `logic/empty_fill.py` | Holding empty-fill builders + merge |
| `logic/confirm_dual_tf.py` | Holding 100% dual-TF confirm + proven-plus merge |
| `logic/acc100_streams.py` | ACC100_MULTI_V1 stream filters + merge |
| `logic/accurate_desks.py` | Phase-1 combined accurate desks API |
| `holding_accurate/` | Phase-1 + Phase-2c held together |
| `config/tags.json` | Registry (+ HOLDING entries) |
| `HOLDING_DESIGN.md` | Diagrams |

---

## Guardrails

1. **Not live** until explicit promote from HOLDING → FINALIZED
2. Do not relax champ regimes / soft dual / force OR into this desk
3. Accurate tag path must stay 15m∩5m only
4. Empty fill must stay stack-silent + gap gate
5. Golden 1y stack confirm script still owns the frozen volume desk

---

## Bottom line

- **Final** books stay as in `FINAL_LOGIC.md`
- **Holding** adds: silent-day fill (T35) + **ACC100 V1–V5** (100%) + **wide P92→P75 + cap2** (filter later)
- Expand streams are risk/gap/HTF fragile — keep recipe locks
- Promote only after shadow period + re-confirm 1y stack + agree stamps
