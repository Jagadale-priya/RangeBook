# Deep research — 15m dual gate × 5m entry confirm

**Prod facts:** 15m dual `proven_100` is already live · 5m has **no** proven (only `crown_5m`).

Research only. Final / holding unchanged.

## Question

Can we build a **100% / ≥95% confirm** book whose **entry is 5m**, gated by 15m dual,
and ideally **add** calls beyond prod proven — without inventing a fake 5m proven?

## Baselines (3y)

| Book | N | Hit | Perfect | Day |
|---|---:|---:|---|---:|
| `BASE_dual15_proven` | 41 | **100.0%** | True | 6.1% |
| `BASE_dual15_any` | 150 | **84.67%** | False | 21.5% |
| `BASE_dual5_any` | 56 | **51.79%** | False | 6.2% |
| `BASE_dual5_proven` | 18 | **50.0%** | False | 1.9% |
| `BASE_crown_htf` | 300 | **74.67%** | False | 24.8% |
| `T30_gate15any_entry5any` | 11 | **100.0%** | True | 1.8% |
| `T15_gate15any_entry5any` | 10 | **100.0%** | True | 1.6% |
| `T30_gate15proven_entry_crown` | 0 | **None%** | False | 0.0% |
| `T30_gate15any_entry_crown` | 0 | **None%** | False | 0.0% |
| `D_crown_if_proven15` | 28 | **57.14%** | False | 2.2% |
| `PROVEN15_PLUS_T30_gate15any_entry5any` | 49 | **100.0%** | True | 7.3% |
| `PROVEN15_PLUS_T30_gate15any_entry_crown` | 41 | **100.0%** | True | 6.1% |
| `REF_time30_good_crown` | 12 | **75.0%** | False | 1.9% |
| `REF_agree_good_crown` | 80 | **73.75%** | False | 12.7% |

## Perfect books 3y (n≥8) — max coverage first

| Book | N | Day | Points | 1y hit/n |
|---|---:|---:|---:|---|
| `PROVEN15_PLUS_T30_gate15any_entry5any` | 49 | 7.3% | 2070.0 | 100.0% / 28 |
| `PROVEN15_PLUS_T15_gate15any_entry5any` | 48 | 7.2% | 2025.0 | 100.0% / 28 |
| `PROVEN15_PLUS_T60_gate15any_entry_crown` | 42 | 6.2% | 1812.0 | 100.0% / 25 |
| `BASE_dual15_proven` | 41 | 6.1% | 1812.0 | 100.0% / 24 |
| `BASE_pool15_proven` | 41 | 6.1% | 1812.0 | 100.0% / 24 |
| `PROVEN15_PLUS_T30_gate15champ_entry_crown` | 41 | 6.1% | 1812.0 | 100.0% / 24 |
| `PROVEN15_PLUS_T30_gate15any_entry_crown` | 41 | 6.1% | 1812.0 | 100.0% / 24 |
| `T30_gate15any_entry5any` | 11 | 1.8% | 348.0 | 100.0% / 7 |
| `T30_gate15any_entry_5mprod` | 11 | 1.8% | 348.0 | 100.0% / 7 |
| `CAP1_T30_gate15any_entry5any` | 11 | 1.8% | 348.0 | 100.0% / 7 |
| `T15_gate15any_entry5any` | 10 | 1.6% | 303.0 | 100.0% / 7 |
| `T20_gate15any_entry5any` | 10 | 1.6% | 303.0 | 100.0% / 7 |
| `T15_gate15any_entry_5mprod` | 10 | 1.6% | 303.0 | 100.0% / 7 |
| `T20_gate15any_entry_5mprod` | 10 | 1.6% | 303.0 | 100.0% / 7 |
| `T30_gate15any_entry5any_am` | 10 | 1.6% | 318.0 | 100.0% / 6 |
| `T60_gate15any_entry5any_am` | 10 | 1.6% | 318.0 | 100.0% / 6 |
| `CAP1_T15_gate15any_entry5any` | 10 | 1.6% | 303.0 | 100.0% / 7 |
| `T10_gate15any_entry5any` | 9 | 1.4% | 273.0 | 100.0% / 6 |
| `T10_gate15any_entry_5mprod` | 9 | 1.4% | 273.0 | 100.0% / 6 |
| `T15_gate15any_entry5any_am` | 9 | 1.4% | 273.0 | 100.0% / 6 |

## Both-year ≥95% (sorted perfect → n)

| Book | 1y | 3y | 6m | Nov |
|---|---|---|---|---|
| `PROVEN15_PLUS_T30_gate15any_entry5any` | 100.0%/28 P | **100.0%**/49 P | 100.0%/19 | None%/0 |
| `PROVEN15_PLUS_T15_gate15any_entry5any` | 100.0%/28 P | **100.0%**/48 P | 100.0%/19 | None%/0 |
| `PROVEN15_PLUS_T60_gate15any_entry_crown` | 100.0%/25 P | **100.0%**/42 P | 100.0%/18 | None%/0 |
| `BASE_dual15_proven` | 100.0%/24 P | **100.0%**/41 P | 100.0%/17 | None%/0 |
| `BASE_pool15_proven` | 100.0%/24 P | **100.0%**/41 P | 100.0%/17 | None%/0 |
| `PROVEN15_PLUS_T30_gate15champ_entry_crown` | 100.0%/24 P | **100.0%**/41 P | 100.0%/17 | None%/0 |
| `PROVEN15_PLUS_T30_gate15any_entry_crown` | 100.0%/24 P | **100.0%**/41 P | 100.0%/17 | None%/0 |
| `T30_gate15any_entry5any` | 100.0%/7 P | **100.0%**/11 P | 100.0%/5 | None%/0 |
| `T30_gate15any_entry_5mprod` | 100.0%/7 P | **100.0%**/11 P | 100.0%/5 | None%/0 |
| `CAP1_T30_gate15any_entry5any` | 100.0%/7 P | **100.0%**/11 P | 100.0%/5 | None%/0 |
| `T30_gate15any_entry5any_am` | 100.0%/6 P | **100.0%**/10 P | 100.0%/4 | None%/0 |
| `T60_gate15any_entry5any_am` | 100.0%/6 P | **100.0%**/10 P | 100.0%/4 | None%/0 |
| `T15_gate15any_entry5any` | 100.0%/7 P | **100.0%**/10 P | 100.0%/5 | None%/0 |
| `T20_gate15any_entry5any` | 100.0%/7 P | **100.0%**/10 P | 100.0%/5 | None%/0 |
| `T15_gate15any_entry_5mprod` | 100.0%/7 P | **100.0%**/10 P | 100.0%/5 | None%/0 |
| `T20_gate15any_entry_5mprod` | 100.0%/7 P | **100.0%**/10 P | 100.0%/5 | None%/0 |
| `CAP1_T15_gate15any_entry5any` | 100.0%/7 P | **100.0%**/10 P | 100.0%/5 | None%/0 |
| `T10_gate15any_entry5any` | 100.0%/6 P | **100.0%**/9 P | 100.0%/4 | None%/0 |
| `T10_gate15any_entry_5mprod` | 100.0%/6 P | **100.0%**/9 P | 100.0%/4 | None%/0 |
| `T15_gate15any_entry5any_am` | 100.0%/6 P | **100.0%**/9 P | 100.0%/4 | None%/0 |

## Expand beyond prod proven (PROVEN15_PLUS_*)

- Best add-on combo: `PROVEN15_PLUS_T30_gate15any_entry5any` → **100.0%** n=49 perfect=True day=7.3%
- `BASE_dual15_proven`: n=41 hit=100.0% perfect=True pts=1812.0
- `PROVEN15_PLUS_T30_gate15any_entry5any`: n=49 hit=100.0% perfect=True pts=2070.0
- `PROVEN15_PLUS_T15_gate15any_entry5any`: n=48 hit=100.0% perfect=True pts=2025.0
- `PROVEN15_PLUS_T30_gate15any_entry_crown`: n=41 hit=100.0% perfect=True pts=1812.0
- `PROVEN15_PLUS_T60_gate15any_entry_crown`: n=42 hit=100.0% perfect=True pts=1812.0

## 1y monthly (selected)

### `PROVEN15_PLUS_T30_gate15any_entry5any`

| Month | N | Hit | Perfect | Pts |
|---|---:|---:|---|---:|
| 2025-12 | 3 | 100.0% | True | 115.0 |
| 2026-01 | 2 | 100.0% | True | 95.0 |
| 2026-02 | 3 | 100.0% | True | 108.0 |
| 2026-04 | 1 | 100.0% | True | 46.0 |
| 2026-05 | 1 | 100.0% | True | 30.0 |
| 2026-06 | 2 | 100.0% | True | 115.0 |
| 2026-07 | 1 | 100.0% | True | 34.0 |
| 2026-08 | 3 | 100.0% | True | 98.0 |
| 2026-09 | 5 | 100.0% | True | 197.0 |
| 2026-10 | 7 | 100.0% | True | 411.0 |

### `PROVEN15_PLUS_T15_gate15any_entry5any`

| Month | N | Hit | Perfect | Pts |
|---|---:|---:|---|---:|
| 2025-12 | 3 | 100.0% | True | 115.0 |
| 2026-01 | 2 | 100.0% | True | 95.0 |
| 2026-02 | 3 | 100.0% | True | 108.0 |
| 2026-04 | 1 | 100.0% | True | 46.0 |
| 2026-05 | 1 | 100.0% | True | 30.0 |
| 2026-06 | 2 | 100.0% | True | 115.0 |
| 2026-07 | 1 | 100.0% | True | 34.0 |
| 2026-08 | 3 | 100.0% | True | 98.0 |
| 2026-09 | 5 | 100.0% | True | 197.0 |
| 2026-10 | 7 | 100.0% | True | 411.0 |

### `PROVEN15_PLUS_T60_gate15any_entry_crown`

| Month | N | Hit | Perfect | Pts |
|---|---:|---:|---|---:|
| 2025-12 | 3 | 100.0% | True | 115.0 |
| 2026-01 | 1 | 100.0% | True | 65.0 |
| 2026-02 | 2 | 100.0% | True | 75.0 |
| 2026-04 | 1 | 100.0% | True | 46.0 |
| 2026-06 | 2 | 100.0% | True | 115.0 |
| 2026-07 | 2 | 100.0% | True | 34.0 |
| 2026-08 | 3 | 100.0% | True | 98.0 |
| 2026-09 | 4 | 100.0% | True | 167.0 |
| 2026-10 | 7 | 100.0% | True | 411.0 |

### `BASE_dual15_proven`

| Month | N | Hit | Perfect | Pts |
|---|---:|---:|---|---:|
| 2025-12 | 3 | 100.0% | True | 115.0 |
| 2026-01 | 1 | 100.0% | True | 65.0 |
| 2026-02 | 2 | 100.0% | True | 75.0 |
| 2026-04 | 1 | 100.0% | True | 46.0 |
| 2026-06 | 2 | 100.0% | True | 115.0 |
| 2026-07 | 1 | 100.0% | True | 34.0 |
| 2026-08 | 3 | 100.0% | True | 98.0 |
| 2026-09 | 4 | 100.0% | True | 167.0 |
| 2026-10 | 7 | 100.0% | True | 411.0 |

### `BASE_pool15_proven`

| Month | N | Hit | Perfect | Pts |
|---|---:|---:|---|---:|
| 2025-12 | 3 | 100.0% | True | 115.0 |
| 2026-01 | 1 | 100.0% | True | 65.0 |
| 2026-02 | 2 | 100.0% | True | 75.0 |
| 2026-04 | 1 | 100.0% | True | 46.0 |
| 2026-06 | 2 | 100.0% | True | 115.0 |
| 2026-07 | 1 | 100.0% | True | 34.0 |
| 2026-08 | 3 | 100.0% | True | 98.0 |
| 2026-09 | 4 | 100.0% | True | 167.0 |
| 2026-10 | 7 | 100.0% | True | 411.0 |

### `PROVEN15_PLUS_T30_gate15champ_entry_crown`

| Month | N | Hit | Perfect | Pts |
|---|---:|---:|---|---:|
| 2025-12 | 3 | 100.0% | True | 115.0 |
| 2026-01 | 1 | 100.0% | True | 65.0 |
| 2026-02 | 2 | 100.0% | True | 75.0 |
| 2026-04 | 1 | 100.0% | True | 46.0 |
| 2026-06 | 2 | 100.0% | True | 115.0 |
| 2026-07 | 1 | 100.0% | True | 34.0 |
| 2026-08 | 3 | 100.0% | True | 98.0 |
| 2026-09 | 4 | 100.0% | True | 167.0 |
| 2026-10 | 7 | 100.0% | True | 411.0 |

### `PROVEN15_PLUS_T30_gate15any_entry_crown`

| Month | N | Hit | Perfect | Pts |
|---|---:|---:|---|---:|
| 2025-12 | 3 | 100.0% | True | 115.0 |
| 2026-01 | 1 | 100.0% | True | 65.0 |
| 2026-02 | 2 | 100.0% | True | 75.0 |
| 2026-04 | 1 | 100.0% | True | 46.0 |
| 2026-06 | 2 | 100.0% | True | 115.0 |
| 2026-07 | 1 | 100.0% | True | 34.0 |
| 2026-08 | 3 | 100.0% | True | 98.0 |
| 2026-09 | 4 | 100.0% | True | 167.0 |
| 2026-10 | 7 | 100.0% | True | 411.0 |

### `T30_gate15any_entry5any`

| Month | N | Hit | Perfect | Pts |
|---|---:|---:|---|---:|
| 2026-01 | 1 | 100.0% | True | 30.0 |
| 2026-02 | 1 | 100.0% | True | 33.0 |
| 2026-05 | 1 | 100.0% | True | 30.0 |
| 2026-09 | 4 | 100.0% | True | 120.0 |

## Nov 2026 (n>0)

| Book | N | Hit | Perfect |
|---|---:|---:|---|
| `BASE_crown_all` | 1 | **100.0%** | True |

## Recommended research logic

### A — Pure 5m-entry confirm (thin)

**Tag:** `CONFIRM_DUAL15_DUAL5_TIME30` (`T30_gate15any_entry5any`)

- 3y: **11 @ 100%** · 1y: 7 @ 100% · Nov: 0
- Gate = 15m dual any (proven∪champ) · Entry = 5m dual replay · `|Δhm|≤30`

Of the 11: **3** fall on proven days (overlap) · **8** are new days.

### B — Expand prod proven with those 8 (best n @ 100%)

**Tag:** `PROVEN15_PLUS_CONFIRM_T30` (`PROVEN15_PLUS_T30_gate15any_entry5any`)

- 3y: **49 @ 100%** (41 proven + 8 timed 5m confirms) · +258 pts vs proven alone
- 1y monthly: every listed month perfect
- Hybrid desk: proven keeps **15m** tickets; add-ons are **5m** tickets

```
1. Keep prod proven_100 as-is (15m dual)
2. Also score dual packs on 5m OR-break (research replay — not a 5m proven pack)
3. IF 15m dual any ∩ 5m dual same side AND |hm15−hm5|≤30
      AND day has no proven_100 call:
         emit CONFIRM on 5m ticket
4. Crown timed-agree @ ±30m with dual15 = 0 calls — do not use for confirm
```

Code: `prod_live/logic/confirm_dual_tf.py`

## Verdict

1. **Yes — deep research confirms a 100% path**, but it does **not** create a 5m proven model.
2. **Prod 15m `proven_100` stays the core** (41/3y). Nothing replaces it.
3. **Best expand:** proven ∪ timed dual5 confirm → **49 @ 100%** (+8 calls, all wins).
4. **Pure 5m confirm** alone is only **11 @ 100%** — accurate tag / parallel, not volume.
5. **Crown cannot fill the 5m proven hole** for timed confirm (0 overlaps at ±30m; day-side-only crown∩proven = 57%).
6. Nov 1–13: no dual×dual confirms (only 1 crown_all win unrelated).
7. **Not live** until explicit promote from RESEARCH → HOLDING/FINALIZED.

Elapsed 2.2s · `CONFIRM_DUAL_TF_DEEP.md`
