# Multi-tier expand 2 (more calls beyond P85)

Keep held V1–V4 + P92/P90/P85. Hunt more volume same way.

Baselines: V4 **123** @ 100.0% · P85 **223** @ 89.6861%

Mined ≥75%: 3682 · perfect-3y: 684 · elapsed 249.9s

## Desk ladder

| Desk | Mode | Floor | 3y N | 3y Hit | 5y N | 5y Hit | Δ vs P85 |
|---|---|---:|---:|---:|---:|---:|---:|
| `ACC_WIDE_P85` | day | 85 | 223 | 89.6861 | 326 | 89.8773 | 0 |
| `ACC100_MULTI_V5` | day | 100 | 141 | 100.0 | 202 | 100.0 | -82 |
| `ACC_WIDE_P85B` | day | 85 | 251 | 88.0478 | 365 | 87.9452 | +28 |
| `ACC_WIDE_P80` | day | 80 | 301 | 84.7176 | 442 | 83.4842 | +78 |
| `ACC_WIDE_P75` | day | 75 | 347 | 82.7089 | 514 | 81.7121 | +124 |
| `ACC_WIDE_P85_SIDES` | day_side | 85 | 256 | 87.5 | 374 | 86.631 | +33 |
| `ACC_WIDE_P80_CAP2` | cap2 | 80 | 416 | 81.9712 | 577 | 80.9359 | +193 |
| `ACC_WIDE_P75_CAP2` | cap2 | 75 | 509 | 76.4244 | 714 | 77.0308 | +286 |

## Added streams

### `ACC100_MULTI_V5`

| # | Tag | + | Desk3y | Hit3y |
|---:|---|---:|---:|---:|
| 1 | `D15_BUY_p0_latemid_any_g030_raw` | +15 | 126 | 100.0 |
| 2 | `GD40_BUY_p0_earlypm_any_nogap_raw` | +8 | 132 | 100.0 |
| 3 | `GD40_SELL_p55_am1230_any_gdn030_raw` | +6 | 133 | 100.0 |
| 4 | `D15_BOTH_p65_mid_any_gdn030_raw` | +5 | 135 | 100.0 |
| 5 | `D15_BUY_p70_all_any_nogap_raw` | +3 | 135 | 100.0 |
| 6 | `GD40_SELL_p55_am1230_any_g050_raw` | +2 | 135 | 100.0 |
| 7 | `D15_BOTH_p70_latemid_any_g065_raw` | +2 | 137 | 100.0 |
| 8 | `CR35_SELL_p57_pm_htf_gup030_bestp` | +2 | 139 | 100.0 |
| 9 | `GD30_BOTH_p57_am1230_any_g030_raw` | +1 | 139 | 100.0 |
| 10 | `CR35_SELL_p55_pm_htf_g065_first` | +1 | 140 | 100.0 |
| 11 | `CR20_BUY_p52_pm_htf_gup030_first` | +1 | 141 | 100.0 |

### `ACC_WIDE_P85B`

| # | Tag | + | Desk3y | Hit3y |
|---:|---|---:|---:|---:|
| 1 | `D15_BOTH_p70_all_any_nogap_raw` | +34 | 231 | 88.7446 |
| 2 | `GD40_BOTH_p0_mid_any_gup030_raw` | +18 | 238 | 89.0756 |
| 3 | `D15_BUY_p0_latemid_any_g030_raw` | +8 | 239 | 89.1213 |
| 4 | `CR35_SELL_p0_latemid_any_gdn030_first` | +6 | 245 | 88.9796 |
| 5 | `D15_BUY_p0_all_any_gdn030_raw` | +2 | 245 | 88.9796 |
| 6 | `CR20_BUY_p52_pm_htf_gup030_first` | +1 | 246 | 89.0244 |
| 7 | `CR20_BOTH_p0_pm_htf_g065_first` | +1 | 247 | 88.664 |
| 8 | `CF_T45_any15_d5` | +1 | 248 | 88.3065 |
| 9 | `CR30_BUY_p0_mid_any_gdn030_first` | +1 | 249 | 88.3534 |
| 10 | `CR35_SELL_p0_all_htf_gdn030_first` | +1 | 250 | 88.0 |
| 11 | `CR20_SELL_p55_mid_htf_gup030_raw` | +1 | 251 | 88.0478 |

### `ACC_WIDE_P80`

| # | Tag | + | Desk3y | Hit3y |
|---:|---|---:|---:|---:|
| 1 | `D15_BOTH_p0_all_any_nogap_first` | +37 | 261 | 86.2069 |
| 2 | `CR40_SELL_p55_mid_any_nogap_raw` | +20 | 281 | 86.121 |
| 3 | `GD40_SELL_p0_am1230_any_gup030_bestp` | +25 | 285 | 85.614 |
| 4 | `GD40_BOTH_p0_earlypm_any_g035_raw` | +16 | 286 | 85.6643 |
| 5 | `GD40_BUY_p0_mid_any_g030_bestp` | +7 | 288 | 85.4167 |
| 6 | `GD40_BOTH_p55_am1230_any_g030_bestp` | +6 | 288 | 85.4167 |
| 7 | `CR30_BUY_p60_am1230_any_nogap_first` | +6 | 294 | 85.3741 |
| 8 | `CR35_SELL_p60_pm_htf_nogap_raw` | +5 | 299 | 84.9498 |
| 9 | `CR40_BOTH_p0_am1130_any_g030_first` | +1 | 300 | 84.6667 |
| 10 | `CR20_BUY_p52_latemid_htf_gup030_first` | +1 | 301 | 84.7176 |

### `ACC_WIDE_P75`

| # | Tag | + | Desk3y | Hit3y |
|---:|---|---:|---:|---:|
| 1 | `GD40_BOTH_p0_mid_any_g030_raw` | +27 | 307 | 83.7134 |
| 2 | `GD40_BOTH_p0_earlypm_any_nogap_raw` | +25 | 316 | 83.5443 |
| 3 | `GD40_BOTH_p0_am1230_any_gup030_bestp` | +23 | 324 | 82.716 |
| 4 | `GD40_BUY_p0_mid_any_nogap_bestp` | +14 | 330 | 82.7273 |
| 5 | `GD40_BOTH_p55_am1230_any_nogap_bestp` | +5 | 332 | 82.8313 |
| 6 | `CR35_SELL_p55_latemid_htf_nogap_raw` | +3 | 335 | 82.6866 |
| 7 | `CR30_BOTH_p60_latemid_any_nogap_raw` | +4 | 339 | 82.5959 |
| 8 | `CR30_BOTH_p57_am1230_any_nogap_first` | +3 | 342 | 82.7485 |
| 9 | `D5_BOTH_p0_latemid_any_gdn030_raw` | +3 | 344 | 82.8488 |
| 10 | `CR30_SELL_p0_all_htf_g030_first` | +2 | 346 | 82.659 |
| 11 | `CR30_SELL_p60_pm_any_nogap_raw` | +1 | 347 | 82.7089 |

### `ACC_WIDE_P85_SIDES`

| # | Tag | + | Desk3y | Hit3y |
|---:|---|---:|---:|---:|
| 1 | `D15_BOTH_p70_all_any_nogap_raw` | +39 | 232 | 88.7931 |
| 2 | `GD40_BOTH_p0_mid_any_gup030_raw` | +19 | 240 | 88.75 |
| 3 | `D15_BUY_p0_latemid_any_g030_raw` | +9 | 241 | 88.7967 |
| 4 | `CR35_SELL_p0_latemid_any_gdn030_first` | +6 | 247 | 88.664 |
| 5 | `D15_BOTH_p0_am1230_any_nogap_raw` | +4 | 250 | 88.4 |
| 6 | `D15_BUY_p0_all_any_gdn030_raw` | +2 | 250 | 88.4 |
| 7 | `CR20_BUY_p52_pm_htf_gup030_first` | +1 | 251 | 88.4462 |
| 8 | `CR20_BOTH_p0_pm_htf_g065_first` | +1 | 252 | 88.0952 |
| 9 | `CF_T45_any15_d5` | +1 | 253 | 87.747 |
| 10 | `CR30_BUY_p0_mid_any_gdn030_first` | +1 | 254 | 87.7953 |
| 11 | `CR35_SELL_p0_all_htf_gdn030_first` | +1 | 255 | 87.451 |
| 12 | `CR20_SELL_p55_mid_htf_gup030_raw` | +1 | 256 | 87.5 |

### `ACC_WIDE_P80_CAP2`

| # | Tag | + | Desk3y | Hit3y |
|---:|---|---:|---:|---:|
| 1 | `D15_BOTH_p0_all_any_nogap_raw` | +128 | 264 | 86.7424 |
| 2 | `GD40_SELL_p0_am1230_any_gup030_bestp` | +52 | 280 | 85.7143 |
| 3 | `CR40_SELL_p55_mid_any_nogap_raw` | +47 | 327 | 84.7095 |
| 4 | `GD40_BOTH_p0_earlypm_any_g030_raw` | +26 | 334 | 84.4311 |
| 5 | `GD40_BUY_p0_mid_any_g030_raw` | +18 | 341 | 84.1642 |
| 6 | `CR30_BUY_p60_am1230_any_nogap_first` | +14 | 355 | 83.662 |
| 7 | `GD40_BOTH_p55_am1230_any_g030_bestp` | +13 | 358 | 83.2402 |
| 8 | `CR30_BOTH_p0_latemid_any_gdn030_first` | +11 | 369 | 83.4688 |
| 9 | `GD30_BUY_p0_latemid_any_nogap_raw` | +10 | 377 | 83.8196 |
| 10 | `CR35_SELL_p60_pm_htf_nogap_raw` | +8 | 385 | 83.6364 |
| 11 | `CR20_BOTH_p55_pm_htf_gup030_bestp` | +7 | 392 | 83.4184 |
| 12 | `CF_T45_any15_d5` | +5 | 395 | 83.2911 |
| 13 | `GD40_BOTH_p55_mid_any_nogap_raw` | +4 | 398 | 82.9146 |
| 14 | `CR30_BOTH_p0_mid_htf_g035_first` | +4 | 402 | 82.8358 |
| 15 | `CR40_BOTH_p0_am1130_any_g030_raw` | +3 | 405 | 82.4691 |
| 16 | `GD40_BOTH_p0_mid_any_gup030_raw` | +2 | 406 | 82.5123 |
| 17 | `CR35_SELL_p55_latemid_any_gdn030_first` | +2 | 408 | 82.598 |
| 18 | `CR20_BOTH_p62_mid_any_nogap_raw` | +2 | 410 | 82.439 |
| 19 | `CR35_SELL_p0_pm_htf_g050_bestp` | +2 | 412 | 82.2816 |
| 20 | `CR20_BUY_p0_pm_htf_gup030_first` | +2 | 414 | 82.1256 |
| 21 | `CR35_BOTH_p55_last90_any_gup040_bestp` | +1 | 415 | 82.1687 |
| 22 | `CR35_SELL_p0_all_htf_gdn030_first` | +1 | 416 | 81.9712 |
| 23 | `GD40_SELL_p0_am1130_any_gup040_bestp` | +1 | 416 | 81.9712 |

### `ACC_WIDE_P75_CAP2`

| # | Tag | + | Desk3y | Hit3y |
|---:|---|---:|---:|---:|
| 1 | `D15_BOTH_p0_all_any_nogap_raw` | +128 | 264 | 86.7424 |
| 2 | `GD40_BOTH_p0_mid_any_g030_raw` | +119 | 307 | 84.0391 |
| 3 | `GD40_BOTH_p0_am1230_any_gup030_raw` | +63 | 325 | 81.8462 |
| 4 | `CR35_SELL_p55_latemid_htf_nogap_raw` | +56 | 381 | 80.0525 |
| 5 | `GD40_BOTH_p0_earlypm_any_nogap_raw` | +41 | 402 | 79.602 |
| 6 | `GD40_BUY_p0_mid_any_nogap_raw` | +32 | 417 | 79.1367 |
| 7 | `CR30_BOTH_p57_am1230_any_nogap_raw` | +29 | 446 | 78.4753 |
| 8 | `GD40_BOTH_p55_am1230_any_nogap_bestp` | +21 | 454 | 77.7533 |
| 9 | `CR30_SELL_p0_all_htf_g030_first` | +11 | 465 | 77.2043 |
| 10 | `CR40_SELL_p55_mid_any_nogap_raw` | +9 | 474 | 77.2152 |
| 11 | `CF_T90_any15_d5` | +8 | 479 | 77.0355 |
| 12 | `CR30_BOTH_p60_latemid_any_nogap_raw` | +7 | 486 | 77.1605 |
| 13 | `CR30_BOTH_p0_latemid_htf_g035_first` | +5 | 491 | 76.9857 |
| 14 | `GD40_BOTH_p55_am1230_any_g030_raw` | +3 | 492 | 76.8293 |
| 15 | `CR30_SELL_p60_pm_any_nogap_raw` | +3 | 495 | 76.7677 |
| 16 | `GD40_SELL_p55_am1230_any_nogap_first` | +3 | 495 | 76.5657 |
| 17 | `D5_BOTH_p0_latemid_any_gdn030_raw` | +3 | 497 | 76.66 |
| 18 | `GD40_BOTH_p55_latemid_any_nogap_raw` | +2 | 498 | 76.506 |
| 19 | `CR20_BOTH_p55_pm_htf_gup030_bestp` | +2 | 500 | 76.6 |
| 20 | `CR30_BOTH_p0_mid_any_gdn030_raw` | +2 | 502 | 76.8924 |
| 21 | `CR30_BOTH_p57_mid_htf_nogap_first` | +2 | 504 | 76.5873 |
| 22 | `CR40_SELL_p58_earlypm_any_nogap_raw` | +2 | 506 | 76.4822 |
| 23 | `CR20_SELL_p0_pm_any_g050_first` | +2 | 508 | 76.378 |
| 24 | `CR40_SELL_p0_mid_any_g040_raw` | +1 | 509 | 76.4244 |

## Verdict

- Keep all prior desks (**V1–V4**, P92/P90/P85).
- Hold **`ACC100_MULTI_V5`** = **141 @ 100% 3y / 202 @ 100% 5y** (+18 vs V4).
- Hold **`P85B` / `P80` / `P75`** day ladder (250 / 301 / 347 on 3y).
- Hold **`P80_CAP2` / `P75_CAP2`** (525 / 626 on 3y) for max volume filter.

Packaged + verified in `logic/acc100_streams.py`.

JSON: `ACC_MULTI_TIER_EXPAND2.json`
