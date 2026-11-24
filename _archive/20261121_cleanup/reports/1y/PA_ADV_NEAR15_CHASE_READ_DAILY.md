# adv_near15_chase_read · daily (NIFTY 20 sessions)

**Window:** `2026-10-26` → `2026-11-20`
**Cfg:** `sr_gate=adv_near_wall` · `near_wall_max_R=1.5` · `sl_kill=chase_v1` · `candle_entry=read_v3` · `trail=pin_protect`
**Live lock unchanged:** `adv_near_wall_10` (this is research-only).

## Totals

- **N=24** hit=**91.67%** avgR=**0.860** sum=**319.65**
- Hard SL=2 · trail_sl=22 · time=0

## Per day summary

| Day | N | Hit% | Sum pts | AvgR | W/L | Hard SL | Snapshot |
|---|---:|---:|---:|---:|---|---:|---|
| 2026-10-26 | 1 | 100.0 | 42.00 | 2.205 | 1/0 | 0 | 13:09 B/BREAK_HOLD R=+2.21 trail_sl |
| 2026-10-27 | 4 | 75.0 | 40.90 | 0.719 | 3/1 | 1 | 10:10 B/OR_RETEST R=-1.00 sl; 10:33 B/BREAK_HOLD R=+0.76 trail_sl; 11:47 B/SWEEP_RECLAIM R=+0.47 trail_sl; 12:36 B/OR_RETEST R=+2.65 trail_sl |
| 2026-10-28 | 0 | — | 0 | — | — | 0 | — |
| 2026-10-29 | 0 | — | 0 | — | — | 0 | — |
| 2026-10-30 | 1 | 100.0 | 10.30 | 0.572 | 1/0 | 0 | 12:18 B/BREAK_HOLD R=+0.57 trail_sl |
| 2026-11-02 | 2 | 100.0 | 33.80 | 1.095 | 2/0 | 0 | 10:03 B/SWEEP_RECLAIM R=+1.28 trail_sl; 12:09 B/OR_RETEST R=+0.91 trail_sl |
| 2026-11-03 | 0 | — | 0 | — | — | 0 | — |
| 2026-11-04 | 0 | — | 0 | — | — | 0 | — |
| 2026-11-05 | 0 | — | 0 | — | — | 0 | — |
| 2026-11-06 | 1 | 100.0 | 13.20 | 0.822 | 1/0 | 0 | 11:53 B/OR_RETEST R=+0.82 trail_sl |
| 2026-11-08 | 0 | — | 0 | — | — | 0 | — |
| 2026-11-09 | 1 | 100.0 | 11.30 | 0.751 | 1/0 | 0 | 13:06 S/SWEEP_RECLAIM R=+0.75 trail_sl |
| 2026-11-11 | 0 | — | 0 | — | — | 0 | — |
| 2026-11-12 | 1 | 100.0 | 10.40 | 0.605 | 1/0 | 0 | 09:57 B/OR_RETEST R=+0.60 trail_sl |
| 2026-11-13 | 1 | 100.0 | 9.00 | 0.429 | 1/0 | 0 | 10:31 B/BREAK_HOLD R=+0.43 trail_sl |
| 2026-11-16 | 4 | 100.0 | 52.00 | 1.025 | 4/0 | 0 | 11:06 S/SWEEP_RECLAIM R=+1.42 trail_sl; 12:07 B/BREAK_HOLD R=+1.18 trail_sl; 13:26 S/SWEEP_RECLAIM R=+0.96 trail_sl; 13:44 S/BREAK_HOLD R=+0.54 trail_sl |
| 2026-11-17 | 2 | 50.0 | -10.20 | -0.161 | 1/1 | 1 | 12:12 B/BREAK_HOLD R=-1.00 sl; 14:18 B/SWEEP_RECLAIM R=+0.68 trail_sl |
| 2026-11-18 | 4 | 100.0 | 75.95 | 1.088 | 4/0 | 0 | 10:39 S/SWEEP_RECLAIM R=+0.89 trail_sl; 11:35 S/SWEEP_RECLAIM R=+1.02 trail_sl; 11:52 S/SWEEP_RECLAIM R=+1.45 trail_sl; 13:00 S/BREAK_HOLD R=+0.99 trail_sl |
| 2026-11-19 | 1 | 100.0 | 4.35 | 0.378 | 1/0 | 0 | 10:05 B/OR_RETEST R=+0.38 trail_sl |
| 2026-11-20 | 1 | 100.0 | 26.65 | 1.681 | 1/0 | 0 | 10:21 B/SWEEP_RECLAIM R=+1.68 trail_sl |

## Call detail by day

### 2026-10-26  (n=1)
| Time | Side | Setup | Entry | SL | Risk | Pts | R | Exit | 1R | Why |
|---|---|---|---:|---:|---:|---:|---:|---|---|---|
| 13:09 | BUY | BREAK_HOLD | 22611.0 | 22592.0 | 19.1 | +42.0 | +2.205 | trail_sl | True | close 22611.0 > swing_hi 22607.1 · SL under prev_low=22592.7/swing_lo=22592.7 ·  |

### 2026-10-27  (n=4)
| Time | Side | Setup | Entry | SL | Risk | Pts | R | Exit | 1R | Why |
|---|---|---|---:|---:|---:|---:|---:|---|---|---|
| 10:10 | BUY | OR_RETEST | 22781.3 | 22761.6 | 19.7 | -19.7 | -1.000 | sl | False | retest OR_hi 22767.5 after break · SL under prev_low=22768.0/swing_lo=22762.3 ·  |
| 10:33 | BUY | BREAK_HOLD | 22738.8 | 22719.2 | 19.5 | +14.8 | +0.756 | trail_sl | True | close 22738.8 > swing_hi 22732.8 · SL under prev_low=22721.5/swing_lo=22720.0 ·  |
| 11:47 | BUY | SWEEP_RECLAIM | 22756.5 | 22744.1 | 12.4 | +5.8 | +0.466 | trail_sl | True | swept 22743.9 < prev_lo 22744.8, reclaim close · SL under prev_low=22744.8/swing |
| 12:36 | BUY | OR_RETEST | 22774.7 | 22759.6 | 15.1 | +40.0 | +2.652 | trail_sl | True | retest OR_hi 22767.5 after break · SL under prev_low=22766.4/swing_lo=22760.3 ·  |

### 2026-10-28  (n=0)
_No trades_

### 2026-10-29  (n=0)
_No trades_

### 2026-10-30  (n=1)
| Time | Side | Setup | Entry | SL | Risk | Pts | R | Exit | 1R | Why |
|---|---|---|---:|---:|---:|---:|---:|---|---|---|
| 12:18 | BUY | BREAK_HOLD | 23089.5 | 23071.5 | 18.0 | +10.3 | +0.572 | trail_sl | True | close 23089.5 > swing_hi 23085.7 · SL under prev_low=23078.2/swing_lo=23072.3 ·  |

### 2026-11-02  (n=2)
| Time | Side | Setup | Entry | SL | Risk | Pts | R | Exit | 1R | Why |
|---|---|---|---:|---:|---:|---:|---:|---|---|---|
| 10:03 | BUY | SWEEP_RECLAIM | 23302.2 | 23291.1 | 11.1 | +14.1 | +1.276 | trail_sl | True | swept 23290.6 < prev_lo 23293.0, reclaim close · SL under prev_low=23293.0/swing |
| 12:09 | BUY | OR_RETEST | 23322.5 | 23301.0 | 21.6 | +19.7 | +0.914 | trail_sl | True | retest OR_hi 23317.0 after break · SL under prev_low=23309.3/swing_lo=23301.8 ·  |

### 2026-11-03  (n=0)
_No trades_

### 2026-11-04  (n=0)
_No trades_

### 2026-11-05  (n=0)
_No trades_

### 2026-11-06  (n=1)
| Time | Side | Setup | Entry | SL | Risk | Pts | R | Exit | 1R | Why |
|---|---|---|---:|---:|---:|---:|---:|---|---|---|
| 11:53 | BUY | OR_RETEST | 24597.1 | 24581.0 | 16.1 | +13.2 | +0.822 | trail_sl | True | retest OR_hi 24582.0 after break · SL under prev_low=24581.8/swing_lo=24581.8 ·  |

### 2026-11-08  (n=0)
_No trades_

### 2026-11-09  (n=1)
| Time | Side | Setup | Entry | SL | Risk | Pts | R | Exit | 1R | Why |
|---|---|---|---:|---:|---:|---:|---:|---|---|---|
| 13:06 | SELL | SWEEP_RECLAIM | 24953.2 | 24968.2 | 15.1 | +11.3 | +0.751 | trail_sl | True | swept 24966.0 > prev_hi 24963.7, reclaim close · SL above prev_high=24963.7/swin |

### 2026-11-11  (n=0)
_No trades_

### 2026-11-12  (n=1)
| Time | Side | Setup | Entry | SL | Risk | Pts | R | Exit | 1R | Why |
|---|---|---|---:|---:|---:|---:|---:|---|---|---|
| 09:57 | BUY | OR_RETEST | 25361.2 | 25344.0 | 17.2 | +10.4 | +0.605 | trail_sl | True | retest OR_hi 25355.8 after break · SL under prev_low=25348.5/swing_lo=25344.8 ·  |

### 2026-11-13  (n=1)
| Time | Side | Setup | Entry | SL | Risk | Pts | R | Exit | 1R | Why |
|---|---|---|---:|---:|---:|---:|---:|---|---|---|
| 10:31 | BUY | BREAK_HOLD | 25207.5 | 25186.5 | 21.0 | +9.0 | +0.429 | trail_sl | True | close 25207.5 > swing_hi 25203.7 · SL under prev_low=25192.7/swing_lo=25187.2 ·  |

### 2026-11-16  (n=4)
| Time | Side | Setup | Entry | SL | Risk | Pts | R | Exit | 1R | Why |
|---|---|---|---:|---:|---:|---:|---:|---|---|---|
| 11:06 | SELL | SWEEP_RECLAIM | 25241.3 | 25248.8 | 7.5 | +10.6 | +1.416 | trail_sl | True | swept 25249.2 > prev_hi 25248.0, reclaim close · SL above prev_high=25248.0/swin |
| 12:07 | BUY | BREAK_HOLD | 25262.2 | 25241.5 | 20.6 | +24.4 | +1.182 | trail_sl | True | close 25262.2 > swing_hi 25259.4 · SL under prev_low=25248.6/swing_lo=25242.2 ·  |
| 13:26 | SELL | SWEEP_RECLAIM | 25249.0 | 25259.5 | 10.4 | +10.0 | +0.957 | trail_sl | True | swept 25255.6 > prev_hi 25254.0, reclaim close · SL above prev_high=25254.0/swin |
| 13:44 | SELL | BREAK_HOLD | 25243.3 | 25256.3 | 12.9 | +7.0 | +0.544 | trail_sl | True | close 25243.3 < swing_lo 25245.7 · SL above prev_high=25254.5/swing_hi=25255.5 · |

### 2026-11-17  (n=2)
| Time | Side | Setup | Entry | SL | Risk | Pts | R | Exit | 1R | Why |
|---|---|---|---:|---:|---:|---:|---:|---|---|---|
| 12:12 | BUY | BREAK_HOLD | 25493.2 | 25473.8 | 19.4 | -19.4 | -1.000 | sl | False | close 25493.2 > swing_hi 25491.1 · SL under prev_low=25481.8/swing_lo=25474.5 ·  |
| 14:18 | BUY | SWEEP_RECLAIM | 25451.2 | 25437.5 | 13.7 | +9.2 | +0.678 | trail_sl | True | swept 25436.8 < prev_lo 25438.2, reclaim close · SL under prev_low=25438.2/swing |

### 2026-11-18  (n=4)
| Time | Side | Setup | Entry | SL | Risk | Pts | R | Exit | 1R | Why |
|---|---|---|---:|---:|---:|---:|---:|---|---|---|
| 10:39 | SELL | SWEEP_RECLAIM | 25245.4 | 25264.9 | 19.5 | +17.4 | +0.892 | trail_sl | True | swept 25251.7 > prev_hi 25249.8, reclaim close · SL above prev_high=25249.8/swin |
| 11:35 | SELL | SWEEP_RECLAIM | 25262.1 | 25282.7 | 20.6 | +20.9 | +1.017 | trail_sl | True | swept 25272.8 > prev_hi 25271.4, reclaim close · SL above prev_high=25271.4/swin |
| 11:52 | SELL | SWEEP_RECLAIM | 25253.0 | 25264.0 | 10.9 | +15.8 | +1.447 | trail_sl | True | swept 25259.5 > prev_hi 25258.0, reclaim close · SL above prev_high=25258.0/swin |
| 13:00 | SELL | BREAK_HOLD | 25181.0 | 25202.8 | 21.9 | +21.8 | +0.995 | trail_sl | True | close 25181.0 < swing_lo 25184.5 · SL above prev_high=25201.9/swing_hi=25202.1 · |

### 2026-11-19  (n=1)
| Time | Side | Setup | Entry | SL | Risk | Pts | R | Exit | 1R | Why |
|---|---|---|---:|---:|---:|---:|---:|---|---|---|
| 10:05 | BUY | OR_RETEST | 25275.1 | 25263.6 | 11.5 | +4.3 | +0.378 | trail_sl | True | retest OR_hi 25255.6 after break · SL under prev_low=25264.3/swing_lo=25264.3 ·  |

### 2026-11-20  (n=1)
| Time | Side | Setup | Entry | SL | Risk | Pts | R | Exit | 1R | Why |
|---|---|---|---:|---:|---:|---:|---:|---|---|---|
| 10:21 | BUY | SWEEP_RECLAIM | 25500.0 | 25484.2 | 15.8 | +26.6 | +1.681 | trail_sl | True | swept 25476.8 < prev_lo 25485.0, reclaim close · SL under prev_low=25485.0/swing |

