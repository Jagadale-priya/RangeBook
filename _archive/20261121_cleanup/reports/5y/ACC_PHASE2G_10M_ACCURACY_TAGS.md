# P2G 10m — measured accuracy tags

**Source:** `ACC_PHASE2G_10M_5Y.json`
**Rule:** `accuracy_lo/hi` = min/max hit% across **1y · 3y · 5y · extra_2y**
**Brackets:** Target **+30** · SL **−30** (same as P2F/P2G path risk)
**Lane:** RESEARCH · not live

## Stamp table

| accurate_tag | OLD (copied P2F) | NEW accuracy_tag | Lo–Hi | Band | Floor | Covers? | 5y OK |
|---|---|---|---|---|---:|---|---|
| `ACC100_MULTI_V12_P2G_10M` | `ACC_RANGE_98_100` | `ACC_RANGE_94_100` | 94.51–100.0 | `ACC_BAND_B_HIGH_90` | 100.0 | Y | N |
| `ACC_WIDE_P92_P2G_10M` | `ACC_RANGE_91_100` | `ACC_RANGE_83_100` | 83.08–100.0 | `ACC_BAND_D_VOL_80` | 99.24 | Y | N |
| `ACC_WIDE_P90_P2G_10M` | `ACC_RANGE_89_96` | `ACC_RANGE_92_100` | 92.92–100.0 | `ACC_BAND_B_HIGH_90` | 95.4 | Y | N |
| `ACC_WIDE_P85_P2G_10M` | `ACC_RANGE_84_90` | `ACC_RANGE_86_97` | 86.17–96.72 | `ACC_BAND_C_MID_85` | 89.69 | Y | Y |
| `ACC_WIDE_P85B_P2G_10M` | `ACC_RANGE_81_89` | `ACC_RANGE_88_95` | 88.41–94.23 | `ACC_BAND_C_MID_85` | 88.4 | Y | Y |
| `ACC_WIDE_P80_P2G_10M` | `ACC_RANGE_76_85` | `ACC_RANGE_81_85` | 81.37–84.81 | `ACC_BAND_D_VOL_80` | 84.72 | Y | N |
| `ACC_WIDE_P75_P2G_10M` | `ACC_RANGE_75_83` | `ACC_RANGE_81_84` | 81.46–83.49 | `ACC_BAND_D_VOL_80` | 82.71 | Y | N |

## Per-desk measured hits

### `ACC100_MULTI_V12_P2G_10M`

- **accuracy_tag:** `ACC_RANGE_94_100` · **lo/hi:** 94.51–100.0
- **3y+5y only:** 98.05–100.0
- **tags:** `ACC100_MULTI_V12_P2G_10M`, `ACC_RANGE_94_100`, `ACC_BAND_B_HIGH_90`, `ACC_FLOOR_100`, `LOGIC_P2G`, `LANE_RESEARCH`

| Window | N | Hit% |
|---|---:|---:|
| extra_2y | 91 | 94.51 |
| 3y | 165 | 100.0 |
| 5y | 256 | 98.05 |
| 1y | 61 | 100.0 |

### `ACC_WIDE_P92_P2G_10M`

- **accuracy_tag:** `ACC_RANGE_83_100` · **lo/hi:** 83.08–100.0
- **3y+5y only:** 92.53–98.17
- **tags:** `ACC_WIDE_P92_P2G_10M`, `ACC_RANGE_83_100`, `ACC_BAND_D_VOL_80`, `ACC_FLOOR_99p24`, `LOGIC_P2G`, `LANE_RESEARCH`

| Window | N | Hit% |
|---|---:|---:|
| extra_2y | 65 | 83.08 |
| 3y | 109 | 98.17 |
| 5y | 174 | 92.53 |
| 1y | 34 | 100.0 |

### `ACC_WIDE_P90_P2G_10M`

- **accuracy_tag:** `ACC_RANGE_92_100` · **lo/hi:** 92.92–100.0
- **3y+5y only:** 94.69–95.65
- **tags:** `ACC_WIDE_P90_P2G_10M`, `ACC_RANGE_92_100`, `ACC_BAND_B_HIGH_90`, `ACC_FLOOR_95p4`, `LOGIC_P2G`, `LANE_RESEARCH`

| Window | N | Hit% |
|---|---:|---:|
| extra_2y | 113 | 92.92 |
| 3y | 207 | 95.65 |
| 5y | 320 | 94.69 |
| 1y | 75 | 100.0 |

### `ACC_WIDE_P85_P2G_10M`

- **accuracy_tag:** `ACC_RANGE_86_97` · **lo/hi:** 86.17–96.72
- **3y+5y only:** 90.11–92.06
- **tags:** `ACC_WIDE_P85_P2G_10M`, `ACC_RANGE_86_97`, `ACC_BAND_C_MID_85`, `ACC_FLOOR_89p69`, `LOGIC_P2G`, `LANE_RESEARCH`

| Window | N | Hit% |
|---|---:|---:|
| extra_2y | 94 | 86.17 |
| 3y | 189 | 92.06 |
| 5y | 283 | 90.11 |
| 1y | 61 | 96.72 |

### `ACC_WIDE_P85B_P2G_10M`

- **accuracy_tag:** `ACC_RANGE_88_95` · **lo/hi:** 88.41–94.23
- **3y+5y only:** 88.76–88.93
- **tags:** `ACC_WIDE_P85B_P2G_10M`, `ACC_RANGE_88_95`, `ACC_BAND_C_MID_85`, `ACC_FLOOR_88p4`, `LOGIC_P2G`, `LANE_RESEARCH`

| Window | N | Hit% |
|---|---:|---:|
| extra_2y | 138 | 88.41 |
| 3y | 280 | 88.93 |
| 5y | 418 | 88.76 |
| 1y | 104 | 94.23 |

### `ACC_WIDE_P80_P2G_10M`

- **accuracy_tag:** `ACC_RANGE_81_85` · **lo/hi:** 81.37–84.81
- **3y+5y only:** 83.53–84.81
- **tags:** `ACC_WIDE_P80_P2G_10M`, `ACC_RANGE_81_85`, `ACC_BAND_D_VOL_80`, `ACC_FLOOR_84p72`, `LOGIC_P2G`, `LANE_RESEARCH`

| Window | N | Hit% |
|---|---:|---:|
| extra_2y | 161 | 81.37 |
| 3y | 270 | 84.81 |
| 5y | 431 | 83.53 |
| 1y | 98 | 83.67 |

### `ACC_WIDE_P75_P2G_10M`

- **accuracy_tag:** `ACC_RANGE_81_84` · **lo/hi:** 81.46–83.49
- **3y+5y only:** 82.42–82.99
- **tags:** `ACC_WIDE_P75_P2G_10M`, `ACC_RANGE_81_84`, `ACC_BAND_D_VOL_80`, `ACC_FLOOR_82p71`, `LOGIC_P2G`, `LANE_RESEARCH`

| Window | N | Hit% |
|---|---:|---:|
| extra_2y | 178 | 81.46 |
| 3y | 294 | 82.99 |
| 5y | 472 | 82.42 |
| 1y | 109 | 83.49 |

## Example row stamp

```
lane=RESEARCH
logic_level=P2G
accurate_tag=ACC_WIDE_P85B_P2G_10M
accuracy_tag=ACC_RANGE_88_95
accuracy_lo=88.41
accuracy_hi=94.23
accuracy_band=C_MID_85
tags=[ACC_WIDE_P85B_P2G_10M, ACC_RANGE_88_95, ACC_BAND_C_MID_85, ACC_FLOOR_88p4, LOGIC_P2G, LANE_RESEARCH]
```

