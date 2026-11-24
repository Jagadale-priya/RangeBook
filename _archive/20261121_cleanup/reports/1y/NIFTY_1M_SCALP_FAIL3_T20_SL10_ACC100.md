# NIFTY 1m — why calls fail (prior-3) + **ACC100 T1=20 SL≤10**

Constraints: **target 20 (>15)** · **SL max 10** · path = target before SL · max calls under 100%.

## Why failures happen

Analyze baseline (any SL≤10 style): **37988** calls · hit **28.46%** · losses **27178** (of which MFE≥20 after SL-first: **17620**).

### Failure signals (more common in losses than wins)

| Feature | In losses% | In wins% | Δ |
|---|---:|---:|---:|
| NOT close_ok | 44.1 | 38.5 | 5.6 |
| adv_hi | 36.7 | 31.5 | 5.2 |
| fail_risk | 71.9 | 69.8 | 2.1 |
| pre3_rej>=2 | 11.4 | 10.5 | 0.9 |
| pre3_opp>=2 | 42.2 | 43.0 | -0.8 |
| pre3_weak_struct | 58.4 | 59.7 | -1.3 |

### Top loss prior-3 stacks (dir of candle-3 → candle-1 before signal)

`[('up_dn_up', 4736), ('dn_up_dn', 4633), ('dn_dn_up', 3848), ('up_up_dn', 3747), ('up_up_up', 2471), ('dn_up_up', 2458), ('dn_dn_dn', 2436), ('up_dn_dn', 2402)]`

Win stacks: `[('up_dn_up', 1825), ('dn_up_dn', 1812), ('dn_dn_up', 1566), ('up_up_dn', 1538), ('dn_dn_dn', 1009), ('up_up_up', 986), ('dn_up_up', 963), ('up_dn_dn', 952)]`

- Loss hours: `[('12', 4864), ('11', 4847), ('14+', 4838), ('13', 4815), ('10', 4691), ('09', 3123)]`
- Loss VIX: `[('NORMAL', 14272), ('LOW', 9835), ('ELEVATED', 2450), ('HIGH', 361), ('UNK', 260)]`
- Loss patterns: `[('bull_run2', 4429), ('bear_run2', 4119), ('bull_run3', 2818), ('bear_run3', 2555), ('bull_engulf', 2419), ('bear_engulf', 2281)]`
- Loss struct2: `[('break_hi_hold', 8567), ('break_lo_hold', 8129), ('hold_above_lo', 3398), ('hold_under_hi', 3276), ('cut_lo', 1013)]`
- Loss avg MAE/MFE: 70.01 / 55.01

## Anti-fail filter lift (still not 100% alone)

| Gate | Analyze | Hold |
|---|---|---|
| `raw` | 37988@28.46% | 16263@29.62% |
| `no_fail_risk` | 10895@29.97% | 5037@31.86% |
| `opp_le1` | 21876@28.19% | 9810@29.26% |
| `opp0_close_ok` | 2537@31.02% | 1355@32.47% |
| `opp0_advlo_b70` | 1048@33.4% | 629@33.39% |
| `strong_opp0` | 596@33.39% | 370@31.35% |
| `very_strong_opp0` | 264@34.47% | 151@37.75% |
| `vs_opp0_advlo_vix` | 223@33.18% | 110@33.64% |
| `vs_breakhold_opp0` | 287@34.49% | 166@38.55% |

## ACC100 books (100% on 2024 + 2025 + hold 2026 + FWD, SL≤10, T1=20)

| Book | Micros | Total | 2024 | 2025 | Hold | FWD | all_win |
|---|---:|---:|---|---|---|---|:---:|
| **ACC100_SOFT** | 3 | 15 | 6@100.0% | 6@100.0% | 3@100.0% | 0@0.0% | True |
| **ACC100_NOFAIL** | 3 | 17 | 8@100.0% | 6@100.0% | 3@100.0% | 0@0.0% | True |
| **ACC100_PRE3** | 5 | 23 | 10@100.0% | 8@100.0% | 5@100.0% | 0@0.0% | True |
| **ACC100_PRE3_DENSE** | 18 | 67 | 39@100.0% | 21@100.0% | 7@100.0% | 0@0.0% | True |
| **ACC100_PRE3_RAW** | 72 | 264 | 156@100.0% | 84@100.0% | 24@100.0% | 0@0.0% | True |
| **ACC100_VS** | 1 | 4 | 2@100.0% | 1@100.0% | 1@100.0% | 0@0.0% | True |
| **ACC100_STRONG** | 1 | 4 | 2@100.0% | 1@100.0% | 1@100.0% | 0@0.0% | True |

**Best densest 100% book: `ACC100_PRE3_RAW`** (264 calls).

### Micros

- `sig` cal=2 l3m=1 hold=3 fwd=0 avgSL=9.02 · `('engulf', 'BUY', 1, 'mid', 'b70+', 'sl12-16', 'adv_lo', 'stdn_dn')`
- `sig` cal=3 l3m=1 hold=2 fwd=0 avgSL=7.69 · `('P3', 'SELL', 'up_dn_up', 'hold_under_hi', 'adv_mid', 'ELEVATED', '09')`
- `p60` cal=3 l3m=2 hold=1 fwd=0 avgSL=4.09 · `('bear_run2', 'SELL', 'balanced', 1, 'midday', 'b45+', 'sl4-8', 'mid', 'adv_lo', 'ba>0.5',`
- `cap8` cal=3 l3m=3 hold=0 fwd=0 avgSL=8.0 · `('GEOM', 'BUY', 'reversal', 0, 'early', 'b<45', 'sl12-16', 'lo', 'adv_lo', 'ba<0.5', 'stdn`
- `sig` cal=2 l3m=1 hold=2 fwd=0 avgSL=5.1 · `('GEOM', 'SELL', 'continuation', 1, 'midday', 'b70+', 'sl4-8', 'mid', 'adv_mid', 'ba>0.5',`
- `prev` cal=2 l3m=1 hold=2 fwd=0 avgSL=8.73 · `('three_outside_dn', 'SELL', 'balanced', 'morning', 'b45+', 'sl8-12', 'adv_lo')`
- `prev` cal=2 l3m=1 hold=2 fwd=0 avgSL=9.55 · `('bear_run3', 'SELL', 'reversal', 'midday', 'b55+', 'sl8-12', 'adv_hi')`
- `cap10` cal=2 l3m=1 hold=2 fwd=0 avgSL=9.87 · `('GEOM', 'BUY', 'reversal', 1, 'morning', 'b70+', 'sl8-12', 'mid', 'adv_lo', 'ba<0.5', 'st`
- `prev` cal=2 l3m=2 hold=1 fwd=0 avgSL=6.38 · `('GEOM', 'BUY', 'reversal', 1, 'early', 'b55+', 'sl4-8', 'mid', 'adv_hi', 'ba<0.5', 'stdn_`
- `p75` cal=2 l3m=2 hold=1 fwd=0 avgSL=9.34 · `('bull_engulf', 'BUY', 'balanced', 1, 'midday', 'b70+', 'sl12-16', 'mid', 'adv_lo', 'ba>0.`
- `p75` cal=2 l3m=2 hold=1 fwd=0 avgSL=9.35 · `('bear_kicker', 'SELL', 'morn', 1, 'b70+', 'sl12-16', 'adv_lo')`
- `sig` cal=4 l3m=1 hold=0 fwd=0 avgSL=8.0 · `('belt_maru', 'BUY', 'balanced', 0, 'am', 'b70+', 'sl16-20', 'adv_mid')`
- `sig` cal=3 l3m=2 hold=0 fwd=0 avgSL=8.15 · `('GEOM', 'BUY', 'reversal', 1, 'morning', 'b70+', 'sl12-16', 'lo', 'adv_lo', 'ba>0.8', 'st`
- `p75` cal=3 l3m=2 hold=0 fwd=0 avgSL=9.33 · `('three_outside_dn', 'SELL', 'continuation', 'midday', 'b55+', 'sl12-16', 'adv_lo')`
- `p75` cal=2 l3m=1 hold=1 fwd=0 avgSL=7.07 · `('GEOM', 'BUY', 'reversal', 1, 'early', 'b45+', 'sl8-12', 'lo', 'adv_hi', 'ba>0.5', 'stdn_`
- `p75` cal=2 l3m=1 hold=1 fwd=0 avgSL=7.49 · `('bull_run2', 'BUY', 'continuation', 0, 'morning', 'b<45', 'sl8-12', 'hi', 'adv_mid', 'ba<`
- `p75` cal=2 l3m=1 hold=1 fwd=0 avgSL=7.64 · `('rising_3_methods', 'BUY', 'morn', 1, 'b<45', 'sl8-12', 'adv_lo')`
- `cap8` cal=2 l3m=1 hold=1 fwd=0 avgSL=8.0 · `('bull_engulf', 'BUY', 'reversal', 0, 'early', 'b55+', 'sl12-16', 'mid', 'adv_mid', 'ba>0.`
- `sig` cal=2 l3m=1 hold=1 fwd=0 avgSL=8.35 · `('three', 'BUY', 1, 'close', 'b55+', 'sl16-20', 'adv_lo', 'stdn_up')`
- `prev` cal=2 l3m=1 hold=1 fwd=0 avgSL=9.42 · `('bear_run2', 'SELL', 'balanced', 'early', 'b45+', 'sl8-12', 'adv_hi')`
- `p60` cal=2 l3m=1 hold=1 fwd=0 avgSL=9.75 · `('runs', 'BUY', 0, 'morn', 'b45+', 'sl16-20', 'adv_hi', 'stup_up')`
- `cap10` cal=2 l3m=1 hold=1 fwd=0 avgSL=10.0 · `('GEOM', 'BUY', 'reversal', 0, 'morning', 'b<45', 'sl12-16', 'lo', 'adv_mid', 'ba<0.5', 's`
- `p60` cal=2 l3m=2 hold=0 fwd=0 avgSL=4.0 · `('GEOM', 'BUY', 'reversal', 0, 'morning', 'b45+', 'sl4-8', 'lo', 'adv_mid', 'ba>0.5', 'std`
- `p60` cal=3 l3m=1 hold=0 fwd=0 avgSL=5.6 · `('tweezer_top', 'SELL', 'reversal', 'early', 'b55+', 'sl8-12', 'adv_hi')`
- `p60` cal=3 l3m=1 hold=0 fwd=0 avgSL=5.98 · `('GEOM', 'SELL', 'balanced', 1, 'late', 'b45+', 'sl8-12', 'mid', 'adv_lo', 'ba<0.5', 'stup`
- `cap8` cal=2 l3m=2 hold=0 fwd=0 avgSL=8.0 · `('marubozu_bull', 'BUY', 'reversal', 1, 'midday', 'b70+', 'sl8-12', 'hi', 'adv_lo', 'ba>0.`
- `p75` cal=2 l3m=2 hold=0 fwd=0 avgSL=9.58 · `('GEOM', 'BUY', 'continuation', 1, 'late', 'b70+', 'sl12-16', 'mid', 'adv_lo', 'ba>0.8', '`
- `p75` cal=3 l3m=1 hold=0 fwd=0 avgSL=9.67 · `('SLOT', 'BUY', 'mid', 'reversal', 0, 'b<45', 'sl12-16', 'adv_hi')`
- `cap10` cal=2 l3m=2 hold=0 fwd=0 avgSL=10.0 · `('bull_engulf', 'BUY', 'continuation', 1, 'early', 'b70+', 'sl12-16', 'hi', 'adv_mid', 'ba`
- `cap10` cal=3 l3m=1 hold=0 fwd=0 avgSL=10.0 · `('bear_run2', 'SELL', 'reversal', 0, 'early', 'b45+', 'sl16-20', 'mid', 'adv_hi', 'ba<0.5'`
- `cap10` cal=3 l3m=1 hold=0 fwd=0 avgSL=10.0 · `('GEOM', 'BUY', 'reversal', 0, 'morning', 'b70+', 'sl12-16', 'lo', 'adv_lo', 'ba>0.5', 'st`
- `p60` cal=2 l3m=1 hold=0 fwd=0 avgSL=4.01 · `('tweezer_top', 'SELL', 'reversal', 'early', 'b55+', 'sl4-8', 'adv_lo')`
- `p60` cal=2 l3m=1 hold=0 fwd=0 avgSL=4.21 · `('bull_run3', 'BUY', 'continuation', 1, 'midday', 'b55+', 'sl4-8', 'hi', 'adv_hi', 'ba>0.8`
- `p60` cal=2 l3m=1 hold=0 fwd=0 avgSL=4.27 · `('bull_engulf', 'BUY', 'balanced', 0, 'morning', 'b45+', 'sl4-8', 'mid', 'adv_hi', 'ba>0.5`
- `min_ps` cal=2 l3m=1 hold=0 fwd=0 avgSL=4.72 · `('kick', 'SELL', 0, 'close', 'b<45', 'sl4-8', 'adv_hi', 'stdn_up')`
- `min_ps` cal=2 l3m=1 hold=0 fwd=0 avgSL=4.82 · `('three_outside_up', 'BUY', 'balanced', 1, 'midday', 'b<45', 'sl4-8', 'hi', 'adv_hi', 'ba<`
- `sig` cal=2 l3m=1 hold=0 fwd=0 avgSL=4.97 · `('GEOM', 'BUY', 'continuation', 1, 'midday', 'b45+', 'sl4-8', 'mid', 'adv_hi', 'ba<0.5', '`
- `sig` cal=2 l3m=1 hold=0 fwd=0 avgSL=5.15 · `('GEOM', 'BUY', 'reversal', 1, 'early', 'b70+', 'sl4-8', 'mid', 'adv_lo', 'ba<0.5', 'stdn_`
- `sig` cal=2 l3m=1 hold=0 fwd=0 avgSL=5.5 · `('bull_run3', 'BUY', 'continuation', 0, 'morning', 'b55+', 'sl4-8', 'mid', 'adv_lo', 'ba<0`
- `sig` cal=2 l3m=1 hold=0 fwd=0 avgSL=5.52 · `('FAM', 'three', 'SELL', 'reversal', 1, 'early', 'adv_hi', 'sl4-8')`

Pack: `C:\Users\Priyanka\Agent\stock_signal_data\fno_validate\research\nifty_1m_scalp_t20_sl10_acc100`
Elapsed: 108.8s
