# Held accurate desks — complete logic + multi-tags

**Status:** `HELD_COMPLETE` · **Latest:** Phase-2f · **P2F day → LIVE (PROMOTED)** · Cap2 still HOLDING

Keep **every** level (P1 → P2F). Live volume + P2F day: `FINAL_LOGIC.md` · `LIVE_CHANNELS.md`.

## Multi-tag stamp (every row)

Each call carries **multiple tags** — desk identity **and** hit-accuracy range:

```
lane=HOLDING
logic_level=P2F
desk_tag=ACC100_MULTI_V11
accurate_tag=ACC100_MULTI_V11          # desk / channel
accuracy_tag=ACC_RANGE_98_100          # hit-target accuracy range
accuracy_range_tag=ACC_RANGE_98_100    # same (alias)
accuracy_lo=98.17
accuracy_hi=100.0
accuracy_band=A_PERFECT_3Y5Y
tags=[ACC100_MULTI_V11, ACC_RANGE_98_100, ACC_BAND_A_PERFECT_3Y5Y, ACC_FLOOR_100, LOGIC_P2F]
```

| Tag field | Meaning |
|---|---|
| `accurate_tag` | Which desk / channel fired |
| `accuracy_tag` / `ACC_RANGE_*` | Research hit% range (lo–hi across 3y/5y/10y) for that desk family |
| `ACC_BAND_*` | Band group (perfect / high-90 / mid-85 / vol-80 / vol-75) |
| `ACC_FLOOR_*` | 3y hit floor used when building the desk |
| `LOGIC_*` | Logic level |

Machine registry: `desks_held.json`

## How a desk is built

1. **Phase-1** — fixed stream recipes in `logic/acc100_streams.py` (LOCKED).
2. **Phase-2c…2f** — start from Phase-1 desk, **greedily union** mined path-true
   stream tags that keep the desk’s **3y hit floor**.
3. **Day mode** = 1 call/day. **Cap2 mode** = ≤2 same-side calls/day.
4. Nested priorities share calendar days across desks; **no within-desk day dups**.

## Accuracy-range tags (hit target %)

| accuracy_tag | Lo–Hi % | Band | Example desks |
|---|---|---|---|
| `ACC_RANGE_100_100` | 100–100 | A | `PROVEN15_PLUS_CONFIRM_T30` |
| `ACC_RANGE_96_100` | 96.62–100 | A | `ACC100_MULTI_V1` |
| `ACC_RANGE_97_100` | 97.8–100 | A | V2, V3, V4 |
| `ACC_RANGE_98_100` | 98.17–100 | A | V5, V8–V11, Cap2_P2F |
| `ACC_RANGE_91_100` | 91.1–99.24 | B | P92 ladder |
| `ACC_RANGE_89_96` | 89.88–95.4 | B | P90 ladder |
| `ACC_RANGE_84_90` | 84–89.88 | C | P85 ladder |
| `ACC_RANGE_81_89` | 81.1–88.4 | C | P85B ladder |
| `ACC_RANGE_76_85` | 76.63–84.72 | D | P80 day |
| `ACC_RANGE_77_87` | 77.7–86.29 | D | P80 Cap2 |
| `ACC_RANGE_75_83` | 75.15–82.71 | E | P75 day |
| `ACC_RANGE_75_84` | 75.5–83.39 | E | P75 Cap2 |

## Latest recommended stamps (P2F day = LIVE)

| Priority | accurate_tag | accuracy_tag | Lo–Hi | Floor | Mode | Lane | 3y N @ hit |
|---:|---|---|---|---:|---|---|---|
| 1 | `ACC100_MULTI_V11` | `ACC_RANGE_98_100` | 98.17–100.0 | 100.0 | day | **LIVE** | 291 @ 100.0% |
| 2 | `ACC_WIDE_P92_P2F` | `ACC_RANGE_91_100` | 91.1–99.24 | 99.24 | day | **LIVE** | 292 @ 99.6575% |
| 3 | `ACC_WIDE_P90_P2F` | `ACC_RANGE_89_96` | 89.88–95.4 | 95.4 | day | **LIVE** | 303 @ 96.6997% |
| 4 | `ACC_WIDE_P85_P2F` | `ACC_RANGE_84_90` | 84.0–89.88 | 89.69 | day | **LIVE** | 326 @ 89.8773% |
| 5 | `ACC_WIDE_P85B_P2F` | `ACC_RANGE_81_89` | 81.1–88.4 | 88.4 | day | **LIVE** | 342 @ 88.5965% |
| 6 | `ACC_WIDE_P80_P2F` | `ACC_RANGE_76_85` | 76.63–84.72 | 84.72 | day | **LIVE** | 375 @ 84.8% |
| 7 | `ACC_WIDE_P75_P2F` | `ACC_RANGE_75_83` | 75.15–82.71 | 82.71 | day | **LIVE** | 386 @ 82.9016% |
| 8 | `ACC100_MULTI_V5_CAP2_P2F` | `ACC_RANGE_98_100` | 98.17–100.0 | 100.0 | cap2 | **LIVE** | 417 @ 100.0% |
| 9 | `ACC_WIDE_P92_CAP2_P2F` | `ACC_RANGE_91_100` | 91.1–99.24 | 99.24 | cap2 | **LIVE** | 418 @ 99.7608% |
| 10 | `ACC_WIDE_P90_CAP2_P2F` | `ACC_RANGE_89_96` | 89.88–95.4 | 95.4 | cap2 | **LIVE** | 434 @ 97.235% |
| 11 | `ACC_WIDE_P85_CAP2_P2F` | `ACC_RANGE_84_90` | 84.0–89.88 | 89.69 | cap2 | **LIVE** | 472 @ 89.8305% |

## All desks by logic level

### Phase-1 LOCKED

| accurate_tag | accuracy_tag | Lo–Hi | Floor | Mode | 3y N | Hit% | tags |
|---|---|---|---:|---|---:|---:|---|
| `PROVEN15_PLUS_CONFIRM_T30` | `ACC_RANGE_100_100` | 100.0–100.0 | 100.0 | day | 49 | 100.0 | `PROVEN15_PLUS_CONFIRM_T30`, `ACC_RANGE_100_100`, `ACC_BAND_A_PERFECT_3Y5Y`, `ACC_FLOOR_100`, `LOGIC_P1` |
| `ACC100_MULTI_V1` | `ACC_RANGE_96_100` | 96.62–100.0 | 100.0 | day | 70 | 100.0 | `ACC100_MULTI_V1`, `ACC_RANGE_96_100`, `ACC_BAND_A_PERFECT_3Y5Y`, `ACC_FLOOR_100`, `LOGIC_P1` |
| `ACC100_MULTI_V2` | `ACC_RANGE_97_100` | 97.8–100.0 | 100.0 | day | 118 | 100.0 | `ACC100_MULTI_V2`, `ACC_RANGE_97_100`, `ACC_BAND_A_PERFECT_3Y5Y`, `ACC_FLOOR_100`, `LOGIC_P1` |
| `ACC100_MULTI_V3` | `ACC_RANGE_97_100` | 97.9–100.0 | 100.0 | day | 122 | 100.0 | `ACC100_MULTI_V3`, `ACC_RANGE_97_100`, `ACC_BAND_A_PERFECT_3Y5Y`, `ACC_FLOOR_100`, `LOGIC_P1` |
| `ACC100_MULTI_V4` | `ACC_RANGE_97_100` | 97.92–100.0 | 100.0 | day | 123 | 100.0 | `ACC100_MULTI_V4`, `ACC_RANGE_97_100`, `ACC_BAND_A_PERFECT_3Y5Y`, `ACC_FLOOR_100`, `LOGIC_P1` |
| `ACC100_MULTI_V5` | `ACC_RANGE_98_100` | 98.17–100.0 | 100.0 | day | 141 | 100.0 | `ACC100_MULTI_V5`, `ACC_RANGE_98_100`, `ACC_BAND_A_PERFECT_3Y5Y`, `ACC_FLOOR_100`, `LOGIC_P1` |
| `ACC_WIDE_P92` | `ACC_RANGE_91_100` | 91.1–99.24 | 99.24 | day | 131 | 99.24 | `ACC_WIDE_P92`, `ACC_RANGE_91_100`, `ACC_BAND_B_HIGH_90`, `ACC_FLOOR_99p24`, `LOGIC_P1` |
| `ACC_WIDE_P90` | `ACC_RANGE_89_96` | 89.88–95.4 | 95.4 | day | 174 | 95.4 | `ACC_WIDE_P90`, `ACC_RANGE_89_96`, `ACC_BAND_B_HIGH_90`, `ACC_FLOOR_95p4`, `LOGIC_P1` |
| `ACC_WIDE_P85` | `ACC_RANGE_84_90` | 84.0–89.88 | 89.69 | day | 223 | 89.69 | `ACC_WIDE_P85`, `ACC_RANGE_84_90`, `ACC_BAND_C_MID_85`, `ACC_FLOOR_89p69`, `LOGIC_P1` |
| `ACC_WIDE_P85B` | `ACC_RANGE_81_89` | 81.1–88.4 | 88.4 | day | 250 | 88.4 | `ACC_WIDE_P85B`, `ACC_RANGE_81_89`, `ACC_BAND_C_MID_85`, `ACC_FLOOR_88p4`, `LOGIC_P1` |
| `ACC_WIDE_P80` | `ACC_RANGE_76_85` | 76.63–84.72 | 84.72 | day | 301 | 84.72 | `ACC_WIDE_P80`, `ACC_RANGE_76_85`, `ACC_BAND_D_VOL_80`, `ACC_FLOOR_84p72`, `LOGIC_P1` |
| `ACC_WIDE_P80_CAP2` | `ACC_RANGE_77_87` | 77.7–86.29 | 84.72 | cap2 | 525 | 86.29 | `ACC_WIDE_P80_CAP2`, `ACC_RANGE_77_87`, `ACC_BAND_D_VOL_80`, `ACC_FLOOR_84p72`, `LOGIC_P1` |
| `ACC_WIDE_P75` | `ACC_RANGE_75_83` | 75.15–82.71 | 82.71 | day | 347 | 82.71 | `ACC_WIDE_P75`, `ACC_RANGE_75_83`, `ACC_BAND_E_VOL_75`, `ACC_FLOOR_82p71`, `LOGIC_P1` |
| `ACC_WIDE_P75_CAP2` | `ACC_RANGE_75_84` | 75.5–83.39 | 82.71 | cap2 | 626 | 83.39 | `ACC_WIDE_P75_CAP2`, `ACC_RANGE_75_84`, `ACC_BAND_E_VOL_75`, `ACC_FLOOR_82p71`, `LOGIC_P1` |

### Phase-2c HELD

_Phase-1 base ∪ greedily added path-true stream tags (P2/P2b/P2c) keeping floor_

| accurate_tag | accuracy_tag | Lo–Hi | Floor | Mode | 3y N | Hit% | tags |
|---|---|---|---:|---|---:|---:|---|
| `ACC100_MULTI_V5_CAP2_P2C` | `ACC_RANGE_98_100` | 98.17–100.0 | 100.0 | cap2 | 256 | 100.0 | `ACC100_MULTI_V5_CAP2_P2C`, `ACC_RANGE_98_100`, `ACC_BAND_A_PERFECT_3Y5Y`, `ACC_FLOOR_100`, `LOGIC_P2C` |
| `ACC100_MULTI_V8` | `ACC_RANGE_98_100` | 98.17–100.0 | 100.0 | day | 199 | 100.0 | `ACC100_MULTI_V8`, `ACC_RANGE_98_100`, `ACC_BAND_A_PERFECT_3Y5Y`, `ACC_FLOOR_100`, `LOGIC_P2C` |
| `ACC_WIDE_P92_P2C` | `ACC_RANGE_91_100` | 91.1–99.24 | 99.24 | day | 203 | 99.5074 | `ACC_WIDE_P92_P2C`, `ACC_RANGE_91_100`, `ACC_BAND_B_HIGH_90`, `ACC_FLOOR_99p24`, `LOGIC_P2C` |
| `ACC_WIDE_P92_CAP2_P2C` | `ACC_RANGE_91_100` | 91.1–99.24 | 99.24 | cap2 | 261 | 99.6169 | `ACC_WIDE_P92_CAP2_P2C`, `ACC_RANGE_91_100`, `ACC_BAND_B_HIGH_90`, `ACC_FLOOR_99p24`, `LOGIC_P2C` |
| `ACC_WIDE_P90_P2C` | `ACC_RANGE_89_96` | 89.88–95.4 | 95.4 | day | 237 | 95.7806 | `ACC_WIDE_P90_P2C`, `ACC_RANGE_89_96`, `ACC_BAND_B_HIGH_90`, `ACC_FLOOR_95p4`, `LOGIC_P2C` |
| `ACC_WIDE_P90_CAP2_P2C` | `ACC_RANGE_89_96` | 89.88–95.4 | 95.4 | cap2 | 309 | 96.1165 | `ACC_WIDE_P90_CAP2_P2C`, `ACC_RANGE_89_96`, `ACC_BAND_B_HIGH_90`, `ACC_FLOOR_95p4`, `LOGIC_P2C` |
| `ACC_WIDE_P85B_P2C` | `ACC_RANGE_81_89` | 81.1–88.4 | 88.4 | day | 303 | 88.4488 | `ACC_WIDE_P85B_P2C`, `ACC_RANGE_81_89`, `ACC_BAND_C_MID_85`, `ACC_FLOOR_88p4`, `LOGIC_P2C` |
| `ACC_WIDE_P85_P2C` | `ACC_RANGE_84_90` | 84.0–89.88 | 89.69 | day | 293 | 89.7611 | `ACC_WIDE_P85_P2C`, `ACC_RANGE_84_90`, `ACC_BAND_C_MID_85`, `ACC_FLOOR_89p69`, `LOGIC_P2C` |
| `ACC_WIDE_P80_P2C` | `ACC_RANGE_76_85` | 76.63–84.72 | 84.72 | day | 341 | 84.7507 | `ACC_WIDE_P80_P2C`, `ACC_RANGE_76_85`, `ACC_BAND_D_VOL_80`, `ACC_FLOOR_84p72`, `LOGIC_P2C` |
| `ACC_WIDE_P75_P2C` | `ACC_RANGE_75_83` | 75.15–82.71 | 82.71 | day | 372 | 82.7957 | `ACC_WIDE_P75_P2C`, `ACC_RANGE_75_83`, `ACC_BAND_E_VOL_75`, `ACC_FLOOR_82p71`, `LOGIC_P2C` |

### Phase-2d HELD

_P2C seed ∪ denser mine · same floor · more calls_

| accurate_tag | accuracy_tag | Lo–Hi | Floor | Mode | 3y N | Hit% | tags |
|---|---|---|---:|---|---:|---:|---|
| `ACC100_MULTI_V5_CAP2_P2D` | `ACC_RANGE_98_100` | 98.17–100.0 | 100.0 | cap2 | 281 | 100.0 | `ACC100_MULTI_V5_CAP2_P2D`, `ACC_RANGE_98_100`, `ACC_BAND_A_PERFECT_3Y5Y`, `ACC_FLOOR_100`, `LOGIC_P2D` |
| `ACC100_MULTI_V9` | `ACC_RANGE_98_100` | 98.17–100.0 | 100.0 | day | 216 | 100.0 | `ACC100_MULTI_V9`, `ACC_RANGE_98_100`, `ACC_BAND_A_PERFECT_3Y5Y`, `ACC_FLOOR_100`, `LOGIC_P2D` |
| `ACC_WIDE_P92_P2D` | `ACC_RANGE_91_100` | 91.1–99.24 | 99.24 | day | 220 | 99.5455 | `ACC_WIDE_P92_P2D`, `ACC_RANGE_91_100`, `ACC_BAND_B_HIGH_90`, `ACC_FLOOR_99p24`, `LOGIC_P2D` |
| `ACC_WIDE_P92_CAP2_P2D` | `ACC_RANGE_91_100` | 91.1–99.24 | 99.24 | cap2 | 286 | 99.6503 | `ACC_WIDE_P92_CAP2_P2D`, `ACC_RANGE_91_100`, `ACC_BAND_B_HIGH_90`, `ACC_FLOOR_99p24`, `LOGIC_P2D` |
| `ACC_WIDE_P90_P2D` | `ACC_RANGE_89_96` | 89.88–95.4 | 95.4 | day | 253 | 96.0474 | `ACC_WIDE_P90_P2D`, `ACC_RANGE_89_96`, `ACC_BAND_B_HIGH_90`, `ACC_FLOOR_95p4`, `LOGIC_P2D` |
| `ACC_WIDE_P90_CAP2_P2D` | `ACC_RANGE_89_96` | 89.88–95.4 | 95.4 | cap2 | 334 | 96.4072 | `ACC_WIDE_P90_CAP2_P2D`, `ACC_RANGE_89_96`, `ACC_BAND_B_HIGH_90`, `ACC_FLOOR_95p4`, `LOGIC_P2D` |
| `ACC_WIDE_P85B_P2D` | `ACC_RANGE_81_89` | 81.1–88.4 | 88.4 | day | 314 | 88.535 | `ACC_WIDE_P85B_P2D`, `ACC_RANGE_81_89`, `ACC_BAND_C_MID_85`, `ACC_FLOOR_88p4`, `LOGIC_P2D` |
| `ACC_WIDE_P85_P2D` | `ACC_RANGE_84_90` | 84.0–89.88 | 89.69 | day | 305 | 89.8361 | `ACC_WIDE_P85_P2D`, `ACC_RANGE_84_90`, `ACC_BAND_C_MID_85`, `ACC_FLOOR_89p69`, `LOGIC_P2D` |
| `ACC_WIDE_P85B_CAP2_P2D` | `ACC_RANGE_81_89` | 81.1–88.4 | 88.4 | cap2 | 435 | 88.5057 | `ACC_WIDE_P85B_CAP2_P2D`, `ACC_RANGE_81_89`, `ACC_BAND_C_MID_85`, `ACC_FLOOR_88p4`, `LOGIC_P2D` |
| `ACC_WIDE_P85_CAP2_P2D` | `ACC_RANGE_84_90` | 84.0–89.88 | 89.69 | cap2 | 424 | 89.8585 | `ACC_WIDE_P85_CAP2_P2D`, `ACC_RANGE_84_90`, `ACC_BAND_C_MID_85`, `ACC_FLOOR_89p69`, `LOGIC_P2D` |
| `ACC_WIDE_P80_P2D` | `ACC_RANGE_76_85` | 76.63–84.72 | 84.72 | day | 350 | 84.8571 | `ACC_WIDE_P80_P2D`, `ACC_RANGE_76_85`, `ACC_BAND_D_VOL_80`, `ACC_FLOOR_84p72`, `LOGIC_P2D` |
| `ACC_WIDE_P75_P2D` | `ACC_RANGE_75_83` | 75.15–82.71 | 82.71 | day | 376 | 82.7128 | `ACC_WIDE_P75_P2D`, `ACC_RANGE_75_83`, `ACC_BAND_E_VOL_75`, `ACC_FLOOR_82p71`, `LOGIC_P2D` |

### Phase-2e HELD

_P2D seed ∪ last/second picks · cross-CF · day_side · same floor_

| accurate_tag | accuracy_tag | Lo–Hi | Floor | Mode | 3y N | Hit% | tags |
|---|---|---|---:|---|---:|---:|---|
| `ACC100_MULTI_V10` | `ACC_RANGE_98_100` | 98.17–100.0 | 100.0 | day | 241 | 100.0 | `ACC100_MULTI_V10`, `ACC_RANGE_98_100`, `ACC_BAND_A_PERFECT_3Y5Y`, `ACC_FLOOR_100`, `LOGIC_P2E` |
| `ACC100_MULTI_V5_CAP2_P2E` | `ACC_RANGE_98_100` | 98.17–100.0 | 100.0 | cap2 | 325 | 100.0 | `ACC100_MULTI_V5_CAP2_P2E`, `ACC_RANGE_98_100`, `ACC_BAND_A_PERFECT_3Y5Y`, `ACC_FLOOR_100`, `LOGIC_P2E` |
| `ACC_WIDE_P92_P2E` | `ACC_RANGE_91_100` | 91.1–99.24 | 99.24 | day | 243 | 99.5885 | `ACC_WIDE_P92_P2E`, `ACC_RANGE_91_100`, `ACC_BAND_B_HIGH_90`, `ACC_FLOOR_99p24`, `LOGIC_P2E` |
| `ACC_WIDE_P92_CAP2_P2E` | `ACC_RANGE_91_100` | 91.1–99.24 | 99.24 | cap2 | 327 | 99.6942 | `ACC_WIDE_P92_CAP2_P2E`, `ACC_RANGE_91_100`, `ACC_BAND_B_HIGH_90`, `ACC_FLOOR_99p24`, `LOGIC_P2E` |
| `ACC_WIDE_P90_P2E` | `ACC_RANGE_89_96` | 89.88–95.4 | 95.4 | day | 274 | 96.3504 | `ACC_WIDE_P90_P2E`, `ACC_RANGE_89_96`, `ACC_BAND_B_HIGH_90`, `ACC_FLOOR_95p4`, `LOGIC_P2E` |
| `ACC_WIDE_P90_CAP2_P2E` | `ACC_RANGE_89_96` | 89.88–95.4 | 95.4 | cap2 | 370 | 96.7568 | `ACC_WIDE_P90_CAP2_P2E`, `ACC_RANGE_89_96`, `ACC_BAND_B_HIGH_90`, `ACC_FLOOR_95p4`, `LOGIC_P2E` |
| `ACC_WIDE_P85B_P2E` | `ACC_RANGE_81_89` | 81.1–88.4 | 88.4 | day | 329 | 88.4498 | `ACC_WIDE_P85B_P2E`, `ACC_RANGE_81_89`, `ACC_BAND_C_MID_85`, `ACC_FLOOR_88p4`, `LOGIC_P2E` |
| `ACC_WIDE_P85_P2E` | `ACC_RANGE_84_90` | 84.0–89.88 | 89.69 | day | 317 | 89.9054 | `ACC_WIDE_P85_P2E`, `ACC_RANGE_84_90`, `ACC_BAND_C_MID_85`, `ACC_FLOOR_89p69`, `LOGIC_P2E` |
| `ACC_WIDE_P85B_CAP2_P2E` | `ACC_RANGE_81_89` | 81.1–88.4 | 88.4 | cap2 | 459 | 88.4532 | `ACC_WIDE_P85B_CAP2_P2E`, `ACC_RANGE_81_89`, `ACC_BAND_C_MID_85`, `ACC_FLOOR_88p4`, `LOGIC_P2E` |
| `ACC_WIDE_P85_CAP2_P2E` | `ACC_RANGE_84_90` | 84.0–89.88 | 89.69 | cap2 | 447 | 89.7092 | `ACC_WIDE_P85_CAP2_P2E`, `ACC_RANGE_84_90`, `ACC_BAND_C_MID_85`, `ACC_FLOOR_89p69`, `LOGIC_P2E` |
| `ACC_WIDE_P80_P2E` | `ACC_RANGE_76_85` | 76.63–84.72 | 84.72 | day | 360 | 84.7222 | `ACC_WIDE_P80_P2E`, `ACC_RANGE_76_85`, `ACC_BAND_D_VOL_80`, `ACC_FLOOR_84p72`, `LOGIC_P2E` |
| `ACC_WIDE_P80_CAP2_P2E` | `ACC_RANGE_77_87` | 77.7–86.29 | 84.72 | cap2 | 521 | 84.8369 | `ACC_WIDE_P80_CAP2_P2E`, `ACC_RANGE_77_87`, `ACC_BAND_D_VOL_80`, `ACC_FLOOR_84p72`, `LOGIC_P2E` |
| `ACC_WIDE_P75_P2E` | `ACC_RANGE_75_83` | 75.15–82.71 | 82.71 | day | 382 | 82.7225 | `ACC_WIDE_P75_P2E`, `ACC_RANGE_75_83`, `ACC_BAND_E_VOL_75`, `ACC_FLOOR_82p71`, `LOGIC_P2E` |

### Phase-2f HELD (latest)

_P2E seed ∪ micro-bands · weekday · mid pick · triple-CF · same floor (latest)_

| accurate_tag | accuracy_tag | Lo–Hi | Floor | Mode | 3y N | Hit% | tags |
|---|---|---|---:|---|---:|---:|---|
| `ACC100_MULTI_V11` | `ACC_RANGE_98_100` | 98.17–100.0 | 100.0 | day | 291 | 100.0 | `ACC100_MULTI_V11`, `ACC_RANGE_98_100`, `ACC_BAND_A_PERFECT_3Y5Y`, `ACC_FLOOR_100`, `LOGIC_P2F` |
| `ACC100_MULTI_V5_CAP2_P2F` | `ACC_RANGE_98_100` | 98.17–100.0 | 100.0 | cap2 | 417 | 100.0 | `ACC100_MULTI_V5_CAP2_P2F`, `ACC_RANGE_98_100`, `ACC_BAND_A_PERFECT_3Y5Y`, `ACC_FLOOR_100`, `LOGIC_P2F` |
| `ACC_WIDE_P92_P2F` | `ACC_RANGE_91_100` | 91.1–99.24 | 99.24 | day | 292 | 99.6575 | `ACC_WIDE_P92_P2F`, `ACC_RANGE_91_100`, `ACC_BAND_B_HIGH_90`, `ACC_FLOOR_99p24`, `LOGIC_P2F` |
| `ACC_WIDE_P92_CAP2_P2F` | `ACC_RANGE_91_100` | 91.1–99.24 | 99.24 | cap2 | 418 | 99.7608 | `ACC_WIDE_P92_CAP2_P2F`, `ACC_RANGE_91_100`, `ACC_BAND_B_HIGH_90`, `ACC_FLOOR_99p24`, `LOGIC_P2F` |
| `ACC_WIDE_P90_P2F` | `ACC_RANGE_89_96` | 89.88–95.4 | 95.4 | day | 303 | 96.6997 | `ACC_WIDE_P90_P2F`, `ACC_RANGE_89_96`, `ACC_BAND_B_HIGH_90`, `ACC_FLOOR_95p4`, `LOGIC_P2F` |
| `ACC_WIDE_P90_CAP2_P2F` | `ACC_RANGE_89_96` | 89.88–95.4 | 95.4 | cap2 | 434 | 97.235 | `ACC_WIDE_P90_CAP2_P2F`, `ACC_RANGE_89_96`, `ACC_BAND_B_HIGH_90`, `ACC_FLOOR_95p4`, `LOGIC_P2F` |
| `ACC_WIDE_P85B_P2F` | `ACC_RANGE_81_89` | 81.1–88.4 | 88.4 | day | 342 | 88.5965 | `ACC_WIDE_P85B_P2F`, `ACC_RANGE_81_89`, `ACC_BAND_C_MID_85`, `ACC_FLOOR_88p4`, `LOGIC_P2F` |
| `ACC_WIDE_P85_P2F` | `ACC_RANGE_84_90` | 84.0–89.88 | 89.69 | day | 326 | 89.8773 | `ACC_WIDE_P85_P2F`, `ACC_RANGE_84_90`, `ACC_BAND_C_MID_85`, `ACC_FLOOR_89p69`, `LOGIC_P2F` |
| `ACC_WIDE_P85_CAP2_P2F` | `ACC_RANGE_84_90` | 84.0–89.88 | 89.69 | cap2 | 472 | 89.8305 | `ACC_WIDE_P85_CAP2_P2F`, `ACC_RANGE_84_90`, `ACC_BAND_C_MID_85`, `ACC_FLOOR_89p69`, `LOGIC_P2F` |
| `ACC_WIDE_P80_P2F` | `ACC_RANGE_76_85` | 76.63–84.72 | 84.72 | day | 375 | 84.8 | `ACC_WIDE_P80_P2F`, `ACC_RANGE_76_85`, `ACC_BAND_D_VOL_80`, `ACC_FLOOR_84p72`, `LOGIC_P2F` |
| `ACC_WIDE_P75_P2F` | `ACC_RANGE_75_83` | 75.15–82.71 | 82.71 | day | 386 | 82.9016 | `ACC_WIDE_P75_P2F`, `ACC_RANGE_75_83`, `ACC_BAND_E_VOL_75`, `ACC_FLOOR_82p71`, `LOGIC_P2F` |

## Logic detail — Phase-2f desks (latest)

### `ACC100_MULTI_V11`

- **accurate_tag:** `ACC100_MULTI_V11`
- **accuracy_tag:** `ACC_RANGE_98_100` (98.17–100.0%)
- **tags:** `ACC100_MULTI_V11`, `ACC_RANGE_98_100`, `ACC_BAND_A_PERFECT_3Y5Y`, `ACC_FLOOR_100`, `LOGIC_P2F`
- **logic_level:** `P2F` · base=`ACC100_MULTI_V5` · mode=day · floor=100.0
- **3y:** 291 @ 100.0% · streams=151
- **logic:** P2E seed ∪ micro-bands · weekday · mid pick · triple-CF · same floor (latest) · base=`ACC100_MULTI_V5` · mode=day · merge=1 call/day

### `ACC100_MULTI_V5_CAP2_P2F`

- **accurate_tag:** `ACC100_MULTI_V5_CAP2_P2F`
- **accuracy_tag:** `ACC_RANGE_98_100` (98.17–100.0%)
- **tags:** `ACC100_MULTI_V5_CAP2_P2F`, `ACC_RANGE_98_100`, `ACC_BAND_A_PERFECT_3Y5Y`, `ACC_FLOOR_100`, `LOGIC_P2F`
- **logic_level:** `P2F` · base=`ACC100_MULTI_V5_CAP2` · mode=cap2 · floor=100.0
- **3y:** 417 @ 100.0% · streams=186
- **logic:** P2E seed ∪ micro-bands · weekday · mid pick · triple-CF · same floor (latest) · base=`ACC100_MULTI_V5_CAP2` · mode=cap2 · merge=cap2≤2 same-side

### `ACC_WIDE_P92_P2F`

- **accurate_tag:** `ACC_WIDE_P92_P2F`
- **accuracy_tag:** `ACC_RANGE_91_100` (91.1–99.24%)
- **tags:** `ACC_WIDE_P92_P2F`, `ACC_RANGE_91_100`, `ACC_BAND_B_HIGH_90`, `ACC_FLOOR_99p24`, `LOGIC_P2F`
- **logic_level:** `P2F` · base=`ACC_WIDE_P92` · mode=day · floor=99.24
- **3y:** 292 @ 99.6575% · streams=146
- **logic:** P2E seed ∪ micro-bands · weekday · mid pick · triple-CF · same floor (latest) · base=`ACC_WIDE_P92` · mode=day · merge=1 call/day

### `ACC_WIDE_P92_CAP2_P2F`

- **accurate_tag:** `ACC_WIDE_P92_CAP2_P2F`
- **accuracy_tag:** `ACC_RANGE_91_100` (91.1–99.24%)
- **tags:** `ACC_WIDE_P92_CAP2_P2F`, `ACC_RANGE_91_100`, `ACC_BAND_B_HIGH_90`, `ACC_FLOOR_99p24`, `LOGIC_P2F`
- **logic_level:** `P2F` · base=`ACC_WIDE_P92_CAP2` · mode=cap2 · floor=99.24
- **3y:** 418 @ 99.7608% · streams=185
- **logic:** P2E seed ∪ micro-bands · weekday · mid pick · triple-CF · same floor (latest) · base=`ACC_WIDE_P92_CAP2` · mode=cap2 · merge=cap2≤2 same-side

### `ACC_WIDE_P90_P2F`

- **accurate_tag:** `ACC_WIDE_P90_P2F`
- **accuracy_tag:** `ACC_RANGE_89_96` (89.88–95.4%)
- **tags:** `ACC_WIDE_P90_P2F`, `ACC_RANGE_89_96`, `ACC_BAND_B_HIGH_90`, `ACC_FLOOR_95p4`, `LOGIC_P2F`
- **logic_level:** `P2F` · base=`ACC_WIDE_P90` · mode=day · floor=95.4
- **3y:** 303 @ 96.6997% · streams=134
- **logic:** P2E seed ∪ micro-bands · weekday · mid pick · triple-CF · same floor (latest) · base=`ACC_WIDE_P90` · mode=day · merge=1 call/day

### `ACC_WIDE_P90_CAP2_P2F`

- **accurate_tag:** `ACC_WIDE_P90_CAP2_P2F`
- **accuracy_tag:** `ACC_RANGE_89_96` (89.88–95.4%)
- **tags:** `ACC_WIDE_P90_CAP2_P2F`, `ACC_RANGE_89_96`, `ACC_BAND_B_HIGH_90`, `ACC_FLOOR_95p4`, `LOGIC_P2F`
- **logic_level:** `P2F` · base=`ACC_WIDE_P90_CAP2` · mode=cap2 · floor=95.4
- **3y:** 434 @ 97.235% · streams=169
- **logic:** P2E seed ∪ micro-bands · weekday · mid pick · triple-CF · same floor (latest) · base=`ACC_WIDE_P90_CAP2` · mode=cap2 · merge=cap2≤2 same-side

### `ACC_WIDE_P85B_P2F`

- **accurate_tag:** `ACC_WIDE_P85B_P2F`
- **accuracy_tag:** `ACC_RANGE_81_89` (81.1–88.4%)
- **tags:** `ACC_WIDE_P85B_P2F`, `ACC_RANGE_81_89`, `ACC_BAND_C_MID_85`, `ACC_FLOOR_88p4`, `LOGIC_P2F`
- **logic_level:** `P2F` · base=`ACC_WIDE_P85B` · mode=day · floor=88.4
- **3y:** 342 @ 88.5965% · streams=93
- **logic:** P2E seed ∪ micro-bands · weekday · mid pick · triple-CF · same floor (latest) · base=`ACC_WIDE_P85B` · mode=day · merge=1 call/day

### `ACC_WIDE_P85_P2F`

- **accurate_tag:** `ACC_WIDE_P85_P2F`
- **accuracy_tag:** `ACC_RANGE_84_90` (84.0–89.88%)
- **tags:** `ACC_WIDE_P85_P2F`, `ACC_RANGE_84_90`, `ACC_BAND_C_MID_85`, `ACC_FLOOR_89p69`, `LOGIC_P2F`
- **logic_level:** `P2F` · base=`ACC_WIDE_P85` · mode=day · floor=89.69
- **3y:** 326 @ 89.8773% · streams=92
- **logic:** P2E seed ∪ micro-bands · weekday · mid pick · triple-CF · same floor (latest) · base=`ACC_WIDE_P85` · mode=day · merge=1 call/day

### `ACC_WIDE_P85_CAP2_P2F`

- **accurate_tag:** `ACC_WIDE_P85_CAP2_P2F`
- **accuracy_tag:** `ACC_RANGE_84_90` (84.0–89.88%)
- **tags:** `ACC_WIDE_P85_CAP2_P2F`, `ACC_RANGE_84_90`, `ACC_BAND_C_MID_85`, `ACC_FLOOR_89p69`, `LOGIC_P2F`
- **logic_level:** `P2F` · base=`ACC_WIDE_P85_CAP2` · mode=cap2 · floor=89.69
- **3y:** 472 @ 89.8305% · streams=90
- **logic:** P2E seed ∪ micro-bands · weekday · mid pick · triple-CF · same floor (latest) · base=`ACC_WIDE_P85_CAP2` · mode=cap2 · merge=cap2≤2 same-side

### `ACC_WIDE_P80_P2F`

- **accurate_tag:** `ACC_WIDE_P80_P2F`
- **accuracy_tag:** `ACC_RANGE_76_85` (76.63–84.72%)
- **tags:** `ACC_WIDE_P80_P2F`, `ACC_RANGE_76_85`, `ACC_BAND_D_VOL_80`, `ACC_FLOOR_84p72`, `LOGIC_P2F`
- **logic_level:** `P2F` · base=`ACC_WIDE_P80` · mode=day · floor=84.72
- **3y:** 375 @ 84.8% · streams=71
- **logic:** P2E seed ∪ micro-bands · weekday · mid pick · triple-CF · same floor (latest) · base=`ACC_WIDE_P80` · mode=day · merge=1 call/day

### `ACC_WIDE_P75_P2F`

- **accurate_tag:** `ACC_WIDE_P75_P2F`
- **accuracy_tag:** `ACC_RANGE_75_83` (75.15–82.71%)
- **tags:** `ACC_WIDE_P75_P2F`, `ACC_RANGE_75_83`, `ACC_BAND_E_VOL_75`, `ACC_FLOOR_82p71`, `LOGIC_P2F`
- **logic_level:** `P2F` · base=`ACC_WIDE_P75` · mode=day · floor=82.71
- **3y:** 386 @ 82.9016% · streams=48
- **logic:** P2E seed ∪ micro-bands · weekday · mid pick · triple-CF · same floor (latest) · base=`ACC_WIDE_P75` · mode=day · merge=1 call/day

## Phase-2G RESEARCH — 10m dual (measured ranges)

_Source: `reports/5y/ACC_PHASE2G_10M_5Y.json` · lo/hi = min/max of 1y·3y·5y·extra_2y · brackets ±30._

| Priority | accurate_tag | accuracy_tag | Lo–Hi | Floor | 5y OK | 5y N@hit | tags |
|---:|---|---|---|---:|---|---|---|
| 1 | `ACC100_MULTI_V12_P2G_10M` | `ACC_RANGE_94_100` | 94.51–100.0 | 100.0 | N | 256@98.05 | `ACC100_MULTI_V12_P2G_10M`, `ACC_RANGE_94_100`, `ACC_BAND_B_HIGH_90`, `ACC_FLOOR_100`, `LOGIC_P2G`, `LANE_RESEARCH` |
| 2 | `ACC_WIDE_P92_P2G_10M` | `ACC_RANGE_83_100` | 83.08–100.0 | 99.24 | N | 174@92.53 | `ACC_WIDE_P92_P2G_10M`, `ACC_RANGE_83_100`, `ACC_BAND_D_VOL_80`, `ACC_FLOOR_99p24`, `LOGIC_P2G`, `LANE_RESEARCH` |
| 3 | `ACC_WIDE_P90_P2G_10M` | `ACC_RANGE_92_100` | 92.92–100.0 | 95.4 | N | 320@94.69 | `ACC_WIDE_P90_P2G_10M`, `ACC_RANGE_92_100`, `ACC_BAND_B_HIGH_90`, `ACC_FLOOR_95p4`, `LOGIC_P2G`, `LANE_RESEARCH` |
| 4 | `ACC_WIDE_P85_P2G_10M` | `ACC_RANGE_86_97` | 86.17–96.72 | 89.69 | Y | 283@90.11 | `ACC_WIDE_P85_P2G_10M`, `ACC_RANGE_86_97`, `ACC_BAND_C_MID_85`, `ACC_FLOOR_89p69`, `LOGIC_P2G`, `LANE_RESEARCH` |
| 5 | `ACC_WIDE_P85B_P2G_10M` | `ACC_RANGE_88_95` | 88.41–94.23 | 88.4 | Y | 418@88.76 | `ACC_WIDE_P85B_P2G_10M`, `ACC_RANGE_88_95`, `ACC_BAND_C_MID_85`, `ACC_FLOOR_88p4`, `LOGIC_P2G`, `LANE_RESEARCH` |
| 6 | `ACC_WIDE_P80_P2G_10M` | `ACC_RANGE_81_85` | 81.37–84.81 | 84.72 | N | 431@83.53 | `ACC_WIDE_P80_P2G_10M`, `ACC_RANGE_81_85`, `ACC_BAND_D_VOL_80`, `ACC_FLOOR_84p72`, `LOGIC_P2G`, `LANE_RESEARCH` |
| 7 | `ACC_WIDE_P75_P2G_10M` | `ACC_RANGE_81_84` | 81.46–83.49 | 82.71 | N | 472@82.42 | `ACC_WIDE_P75_P2G_10M`, `ACC_RANGE_81_84`, `ACC_BAND_D_VOL_80`, `ACC_FLOOR_82p71`, `LOGIC_P2G`, `LANE_RESEARCH` |

### New ACC_RANGE tags (P2G 10m only)

| accuracy_tag | Lo–Hi % | Band | Desk |
|---|---|---|---|
| `ACC_RANGE_94_100` | 94.51–100.0 | B_HIGH_90 | `ACC100_MULTI_V12_P2G_10M` |
| `ACC_RANGE_83_100` | 83.08–100.0 | D_VOL_80 | `ACC_WIDE_P92_P2G_10M` |
| `ACC_RANGE_92_100` | 92.92–100.0 | B_HIGH_90 | `ACC_WIDE_P90_P2G_10M` |
| `ACC_RANGE_86_97` | 86.17–96.72 | C_MID_85 | `ACC_WIDE_P85_P2G_10M` |
| `ACC_RANGE_88_95` | 88.41–94.23 | C_MID_85 | `ACC_WIDE_P85B_P2G_10M` |
| `ACC_RANGE_81_85` | 81.37–84.81 | D_VOL_80 | `ACC_WIDE_P80_P2G_10M` |
| `ACC_RANGE_81_84` | 81.46–83.49 | D_VOL_80 | `ACC_WIDE_P75_P2G_10M` |

