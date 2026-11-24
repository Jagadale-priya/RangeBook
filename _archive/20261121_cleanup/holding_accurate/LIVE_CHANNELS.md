# Live channels — FINAL NIFTY F&O (HELD)

**Calls board (lists BUY/SELL):** **CHAMP_PLUS** `CHAMP_PLUS_T30SL30_CAP6` (±30 · Cap6)  
**Flag:** `SUPPRESS_DUAL_LIST=1` — dual proven/champion does **not** list.

**Annotate / UI merge (FINAL 3 books):**

1. **P2F** — day + Cap2 accurate desks  
2. **P2G 10m** — day desks (`*_P2G_10M`)  
3. **CHAMP_PLUS** — `CHAMP_PLUS_T30SL30_CAP6`

**Excluded from Calls listing:** dual proven_100/champion · `STACK_PLUS_CROWN_HTF_CAP2` · `AGREE_15M_ANY5` · ExtraTrees single  
**Restore dual-first:** `SUPPRESS_DUAL_LIST=0`

Full desk logic: **`DESKS.md`** · finalize: **`FINAL_LOGIC.md`** · combine: **`logic/combined_live_book.py`**

## UI multi-tag rule

```
same (day, side, hm) → 1 UI call
tags = all satisfying desks (accuracy-first)
never block a distinct entry
```

## P2F day

| Priority | accurate_tag | accuracy_tag | Floor |
|---:|---|---|---:|
| 1 | `ACC100_MULTI_V11` | `ACC_RANGE_98_100` | 100 |
| 2 | `ACC_WIDE_P92_P2F` | `ACC_RANGE_91_100` | 99.24 |
| 3 | `ACC_WIDE_P90_P2F` | `ACC_RANGE_89_96` | 95.4 |
| 4 | `ACC_WIDE_P85_P2F` | `ACC_RANGE_84_90` | 89.69 |
| 5 | `ACC_WIDE_P85B_P2F` | `ACC_RANGE_81_89` | 88.4 |
| 6 | `ACC_WIDE_P80_P2F` | `ACC_RANGE_76_85` | 84.72 |
| 7 | `ACC_WIDE_P75_P2F` | `ACC_RANGE_75_83` | 82.71 |

## P2F Cap2

| Priority | accurate_tag | accuracy_tag | Floor |
|---:|---|---|---:|
| 1 | `ACC100_MULTI_V5_CAP2_P2F` | `ACC_RANGE_98_100` | 100 |
| 2 | `ACC_WIDE_P92_CAP2_P2F` | `ACC_RANGE_91_100` | 99.24 |
| 3 | `ACC_WIDE_P90_CAP2_P2F` | `ACC_RANGE_89_96` | 95.4 |
| 4 | `ACC_WIDE_P85_CAP2_P2F` | `ACC_RANGE_84_90` | 89.69 |

## P2G 10m (measured ranges)

| Priority | accurate_tag | accuracy_tag | Lo–Hi | 5y OK |
|---:|---|---|---|---|
| 1 | `ACC100_MULTI_V12_P2G_10M` | `ACC_RANGE_94_100` | 94.51–100 | N |
| 2 | `ACC_WIDE_P90_P2G_10M` | `ACC_RANGE_92_100` | 92.92–100 | N |
| 3 | `ACC_WIDE_P85B_P2G_10M` | `ACC_RANGE_88_95` | 88.41–94.23 | Y |
| 4 | `ACC_WIDE_P85_P2G_10M` | `ACC_RANGE_86_97` | 86.17–96.72 | Y |
| 5 | `ACC_WIDE_P92_P2G_10M` | `ACC_RANGE_83_100` | 83.08–100 | N |
| 6 | `ACC_WIDE_P80_P2G_10M` | `ACC_RANGE_81_85` | 81.37–84.81 | N |
| 7 | `ACC_WIDE_P75_P2G_10M` | `ACC_RANGE_81_84` | 81.46–83.49 | N |

## CHAMP_PLUS

| accurate_tag | accuracy_tag | Lo–Hi | Cap |
|---|---|---|---|
| `CHAMP_PLUS_T30SL30_CAP6` | `ACC_RANGE_93_100` | 93.19–99.61 | 6 same-side |

Confirm: `python -u prod_live/tests/confirm_final_nifty_3books.py`
