# NIFTY — PA **PROVEN LOGIC** gate (BOS / CHoCH / FVG)

> **RESEARCH ONLY.** No Scalper mode ships until verdict = **PROVEN**.

Window **2025-12-26 → 2026-11-16** (220 sessions). Walk-forward split OOS from **2026-06-10**.
Target **3.0R**, hold ≤90m, **1 trade/day**.

## 0) External evidence (must shape what we test)

| Claim | Evidence | Implication |
|---|---|---|
| BOS / CHoCH alone | ~0 edge, PF≈1.00 on 9k+ trades ([s4u](https://s4u.pro/en/bos-choch-strategy/)) | Structure signal ≠ entry |
| CHoCH + FVG | PF 1.03 | Too weak to ship alone |
| **Sweep → CHoCH → retest** | 38.2%@3R, PF 1.16, +0.095R / 2209 trades ([s4u](https://s4u.pro/en/bos-choch-strategy/)) | Best published chain |
| FVG 'hold' rate | ≈ random band on ES/NQ ([TEJ](https://tradingedgejournal.com/blog/do-fair-value-gaps-work/)) | Need structure + filters, not bare FVG |
| Filtered FVG retrace | ~38% WR, +0.29R on DXY ([DoesItRepeat](https://doesitrepeat.com/blog/ict-fair-value-gap-backtest)) | Size/validity filters matter |

Prior 44d sample (41.7%@3R, n=12) is **insufficient** — below prove floor.

## 1) Prove rules (this repo)

- **PROVEN:** TRAIN + OOS each `n≥30`, hit@3R `≥35.0%`, exp_R `≥0.2`, OOS t-score `≥1.5`
- **PROMISING:** TRAIN + OOS each `n≥20`, hit `≥32.0%`, exp_R `≥0.1`, both exp>0
- Else **NOT_PROVEN** — do not wire live.

## 2) Walk-forward results

| Book | Verdict | Full n/hit/expR | Train n/hit/expR | OOS n/hit/expR/t |
|---|---|---|---|---|
| `A_fvg5` | **NOT_PROVEN** | 118/32.2%/0.307 | 69/26.09%/0.077 | 49/40.82%/0.633/t=2.23 |
| `A_open_fvg4` | **NOT_PROVEN** | 88/30.68%/0.253 | 52/25.0%/0.044 | 36/38.89%/0.556/t=1.69 |
| `A_open_only` | **NOT_PROVEN** | 119/31.93%/0.296 | 62/29.03%/0.198 | 57/35.09%/0.404/t=1.58 |
| `A_risk5_25` | **NOT_PROVEN** | 173/31.21%/0.262 | 90/27.78%/0.136 | 83/34.94%/0.398/t=1.89 |
| `C_bos_fvg` | **NOT_PROVEN** | 219/29.68%/0.196 | 110/27.27%/0.091 | 109/32.11%/0.302/t=1.68 |
| `A_choch_fvg_htf` | **NOT_PROVEN** | 217/28.11%/0.135 | 109/26.61%/0.085 | 108/29.63%/0.185/t=1.05 |
| `C_bos_fvg_disp` | **NOT_PROVEN** | 116/26.72%/0.085 | 56/25.0%/0.0 | 60/28.33%/0.165/t=0.71 |
| `A_choch_fvg_nohtf` | **NOT_PROVEN** | 219/22.37%/-0.105 | 110/19.09%/-0.236 | 109/25.69%/0.028/t=0.16 |
| `B_choch_bos_fvg` | **NOT_PROVEN** | 218/26.15%/0.046 | 109/27.52%/0.101 | 109/24.77%/-0.009/t=-0.06 |
| `E2_sweep_choch_fvg` | **NOT_PROVEN** | 187/20.86%/-0.166 | 101/17.82%/-0.287 | 86/24.42%/-0.023/t=-0.12 |
| `D_choch_retest` | **NOT_PROVEN** | 214/21.96%/-0.121 | 109/21.1%/-0.156 | 105/22.86%/-0.086/t=-0.52 |
| `E_sweep_choch_retest` | **NOT_PROVEN** | 214/21.5%/-0.14 | 109/20.18%/-0.193 | 105/22.86%/-0.086/t=-0.52 |

## 3) Verdict

**NOT PROVEN.** No book cleared TRAIN+OOS floors on this 1Y NIFTY walk-forward.

| Near-miss (OOS only) | Why it fails prove | Note |
|---|---|---|
| `A_fvg5` OOS 40.8% / +0.63R / t=2.23 | TRAIN only 26.1% / +0.08R | Classic OOS luck / regime — **reject** |
| `A_open_fvg4` OOS 38.9% | TRAIN 25.0% | Same failure mode |
| `A_open_only` OOS 35.1% / t=1.58 | TRAIN 29.0% < 35% floor | Closest structurally; still fail |
| `A_risk5_25` OOS 34.9% | TRAIN 27.8% | Below hit floor both sides of hard gate |
| Sweep→CHoCH→retest (E) | OOS 22.9% / −0.09R | Published FX/multi-asset edge **did not transfer** to NIFTY 1m here |

**Ship decision:** do **not** wire `pa_fvg_1m` (or any transcript PA mode) into Scalper. Keep **Oracle T15 clean / TierAB** as the working path until a book is PROVEN under these same rules.

## 4) What this means vs the transcript

1. The transcript framework is **conceptually correct** (direction → confirm → invalidate).
2. It is **not automatically a proven NIFTY 1m entry model** — external + our WF both say bare CHoCH/FVG is thin.
3. Published **sweep → CHoCH → retest** did **not** transfer to NIFTY 1m in this test (neg EV). Closest local near-miss = open-window + HTF FVG mid — still fails TRAIN.
4. **Oracle T15 clean / TierAB** stays the working Scalper path; transcript PA is research-only until PROVEN.
5. Do **not** flip Scalper default on transcript simplicity alone.

_Generated in 14.8s._
