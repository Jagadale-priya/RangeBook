# NIFTY 1m — Oracle T15 + EMA34 trail · accuracy research

> **RESEARCH ONLY — not changing Scalper live Setup A/B.**

Window **2026-10-15 → 2026-11-16** (22 sessions) · session 09:30–14:30 · exit **EMA34 trail strict**.

## 1) What is “Not into session extreme”?

On each bar we track **today’s session high / low so far** (only bars before entry).

```
near_sess_high = distance to session high ≤ max(8 pts, 1×ATR)
near_sess_low  = distance to session low  ≤ max(8 pts, 1×ATR)

into_sess_extreme =
  BUY  when price is already near the session HIGH  (buying the top)
  SELL when price is already near the session LOW   (selling the bottom)

not_extreme = NOT into_sess_extreme
```

Intended idea: don’t chase the day’s high/low (no room for T15).  
**Nuance (this window):** extremes also mark **continuation breakouts** that often still trail-win — see §5. So “not extreme” is hygiene for *first call of day*, not a universal ban.

Among all sess textbook events this window: T15 path-wins **1686** / losses **2663**.
- `into_sess_extreme` on **wins**: 375 (22.2%)
- `into_sess_extreme` on **losses**: 187 (7.0%)

## 2) Oracle T15 · EMA34 trail (the logic you like)

Oracle = take textbook events that **already path-win** T15 under EMA34 trail (hindsight). Scalper chart marks those. High hit% is expected because losers are hidden.

| Book | T1 | n | Hit% | Cover | avg pts |
|---|---:|---:|---:|---:|---:|
| Oracle 1/day | 15 | 22 | **100.0** | 100.0 | 15.0 |
| Oracle 1/day | 12 | 22 | **100.0** | 100.0 | 12.0 |
| Oracle gap15 | 15 | 314 | **100.0** | 1427.27 | 15.0 |

Oracle hit is **100% by construction** (only path-wins are plotted). When you ‘see fails’, that is usually **Setup / Tier** mode, or mixing modes — not pure Oracle.

## 3) Using Oracle *style* for more accuracy (blind filters + T15 trail)

We keep **same exit** (EMA34 trail · T15) and test **entry filters** without peeking.
Ranked by 1-call/day hit% (n≥8):

| Gate (blind) | 1cpd Hit% | n | cover | gap15 Hit% | n |
|---|---:|---:|---:|---:|---:|
| `HELD + !extreme + AD` | **85.71** | 21 | 95.45% | 61.25 | 160 |
| `HELD` | **80.95** | 21 | 95.45% | 61.6 | 250 |
| `HELD + !extreme + ctrl` | **80.95** | 21 | 95.45% | 60.8 | 176 |
| `HELD + !extreme + clear + AD` | **78.95** | 19 | 86.36% | 66.04 | 53 |
| `HELD + !extreme + clear + AD + ctrl` | **78.95** | 19 | 86.36% | 66.0 | 50 |
| `HELD + !extreme (code default)` | **76.19** | 21 | 95.45% | 56.5 | 200 |
| `HELD + !ext_1atr` | **76.19** | 21 | 95.45% | 56.72 | 201 |
| `HELD + !ext_2atr` | **71.43** | 21 | 95.45% | 57.53 | 146 |
| `HELD + clear_path` | **71.43** | 21 | 95.45% | 65.67 | 67 |
| `HELD + !extreme + clear` | **71.43** | 21 | 95.45% | 65.67 | 67 |
| `HELD + !extreme + clear + ctrl` | **71.43** | 21 | 95.45% | 65.57 | 61 |
| `TierA only` | **70.0** | 10 | 45.45% | 68.75 | 16 |
| `TierAB + !extreme` | **63.16** | 19 | 86.36% | 60.34 | 58 |
| `HELD + !extreme + di8` | **61.9** | 21 | 95.45% | 57.52 | 153 |
| `HELD + !extreme + clear + di8` | **61.9** | 21 | 95.45% | 63.79 | 58 |
| `ALL textbook sess` | **54.55** | 22 | 100.0% | 36.9 | 420 |
| `TierAB + clear` | **44.44** | 9 | 40.91% | 50.0 | 12 |

### Feature lift on HELD pool (T15 trail hit)

HELD baseline T15 hit (all HELD bars, not 1/day): **60.73%** n=1235

| Condition | n | T15 hit% | lift vs HELD |
|---|---:|---:|---:|
| `not_extreme` | 746 | 57.37 | -3.36 |
| `INTO extreme (bad)` | 489 | 65.85 | 5.12 |
| `!ext_1atr` | 748 | 57.35 | -3.38 |
| `clear_path` | 162 | 61.73 | 1.0 |
| `ad_with` | 994 | 62.17 | 1.44 |
| `ctrl` | 922 | 61.71 | 0.98 |
| `di8` | 996 | 62.15 | 1.42 |
| `not_extreme+clear` | 162 | 61.73 | 1.0 |
| `not_extreme+clear+AD` | 128 | 60.16 | -0.57 |
| `not_extreme+clear+ctrl` | 126 | 60.32 | -0.41 |
## 4) Research conclusion (not live yet)

**Keep Oracle T15 + EMA34 trail** as the quality ceiling / chart teacher.

See §5–§6 for the corrected extreme finding and best blind approximation.

## 5) Deeper cut — extreme is NOT always bad for T15 trail

On **HELD** bars this window, buying/selling **into** the session extreme (continuation near day high/low) actually **won more** under EMA34 trail than avoiding it. So a hard `not_extreme` gate is **not** the accuracy booster for Oracle-style T15.

| Condition on HELD | n | T15 trail hit% |
|---|---:|---:|
| `HELD all` | 1235 | 60.73 |
| `into_sess_extreme` | 489 | 65.85 |
| `not_extreme` | 746 | 57.37 |
| `at_liq_magnet (buy near low / sell near high)` | 0 | None |
| `AD_with` | 994 | 62.17 |
| `AD + magnet` | 0 | None |
| `AD + into_extreme` | 450 | 65.11 |
| `AD + not_extreme` | 544 | 59.74 |
| `AD + clear_path` | 128 | 60.16 |
| `AD + control` | 771 | 62.65 |

### Oracle 1/day fingerprint (what winners look like)

n=22 first T15 path-wins/day:

- `held`: **45.5%**
- `ad_with`: **68.2%**
- `ctrl`: **81.8%**
- `clear`: **13.6%**
- `magnet`: **9.1%**
- `into_sess_extreme`: **31.8%**
- `not_extreme`: **68.2%**
- `setup_ok`: **9.1%**

### Blind 1-call/day (same T15 trail exit)

| Gate | n | Hit% |
|---|---:|---:|
| `HELD` | 21 | **80.95** |
| `HELD + AD` | 21 | **80.95** |
| `HELD + magnet` | 0 | **None** |
| `HELD + AD + magnet` | 0 | **None** |
| `HELD + AD + into_extreme` | 21 | **76.19** |
| `HELD + AD + !extreme` | 21 | **85.71** |
| `HELD + AD + clear` | 19 | **78.95** |

## 6) Revised takeaway (research only)

**Oracle T15 + EMA34 trail** = best chart teacher (100% by selecting path-wins). Keep that exit logic.

**Not into session extreme** = don’t BUY already at day high / SELL already at day low.  
- On **all HELD bars**: into-extreme hit **higher** (65.9% vs 57.4%) → many are continuation.  
- On **1-call/day**: `HELD + AD + !extreme` is best (**85.7%**) vs `HELD + AD + into_extreme` (76.2%).

Closest **blind** approximation of Oracle accuracy on this 22d window:
1. Exit: **T15 · EMA34 trail** (same as Oracle)
2. Entry: **HELD + AD_with + not_extreme** → **85.7%** 1cpd (21 days)
3. Don’t hard-ban extremes on every bar — use `!extreme` mainly for the **first** daily pick

Still research-only — Scalper live Setup A/B unchanged.
