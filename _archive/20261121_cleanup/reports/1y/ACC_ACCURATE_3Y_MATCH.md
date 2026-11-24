# Accurate desks — 3y match vs research

**Logic file:** `logic/accurate_desks.py` (Lane B HOLDING — separate from LIVE)
**Window:** `2023-11-14` → `2026-11-13`
**Lock:** `ACC_ALL_DESKS_10Y.md` · hit tol ±0.05

## Verdict: **PASS**

## Tags by accuracy range (3y→10y research)

- `ACC_RANGE_100_100` → `PROVEN15_PLUS_CONFIRM_T30`
- `ACC_RANGE_75_83` → `ACC_WIDE_P75`
- `ACC_RANGE_75_84` → `ACC_WIDE_P75_CAP2`
- `ACC_RANGE_76_85` → `ACC_WIDE_P80`
- `ACC_RANGE_77_87` → `ACC_WIDE_P80_CAP2`
- `ACC_RANGE_81_89` → `ACC_WIDE_P85B`
- `ACC_RANGE_84_90` → `ACC_WIDE_P85`
- `ACC_RANGE_89_96` → `ACC_WIDE_P90`
- `ACC_RANGE_91_100` → `ACC_WIDE_P92`
- `ACC_RANGE_96_100` → `ACC100_MULTI_V1`
- `ACC_RANGE_97_100` → `ACC100_MULTI_V2`, `ACC100_MULTI_V3`, `ACC100_MULTI_V4`
- `ACC_RANGE_98_100` → `ACC100_MULTI_V5`

## 3y compare

| Pass | Desk | Range tag | Band | Exp N | Got N | Exp Hit | Got Hit | ΔN | ΔHit |
|---|---|---|---|---:|---:|---:|---:|---:|---:|
| ✅ | `PROVEN15_PLUS_CONFIRM_T30` | `ACC_RANGE_100_100` | `A_PERFECT_3Y5Y` | 49 | 49 | 100.0 | 100.0 | +0 | +0 |
| ✅ | `ACC100_MULTI_V1` | `ACC_RANGE_96_100` | `A_PERFECT_3Y5Y` | 70 | 70 | 100.0 | 100.0 | +0 | +0 |
| ✅ | `ACC100_MULTI_V2` | `ACC_RANGE_97_100` | `A_PERFECT_3Y5Y` | 118 | 118 | 100.0 | 100.0 | +0 | +0 |
| ✅ | `ACC100_MULTI_V3` | `ACC_RANGE_97_100` | `A_PERFECT_3Y5Y` | 122 | 122 | 100.0 | 100.0 | +0 | +0 |
| ✅ | `ACC100_MULTI_V4` | `ACC_RANGE_97_100` | `A_PERFECT_3Y5Y` | 123 | 123 | 100.0 | 100.0 | +0 | +0 |
| ✅ | `ACC100_MULTI_V5` | `ACC_RANGE_98_100` | `A_PERFECT_3Y5Y` | 141 | 141 | 100.0 | 100.0 | +0 | +0 |
| ✅ | `ACC_WIDE_P92` | `ACC_RANGE_91_100` | `B_HIGH_90` | 131 | 131 | 99.24 | 99.24 | +0 | +0 |
| ✅ | `ACC_WIDE_P90` | `ACC_RANGE_89_96` | `B_HIGH_90` | 174 | 174 | 95.4 | 95.4 | +0 | +0 |
| ✅ | `ACC_WIDE_P85` | `ACC_RANGE_84_90` | `C_MID_85` | 223 | 223 | 89.69 | 89.69 | +0 | +0 |
| ✅ | `ACC_WIDE_P85B` | `ACC_RANGE_81_89` | `C_MID_85` | 250 | 250 | 88.4 | 88.4 | +0 | +0 |
| ✅ | `ACC_WIDE_P80` | `ACC_RANGE_76_85` | `D_VOL_80` | 301 | 301 | 84.72 | 84.72 | +0 | +0 |
| ✅ | `ACC_WIDE_P80_CAP2` | `ACC_RANGE_77_87` | `D_VOL_80` | 525 | 525 | 86.29 | 86.29 | +0 | +0 |
| ✅ | `ACC_WIDE_P75` | `ACC_RANGE_75_83` | `E_VOL_75` | 347 | 347 | 82.71 | 82.71 | +0 | +0 |
| ✅ | `ACC_WIDE_P75_CAP2` | `ACC_RANGE_75_84` | `E_VOL_75` | 626 | 626 | 83.39 | 83.39 | +0 | +0 |

## Bands

- `A_PERFECT_3Y5Y`: `PROVEN15_PLUS_CONFIRM_T30`, `ACC100_MULTI_V1`, `ACC100_MULTI_V2`, `ACC100_MULTI_V3`, `ACC100_MULTI_V4`, `ACC100_MULTI_V5`
- `B_HIGH_90`: `ACC_WIDE_P92`, `ACC_WIDE_P90`
- `C_MID_85`: `ACC_WIDE_P85`, `ACC_WIDE_P85B`
- `D_VOL_80`: `ACC_WIDE_P80`, `ACC_WIDE_P80_CAP2`
- `E_VOL_75`: `ACC_WIDE_P75`, `ACC_WIDE_P75_CAP2`

Elapsed 6.5s

JSON: `ACC_ACCURATE_3Y_MATCH.json`
