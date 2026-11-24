# Phase-2d — keep going @ same accuracy

**Phase-1 LOCKED.** **Phase-2c HELD** in `holding_accurate/`.
Seeds from held P2c recipes + denser mine + more cap2 desks.

Mined ≥75%: 32168 · perfect-3y: 6236 · elapsed 26001.8s

## Day-dedupe

| Desk | Floor | P1 | P2c | **P2d** | ΔP1 | ΔP2c | Hit | Candidate |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `ACC100_MULTI_V5` | 100 | 141 | 199 | **216** | +75 | +17 | 100.0 | `ACC100_MULTI_V9` |
| `ACC_WIDE_P92` | 99.24 | 131 | 203 | **220** | +89 | +17 | 99.5455 | `ACC_WIDE_P92_P2D` |
| `ACC_WIDE_P90` | 95.4 | 174 | 237 | **253** | +79 | +16 | 96.0474 | `ACC_WIDE_P90_P2D` |
| `ACC_WIDE_P85` | 89.69 | 223 | 293 | **305** | +82 | +12 | 89.8361 | `ACC_WIDE_P85_P2D` |
| `ACC_WIDE_P85B` | 88.4 | 250 | 303 | **314** | +64 | +11 | 88.535 | `ACC_WIDE_P85B_P2D` |
| `ACC_WIDE_P80` | 84.72 | 301 | 341 | **350** | +49 | +9 | 84.8571 | `ACC_WIDE_P80_P2D` |
| `ACC_WIDE_P75` | 82.71 | 347 | 372 | **376** | +29 | +4 | 82.7128 | `ACC_WIDE_P75_P2D` |

## Cap2 @ same accuracy

| Desk | Floor | P1 | P2c | Cap2 P2d | ΔP1 | ΔP2c | Hit | Candidate |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `ACC100_MULTI_V5_CAP2` | 100 | 141 | 256 | **281** | +140 | +25 | 100.0 | `ACC100_MULTI_V5_CAP2_P2D` |
| `ACC_WIDE_P92_CAP2` | 99.24 | 131 | 261 | **286** | +155 | +25 | 99.6503 | `ACC_WIDE_P92_CAP2_P2D` |
| `ACC_WIDE_P90_CAP2` | 95.4 | 174 | 309 | **334** | +160 | +25 | 96.4072 | `ACC_WIDE_P90_CAP2_P2D` |
| `ACC_WIDE_P85_CAP2` | 89.69 | 223 | — | **424** | +201 | — | 89.8585 | `ACC_WIDE_P85_CAP2_P2D` |
| `ACC_WIDE_P85B_CAP2` | 88.4 | 250 | — | **435** | +185 | — | 88.5057 | `ACC_WIDE_P85B_CAP2_P2D` |

## New streams beyond P2c seed (day)

### `ACC100_MULTI_V5`

| # | Tag | + | Desk3y | Hit |
|---:|---|---:|---:|---:|
| 1 | `D15_BUY_p0_first15_htf_nogap_raw` | +9 | 185 | 100.0 |
| 2 | `GD30_BOTH_p54_first15_any_gup010_raw` | +7 | 189 | 100.0 |
| 3 | `D15_BUY_p0_brunch_any_gup010_raw` | +4 | 191 | 100.0 |
| 4 | `D5_BOTH_p0_brunch2_any_g075_raw` | +3 | 193 | 100.0 |
| 5 | `D15_SELL_p65_brunch2_any_g022_raw` | +3 | 193 | 100.0 |
| 6 | `D15_BUY_p0_first30_any_gup010_raw` | +3 | 194 | 100.0 |
| 7 | `CR20_BOTH_p54_last60_any_gup015_first` | +3 | 197 | 100.0 |
| 8 | `GD30_BUY_p53_open_any_gup050_raw` | +2 | 197 | 100.0 |
| 9 | `CR35_SELL_p53_am12_any_gdn025_raw` | +2 | 199 | 100.0 |
| 10 | `CR35_BOTH_p59_last90_htf_gdn010_raw` | +2 | 201 | 100.0 |
| 11 | `CR30_BUY_p58_mid_htf_gdn010_first` | +2 | 203 | 100.0 |
| 12 | `CH_BOTH_p74_last120_htf_nogap_raw` | +2 | 204 | 100.0 |
| 13 | `GD40_SELL_p56_mid2_htf_gdn010_raw` | +1 | 205 | 100.0 |
| 14 | `D15_BOTH_p0_all_any_g090_raw` | +1 | 206 | 100.0 |
| 15 | `CR40_SELL_p60_last150_any_gup010_raw` | +1 | 207 | 100.0 |
| 16 | `CR35_SELL_p54_am1130_any_gdn010_raw` | +1 | 208 | 100.0 |
| 17 | `CR35_SELL_p53_am1130_htf_g018_raw` | +1 | 209 | 100.0 |
| 18 | `CR30_SELL_p61_mid2_any_nogap_raw` | +1 | 210 | 100.0 |
| 19 | `CR30_SELL_p0_am12_any_gdn030_raw` | +1 | 211 | 100.0 |
| 20 | `CR30_BUY_p52_last150_any_g050_raw` | +1 | 212 | 100.0 |
| 21 | `CR30_BOTH_p60_am12_htf_nogap_first` | +1 | 213 | 100.0 |
| 22 | `CR20_BOTH_p61_pm_any_gup010_raw` | +1 | 214 | 100.0 |
| 23 | `CR20_BOTH_p53_last45_htf_gup010_first` | +1 | 215 | 100.0 |
| 24 | `CF_T105_d5_cr20` | +1 | 216 | 100.0 |

### `ACC_WIDE_P92`

| # | Tag | + | Desk3y | Hit |
|---:|---|---:|---:|---:|
| 1 | `D15_BUY_p0_first15_htf_nogap_raw` | +9 | 191 | 99.4764 |
| 2 | `GD30_BOTH_p54_first15_any_gup010_raw` | +7 | 195 | 99.4872 |
| 3 | `D15_BUY_p0_brunch_any_gup010_raw` | +4 | 197 | 99.4924 |
| 4 | `D5_BOTH_p0_brunch2_any_g075_raw` | +3 | 199 | 99.4975 |
| 5 | `D15_SELL_p65_brunch2_any_g022_raw` | +3 | 199 | 99.4975 |
| 6 | `D15_BUY_p0_first30_any_gup010_raw` | +3 | 200 | 99.5 |
| 7 | `CR20_BOTH_p53_last45_htf_gup010_first` | +3 | 203 | 99.5074 |
| 8 | `GD40_SELL_p56_mid2_htf_gdn010_raw` | +2 | 204 | 99.5098 |
| 9 | `CR35_SELL_p53_am12_any_gdn025_raw` | +2 | 206 | 99.5146 |
| 10 | `CR35_BOTH_p59_last90_htf_gdn010_raw` | +2 | 208 | 99.5192 |
| 11 | `CR30_BUY_p58_mid_htf_gdn010_first` | +2 | 210 | 99.5238 |
| 12 | `CH_BOTH_p74_last120_htf_nogap_raw` | +2 | 211 | 99.5261 |
| 13 | `D15_BOTH_p0_all_any_g090_raw` | +1 | 212 | 99.5283 |
| 14 | `CR40_SELL_p60_last150_any_gup010_raw` | +1 | 213 | 99.5305 |
| 15 | `CR35_SELL_p54_am1130_any_gdn010_raw` | +1 | 214 | 99.5327 |
| 16 | `CR35_SELL_p53_am1130_htf_g018_raw` | +1 | 215 | 99.5349 |
| 17 | `CR30_SELL_p61_mid2_any_nogap_raw` | +1 | 216 | 99.537 |
| 18 | `CR30_BUY_p52_last150_any_g050_raw` | +1 | 217 | 99.5392 |
| 19 | `CR30_BOTH_p60_am12_htf_nogap_first` | +1 | 218 | 99.5413 |
| 20 | `CR20_BOTH_p61_pm_any_gup010_raw` | +1 | 219 | 99.5434 |
| 21 | `CF_T105_d5_cr20` | +1 | 220 | 99.5455 |

### `ACC_WIDE_P90`

| # | Tag | + | Desk3y | Hit |
|---:|---|---:|---:|---:|
| 1 | `GD30_BOTH_p54_first15_any_gup010_raw` | +7 | 229 | 96.0699 |
| 2 | `D15_SELL_p0_brunch2_any_gup015_raw` | +6 | 230 | 96.087 |
| 3 | `D15_BOTH_p85_am1230_any_g028_raw` | +4 | 231 | 96.1039 |
| 4 | `GD40_BUY_p0_mid2_any_g038_raw` | +3 | 233 | 96.1373 |
| 5 | `D5_BOTH_p0_brunch2_any_g075_raw` | +3 | 235 | 96.1702 |
| 6 | `CR20_BOTH_p53_last45_htf_gup010_first` | +3 | 238 | 96.2185 |
| 7 | `CR35_BOTH_p59_last90_htf_gdn010_raw` | +2 | 240 | 96.25 |
| 8 | `CH_BOTH_p74_last120_htf_nogap_raw` | +2 | 241 | 96.2656 |
| 9 | `GD40_SELL_p56_mid2_htf_gdn010_raw` | +1 | 242 | 96.281 |
| 10 | `D15_BOTH_p0_all_any_g090_raw` | +1 | 243 | 96.2963 |
| 11 | `CR40_SELL_p60_last150_any_gup010_raw` | +1 | 244 | 96.3115 |
| 12 | `CR35_SELL_p54_am1130_any_gdn010_raw` | +1 | 245 | 96.3265 |
| 13 | `CR35_SELL_p53_am12_any_gdn025_raw` | +1 | 246 | 96.3415 |
| 14 | `CR35_SELL_p53_am1130_htf_g018_raw` | +1 | 247 | 96.3563 |
| 15 | `CR30_SELL_p61_mid2_any_nogap_raw` | +1 | 248 | 96.371 |
| 16 | `CR30_BUY_p58_mid_htf_gdn010_first` | +1 | 249 | 96.3855 |
| 17 | `CR30_BOTH_p60_am12_htf_nogap_first` | +1 | 250 | 96.4 |
| 18 | `CR20_BOTH_p61_pm_any_gup010_raw` | +1 | 251 | 96.4143 |
| 19 | `CF_T105_d5_cr20` | +1 | 252 | 96.4286 |
| 20 | `GD40_BOTH_p55_am12_any_gup015_first` | +1 | 253 | 96.0474 |

### `ACC_WIDE_P85`

| # | Tag | + | Desk3y | Hit |
|---:|---|---:|---:|---:|
| 1 | `GD40_SELL_p53_brunch2_any_g065_raw` | +12 | 278 | 89.9281 |
| 2 | `GD40_BOTH_p54_am1130_any_gup015_bestp` | +11 | 284 | 89.7887 |
| 3 | `CR30_BOTH_p61_mid_htf_nogap_raw` | +4 | 288 | 89.9306 |
| 4 | `GD40_BOTH_p0_pm_any_g018_raw` | +4 | 289 | 89.9654 |
| 5 | `D15_SELL_p74_earlypm_any_g010_raw` | +4 | 290 | 90.0 |
| 6 | `D5_BOTH_p0_brunch2_any_g075_raw` | +3 | 292 | 90.0685 |
| 7 | `GD40_BUY_p54_brunch2_any_nogap_raw` | +3 | 293 | 89.7611 |
| 8 | `CR20_BOTH_p53_last45_htf_gup010_first` | +2 | 295 | 89.8305 |
| 9 | `GD40_BUY_p0_brunch2_any_gup025_bestp` | +2 | 296 | 89.8649 |
| 10 | `CR30_BOTH_p58_latemid_any_gdn010_first` | +2 | 298 | 89.9329 |
| 11 | `CR30_BUY_p53_am12_any_nogap_first` | +2 | 300 | 90.0 |
| 12 | `CR35_SELL_p0_pm2_htf_gdn025_first` | +2 | 302 | 89.7351 |
| 13 | `GD40_SELL_p54_am11_any_g028_raw` | +1 | 302 | 89.7351 |
| 14 | `GD35_BUY_p55_open_any_gup010_raw` | +1 | 303 | 89.769 |
| 15 | `CH_BOTH_p74_last120_any_nogap_raw` | +1 | 303 | 89.769 |
| 16 | `CR30_BOTH_p0_last150_any_gdn050_first` | +1 | 304 | 89.8026 |
| 17 | `GD40_SELL_p55_am1230_any_gdn010_raw` | +1 | 304 | 89.8026 |
| 18 | `CR40_SELL_p56_am12_any_nogap_raw` | +1 | 305 | 89.8361 |

### `ACC_WIDE_P85B`

| # | Tag | + | Desk3y | Hit |
|---:|---|---:|---:|---:|
| 1 | `GD40_BOTH_p54_am1130_any_gup010_bestp` | +15 | 295 | 88.8136 |
| 2 | `GD40_SELL_p53_brunch2_any_g065_raw` | +10 | 295 | 88.8136 |
| 3 | `CR30_BOTH_p61_mid_htf_nogap_raw` | +4 | 299 | 88.9632 |
| 4 | `D5_BOTH_p0_brunch2_any_g075_raw` | +3 | 301 | 89.0365 |
| 5 | `GD40_BUY_p54_brunch2_any_nogap_raw` | +3 | 302 | 88.7417 |
| 6 | `CR20_BOTH_p53_last60_htf_gup010_first` | +3 | 305 | 88.8525 |
| 7 | `CR30_BOTH_p58_latemid_any_gdn010_first` | +2 | 307 | 88.9251 |
| 8 | `CR30_BUY_p53_am12_any_nogap_first` | +2 | 309 | 88.9968 |
| 9 | `GD40_BUY_p0_brunch2_any_gup020_bestp` | +2 | 310 | 88.7097 |
| 10 | `GD40_SELL_p54_am11_any_g028_raw` | +1 | 310 | 88.7097 |
| 11 | `GD40_SELL_p0_pm_any_gdn010_raw` | +1 | 310 | 88.7097 |
| 12 | `CR30_BOTH_p0_last150_any_gdn050_first` | +1 | 311 | 88.746 |
| 13 | `CF_T90_d5_any15` | +1 | 312 | 88.4615 |
| 14 | `GD40_SELL_p55_am1230_any_gdn010_raw` | +1 | 312 | 88.4615 |
| 15 | `GD40_BUY_p0_mid2_any_g015_raw` | +1 | 312 | 88.4615 |
| 16 | `CR40_SELL_p56_am12_any_nogap_raw` | +1 | 313 | 88.4984 |
| 17 | `CR35_SELL_p0_pm2_htf_gdn025_first` | +1 | 314 | 88.535 |
| 18 | `D15_BUY_p0_all_any_g022_raw` | +1 | 314 | 88.535 |

### `ACC_WIDE_P80`

| # | Tag | + | Desk3y | Hit |
|---:|---|---:|---:|---:|
| 1 | `GD40_BOTH_p54_brunch2_any_nogap_bestp` | +10 | 326 | 84.9693 |
| 2 | `D5_BOTH_p0_earlypm_any_g032_raw` | +7 | 327 | 85.0153 |
| 3 | `GD40_BOTH_p0_brunch2_any_gup025_bestp` | +5 | 328 | 85.061 |
| 4 | `GD40_SELL_p54_am1130_any_g010_bestp` | +4 | 328 | 85.061 |
| 5 | `CR30_BOTH_p57_latemid_any_gdn010_first` | +3 | 331 | 84.8943 |
| 6 | `CR30_BUY_p53_am12_any_nogap_first` | +2 | 333 | 84.985 |
| 7 | `GD40_BUY_p0_brunch2_any_gup020_bestp` | +2 | 334 | 84.7305 |
| 8 | `CR20_BOTH_p53_last60_htf_gup010_first` | +2 | 336 | 84.8214 |
| 9 | `CR30_BOTH_p56_last60_htf_g018_first` | +2 | 338 | 84.9112 |
| 10 | `GD35_BOTH_p0_earlypm_any_gup010_raw` | +2 | 339 | 84.9558 |
| 11 | `CR20_BOTH_p55_lunch_htf_gup015_first` | +2 | 341 | 84.7507 |
| 12 | `CR30_BUY_p0_mid2_any_gdn015_first` | +2 | 343 | 84.8397 |
| 13 | `GD40_SELL_p0_pm_any_gdn010_raw` | +1 | 343 | 84.8397 |
| 14 | `GD35_BUY_p55_open_any_gup010_raw` | +1 | 344 | 84.8837 |
| 15 | `D5_BOTH_p0_brunch2_any_g075_raw` | +1 | 345 | 84.9275 |
| 16 | `CR20_BOTH_p61_pm_any_gup010_raw` | +1 | 346 | 84.9711 |
| 17 | `GD35_BUY_p53_am1130_any_gup015_raw` | +2 | 347 | 84.7262 |
| 18 | `GD40_SELL_p53_mid_htf_g028_raw` | +1 | 348 | 84.7701 |
| 19 | `CR30_BOTH_p0_last150_any_gdn050_first` | +1 | 349 | 84.8138 |
| 20 | `GD40_BUY_p0_brunch2_any_g025_bestp` | +1 | 349 | 84.8138 |
| 21 | `CR40_SELL_p0_lunch_htf_gdn010_first` | +1 | 350 | 84.8571 |

### `ACC_WIDE_P75`

| # | Tag | + | Desk3y | Hit |
|---:|---|---:|---:|---:|
| 1 | `D5_BOTH_p0_earlypm_any_g032_raw` | +7 | 362 | 82.8729 |
| 2 | `GD40_BOTH_p0_brunch2_any_gup025_bestp` | +5 | 363 | 82.9201 |
| 3 | `GD40_SELL_p53_am1230_any_g028_first` | +7 | 365 | 82.7397 |
| 4 | `CR20_BOTH_p53_last60_htf_gup010_first` | +2 | 367 | 82.8338 |
| 5 | `CR30_BOTH_p56_last60_htf_g018_first` | +2 | 369 | 82.9268 |
| 6 | `GD40_SELL_p53_brunch2_any_gup015_bestp` | +3 | 371 | 82.7493 |
| 7 | `D5_BOTH_p0_brunch2_any_g075_raw` | +1 | 372 | 82.7957 |
| 8 | `CR40_SELL_p0_lunch_htf_gdn010_first` | +1 | 373 | 82.8418 |
| 9 | `CR30_BUY_p53_mid2_any_gdn010_first` | +1 | 374 | 82.8877 |
| 10 | `GD40_BOTH_p0_mid2_any_gup020_bestp` | +3 | 376 | 82.7128 |

## Hold

Phase-1 locked · Phase-2c held in `holding_accurate/` · P2d = new candidates.

JSON: `ACC_PHASE2D_KEEP_GOING.json`
