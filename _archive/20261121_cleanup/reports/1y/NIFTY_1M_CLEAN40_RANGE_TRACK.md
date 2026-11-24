# NIFTY 1m — Clean ≥40 **one-direction** moves + Range / S / R tracking

## What we mean (your definition)

```
UP move  : start price P → P+40, and EVERY 1m candle until +40 is GREEN only
DOWN move: start price P → P−40, and EVERY 1m candle until −40 is RED only
No opposite-color candle allowed before 40 pts is tagged.
Mark level = OPEN of the first candle of that clean streak.
```

Window **2026-05-26 → 2026-11-16** (120 sessions).

## 1) How many such moves exist?

| Metric | Value |
|---|---:|
| **Total clean ≥40 moves** | **558** |
| BUY (all-green to +40) | 244 |
| SELL (all-red to −40) | 314 |
| Days with ≥1 move | 106 / 120 |
| Avg moves / active day | 5.26 |
| Avg bars to reach 40 | 3.96 |
| Median bars to 40 | 3 |
| Avg full streak extension | 58.2 pts |

## 2) Where do they start? (origin / mark context)

Before each clean move we mark:

| Mark | Meaning |
|---|---|
| **RANGE BLOCK** | Last ~20 bars width ≤ 2.5×ATR (market coiling) |
| **RANGE BREAK** | First candle closes outside that block → trend start |
| **SUPPORT / RESIST** | Nearest swing low/high within 0.5×ATR |
| **OR15 / OR30** | Opening range edge break |
| **PDHL** | Prior-day high/low break |
| **SESSION EXT** | New session high/low on ignition bar |

| Origin class | n | % of clean40 |
|---|---:|---:|
| `OPEN_TREND` | 159 | 28.5 |
| `BOX_BREAK` | 95 | 17.0 |
| `PDHL_BREAK` | 67 | 12.0 |
| `RESIST_BOUNCE` | 64 | 11.5 |
| `SUPPORT_BOUNCE` | 59 | 10.6 |
| `OR30_BREAK` | 56 | 10.0 |
| `RANGE_BREAK` | 27 | 4.8 |
| `INSIDE_RANGE` | 16 | 2.9 |
| `SESSION_EXT` | 9 | 1.6 |
| `OR15_BREAK` | 6 | 1.1 |

## 3) Marker coverage at ignition (of all clean40 moves)

This answers: *when a clean ≥40 happened, was the mark already visible?*

| Marker at start bar | % of clean40 moves |
|---|---:|
| `prev_opposite` | 99.5 |
| `ctrl` | 79.6 |
| `held` | 38.7 |
| `ad` | 61.1 |
| `confirm1` | 84.8 |
| `in_range_block` | 13.8 |
| `range_break` | 4.8 |
| `box_break` | 21.9 |
| `near_support` | 38.0 |
| `near_resist` | 36.0 |
| `or15_break` | 19.7 |
| `or30_break` | 16.8 |
| `pd_break` | 24.4 |
| `new_sess_ext` | 7.3 |
| `disp08` | 51.8 |
| `big_body` | 56.6 |
| `am` | 64.5 |

## 4) How many can we **track / identify**?

Coverage = share of true clean ≥40 moves that match the identifier at start (or start+1).

| Identifier | Tracked | Total | **Coverage %** | BUY | SELL | avg ext |
|---|---:|---:|---:|---:|---:|---:|
| `prev_opp` | 555 | 558 | **99.5** | 243 | 312 | 58.2 |
| `prev_opp+confirm1` | 470 | 558 | **84.2** | 207 | 263 | 55.7 |
| `structure_or_SR` | 383 | 558 | **68.6** | 166 | 217 | 57.6 |
| `prev_opp+ctrl+confirm1` | 380 | 558 | **68.1** | 170 | 210 | 55.7 |
| `structure_or_SR+confirm1` | 334 | 558 | **59.9** | 146 | 188 | 55.8 |
| `prev_opp+ad+confirm1` | 286 | 558 | **51.3** | 122 | 164 | 55.6 |
| `any_structure_break` | 260 | 558 | **46.6** | 107 | 153 | 56.8 |
| `structure_break+confirm1` | 230 | 558 | **41.2** | 93 | 137 | 54.6 |
| `prev_opp+held+confirm1` | 174 | 558 | **31.2** | 72 | 102 | 56.0 |
| `box_break (prior 20-bar H/L)` | 122 | 558 | **21.9** | 55 | 67 | 59.3 |
| `box_break+confirm1` | 117 | 558 | **21.0** | 52 | 65 | 59.4 |
| `R_bounce (SELL near_res)` | 112 | 558 | **20.1** | 0 | 112 | 57.7 |
| `or15_break` | 110 | 558 | **19.7** | 44 | 66 | 54.2 |
| `S_bounce (BUY near_sup)` | 98 | 558 | **17.6** | 98 | 0 | 61.8 |
| `or30_break` | 94 | 558 | **16.8** | 39 | 55 | 55.2 |
| `new_sess_ext` | 41 | 558 | **7.3** | 17 | 24 | 59.5 |
| `new_sess_ext+confirm1` | 35 | 558 | **6.3** | 12 | 23 | 54.6 |
| `tight_range_break` | 27 | 558 | **4.8** | 13 | 14 | 60.4 |
| `tight_range_break+confirm1` | 27 | 558 | **4.8** | 13 | 14 | 60.4 |

## 5) How to think about it (method)

```
1. While market chops → mark RANGE BLOCK (tight high/low band)
2. Also mark SUPPORT (swing lows) and RESISTANCE (swing highs)
3. Opening RANGE (OR15/OR30) is a special morning block
4. When price CLOSES outside the block / through S or R → TREND ignition
5. Track only if next 1m candles stay SAME COLOR until +40 / −40
6. If an opposite-color candle prints before 40 → NOT a clean one-direction move
```

### Best practical trackers from this window

- **Earliest generic:** `prev_opp+confirm1` covers **84.2%** (470/558) of clean ≥40 moves.
- **Structure/range marks:** `structure_or_SR` covers **68.6%** (383/558).

Important: high coverage ≠ high precision. Coverage = *of real clean40, how many we flag*.
Precision (flag → clean40) is a separate question; this report focuses on **finding & tracking the moves**.

## 6) Sample clean ≥40 moves

| Day | Start | Hit40 | Side | Start px | Ext | bars→40 | Origin | range_brk | OR30 | sess_ext |
|---|---|---|---|---:|---:|---:|---|---|---|---|
| 2026-11-09 | 13:14 | 13:16 | **SELL** | **24921.85** | 68.75 | 3 | RANGE_BREAK | True | False | False |
| 2026-11-09 | 14:16 | 14:17 | **BUY** | **24979.65** | 58.65 | 2 | BOX_BREAK | False | False | False |
| 2026-11-11 | 09:15 | 09:15 | **SELL** | **25337.8** | 74.0 | 1 | OPEN_TREND | False | False | False |
| 2026-11-11 | 09:18 | 09:19 | **BUY** | **25329.7** | 47.7 | 2 | PDHL_BREAK | False | False | True |
| 2026-11-11 | 09:20 | 09:24 | **SELL** | **25376.2** | 65.45 | 5 | OPEN_TREND | False | False | False |
| 2026-11-11 | 09:31 | 09:34 | **BUY** | **25326.9** | 44.5 | 4 | PDHL_BREAK | False | False | False |
| 2026-11-11 | 09:49 | 09:54 | **SELL** | **25413.45** | 64.75 | 6 | OPEN_TREND | False | False | False |
| 2026-11-11 | 12:05 | 12:12 | **SELL** | **25389.4** | 69.4 | 8 | RESIST_BOUNCE | False | False | False |
| 2026-11-11 | 12:48 | 12:50 | **BUY** | **25284.3** | 41.75 | 3 | PDHL_BREAK | False | False | False |
| 2026-11-11 | 13:25 | 13:31 | **SELL** | **25281.15** | 71.2 | 7 | OPEN_TREND | False | False | False |
| 2026-11-11 | 13:44 | 13:48 | **SELL** | **25228.7** | 66.0 | 5 | OR30_BREAK | False | True | False |
| 2026-11-11 | 13:54 | 13:58 | **BUY** | **25165.6** | 57.7 | 5 | PDHL_BREAK | False | False | False |
| 2026-11-11 | 14:02 | 14:07 | **BUY** | **25219.7** | 41.8 | 6 | BOX_BREAK | False | False | False |
| 2026-11-12 | 09:15 | 09:16 | **BUY** | **25213.5** | 88.05 | 2 | SUPPORT_BOUNCE | False | False | False |
| 2026-11-12 | 09:23 | 09:26 | **BUY** | **25275.25** | 64.7 | 4 | SUPPORT_BOUNCE | False | False | False |
| 2026-11-12 | 09:42 | 09:47 | **SELL** | **25355.35** | 42.9 | 6 | OPEN_TREND | False | False | False |
| 2026-11-12 | 10:09 | 10:11 | **SELL** | **25368.65** | 46.25 | 3 | OPEN_TREND | False | False | False |
| 2026-11-12 | 11:09 | 11:13 | **SELL** | **25329.85** | 43.85 | 5 | OPEN_TREND | False | False | False |
| 2026-11-12 | 12:04 | 12:08 | **SELL** | **25277.3** | 49.9 | 5 | RANGE_BREAK | True | False | False |
| 2026-11-13 | 09:15 | 09:15 | **SELL** | **25209.85** | 93.05 | 1 | PDHL_BREAK | False | False | False |
| 2026-11-13 | 09:19 | 09:21 | **SELL** | **25127.4** | 49.85 | 3 | PDHL_BREAK | False | False | False |
| 2026-11-13 | 09:23 | 09:24 | **BUY** | **25082.0** | 44.5 | 2 | OPEN_TREND | False | False | False |
| 2026-11-13 | 09:32 | 09:35 | **BUY** | **25119.1** | 74.5 | 4 | RANGE_BREAK | True | False | False |
| 2026-11-13 | 09:44 | 09:47 | **BUY** | **25173.1** | 40.05 | 4 | OPEN_TREND | False | False | False |
| 2026-11-16 | 09:15 | 09:15 | **BUY** | **25206.15** | 87.3 | 1 | PDHL_BREAK | False | False | False |
| 2026-11-16 | 09:16 | 09:17 | **SELL** | **25290.9** | 68.3 | 2 | OPEN_TREND | False | False | False |
| 2026-11-16 | 09:58 | 10:02 | **SELL** | **25330.7** | 41.7 | 5 | OPEN_TREND | False | False | False |
| 2026-11-16 | 10:28 | 10:32 | **SELL** | **25281.35** | 67.25 | 5 | BOX_BREAK | False | False | False |
| 2026-11-16 | 10:57 | 11:02 | **BUY** | **25204.0** | 41.55 | 6 | SUPPORT_BOUNCE | False | False | False |
| 2026-11-16 | 12:06 | 12:10 | **BUY** | **25252.15** | 46.85 | 5 | BOX_BREAK | False | False | False |

_Generated in 10.4s._
