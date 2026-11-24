# DEEP logic — **blind prove on UNKNOWN 2026 1m candles**

## Which candles are new / unknown?

| Window | Dates | Role |
|---|---|---|
| TRAIN_2024 / TRAIN_2025 | 2024 + 2025 | used to **lock** blind micros |
| **UNK_2026A** | 2026-01-01 → 2026-08-05 | **unknown OOS** |
| **UNK_2026B** | 2026-08-06 → 2026-11-06 | **unknown OOS** |
| **UNK_FWD** | 2026-11-09 → 2026-11-16 | **unknown OOS** (latest local bars) |

No newer bars exist after 2026-11-16 in local store (today).

Prior `HELD_DEEP_1CPD` filtered cells using hold/FWD too — **not** a clean unknown proof.
This run locks `DEEP_BLIND_2024_2025_micros.pkl` on train only.

Blind micros: **253** · T1=20.0 · SL≤10.0 · path

## Blind accuracy on unknown

| Window | Days | Full calls | Full hit% | all_win | 1/day n | 1/day cover | 1/day hit% |
|---|---:|---:|---:|:---:|---:|---:|---:|
| **TRAIN_2024** | 247 | 512 | 100.0% | True | 247 | 100.0% | 100.0% |
| **TRAIN_2025** | 249 | 446 | 100.0% | True | 248 | 99.6% | 100.0% |
| **UNK_2026A** | 146 | 287 | 32.75% | False | 126 | 86.3% | 34.13% |
| **UNK_2026B** | 64 | 104 | 25.0% | False | 52 | 81.2% | 32.69% |
| **UNK_FWD_Nov9_16** | 5 | 9 | 22.22% | False | 4 | 80.0% | 25.0% |
| **UNK_ALL_2026** | 215 | 400 | 30.5% | False | 182 | 84.7% | 33.52% |

### Verdict (UNK_ALL_2026)

- Full path: **400** calls @ **30.5%** · all_win=False
- 1 call/day: **182** days (84.7% cover) @ **33.52%**

Unknown path losses (**278**):

- 2026-01-02 10:39 BUY bull_run2 prev sl=7.85 mfe=58.9 mae=10.2
- 2026-01-02 10:46 BUY bull_run3 cap8 sl=5.3 mfe=55.1 mae=14.0
- 2026-01-05 09:42 BUY belt_bull cap10 sl=10.0 mfe=83.2 mae=17.8
- 2026-01-06 10:42 BUY three_outside_up p60 sl=4.86 mfe=7.6 mae=73.5
- 2026-01-07 13:40 SELL marubozu_bear min_ps sl=7.85 mfe=6.3 mae=79.4
- 2026-01-08 13:52 SELL tweezer_top p75 sl=6.26 mfe=94.3 mae=31.1
- 2026-01-09 12:29 SELL bear_run3 p60 sl=8.22 mfe=64.8 mae=13.7
- 2026-01-12 10:16 SELL bear_engulf cap10 sl=10.0 mfe=77.0 mae=47.8
- 2026-01-12 13:21 BUY belt_bull prev sl=8.55 mfe=110.0 mae=15.9
- 2026-01-14 14:34 BUY bull_run2 cap8 sl=8.0 mfe=209.5 mae=8.9
- 2026-01-16 14:30 SELL dark_cloud p75 sl=7.5 mfe=183.0 mae=32.7
- 2026-01-19 13:36 SELL tweezer_top min_ps sl=5.8 mfe=18.9 mae=89.0
- 2026-01-21 09:53 SELL bear_engulf p60 sl=6.18 mfe=265.8 mae=21.7
- 2026-01-22 11:32 SELL tweezer_top p75 sl=5.14 mfe=78.5 mae=29.6
- 2026-01-23 11:02 SELL bear_run2 prev sl=8.55 mfe=88.6 mae=21.3

## Peeked HELD_DEEP on same unknown (contaminated — reference only)

- UNK_ALL_2026: full 400@100.0% · 1/day 209 cover=97.2% hit=100.0%
- UNK_FWD_Nov9_16: full 5@100.0% · 1/day 4 cover=80.0% hit=100.0%

Pack: `C:\Users\Priyanka\Agent\stock_signal_data\fno_validate\research\nifty_1m_scalp_t20_sl10_acc100\DEEP_BLIND_2024_2025_micros.pkl`
Elapsed: 124.4s
