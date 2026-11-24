# NIFTY — Oracle T15·EMA34 vs **model scores** (last 5 sessions)

> When Oracle T15 fires, what was the trained model `p_t1` / decision
> on **1m · 5m · 10m · 15m** candles at that same time?

Sessions **2026-11-09 → 2026-11-16**. Oracle entries **1022** · scored **40**.
Model: `fno_model` NIFTY pack available=**True** · fno_clip_t1_2.5.
Note: Kite token expired. Add KITE_USER_ID, KITE_PASSWORD, KITE_TOTP_SECRET for auto refresh, or run: py kite_login.py

## How to read

- **Oracle** = textbook pattern entry · EMA34 trail · T15 win/loss
- **p(T1)%** = model probability for Oracle’s side (force_side)
- **decision** = model ticket side (BUY/SELL/HOLD)
- **agree** = model decision matches Oracle side (or p(T1)≥55% if HOLD)
- **candle** = session-model candle_score feature on that TF

## 1) Average model p(T1) when Oracle wins vs loses

| TF | Win avg p(T1)% | n | Lose avg p(T1)% | n | Agree% on wins | Agree% on loses |
|---|---:|---:|---:|---:|---:|---:|
| **1m** | **43.6** | 14 | 44.8 | 26 | 0.0 | 0.0 |
| **5m** | **47.8** | 14 | 47.6 | 26 | 0.0 | 0.0 |
| **10m** | **48.1** | 14 | 47.9 | 26 | 0.0 | 0.0 |
| **15m** | **47.6** | 14 | 47.9 | 26 | 0.0 | 0.0 |

## 2) First Oracle call each day (1/day) + multi-TF scores

### 2026-11-09 09:30 · **SELL** @ **24949.85** · T15=✓ (t1, 15.0)
Pattern: `bear_run2`

| TF | bar | p(T1)% | decision | agree | candle | sess p_up | source |
|---|---|---:|---|---|---:|---:|---|
| **1m** | 09:30 | **40.1** | HOLD | N | 3.0 | 0.418 | extra_trees_fno_t1 |
| **5m** | 09:30 | **48.5** | HOLD | N | -8.0 | 0.3283 | extra_trees_fno_t1 |
| **10m** | 09:30 | **49.5** | HOLD | N | -12.0 | 0.4125 | extra_trees_fno_t1 |
| **15m** | 09:30 | **47.4** | HOLD | N | 1.0 | 0.553 | extra_trees_fno_t1 |

### 2026-11-11 09:30 · **SELL** @ **25323.9** · T15=✗ (ma_sl, -14.7)
Pattern: `bear_run2`

| TF | bar | p(T1)% | decision | agree | candle | sess p_up | source |
|---|---|---:|---|---|---:|---:|---|
| **1m** | 09:30 | **47.1** | HOLD | N | -1.0 | 0.5441 | extra_trees_fno_t1 |
| **5m** | 09:30 | **49.8** | HOLD | N | 0.0 | 0.8193 | extra_trees_fno_t1 |
| **10m** | 09:30 | **49.9** | HOLD | N | 7.0 | 0.9313 | extra_trees_fno_t1 |
| **15m** | 09:30 | **48.9** | HOLD | N | 2.0 | 0.9169 | extra_trees_fno_t1 |

### 2026-11-12 09:33 · **BUY** @ **25338.3** · T15=✓ (t1, 15.0)
Pattern: `bull_run2`

| TF | bar | p(T1)% | decision | agree | candle | sess p_up | source |
|---|---|---:|---|---|---:|---:|---|
| **1m** | 09:33 | **48.6** | HOLD | N | 0.0 | 0.6792 | extra_trees_fno_t1 |
| **5m** | 09:30 | **47.7** | HOLD | N | 0.0 | 0.7649 | extra_trees_fno_t1 |
| **10m** | 09:30 | **47.9** | HOLD | N | 5.0 | 0.7496 | extra_trees_fno_t1 |
| **15m** | 09:30 | **46.3** | HOLD | N | 5.0 | 0.6972 | extra_trees_fno_t1 |

### 2026-11-13 09:31 · **SELL** @ **25119.5** · T15=✗ (ma_sl, -68.45)
Pattern: `bear_run2`

| TF | bar | p(T1)% | decision | agree | candle | sess p_up | source |
|---|---|---:|---|---|---:|---:|---|
| **1m** | 09:31 | **46.2** | HOLD | N | 3.0 | 0.4506 | extra_trees_fno_t1 |
| **5m** | 09:30 | **48.6** | HOLD | N | 5.0 | 0.4051 | extra_trees_fno_t1 |
| **10m** | 09:30 | **49.2** | HOLD | N | 0.0 | 0.4176 | extra_trees_fno_t1 |
| **15m** | 09:30 | **48.4** | HOLD | N | 5.0 | 0.4449 | extra_trees_fno_t1 |

### 2026-11-16 09:30 · **BUY** @ **25255.3** · T15=✓ (t1, 15.0)
Pattern: `marubozu_bull`

| TF | bar | p(T1)% | decision | agree | candle | sess p_up | source |
|---|---|---:|---|---|---:|---:|---|
| **1m** | 09:30 | **40.7** | HOLD | N | 9.0 | 0.5749 | extra_trees_fno_t1 |
| **5m** | 09:30 | **46.8** | HOLD | N | 18.0 | 0.7716 | extra_trees_fno_t1 |
| **10m** | 09:30 | **48.6** | HOLD | N | 18.0 | 0.7914 | extra_trees_fno_t1 |
| **15m** | 09:30 | **48.0** | HOLD | N | 8.0 | 0.7792 | extra_trees_fno_t1 |

## 3) All scored Oracle entries (compact)

| Day | HM | Side | Entry | T15 | 1m p% | 5m p% | 10m p% | 15m p% | 15m dec | agree15 |
|---|---|---|---:|---|---:|---:|---:|---:|---|---|
| 2026-11-09 | 09:30 | **SELL** | 24949.85 | Y | 40.1 | 48.5 | 49.5 | 47.4 | HOLD | N |
| 2026-11-11 | 09:30 | **SELL** | 25323.9 | N | 47.1 | 49.8 | 49.9 | 48.9 | HOLD | N |
| 2026-11-12 | 09:33 | **BUY** | 25338.3 | Y | 48.6 | 47.7 | 47.9 | 46.3 | HOLD | N |
| 2026-11-13 | 09:31 | **SELL** | 25119.5 | N | 46.2 | 48.6 | 49.2 | 48.4 | HOLD | N |
| 2026-11-16 | 09:30 | **BUY** | 25255.3 | Y | 40.7 | 46.8 | 48.6 | 48.0 | HOLD | N |
| 2026-11-09 | 09:31 | **SELL** | 24938.7 | Y | 41.5 | 48.5 | 49.5 | 47.4 | HOLD | N |
| 2026-11-09 | 09:32 | **BUY** | 24950.25 | Y | 41.9 | 48.0 | 48.5 | 47.3 | HOLD | N |
| 2026-11-09 | 09:33 | **BUY** | 24965.65 | N | 44.1 | 48.0 | 48.5 | 47.3 | HOLD | N |
| 2026-11-09 | 09:35 | **SELL** | 24927.2 | Y | 46.5 | 48.4 | 49.5 | 47.4 | HOLD | N |
| 2026-11-09 | 09:37 | **BUY** | 24940.9 | N | 46.4 | 48.2 | 48.5 | 47.3 | HOLD | N |
| 2026-11-09 | 09:38 | **BUY** | 24940.4 | N | 46.7 | 48.2 | 48.5 | 47.3 | HOLD | N |
| 2026-11-09 | 09:40 | **SELL** | 24888.8 | N | 48.8 | 47.6 | 47.5 | 47.4 | HOLD | N |
| 2026-11-09 | 09:41 | **SELL** | 24879.95 | N | 47.9 | 47.6 | 47.5 | 47.4 | HOLD | N |
| 2026-11-09 | 09:42 | **BUY** | 24904.6 | N | 47.1 | 47.3 | 47.5 | 47.3 | HOLD | N |
| 2026-11-09 | 09:44 | **BUY** | 24924.9 | Y | 46.5 | 47.3 | 47.5 | 47.3 | HOLD | N |
| 2026-11-09 | 09:45 | **BUY** | 24949.75 | Y | 46.0 | 47.8 | 47.5 | 48.4 | HOLD | N |
| 2026-11-09 | 09:46 | **SELL** | 24942.0 | Y | 46.1 | 48.1 | 47.5 | 48.4 | HOLD | N |
| 2026-11-09 | 09:47 | **SELL** | 24925.65 | N | 44.2 | 48.1 | 47.5 | 48.4 | HOLD | N |
| 2026-11-09 | 09:49 | **BUY** | 24946.8 | N | 45.4 | 47.8 | 47.5 | 48.4 | HOLD | N |
| 2026-11-09 | 09:51 | **BUY** | 24950.4 | N | 44.0 | 48.0 | 47.8 | 48.4 | HOLD | N |
| 2026-11-09 | 09:52 | **BUY** | 24953.0 | N | 44.1 | 48.0 | 47.8 | 48.4 | HOLD | N |
| 2026-11-09 | 09:53 | **SELL** | 24941.25 | Y | 43.7 | 48.4 | 47.8 | 48.4 | HOLD | N |
| 2026-11-09 | 09:54 | **SELL** | 24921.5 | Y | 44.4 | 48.4 | 47.8 | 48.4 | HOLD | N |
| 2026-11-09 | 09:56 | **BUY** | 24921.9 | N | 45.2 | 48.0 | 47.8 | 48.4 | HOLD | N |
| 2026-11-09 | 09:57 | **SELL** | 24912.8 | N | 41.4 | 48.3 | 47.8 | 48.4 | HOLD | N |
| 2026-11-09 | 09:58 | **BUY** | 24925.35 | N | 43.8 | 48.0 | 47.8 | 48.4 | HOLD | N |
| 2026-11-09 | 09:59 | **BUY** | 24932.6 | N | 43.7 | 48.0 | 47.8 | 48.4 | HOLD | N |
| 2026-11-09 | 10:00 | **BUY** | 24941.25 | N | 45.4 | 45.3 | 47.3 | 47.7 | HOLD | N |
| 2026-11-09 | 10:02 | **SELL** | 24924.75 | N | 44.7 | 46.3 | 48.0 | 47.7 | HOLD | N |
| 2026-11-09 | 10:04 | **SELL** | 24924.25 | N | 45.1 | 46.3 | 48.0 | 47.7 | HOLD | N |
| 2026-11-09 | 10:05 | **SELL** | 24920.4 | N | 44.5 | 47.9 | 48.0 | 47.7 | HOLD | N |
| 2026-11-09 | 10:10 | **BUY** | 24939.3 | N | 46.7 | 46.8 | 47.0 | 47.7 | HOLD | N |
| 2026-11-09 | 10:12 | **SELL** | 24921.0 | N | 45.9 | 47.1 | 47.6 | 47.7 | HOLD | N |
| 2026-11-09 | 10:14 | **SELL** | 24916.35 | N | 41.6 | 47.1 | 47.6 | 47.7 | HOLD | N |
| 2026-11-09 | 10:15 | **BUY** | 24933.35 | N | 41.5 | 47.1 | 47.0 | 47.4 | HOLD | N |
| 2026-11-09 | 10:18 | **BUY** | 24932.9 | Y | 41.4 | 47.1 | 47.0 | 47.4 | HOLD | N |
| 2026-11-09 | 10:19 | **BUY** | 24939.45 | Y | 41.1 | 47.1 | 47.0 | 47.4 | HOLD | N |
| 2026-11-09 | 10:20 | **BUY** | 24940.7 | Y | 41.5 | 47.4 | 47.7 | 47.4 | HOLD | N |
| 2026-11-09 | 10:21 | **BUY** | 24950.1 | N | 41.3 | 47.4 | 47.7 | 47.4 | HOLD | N |
| 2026-11-09 | 10:22 | **BUY** | 24957.05 | N | 41.2 | 47.4 | 47.7 | 47.4 | HOLD | N |

## 4) Filter Oracle by 15m model p(T1) — does accuracy rise?

| 15m p(T1) ≥ | n | Oracle T15% |
|---:|---:|---:|
| 50% | 0 | — |
| 55% | 0 | — |
| 60% | 0 | — |
| 65% | 0 | — |
| 70% | 0 | — |

## Takeaway

- If winners show **higher** multi-TF p(T1) than losers → model can filter Oracle noise.
- If similar → model score at call time is **not** separating good Oracle entries (last 5d).
- 15m is the dual-track native TF; 1m/5m/10m are the same head on resampled bars (exploratory).

_Generated in 32.4s._
