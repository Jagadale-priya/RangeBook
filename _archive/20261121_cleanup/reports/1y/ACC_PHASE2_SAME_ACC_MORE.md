# Phase-2 — more calls @ same accuracy

**Phase-1 HELD** (`accurate_desks.py` + 3y PASS). This report is research only.

Mined ≥85%: 1937 · perfect-3y: 947 · elapsed 185.6s

## Results

| Base desk | Range | Floor | Base 3y | New 3y | Δ | Hit | Candidate |
|---|---|---:|---:|---:|---:|---:|---|
| `ACC100_MULTI_V5` | `ACC_RANGE_98_100` | 100 | 141@100.0% | **146@100.0%** | +5 | 100.0 | `ACC100_MULTI_V6` |
| `ACC_WIDE_P92` | `ACC_RANGE_91_100` | 99.24 | 131@99.2366% | **154@99.3506%** | +23 | 99.3506 | `ACC_WIDE_P92_P2` |
| `ACC_WIDE_P90` | `ACC_RANGE_89_96` | 95.4 | 174@95.4023% | **193@95.8549%** | +19 | 95.8549 | `ACC_WIDE_P90_P2` |
| `ACC_WIDE_P85` | `ACC_RANGE_84_90` | 89.69 | 223@89.6861% | **250@90.0%** | +27 | 90.0 | `ACC_WIDE_P85_P2` |
| `ACC_WIDE_P85B` | `ACC_RANGE_81_89` | 88.4 | 250@88.4% | **257@88.716%** | +7 | 88.716 | `ACC_WIDE_P85B_P2` |

## Added streams

### `ACC100_MULTI_V5` → `ACC100_MULTI_V6`

| # | Tag | + | Desk3y | Hit |
|---:|---|---:|---:|---:|
| 1 | `GD40_SELL_p55_am1230_any_gdn025_raw` | +6 | 142 | 100.0 |
| 2 | `D15_BUY_p0_latemid_any_g025_raw` | +4 | 143 | 100.0 |
| 3 | `D15_BUY_p70_all_any_nogap_raw` | +3 | 143 | 100.0 |
| 4 | `CR35_BOTH_p57_last90_htf_gup025_bestp` | +3 | 146 | 100.0 |
| 5 | `GD40_SELL_p55_am1230_any_g050_raw` | +2 | 146 | 100.0 |
| 6 | `GD40_BUY_p0_earlypm_any_nogap_raw` | +2 | 146 | 100.0 |
| 7 | `GD30_SELL_p55_first45_any_g025_raw` | +1 | 146 | 100.0 |
| 8 | `GD30_BOTH_p57_open_any_g025_raw` | +1 | 146 | 100.0 |

### `ACC_WIDE_P92` → `ACC_WIDE_P92_P2`

| # | Tag | + | Desk3y | Hit |
|---:|---|---:|---:|---:|
| 1 | `D15_BUY_p0_latemid_any_g025_raw` | +18 | 135 | 99.2593 |
| 2 | `GD40_BUY_p0_earlypm_any_nogap_raw` | +7 | 141 | 99.2908 |
| 3 | `GD40_SELL_p55_am1230_any_gdn025_raw` | +6 | 143 | 99.3007 |
| 4 | `D15_BOTH_p65_mid_any_gdn030_raw` | +5 | 145 | 99.3103 |
| 5 | `D15_BUY_p70_all_any_nogap_raw` | +3 | 145 | 99.3103 |
| 6 | `CR35_SELL_p58_pm_htf_gup025_bestp` | +3 | 148 | 99.3243 |
| 7 | `GD30_SELL_p55_first45_any_g025_raw` | +2 | 148 | 99.3243 |
| 8 | `D15_BOTH_p70_latemid_any_g065_raw` | +2 | 150 | 99.3333 |
| 9 | `CR35_BOTH_p55_last90_any_gup040_bestp` | +2 | 152 | 99.3421 |
| 10 | `CR35_BOTH_p57_last90_htf_gup025_bestp` | +1 | 153 | 99.3464 |
| 11 | `CR20_BUY_p52_pm_htf_gup030_first` | +1 | 154 | 99.3506 |

### `ACC_WIDE_P90` → `ACC_WIDE_P90_P2`

| # | Tag | + | Desk3y | Hit |
|---:|---|---:|---:|---:|
| 1 | `D15_BUY_p0_latemid_any_g025_raw` | +13 | 177 | 95.4802 |
| 2 | `GD40_SELL_p55_am1230_any_g025_first` | +8 | 179 | 95.5307 |
| 3 | `GD40_BUY_p0_earlypm_any_nogap_raw` | +5 | 183 | 95.6284 |
| 4 | `D15_BUY_p70_all_any_nogap_raw` | +3 | 183 | 95.6284 |
| 5 | `CR35_SELL_p58_pm_htf_gup025_bestp` | +3 | 186 | 95.6989 |
| 6 | `D15_SELL_p0_am1230_any_gdn025_raw` | +2 | 187 | 95.7219 |
| 7 | `D15_BOTH_p70_latemid_any_g065_raw` | +2 | 189 | 95.7672 |
| 8 | `CR35_BOTH_p55_last90_any_gup040_bestp` | +2 | 191 | 95.8115 |
| 9 | `CR35_BOTH_p57_last90_htf_gup025_bestp` | +1 | 192 | 95.8333 |
| 10 | `CR20_BUY_p52_pm_htf_gup030_first` | +1 | 193 | 95.8549 |

### `ACC_WIDE_P85` → `ACC_WIDE_P85_P2`

| # | Tag | + | Desk3y | Hit |
|---:|---|---:|---:|---:|
| 1 | `D15_BUY_p0_latemid_any_g030_raw` | +8 | 224 | 89.7321 |
| 2 | `CR35_SELL_p0_earlypm_any_gdn025_first` | +9 | 233 | 89.6996 |
| 3 | `GD30_SELL_p0_earlypm_any_gup025_raw` | +7 | 235 | 89.7872 |
| 4 | `GD40_BUY_p0_mid_any_gup025_bestp` | +5 | 238 | 89.916 |
| 5 | `CR35_SELL_p57_all_htf_gup025_bestp` | +4 | 242 | 90.0826 |
| 6 | `D15_BOTH_p0_latemid_any_gup025_raw` | +9 | 245 | 89.7959 |
| 7 | `D15_BOTH_p85_all_any_g030_raw` | +4 | 245 | 89.7959 |
| 8 | `CR30_BUY_p0_mid_any_gdn025_first` | +2 | 247 | 89.8785 |
| 9 | `CR20_SELL_p55_mid_htf_gup025_raw` | +2 | 249 | 89.9598 |
| 10 | `GD40_SELL_p55_am1230_any_gdn025_raw` | +1 | 249 | 89.9598 |
| 11 | `D15_BUY_p70_all_any_nogap_raw` | +1 | 249 | 89.9598 |
| 12 | `CR20_BUY_p52_pm_htf_gup030_first` | +1 | 250 | 90.0 |

### `ACC_WIDE_P85B` → `ACC_WIDE_P85B_P2`

| # | Tag | + | Desk3y | Hit |
|---:|---|---:|---:|---:|
| 1 | `CR35_SELL_p55_mid_htf_g025_raw` | +3 | 253 | 88.5375 |
| 2 | `GD30_SELL_p0_earlypm_any_gup025_raw` | +2 | 253 | 88.5375 |
| 3 | `GD40_BUY_p0_mid_any_gup025_bestp` | +2 | 254 | 88.5827 |
| 4 | `CR40_BOTH_p57_last90_any_gup025_raw` | +1 | 255 | 88.6275 |
| 5 | `GD40_SELL_p55_am1230_any_gdn025_raw` | +1 | 255 | 88.6275 |
| 6 | `CR35_SELL_p0_earlypm_htf_gdn025_first` | +1 | 256 | 88.6719 |
| 7 | `CR30_BUY_p0_mid_any_gdn025_first` | +1 | 257 | 88.716 |

## Next

- Keep Phase-1 locked.
- Promote any candidate only after packaging + `confirm_accurate_desks_3y_match` still PASS for Phase-1.

JSON: `ACC_PHASE2_SAME_ACC_MORE.json`
