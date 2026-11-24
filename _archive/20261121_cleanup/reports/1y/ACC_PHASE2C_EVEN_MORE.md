# Phase-2c — even more calls @ same accuracy

**Phase-1 HELD.** Continues from P2b seeds + denser mine + cap2.

Mined ≥75%: 17250 · perfect-3y: 3781 · elapsed 840.6s

## Day-dedupe

| Desk | Floor | P1 | P2b | **P2c** | ΔP1 | ΔP2b | Hit | Candidate |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `ACC100_MULTI_V5` | 100 | 141 | 163 | **199** | +58 | +36 | 100.0 | `ACC100_MULTI_V8` |
| `ACC_WIDE_P92` | 99.24 | 131 | 171 | **203** | +72 | +32 | 99.5074 | `ACC_WIDE_P92_P2C` |
| `ACC_WIDE_P90` | 95.4 | 174 | 213 | **237** | +63 | +24 | 95.7806 | `ACC_WIDE_P90_P2C` |
| `ACC_WIDE_P85` | 89.69 | 223 | 275 | **293** | +70 | +18 | 89.7611 | `ACC_WIDE_P85_P2C` |
| `ACC_WIDE_P85B` | 88.4 | 250 | 281 | **303** | +53 | +22 | 88.4488 | `ACC_WIDE_P85B_P2C` |
| `ACC_WIDE_P80` | 84.72 | 301 | 323 | **341** | +40 | +18 | 84.7507 | `ACC_WIDE_P80_P2C` |
| `ACC_WIDE_P75` | 82.71 | 347 | 360 | **372** | +25 | +12 | 82.7957 | `ACC_WIDE_P75_P2C` |

## Cap2 @ same accuracy

| Desk | Floor | P1 | Cap2 P2c | Δ | Hit | Candidate |
|---|---:|---:|---:|---:|---:|---|
| `ACC100_MULTI_V5_CAP2` | 100 | 141 | **256** | +115 | 100.0 | `ACC100_MULTI_V5_CAP2_P2C` |
| `ACC_WIDE_P92_CAP2` | 99.24 | 131 | **261** | +130 | 99.6169 | `ACC_WIDE_P92_CAP2_P2C` |
| `ACC_WIDE_P90_CAP2` | 95.4 | 174 | **309** | +135 | 96.1165 | `ACC_WIDE_P90_CAP2_P2C` |

## New streams beyond P2b seed (day)

### `ACC100_MULTI_V5`

| # | Tag | + | Desk3y | Hit |
|---:|---|---:|---:|---:|
| 1 | `D15_BOTH_p65_brunch_any_g025_raw` | +17 | 163 | 100.0 |
| 2 | `D15_BUY_p0_first20_htf_nogap_raw` | +10 | 169 | 100.0 |
| 3 | `D5_SELL_p0_earlypm_any_g020_raw` | +7 | 170 | 100.0 |
| 4 | `GD40_SELL_p55_first45_any_gup015_raw` | +6 | 172 | 100.0 |
| 5 | `GD40_BUY_p0_brunch_any_gup040_raw` | +6 | 173 | 100.0 |
| 6 | `GD30_BOTH_p54_first20_any_gup015_raw` | +5 | 175 | 100.0 |
| 7 | `GD30_BUY_p53_mid_any_gup025_raw` | +4 | 177 | 100.0 |
| 8 | `D5_BOTH_p0_mid_any_g080_raw` | +3 | 179 | 100.0 |
| 9 | `CR30_BUY_p58_mid_any_gdn015_first` | +3 | 182 | 100.0 |
| 10 | `D5_BOTH_p0_earlypm_any_gdn025_raw` | +2 | 183 | 100.0 |
| 11 | `D15_SELL_p0_open_any_gdn015_raw` | +2 | 183 | 100.0 |
| 12 | `D15_BUY_p0_latemid_any_gup015_raw` | +2 | 183 | 100.0 |
| 13 | `D15_BOTH_p64_brunch_htf_gup015_raw` | +2 | 184 | 100.0 |
| 14 | `CR35_SELL_p53_brunch_any_gdn025_raw` | +2 | 186 | 100.0 |
| 15 | `CR30_SELL_p56_am1230_any_gup015_raw` | +1 | 187 | 100.0 |
| 16 | `CR30_BOTH_p56_last60_htf_gup015_raw` | +1 | 188 | 100.0 |
| 17 | `CH_BOTH_p75_last120_htf_nogap_raw` | +2 | 189 | 100.0 |
| 18 | `GD35_BUY_p54_latemid_any_gup020_raw` | +1 | 190 | 100.0 |
| 19 | `GD30_BUY_p53_open_any_gup055_raw` | +1 | 190 | 100.0 |
| 20 | `D15_BUY_p0_first30_any_gup015_raw` | +1 | 190 | 100.0 |
| 21 | `CR35_SELL_p59_pm_htf_gdn020_raw` | +1 | 191 | 100.0 |
| 22 | `CR35_SELL_p53_am1130_htf_g020_raw` | +1 | 192 | 100.0 |
| 23 | `CR30_SELL_p0_brunch_any_gdn030_raw` | +1 | 193 | 100.0 |
| 24 | `CR30_BOTH_p60_brunch_htf_nogap_first` | +1 | 194 | 100.0 |
| 25 | `CR20_BUY_p55_pm_any_g050_raw` | +1 | 195 | 100.0 |
| 26 | `CR20_BUY_p0_lunch_any_gup040_first` | +1 | 196 | 100.0 |
| 27 | `CR20_BOTH_p54_mid_htf_gup040_first` | +1 | 197 | 100.0 |
| 28 | `CR20_BOTH_p54_last60_htf_gup015_first` | +1 | 198 | 100.0 |
| 29 | `CF_T120_d5_cr20` | +1 | 199 | 100.0 |

### `ACC_WIDE_P92`

| # | Tag | + | Desk3y | Hit |
|---:|---|---:|---:|---:|
| 1 | `D15_BOTH_p65_brunch_any_g025_raw` | +13 | 171 | 99.4152 |
| 2 | `D15_BUY_p0_first20_htf_nogap_raw` | +10 | 177 | 99.435 |
| 3 | `D5_SELL_p0_earlypm_any_g020_raw` | +7 | 178 | 99.4382 |
| 4 | `GD40_SELL_p55_first45_any_gup015_raw` | +6 | 180 | 99.4444 |
| 5 | `GD30_BOTH_p54_first20_any_gup015_raw` | +5 | 182 | 99.4505 |
| 6 | `D5_BOTH_p0_mid_any_g080_raw` | +3 | 184 | 99.4565 |
| 7 | `CR30_BUY_p58_mid_any_gdn015_first` | +3 | 187 | 99.4652 |
| 8 | `GD35_BUY_p54_latemid_any_gup020_raw` | +2 | 189 | 99.4709 |
| 9 | `D5_BOTH_p0_earlypm_any_gdn025_raw` | +2 | 190 | 99.4737 |
| 10 | `D15_BUY_p0_latemid_any_gup015_raw` | +2 | 190 | 99.4737 |
| 11 | `D15_BOTH_p64_brunch_htf_gup015_raw` | +2 | 191 | 99.4764 |
| 12 | `CR35_SELL_p53_brunch_any_gdn025_raw` | +2 | 193 | 99.4819 |
| 13 | `CR30_SELL_p56_am1230_any_gup015_raw` | +1 | 194 | 99.4845 |
| 14 | `CR30_BOTH_p56_last60_htf_gup015_raw` | +1 | 195 | 99.4872 |
| 15 | `CH_BOTH_p75_last120_htf_nogap_raw` | +2 | 196 | 99.4898 |
| 16 | `GD40_SELL_p56_mid_any_gdn015_raw` | +1 | 196 | 99.4898 |
| 17 | `GD30_BUY_p53_open_any_gup055_raw` | +1 | 196 | 99.4898 |
| 18 | `D15_SELL_p0_open_any_gdn015_raw` | +1 | 196 | 99.4898 |
| 19 | `D15_BUY_p0_first30_any_gup015_raw` | +1 | 196 | 99.4898 |
| 20 | `CR35_SELL_p59_pm_htf_gdn020_raw` | +1 | 197 | 99.4924 |
| 21 | `CR35_SELL_p53_am1130_htf_g020_raw` | +1 | 198 | 99.4949 |
| 22 | `CR30_BOTH_p60_brunch_htf_nogap_first` | +1 | 199 | 99.4975 |
| 23 | `CR20_BUY_p55_pm_any_g050_raw` | +1 | 200 | 99.5 |
| 24 | `CR20_BUY_p0_lunch_any_gup040_first` | +1 | 201 | 99.5025 |
| 25 | `CR20_BOTH_p54_last60_htf_gup015_first` | +1 | 202 | 99.505 |
| 26 | `CF_T120_d5_cr20` | +1 | 203 | 99.5074 |

### `ACC_WIDE_P90`

| # | Tag | + | Desk3y | Hit |
|---:|---|---:|---:|---:|
| 1 | `D15_BOTH_p64_brunch_any_gup015_raw` | +14 | 212 | 95.7547 |
| 2 | `D5_SELL_p0_earlypm_any_g020_raw` | +7 | 213 | 95.7746 |
| 3 | `GD40_SELL_p55_open_any_gup015_raw` | +6 | 215 | 95.814 |
| 4 | `GD30_BOTH_p54_first20_any_gup015_raw` | +5 | 217 | 95.8525 |
| 5 | `CR35_SELL_p55_mid_htf_gdn015_raw` | +3 | 220 | 95.9091 |
| 6 | `GD40_BUY_p0_brunch_any_gup025_raw` | +4 | 222 | 95.9459 |
| 7 | `D5_BOTH_p0_mid_any_g080_raw` | +3 | 224 | 95.9821 |
| 8 | `D5_BOTH_p0_earlypm_any_gdn025_raw` | +2 | 225 | 96.0 |
| 9 | `CR30_SELL_p56_am1230_any_gup015_raw` | +1 | 226 | 96.0177 |
| 10 | `CR30_BUY_p60_am1230_any_gdn015_first` | +2 | 228 | 96.0526 |
| 11 | `CR30_BOTH_p56_last60_htf_gup015_raw` | +1 | 229 | 96.0699 |
| 12 | `CH_BOTH_p75_last120_htf_nogap_raw` | +2 | 230 | 96.087 |
| 13 | `GD30_BUY_p53_open_any_gup055_raw` | +1 | 230 | 96.087 |
| 14 | `D15_SELL_p0_open_any_gdn015_raw` | +1 | 230 | 96.087 |
| 15 | `D15_BUY_p0_latemid_any_gup015_raw` | +1 | 230 | 96.087 |
| 16 | `CR35_SELL_p53_brunch_any_gdn025_raw` | +1 | 231 | 96.1039 |
| 17 | `CR35_SELL_p53_am1130_htf_g020_raw` | +1 | 232 | 96.1207 |
| 18 | `CR30_BOTH_p60_brunch_htf_nogap_first` | +1 | 233 | 96.1373 |
| 19 | `CR20_BUY_p0_lunch_any_gup040_first` | +1 | 234 | 96.1538 |
| 20 | `CR20_BOTH_p54_last60_htf_gup015_first` | +1 | 235 | 96.1702 |
| 21 | `CF_T120_d5_cr20` | +1 | 236 | 96.1864 |
| 22 | `GD40_BOTH_p55_am1230_any_gup015_first` | +1 | 237 | 95.7806 |

### `ACC_WIDE_P85`

| # | Tag | + | Desk3y | Hit |
|---:|---|---:|---:|---:|
| 1 | `D15_BOTH_p0_all_any_gup015_raw` | +9 | 276 | 89.8551 |
| 2 | `D5_SELL_p0_earlypm_any_g020_raw` | +7 | 277 | 89.8917 |
| 3 | `GD40_BOTH_p0_brunch_any_gup030_first` | +6 | 277 | 89.8917 |
| 4 | `GD35_BOTH_p54_am10_any_gup015_raw` | +3 | 279 | 89.9642 |
| 5 | `GD40_BUY_p53_brunch_any_nogap_raw` | +3 | 279 | 89.9642 |
| 6 | `D5_BOTH_p0_mid_any_g080_raw` | +3 | 281 | 90.0356 |
| 7 | `GD40_SELL_p53_am1230_any_gup030_bestp` | +3 | 281 | 90.0356 |
| 8 | `CR30_BOTH_p58_latemid_any_gdn015_first` | +3 | 284 | 90.1408 |
| 9 | `D5_BOTH_p0_earlypm_any_gdn025_raw` | +2 | 285 | 90.1754 |
| 10 | `GD40_BUY_p54_mid_any_nogap_raw` | +2 | 286 | 89.8601 |
| 11 | `CR30_BUY_p53_brunch_any_nogap_first` | +2 | 288 | 89.9306 |
| 12 | `GD30_BUY_p53_open_any_gup055_raw` | +1 | 288 | 89.9306 |
| 13 | `CR20_BUY_p0_lunch_any_gup040_first` | +1 | 289 | 89.9654 |
| 14 | `CR20_BOTH_p54_last60_htf_gup015_first` | +1 | 290 | 90.0 |
| 15 | `CH_BOTH_p75_last120_any_nogap_raw` | +1 | 290 | 90.0 |
| 16 | `GD40_BUY_p0_brunch_any_g020_raw` | +1 | 290 | 90.0 |
| 17 | `CR35_BOTH_p53_am1130_any_g015_first` | +1 | 291 | 89.6907 |
| 18 | `CR30_BUY_p0_am1230_any_gdn015_first` | +1 | 292 | 89.726 |
| 19 | `CR40_SELL_p56_brunch_any_nogap_raw` | +1 | 293 | 89.7611 |

### `ACC_WIDE_P85B`

| # | Tag | + | Desk3y | Hit |
|---:|---|---:|---:|---:|
| 1 | `GD35_BOTH_p54_am10_any_gup015_raw` | +7 | 280 | 88.5714 |
| 2 | `D5_SELL_p0_earlypm_any_g020_raw` | +7 | 281 | 88.6121 |
| 3 | `GD40_SELL_p0_pm_any_gdn015_raw` | +6 | 282 | 88.6525 |
| 4 | `GD40_BUY_p53_brunch_any_nogap_raw` | +5 | 284 | 88.7324 |
| 5 | `CR30_BOTH_p58_latemid_any_gdn015_first` | +4 | 288 | 88.8889 |
| 6 | `D5_BOTH_p0_mid_any_g080_raw` | +3 | 290 | 88.9655 |
| 7 | `GD40_BUY_p54_mid_any_nogap_raw` | +3 | 291 | 88.6598 |
| 8 | `D15_BUY_p0_all_any_gup015_raw` | +3 | 291 | 88.6598 |
| 9 | `CR20_BOTH_p53_last60_htf_gup015_first` | +3 | 294 | 88.7755 |
| 10 | `D5_BOTH_p0_earlypm_any_gdn025_raw` | +2 | 295 | 88.8136 |
| 11 | `GD40_SELL_p53_am1230_any_gup030_bestp` | +2 | 295 | 88.8136 |
| 12 | `CR30_BUY_p53_brunch_any_nogap_first` | +2 | 297 | 88.8889 |
| 13 | `CR35_BOTH_p53_am1130_htf_nogap_first` | +2 | 299 | 88.6288 |
| 14 | `GD30_BUY_p53_open_any_gup055_raw` | +1 | 299 | 88.6288 |
| 15 | `CR20_BUY_p0_lunch_any_gup040_first` | +1 | 300 | 88.6667 |
| 16 | `GD40_BUY_p0_brunch_any_g020_raw` | +1 | 300 | 88.6667 |
| 17 | `CR30_BUY_p0_am1230_any_gdn015_first` | +1 | 301 | 88.7043 |
| 18 | `GD40_BUY_p0_mid_any_gup020_bestp` | +2 | 302 | 88.4106 |
| 19 | `CR40_SELL_p56_brunch_any_nogap_raw` | +1 | 303 | 88.4488 |

### `ACC_WIDE_P80`

| # | Tag | + | Desk3y | Hit |
|---:|---|---:|---:|---:|
| 1 | `D5_SELL_p0_earlypm_any_g020_raw` | +7 | 324 | 84.8765 |
| 2 | `GD40_SELL_p53_mid_any_g030_raw` | +7 | 324 | 84.8765 |
| 3 | `GD35_BOTH_p54_am10_any_gup015_raw` | +3 | 326 | 84.9693 |
| 4 | `GD30_BUY_p53_am1130_any_gup025_raw` | +5 | 328 | 84.7561 |
| 5 | `D5_BOTH_p0_mid_any_g080_raw` | +3 | 330 | 84.8485 |
| 6 | `CR20_BOTH_p53_last60_htf_gup015_first` | +3 | 333 | 84.985 |
| 7 | `GD40_BUY_p0_brunch_any_nogap_raw` | +3 | 334 | 85.0299 |
| 8 | `CR30_BUY_p0_latemid_any_gdn015_first` | +3 | 337 | 84.8665 |
| 9 | `D5_BOTH_p0_earlypm_any_gdn025_raw` | +2 | 338 | 84.9112 |
| 10 | `CR30_BUY_p53_brunch_any_nogap_first` | +2 | 340 | 85.0 |
| 11 | `GD40_BUY_p0_mid_any_gup020_bestp` | +2 | 341 | 84.7507 |
| 12 | `GD35_BOTH_p0_earlypm_any_gup015_raw` | +1 | 341 | 84.7507 |
| 13 | `GD40_SELL_p53_am1230_htf_gup025_bestp` | +1 | 341 | 84.7507 |

### `ACC_WIDE_P75`

| # | Tag | + | Desk3y | Hit |
|---:|---|---:|---:|---:|
| 1 | `D5_SELL_p0_earlypm_any_g020_raw` | +6 | 360 | 83.0556 |
| 2 | `GD40_SELL_p53_am1230_any_g030_bestp` | +6 | 361 | 82.8255 |
| 3 | `D5_BOTH_p0_mid_any_g080_raw` | +3 | 363 | 82.9201 |
| 4 | `GD35_BUY_p53_am1130_any_gup015_raw` | +5 | 365 | 82.7397 |
| 5 | `CR20_BOTH_p53_last60_htf_gup015_first` | +2 | 367 | 82.8338 |
| 6 | `GD30_SELL_p54_first30_any_gup015_raw` | +1 | 367 | 82.8338 |
| 7 | `CR30_BUY_p0_am1230_any_gdn015_first` | +1 | 368 | 82.8804 |
| 8 | `CR30_BOTH_p58_latemid_any_gdn015_first` | +1 | 369 | 82.9268 |
| 9 | `GD40_SELL_p53_mid_any_gup015_bestp` | +3 | 371 | 82.7493 |
| 10 | `GD40_SELL_p53_am1230_htf_gup025_bestp` | +1 | 371 | 82.7493 |
| 11 | `CR30_BUY_p0_latemid_any_gdn015_first` | +1 | 372 | 82.7957 |

## Hold

Phase-1 locked. P2/P2b/P2c = candidates until promote.

JSON: `ACC_PHASE2C_EVEN_MORE.json`
