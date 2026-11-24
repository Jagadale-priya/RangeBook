# Phase-2b — deeper more calls @ same accuracy

**Phase-1 HELD.** Denser mine than Phase-2; more desks + day_side.

Mined ≥80%: 7433 · perfect-3y: 1948 · elapsed 428.2s

## Day-dedupe expands

| Desk | Floor | P1 3y | P2 3y | P2b 3y | Δ vs P1 | Δ vs P2 | Hit | Candidate |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `ACC100_MULTI_V5` | 100 | 141 | 146 | **163** | +22 | +17 | 100.0 | `ACC100_MULTI_V7` |
| `ACC_WIDE_P92` | 99.24 | 131 | 154 | **171** | +40 | +17 | 99.4152 | `ACC_WIDE_P92_P2B` |
| `ACC_WIDE_P90` | 95.4 | 174 | 193 | **213** | +39 | +20 | 95.7746 | `ACC_WIDE_P90_P2B` |
| `ACC_WIDE_P85` | 89.69 | 223 | 250 | **275** | +52 | +25 | 89.8182 | `ACC_WIDE_P85_P2B` |
| `ACC_WIDE_P85B` | 88.4 | 250 | 257 | **281** | +31 | +24 | 88.6121 | `ACC_WIDE_P85B_P2B` |
| `ACC_WIDE_P80` | 84.72 | 301 | — | **323** | +22 | — | 84.8297 | `ACC_WIDE_P80_P2B` |
| `ACC_WIDE_P75` | 82.71 | 347 | — | **360** | +13 | — | 83.0556 | `ACC_WIDE_P75_P2B` |

## Day-side expands

| Desk | Floor | P1 3y | P2b sides 3y | Δ | Hit | Candidate |
|---|---:|---:|---:|---:|---:|---|
| `ACC100_MULTI_V5_SIDES` | 100 | 141 | **164** | +23 | 100.0 | `ACC100_MULTI_V5_SIDES_P2B` |
| `ACC_WIDE_P92_SIDES` | 99.24 | 131 | **172** | +41 | 99.4186 | `ACC_WIDE_P92_SIDES_P2B` |

## Added streams (day mode)

### `ACC100_MULTI_V5`

| # | Tag | + | Desk3y | Hit |
|---:|---|---:|---:|---:|
| 1 | `D15_BUY_p0_first30_any_gup020_raw` | +25 | 148 | 100.0 |
| 2 | `GD30_SELL_p54_first45_any_gup020_raw` | +8 | 149 | 100.0 |
| 3 | `D15_BUY_p0_latemid_any_gup020_raw` | +8 | 150 | 100.0 |
| 4 | `GD40_BOTH_p55_earlypm_any_g020_raw` | +7 | 152 | 100.0 |
| 5 | `GD35_SELL_p54_open_any_gup030_first` | +3 | 153 | 100.0 |
| 6 | `D15_BUY_p70_all_any_nogap_raw` | +3 | 153 | 100.0 |
| 7 | `D15_BOTH_p65_open_any_g070_raw` | +3 | 153 | 100.0 |
| 8 | `CR35_BOTH_p57_last90_htf_gup025_bestp` | +3 | 156 | 100.0 |
| 9 | `GD40_SELL_p56_am1230_any_gdn020_raw` | +2 | 156 | 100.0 |
| 10 | `D15_SELL_p72_am1230_any_gdn020_raw` | +2 | 156 | 100.0 |
| 11 | `CR20_SELL_p57_lunch_htf_gup020_first` | +2 | 158 | 100.0 |
| 12 | `CR20_BOTH_p64_mid_any_nogap_raw` | +2 | 160 | 100.0 |
| 13 | `GD40_SELL_p55_mid_any_gdn040_raw` | +1 | 160 | 100.0 |
| 14 | `GD40_BUY_p0_earlypm_any_nogap_raw` | +1 | 160 | 100.0 |
| 15 | `GD30_BOTH_p57_open_any_g025_raw` | +1 | 160 | 100.0 |
| 16 | `GD30_BOTH_p54_am11_htf_gup055_first` | +1 | 161 | 100.0 |
| 17 | `D15_BUY_p0_latemid_any_g030_raw` | +1 | 161 | 100.0 |
| 18 | `CR30_BUY_p60_am1230_any_gdn020_first` | +1 | 162 | 100.0 |
| 19 | `CR20_BOTH_p56_last60_any_gup025_raw` | +1 | 163 | 100.0 |

### `ACC_WIDE_P92`

| # | Tag | + | Desk3y | Hit |
|---:|---|---:|---:|---:|
| 1 | `D15_BUY_p0_first30_any_gup020_raw` | +25 | 138 | 99.2754 |
| 2 | `D15_BUY_p0_latemid_any_gup020_raw` | +19 | 142 | 99.2958 |
| 3 | `GD30_SELL_p54_first45_any_gup020_raw` | +8 | 143 | 99.3007 |
| 4 | `GD40_BUY_p0_earlypm_any_nogap_raw` | +7 | 149 | 99.3289 |
| 5 | `D15_BOTH_p65_mid_any_gdn030_raw` | +7 | 151 | 99.3377 |
| 6 | `GD40_SELL_p55_am1230_any_gdn025_raw` | +6 | 153 | 99.3464 |
| 7 | `D15_BUY_p70_all_any_nogap_raw` | +3 | 153 | 99.3464 |
| 8 | `CR35_SELL_p58_pm_htf_gup025_bestp` | +3 | 156 | 99.359 |
| 9 | `CR20_BOTH_p54_last60_any_gup020_raw` | +3 | 159 | 99.3711 |
| 10 | `D15_SELL_p72_am1230_any_gdn020_raw` | +2 | 159 | 99.3711 |
| 11 | `D15_SELL_p72_all_any_g070_raw` | +2 | 161 | 99.3789 |
| 12 | `D15_BUY_p0_latemid_any_g030_raw` | +2 | 161 | 99.3789 |
| 13 | `D15_BOTH_p65_open_any_g070_raw` | +2 | 161 | 99.3789 |
| 14 | `CR20_SELL_p57_lunch_htf_gup020_first` | +2 | 163 | 99.3865 |
| 15 | `CR20_BOTH_p64_mid_any_nogap_raw` | +2 | 165 | 99.3939 |
| 16 | `GD40_SELL_p56_mid_any_gdn020_raw` | +1 | 165 | 99.3939 |
| 17 | `GD35_SELL_p54_open_any_gup030_first` | +1 | 166 | 99.3976 |
| 18 | `GD30_BOTH_p54_am11_htf_gup055_first` | +1 | 167 | 99.4012 |
| 19 | `CR35_SELL_p57_pm_htf_gup030_bestp` | +1 | 168 | 99.4048 |
| 20 | `CR35_BOTH_p57_last90_htf_gup025_bestp` | +1 | 169 | 99.4083 |
| 21 | `CR30_BUY_p60_am1230_any_gdn020_first` | +1 | 170 | 99.4118 |
| 22 | `CR20_BUY_p52_pm_htf_gup030_first` | +1 | 171 | 99.4152 |

### `ACC_WIDE_P90`

| # | Tag | + | Desk3y | Hit |
|---:|---|---:|---:|---:|
| 1 | `GD35_BOTH_p0_earlypm_any_gup020_raw` | +17 | 184 | 95.6522 |
| 2 | `D15_BUY_p0_latemid_any_gup020_raw` | +14 | 187 | 95.7219 |
| 3 | `GD30_SELL_p54_first45_any_g025_raw` | +10 | 188 | 95.7447 |
| 4 | `GD40_SELL_p55_am1230_any_g020_first` | +6 | 190 | 95.7895 |
| 5 | `GD35_BUY_p54_latemid_any_nogap_raw` | +5 | 193 | 95.8549 |
| 6 | `D15_SELL_p65_am1230_any_gdn020_raw` | +4 | 194 | 95.8763 |
| 7 | `D15_BUY_p70_all_any_nogap_raw` | +3 | 194 | 95.8763 |
| 8 | `D15_BUY_p0_latemid_any_g030_raw` | +3 | 194 | 95.8763 |
| 9 | `CR35_SELL_p58_pm_htf_gup025_bestp` | +3 | 197 | 95.9391 |
| 10 | `D15_BOTH_p82_am1230_htf_g020_raw` | +3 | 200 | 95.5 |
| 11 | `GD40_BUY_p0_earlypm_any_nogap_raw` | +2 | 201 | 95.5224 |
| 12 | `D15_SELL_p72_all_any_g070_raw` | +2 | 203 | 95.5665 |
| 13 | `CR35_BOTH_p56_last90_any_gup030_bestp` | +2 | 205 | 95.6098 |
| 14 | `GD35_SELL_p54_open_any_gup030_first` | +1 | 206 | 95.6311 |
| 15 | `GD30_SELL_p54_first45_any_gup020_raw` | +1 | 206 | 95.6311 |
| 16 | `GD30_BOTH_p54_am11_htf_gup055_first` | +1 | 207 | 95.6522 |
| 17 | `CR35_BOTH_p57_last90_htf_gup025_bestp` | +1 | 208 | 95.6731 |
| 18 | `CR30_SELL_p56_mid_htf_gup020_first` | +1 | 209 | 95.6938 |
| 19 | `CR30_BUY_p60_am1230_any_gdn020_first` | +1 | 210 | 95.7143 |
| 20 | `CR20_BUY_p52_pm_htf_gup030_first` | +1 | 211 | 95.7346 |
| 21 | `CR20_BOTH_p64_mid_any_nogap_raw` | +1 | 212 | 95.7547 |
| 22 | `CR20_BOTH_p56_last60_any_gup025_raw` | +1 | 213 | 95.7746 |

### `ACC_WIDE_P85`

| # | Tag | + | Desk3y | Hit |
|---:|---|---:|---:|---:|
| 1 | `GD40_SELL_p54_am11_any_g030_raw` | +9 | 226 | 89.823 |
| 2 | `GD35_SELL_p0_earlypm_any_gup020_raw` | +9 | 230 | 90.0 |
| 3 | `D15_BUY_p0_all_any_gup020_raw` | +25 | 234 | 89.7436 |
| 4 | `GD40_BOTH_p0_pm_any_g020_raw` | +7 | 236 | 89.8305 |
| 5 | `CR35_SELL_p0_earlypm_any_gdn025_first` | +7 | 243 | 90.1235 |
| 6 | `D15_BOTH_p85_all_any_g020_raw` | +15 | 247 | 89.8785 |
| 7 | `CR40_SELL_p54_am1230_any_gup020_bestp` | +6 | 253 | 89.7233 |
| 8 | `GD40_BUY_p0_mid_any_gup025_bestp` | +5 | 256 | 89.8438 |
| 9 | `GD40_SELL_p54_mid_any_gup020_bestp` | +4 | 258 | 89.9225 |
| 10 | `CR30_SELL_p57_lunch_htf_nogap_first` | +5 | 263 | 89.7338 |
| 11 | `D15_BUY_p0_latemid_any_g030_raw` | +3 | 263 | 89.7338 |
| 12 | `CR30_BUY_p0_mid_any_gdn020_first` | +3 | 266 | 89.8496 |
| 13 | `GD35_BUY_p54_mid_any_g055_raw` | +2 | 267 | 89.8876 |
| 14 | `GD40_BOTH_p56_am1230_any_g020_raw` | +2 | 267 | 89.8876 |
| 15 | `CR40_BOTH_p57_last90_any_gup025_raw` | +1 | 268 | 89.9254 |
| 16 | `GD30_BOTH_p54_am11_htf_gup055_first` | +1 | 269 | 89.9628 |
| 17 | `CR20_BUY_p52_pm_htf_gup030_first` | +1 | 270 | 90.0 |
| 18 | `GD35_BOTH_p54_am1230_any_gup020_first` | +4 | 272 | 89.7059 |
| 19 | `CR20_BOTH_p64_mid_any_nogap_raw` | +1 | 273 | 89.7436 |
| 20 | `CR20_SELL_p55_lunch_htf_gup020_first` | +1 | 274 | 89.781 |
| 21 | `CR40_BOTH_p54_am1130_any_nogap_first` | +1 | 275 | 89.8182 |

### `ACC_WIDE_P85B`

| # | Tag | + | Desk3y | Hit |
|---:|---|---:|---:|---:|
| 1 | `GD40_SELL_p54_am11_any_g030_raw` | +6 | 250 | 88.4 |
| 2 | `GD40_SELL_p0_pm_any_gdn020_raw` | +7 | 252 | 88.4921 |
| 3 | `GD40_SELL_p54_mid_any_gup020_bestp` | +6 | 255 | 88.6275 |
| 4 | `CR35_SELL_p0_lunch_htf_gdn025_raw` | +3 | 258 | 88.7597 |
| 5 | `D15_BUY_p0_all_any_gup020_raw` | +17 | 261 | 88.5057 |
| 6 | `CR40_SELL_p54_am1230_any_gup020_bestp` | +5 | 266 | 88.7218 |
| 7 | `GD40_BUY_p54_mid_any_nogap_raw` | +5 | 269 | 88.4758 |
| 8 | `GD35_SELL_p0_earlypm_any_gup020_raw` | +2 | 270 | 88.5185 |
| 9 | `GD40_BOTH_p56_am1230_any_g020_raw` | +2 | 270 | 88.5185 |
| 10 | `GD40_BUY_p0_mid_any_gup025_bestp` | +2 | 271 | 88.5609 |
| 11 | `CR40_BOTH_p57_last90_any_gup025_raw` | +1 | 272 | 88.6029 |
| 12 | `CR30_SELL_p57_lunch_htf_nogap_first` | +4 | 276 | 88.4058 |
| 13 | `GD30_BOTH_p54_am11_htf_gup055_first` | +1 | 277 | 88.4477 |
| 14 | `CR30_BUY_p60_am1230_any_gdn020_first` | +1 | 278 | 88.4892 |
| 15 | `CR20_BOTH_p64_mid_any_nogap_raw` | +1 | 279 | 88.5305 |
| 16 | `CR40_BOTH_p54_am1130_any_nogap_first` | +1 | 280 | 88.5714 |
| 17 | `CR20_BOTH_p55_mid_htf_gup020_first` | +1 | 281 | 88.6121 |

### `ACC_WIDE_P80`

| # | Tag | + | Desk3y | Hit |
|---:|---|---:|---:|---:|
| 1 | `GD40_BOTH_p0_mid_any_gup025_bestp` | +14 | 305 | 84.918 |
| 2 | `GD40_SELL_p54_am1130_any_g020_raw` | +12 | 306 | 84.9673 |
| 3 | `GD40_BOTH_p54_am1230_htf_gup020_bestp` | +5 | 309 | 84.7896 |
| 4 | `GD40_BOTH_p0_latemid_any_gup020_bestp` | +4 | 310 | 84.8387 |
| 5 | `GD40_BUY_p0_mid_any_g025_bestp` | +3 | 311 | 84.8875 |
| 6 | `GD40_BOTH_p0_earlypm_any_g020_raw` | +2 | 312 | 84.9359 |
| 7 | `CR35_SELL_p0_earlypm_any_gdn020_first` | +3 | 315 | 84.7619 |
| 8 | `CR40_SELL_p54_am1230_any_gup020_bestp` | +2 | 317 | 84.858 |
| 9 | `CR30_BOTH_p56_last60_htf_g020_first` | +2 | 319 | 84.953 |
| 10 | `CR20_BOTH_p55_lunch_htf_gup020_first` | +2 | 321 | 84.7352 |
| 11 | `GD40_BUY_p54_mid_any_nogap_raw` | +1 | 321 | 84.7352 |
| 12 | `CR40_BOTH_p54_am1130_any_nogap_first` | +1 | 322 | 84.7826 |
| 13 | `CR20_BOTH_p52_last60_any_gup025_raw` | +1 | 323 | 84.8297 |

### `ACC_WIDE_P75`

| # | Tag | + | Desk3y | Hit |
|---:|---|---:|---:|---:|
| 1 | `GD40_BOTH_p54_mid_any_nogap_bestp` | +12 | 350 | 82.8571 |
| 2 | `GD40_BOTH_p0_mid_any_gup025_bestp` | +6 | 351 | 82.906 |
| 3 | `GD40_BOTH_p0_latemid_any_gup020_bestp` | +3 | 351 | 82.906 |
| 4 | `CR35_SELL_p0_earlypm_any_gdn020_first` | +3 | 354 | 82.7684 |
| 5 | `GD40_SELL_p54_am11_htf_gdn030_raw` | +2 | 354 | 82.7684 |
| 6 | `CR40_SELL_p54_am1230_any_gup020_bestp` | +2 | 356 | 82.8652 |
| 7 | `CR30_BOTH_p56_last60_htf_g020_first` | +2 | 358 | 82.9609 |
| 8 | `GD40_BOTH_p54_am1230_htf_gup020_bestp` | +1 | 358 | 82.9609 |
| 9 | `CR40_BOTH_p54_am1130_any_nogap_first` | +1 | 359 | 83.0084 |
| 10 | `CR20_BOTH_p55_mid_htf_gup020_first` | +1 | 360 | 83.0556 |

## Hold

- Phase-1 locked.
- Phase-2 / 2b are candidates only until promote.

JSON: `ACC_PHASE2B_DEEPER_MORE.json`
