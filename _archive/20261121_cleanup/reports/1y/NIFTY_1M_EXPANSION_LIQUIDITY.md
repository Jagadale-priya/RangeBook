# NIFTY 1m — Expansion candle × Liquidity

> **RESEARCH ONLY.** Same PROVEN gate as `NIFTY_1M_PA_PROVEN_LOGIC`.

Window **2025-12-26 → 2026-11-16** (220 sessions). OOS from **2026-06-10**.

## Definitions

- **Expansion:** body ≥ 1.0×ATR14, body/range ≥ 0.62, close in extreme 25% of bar.
- **Liquidity sweep:** wick beyond prior 8-bar high/low, close back inside.
- **FVG entry:** after sweep+expansion, first touch of FVG mid.
- **Oracle:** textbook pattern + EMA34 with-trend (live Scalper spirit).

## Walk-forward results

| Book | Verdict | Full n/hit/expR | Train | OOS n/hit/expR/t |
|---|---|---|---|---|
| `D_exp_next_open_3r` | **PROMISING** | 2308/33.02%/0.321 | 1245/33.82%/0.353 | 1063/32.08%/0.283/t=4.94 |
| `D_exp_next_open_t15` | **PROMISING** | 2397/39.92%/0.125 | 1284/39.72%/0.112 | 1113/40.16%/0.14/t=3.34 |
| `D_exp_next_open_sweep_t15` | **PROMISING** | 1240/39.68%/0.115 | 694/40.2%/0.118 | 546/39.01%/0.112/t=1.88 |
| `D_exp_next_open_sweep_3r` | **NOT_PROVEN** | 1156/34.43%/0.382 | 670/37.91%/0.518 | 486/29.63%/0.194/t=2.34 |
| `C_sweep_exp_fvg_3r` | **NOT_PROVEN** | 330/29.09%/0.175 | 198/29.29%/0.19 | 132/28.79%/0.152/t=0.96 |
| `E_oracle_3r` | **NOT_PROVEN** | 4631/26.54%/0.076 | 2338/25.83%/0.048 | 2293/27.26%/0.104/t=2.8 |
| `E_oracle_exp_3r` | **NOT_PROVEN** | 2832/25.81%/0.075 | 1516/25.2%/0.052 | 1316/26.52%/0.101/t=2.07 |
| `A_exp_chase_3r` | **NOT_PROVEN** | 2960/25.41%/0.064 | 1576/25.32%/0.057 | 1384/25.51%/0.072/t=1.52 |
| `B_sweep_exp_t15` | **NOT_PROVEN** | 1274/37.91%/0.069 | 703/38.98%/0.09 | 571/36.6%/0.043/t=0.74 |
| `A_exp_chase_t15` | **NOT_PROVEN** | 2960/37.5%/0.057 | 1576/38.39%/0.075 | 1384/36.49%/0.036/t=0.98 |
| `E_oracle_t15` | **NOT_PROVEN** | 4636/37.01%/0.028 | 2338/37.34%/0.026 | 2298/36.68%/0.03/t=1.06 |
| `C_sweep_exp_fvg_t15` | **NOT_PROVEN** | 362/36.19%/0.023 | 209/36.36%/0.02 | 153/35.95%/0.027/t=0.25 |
| `B_sweep_exp_3r` | **NOT_PROVEN** | 1274/24.96%/0.068 | 703/26.03%/0.106 | 571/23.64%/0.022/t=0.31 |
| `F_strong_exp_sweep_t15` | **NOT_PROVEN** | 549/37.7%/0.067 | 322/39.44%/0.109 | 227/35.24%/0.008/t=0.08 |
| `E_oracle_exp_t15` | **NOT_PROVEN** | 2832/37.29%/0.05 | 1516/38.85%/0.087 | 1316/35.49%/0.007/t=0.19 |
| `E_oracle_sweep_exp_3r` | **NOT_PROVEN** | 1524/24.8%/0.043 | 844/25.59%/0.078 | 680/23.82%/-0.002/t=-0.03 |
| `E_oracle_sweep_exp_t15` | **NOT_PROVEN** | 1524/36.94%/0.041 | 844/38.63%/0.081 | 680/34.85%/-0.008/t=-0.15 |
| `E_oracle_sweep_t15` | **NOT_PROVEN** | 2743/36.24%/0.014 | 1391/38.75%/0.077 | 1352/33.65%/-0.051/t=-1.41 |
| `E_oracle_sweep_3r` | **NOT_PROVEN** | 2743/25.08%/0.022 | 1391/27.32%/0.113 | 1352/22.78%/-0.071/t=-1.55 |
| `F_strong_exp_sweep_3r` | **NOT_PROVEN** | 549/21.68%/-0.012 | 322/24.22%/0.111 | 227/18.06%/-0.187/t=-1.79 |

## Lift vs Oracle (OOS)

| Filter | Mode | Base hit → Filt hit | Δhit pp | Base exp → Filt exp | Δexp | n_oos | Verdict |
|---|---|---|---:|---|---:|---:|---|
| `E_oracle_exp_3r` | 3r | 27.26% → 26.52% | -0.7 | 0.104 → 0.101 | -0.003 | 1316 | NOT_PROVEN |
| `E_oracle_exp_t15` | t15 | 36.68% → 35.49% | -1.2 | 0.03 → 0.007 | -0.023 | 1316 | NOT_PROVEN |
| `E_oracle_sweep_exp_t15` | t15 | 36.68% → 34.85% | -1.8 | 0.03 → -0.008 | -0.038 | 680 | NOT_PROVEN |
| `E_oracle_sweep_t15` | t15 | 36.68% → 33.65% | -3.0 | 0.03 → -0.051 | -0.081 | 1352 | NOT_PROVEN |
| `E_oracle_sweep_exp_3r` | 3r | 27.26% → 23.82% | -3.4 | 0.104 → -0.002 | -0.106 | 680 | NOT_PROVEN |
| `E_oracle_sweep_3r` | 3r | 27.26% → 22.78% | -4.5 | 0.104 → -0.071 | -0.175 | 1352 | NOT_PROVEN |

## Verdict

**No PROVEN.** PROMISING only — not live yet.

Promising (base run):
- `D_exp_next_open_3r` — OOS 32.1% / 0.28R
- `D_exp_next_open_t15` — OOS 40.2% / 0.14R
- `D_exp_next_open_sweep_t15` — OOS 39.0% / 0.11R

### Best OOS by exp (n≥15, any verdict)

- `D_exp_next_open_3r` · PROMISING · OOS 1063/32.08%/0.283R t=4.94
- `D_exp_next_open_sweep_3r` · NOT_PROVEN · OOS 486/29.63%/0.194R t=2.34
- `C_sweep_exp_fvg_3r` · NOT_PROVEN · OOS 132/28.79%/0.152R t=0.96
- `D_exp_next_open_t15` · PROMISING · OOS 1113/40.16%/0.14R t=3.34
- `D_exp_next_open_sweep_t15` · PROMISING · OOS 546/39.01%/0.112R t=1.88
- `E_oracle_3r` · NOT_PROVEN · OOS 2293/27.26%/0.104R t=2.8
- `E_oracle_exp_3r` · NOT_PROVEN · OOS 1316/26.52%/0.101R t=2.07
- `A_exp_chase_3r` · NOT_PROVEN · OOS 1384/25.51%/0.072R t=1.52

## Refinement D2 (next-open grid)

Follow-up grid on **expansion → enter next bar open** (body ATR, sweep optional, session):

| Book | Verdict | Train hit/exp | OOS hit/exp/t |
|---|---|---|---|
| `D2_b1.0_any_am_3r` | **PROMISING** | 36.4% / 0.46R | **34.1% / 0.37R / t=4.75** |
| `D2_b1.0_any_am_t15` | **PROMISING** | 41.3% / 0.14R | **41.8% / 0.17R / t=3.14** |
| `D2_b1.2_any_am_t15` | **PROMISING** | 40.4% / 0.12R | 41.8% / 0.18R / t=2.77 |
| `D2_b1.5_any_am_t15` | **PROMISING** | 40.5% / 0.13R | 42.2% / 0.19R / t=2.09 |

Still **0 PROVEN**. Closest miss: AM-session next-open 3R (OOS hit 34.1% vs 35% floor; exp already clears). T15 AM clears hit but exp_R stays just under 0.20.

See also `NIFTY_1M_EXPANSION_LIQUIDITY_D2.json`.

## What this means

1. Chasing the expansion close is the wrong fill (`A_exp_chase_*` stays weak).
2. Sweep → expansion → FVG mid (`C_*`) did **not** clear prove floors on NIFTY 1m (same story as prior PA research).
3. **Oracle ∩ sweep/expansion filters hurt or did not help OOS** — do not bolt liquidity onto Oracle blindly.
4. Real edge candidate: **see expansion → enter next open (esp. before noon)** — PROMISING, not ship-ready.
5. Do **not** wire a new Scalper mode until verdict = PROVEN.

_Generated in 68.1s._
