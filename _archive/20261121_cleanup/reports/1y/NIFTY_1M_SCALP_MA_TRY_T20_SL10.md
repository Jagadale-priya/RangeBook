# NIFTY 1m — **try MA** (EMA9/21/50) for T20 / SL≤10 path

Blind protocol: lock on **2024–2025 only** → score **unknown 2026**.

## MA gate lift (any SL≤10 style)

| Gate | Train n@hit | Unk2026 n@hit |
|---|---|---|
| `raw` | 115084@28.57% | 50990@30.01% |
| `ma_align` | 60357@28.39% | 27496@30.03% |
| `ma_stack_with` | 48153@28.51% | 22042@30.13% |
| `ma_hard` | 42860@28.48% | 19937@30.29% |
| `ma_pullback` | 3673@24.04% | 1582@24.97% |
| `ma_hard_close_ok` | 24657@30.58% | 11768@32.63% |
| `ma_pull_b70_advlo` | 445@31.91% | 208@36.06% |

## Blind micro books

| Book | Micros | Train hit | Unk full n@hit | Unk 1/day hit | Unk cover |
|---|---:|---:|---|---:|---:|
| **BLIND_DEEP_noMA** | 253 | 960@100.0% | 406@30.3% | 33.88% | 84.7% |
| **BLIND_MA_keys** | 250 | 960@100.0% | 417@29.74% | 34.05% | 85.6% |
| **BLIND_MA_align** | 276 | 929@100.0% | 386@28.24% | 29.35% | 85.2% |
| **BLIND_MA_hard** | 280 | 892@100.0% | 369@23.31% | 23.3% | 81.5% |
| **BLIND_MA_pull** | 173 | 355@100.0% | 140@27.86% | 27.45% | 47.2% |
| **BLIND_MA_hard_close** | 276 | 825@100.0% | 329@27.05% | 26.51% | 76.9% |

## WF2026 MA_hard (train 2021–25)

- micros=708 · unk **350@26.29%** · 1/day **25.29%** cover 80.6%

**Best blind by unk hit:** `BLIND_DEEP_noMA` (30.3% on 406 calls).

MA helps only if unk hit rises vs `BLIND_DEEP_noMA`. 100% OOS still requires rare multi-year atlas logic.

Pack: `C:\Users\Priyanka\Agent\stock_signal_data\fno_validate\research\nifty_1m_scalp_ma_try`
Elapsed: 495.6s
