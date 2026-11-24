# All logic — two lanes (P2F day promoted)

| Lane | Status | Role |
|---|---|---|
| **A — LIVE** | `FINALIZED` + **P2F day+Cap2 PROMOTED** | Volume stack + P2F accurate books |
| **B — HOLDING** | `HOLDING` / `not_live` | Empty fill · pre-promote expand |

Registry: `config/tags.json` (`lane` field on every tag).

---

## Lane A — LIVE

**Docs:** `FINAL_LOGIC.md` · `DESIGN.md`  
**Code:** `logic/stack.py` · `logic/agree_accurate.py` · `logic/p2f_day_live.py` · `logic/p2f_cap2_live.py` · `logic/htf_active.py`  
**Confirm volume:** `tests/confirm_final_hold_1y_match.py`  
**Confirm P2F day:** `tests/confirm_p2f_day_live_1y.py`  
**Confirm P2F Cap2:** `tests/confirm_p2f_cap2_live_1y.py`

### Volume desk

| Tag | Kind | Rule |
|---|---|---|
| `STACK_PLUS_CROWN_HTF_CAP2` | volume_desk | proven > good > champ > crown · **cap2 same side** · crown only on HTF · NSE mid OFF |

**1y golden:** 229 @ **75.11%** (`2025-10-24` → `2026-10-23`)

### Accurate — AGREE (on stack)

| Tag | Kind | Rule |
|---|---|---|
| `AGREE_15M_ANY5` | accurate_tag | 15m `GOOD_PROD2` ∩ any 5m same day+side · stamp on stack |

**1y:** on-stack tagged **54 @ 90.74%**

### Accurate — P2F day (**PROMOTED**, 1 call/day)

| Tag | Floor | 1y N @ hit |
|---|---:|---|
| `ACC100_MULTI_V11` | 100% | 86 @ 100% |
| `ACC_WIDE_P92_P2F` | 99.24% | 86 @ 100% |
| `ACC_WIDE_P90_P2F` | 95.4% | 98 @ 100% |
| `ACC_WIDE_P85_P2F` | 89.69% | 114 @ ~93% |
| `ACC_WIDE_P85B_P2F` | 88.4% | 116 @ ~93% |
| `ACC_WIDE_P80_P2F` | 84.72% | 123 @ ~90% |
| `ACC_WIDE_P75_P2F` | 82.71% | 127 @ ~89% |

Hard gates = Phase-2F floors. Soft live bar: **1y hit > 87%**.

### Accurate — P2F Cap2 (**PROMOTED**)

| Tag | Floor | 1y N @ hit |
|---|---:|---|
| `ACC100_MULTI_V5_CAP2_P2F` | 100% | 124 @ 100% |
| `ACC_WIDE_P92_CAP2_P2F` | 99.24% | 123 @ 100% |
| `ACC_WIDE_P90_CAP2_P2F` | 95.4% | 139 @ ~99% |
| `ACC_WIDE_P85_CAP2_P2F` | 89.69% | 169 @ ~91% |

### Live desk combo

| Tag | Kind |
|---|---|
| `STACK_PLUS_AGREE_15M_ANY5` | volume + AGREE stamps / extras |
| P2F day + Cap2 desks | parallel accurate listing (notify/override, never block) |

### Live tracks (volume members)

| Tag | Priority |
|---|---:|
| `PROVEN_100` | 0 |
| `GOOD_PROD2` | 1 |
| `CHAMPION` | 2 |
| `CROWN_DUAL_HTF` | 3 (needs `HTF_ACTIVE_DAY`) |

```
LIVE session algorithm
1. Score PROVEN / GOOD / CHAMP / CROWN(HTF)
2. Build STACK_PLUS_CROWN_HTF_CAP2
3. Build AGREE_15M_ANY5 → stamp on matching stack rows
4. Annotate P2F day + Cap2 LIVE books (parallel; volume unchanged)
5. Output live listing (volume + accurate book metadata)
```

App hook: `app/fno/fno_p2f_live.py` (`ENABLE_P2F_LIVE_ACCURATE=1`).

---

## Lane B — HOLDING (fill / research)

**Docs:** `HOLDING_LOGIC.md` · **`ACCURATE_LOGIC.md`**  
**Held folder:** **`holding_accurate/`**  
**Code:** `logic/accurate_desks.py` · `acc100_streams.py` · `confirm_dual_tf.py` · `empty_fill.py`  
**Confirm 3y:** `tests/confirm_accurate_desks_3y_match.py`

Lane B Cap2 / empty-fill do **not** rewrite Lane A volume. Empty fills never get `AGREE_15M_ANY5`.
### B1. Empty-day fill (volume add-on)

| Tag | accurate_tag | Rule |
|---|---|---|
| `EMPTY_FILL_FADE1030_GAP055_T35` | **null** | stack-silent + \|gap\|≥0.55 · 10:30 fade · T35 |
| `STACK_PLUS_EMPTY_FILL_GAP055_T35` | uses live AGREE only on stack rows | stack ∪ fill |

### B2. Accurate desks (100% path streams)

| Tag | accurate / holding tag | 3y | 5y | 10y | 1y→today |
|---|---|---:|---:|---:|---:|
| `PROVEN15_PLUS_CONFIRM_T30` | `CONFIRM_DUAL15_DUAL5_TIME30` on confirm rows | 49 @ 100% | — | — | — |
| `ACC100_MULTI_V1` | stream tags + confirm | 70 @ 100% | 104 @ 100% | 148 @ 96.6% | 34 @ 100% |
| `ACC100_MULTI_V2` | + V2 streams | 118 @ 100% | 171 @ 100% | 227 @ 97.8% | 47 @ 100% |
| `ACC100_MULTI_V3` | + V3 streams | 122 @ 100% | 181 @ 100% | 238 @ 97.9% | 49 @ 100% |
| `ACC100_MULTI_V4` | + V4 streams | 123 @ 100% | 182 @ 100% | 240 @ 97.9% | 50 @ 100% |
| **`ACC100_MULTI_V5`** | + dual15 / more | **141 @ 100%** | **202 @ 100%** | **273 @ 98.2%** | **54 @ 100%** |

Nested: V1 ⊂ V2 ⊂ V3 ⊂ V4 ⊂ V5. **Keep all.**

Core stream / confirm tags:

| Tag | Role |
|---|---|
| `CONFIRM_DUAL15_DUAL5_TIME30` | accurate_tag for timed 15m∩5m confirm |
| `ACC100_CROWN_BUY_AM1130_T20` | V1 crown BUY stream |
| `ACC100_GOOD_BUY_LATEMID_GAP045_T30` | V1 good BUY stream |
| (+ expand stream tags in `acc100_streams.py`) | V2–V5 recipes |

### B3. Wide volume desks (filter later)

| Tag | Floor | 3y | 1y call days / no-call (of 243) |
|---|---:|---:|---|
| `ACC_WIDE_P92` | 92 | 131 @ 99.2% | 51 / 192 |
| `ACC_WIDE_P90` | 90 | 174 @ 95.4% | 64 / 179 |
| `ACC_WIDE_P85` | 85 | 223 @ 89.7% | 85 / 158 |
| `ACC_WIDE_P85B` | 85 | 250 @ 88.4% | 97 / 146 |
| `ACC_WIDE_P80` | 80 | 301 @ 84.7% | 107 / 136 |
| `ACC_WIDE_P75` | 75 | 347 @ 82.7% | 114 / 129 |
| `ACC_WIDE_P80_CAP2` | 80 · cap2 | 525 @ 86.3% | 107 / 136 |
| `ACC_WIDE_P75_CAP2` | 75 · cap2 | 626 @ 83.4% | 114 / 129 |

---

## How they stay separate

| Concern | LIVE (A) | HOLDING (B) |
|---|---|---|
| Session output | volume stack + AGREE + **P2F day+Cap2** | Empty-fill / research |
| Accurate tag | `AGREE_15M_ANY5` **and** P2F LIVE desks | confirm / null on empty fill |
| Cap | volume = day 2 same side; P2F day = **1/day**; P2F Cap2 ≤2 | — |
| Cutover | volume final · **P2F day+Cap2 promoted** | fill still holding |

---

## Morning session context (separate — no calls)

**Docs:** `MORNING_CONTEXT_LOGIC.md` · **Tag:** `MORNING_CALIBRATED_V1` (**HELD**)  
**Code:** `app/legacy/morning_session_context.py` · job `morning_pre915_context`  

**Before 9:15:**  
- Range ATR×3.5 — **guaranteed ~96%+**  
- Bias HIGH when US+Asia agree & \|SPX\|≥1.5% — **≥70% when speaking**  
- Gap lean same gate — **not guaranteed**  
- Live news scored + veto · globals + yesterday TA  

Research: `reports/1y/MORNING_CALIBRATED_GUARANTEE.md` · `MORNING_FINAL_REVALIDATE.md`

## Quick map

```
prod_live/
├── ALL_LOGIC.md          ← you are here (both lanes)
├── FINAL_LOGIC.md        ← Lane A only
├── HOLDING_LOGIC.md      ← Lane B overview
├── ACCURATE_LOGIC.md     ← Lane B accurate desks + range tags
├── MORNING_CONTEXT_LOGIC.md  ← pre-live context (no calls)
├── holding_accurate/     ← recipes + registry (P2F day → LIVE stamps)
├── config/tags.json      ← lane + ACC_RANGE_* / ACC_BAND_*
└── logic/
    ├── stack.py / agree_accurate.py / htf_active.py  ← LIVE volume
    ├── p2f_day_live.py   ← LIVE P2F day accurate (promoted)
    ├── p2f_cap2_live.py  ← LIVE P2F Cap2 accurate (promoted)
    ├── accurate_desks.py  ← Phase-1 combined accurate API
    ├── acc100_streams.py / confirm_dual_tf.py / empty_fill.py
```
