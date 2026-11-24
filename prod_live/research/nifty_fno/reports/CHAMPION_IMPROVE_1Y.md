# NIFTY F&O champion improve · last 1y

**Window:** 2025-11-13 → 2026-11-13

Raw champion is kept **out** of the accurate proven book. This sweep only
asks whether tighter gates can rescue 5m/10m champion.

## champ_15m

Raw: n=39 hit=92.3% net=1288.00

| Gate | N | Hit | Net | OK≥70% |
|---|---:|---:|---:|---|
| accurate_champ | 32 | 96.9% | 1194.00 | Y |
| sell_only_strong | 18 | 94.4% | 629.00 | Y |
| live_like | 39 | 92.3% | 1288.00 | Y |
| p_up | 39 | 92.3% | 1288.00 | Y |
| first_only | 39 | 92.3% | 1288.00 | Y |
| tight_ext | 39 | 92.3% | 1288.00 | Y |
| buy_range_mixed | 22 | 90.9% | 697.00 | Y |

Best under rules: `accurate_champ` · n=32 hit=96.9% net=1194.00

## champ_5m

Raw: n=17 hit=35.3% net=-141.00

| Gate | N | Hit | Net | OK≥70% |
|---|---:|---:|---:|---|
| buy_range_mixed | 9 | 44.4% | 3.00 |  |
| sell_only_strong | 10 | 40.0% | -61.00 |  |
| accurate_champ | 13 | 38.5% | -92.00 |  |
| live_like | 17 | 35.3% | -141.00 |  |
| p_up | 17 | 35.3% | -141.00 |  |
| first_only | 17 | 35.3% | -141.00 |  |
| tight_ext | 17 | 35.3% | -141.00 |  |

Best under rules: `buy_range_mixed` · n=9 hit=44.4% net=3.00

## champ_10m

Raw: n=11 hit=36.4% net=-162.00

| Gate | N | Hit | Net | OK≥70% |
|---|---:|---:|---:|---|
| sell_only_strong | 6 | 50.0% | -20.00 |  |
| p_up | 10 | 40.0% | -117.00 |  |
| first_only | 10 | 40.0% | -117.00 |  |
| tight_ext | 10 | 40.0% | -117.00 |  |
| accurate_champ | 10 | 40.0% | -117.00 |  |
| live_like | 11 | 36.4% | -162.00 |  |
| buy_range_mixed | 5 | 20.0% | -125.00 |  |

Best under rules: `sell_only_strong` · n=6 hit=50.0% net=-20.00

## Verdict

- Accurate live research book stays **proven 15m (+ proven 10m fill)**.
- Promote a champion gate only if 5m/10m hold **hit ≥70%** with usable N.
