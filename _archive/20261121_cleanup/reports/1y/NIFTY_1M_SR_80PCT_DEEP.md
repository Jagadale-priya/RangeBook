# NIFTY 1m — S/R Deep Search for ≥80% Accurate Entry

> **RESEARCH ONLY — not wired to live Scalper.**

Window 6m: **2026-05-04 → 2026-11-16** (136 sessions) · 2m: last 45 sessions · horizon 90 bars · 09:30–14:30.

## Accuracy definitions (entry path — no SL/T primary)

| Metric | Definition |
|---|---|
| **Acc%** | MFE≥20 and MFE > MAE |
| **Dom%** | MFE≥15 and MFE ≥ 1.5×MAE |
| **Dom20%** | MFE≥20 and MFE ≥ 1.5×MAE |
| **OneDir%** | MFE≥20 and MFE ≥ 2×MAE |
| **Path12s%** | +12 favour before −8 adverse |
| **Path12%** | +12 favour before −5 adverse |
| **Fav1st%** | +8 favour before −5 adverse |
| **Clean%** | MFE≥30 and MAE≤12 |

Proven bar: **≥80.0% on BOTH 2m and 6m** · n2≥12 · n6≥20 · monthly stability noted.

## PROVEN ≥80.0% on both windows

| Gate | Metric | 2m% | n2 | 6m% | n6 | stab% | edge6 | status |
|---|---|---:|---:|---:|---:|---:|---:|---|
| `held ∧ not_extreme ∧ clear15 ∧ ctrl_sweep ∧ di_ge8 ∧ mid_slot` | acc | **83.33** | 12 | **80.95** | 21 | 0.0 | 67.89 | PROVEN_80_BOTH |
| `held ∧ not_extreme ∧ clear15 ∧ tier_ab ∧ di_ge8 ∧ mid_slot` | acc | **83.33** | 12 | **80.95** | 21 | 0.0 | 67.89 | PROVEN_80_BOTH |
| `held ∧ not_extreme ∧ tier_ab ∧ di_ge8 ∧ mid_slot ∧ ctrl_clear` | acc | **83.33** | 12 | **80.95** | 21 | 0.0 | 67.89 | PROVEN_80_BOTH |
| `held ∧ not_extreme ∧ clear15 ∧ ctrl_sweep ∧ di_ge8 ∧ mid_slot` | dom | **83.33** | 12 | **80.95** | 21 | 0.0 | 67.89 | PROVEN_80_BOTH |
| `held ∧ not_extreme ∧ clear15 ∧ tier_ab ∧ di_ge8 ∧ mid_slot` | dom | **83.33** | 12 | **80.95** | 21 | 0.0 | 67.89 | PROVEN_80_BOTH |
| `held ∧ not_extreme ∧ tier_ab ∧ di_ge8 ∧ mid_slot ∧ ctrl_clear` | dom | **83.33** | 12 | **80.95** | 21 | 0.0 | 67.89 | PROVEN_80_BOTH |
| `held ∧ not_extreme ∧ clear15 ∧ ctrl_sweep ∧ di_ge8 ∧ mid_slot` | dom20 | **83.33** | 12 | **80.95** | 21 | 0.0 | 67.89 | PROVEN_80_BOTH |
| `held ∧ not_extreme ∧ clear15 ∧ tier_ab ∧ di_ge8 ∧ mid_slot` | dom20 | **83.33** | 12 | **80.95** | 21 | 0.0 | 67.89 | PROVEN_80_BOTH |
| `held ∧ not_extreme ∧ tier_ab ∧ di_ge8 ∧ mid_slot ∧ ctrl_clear` | dom20 | **83.33** | 12 | **80.95** | 21 | 0.0 | 67.89 | PROVEN_80_BOTH |
| `held ∧ not_extreme ∧ clear15 ∧ ctrl_sweep ∧ di_ge8 ∧ after1100` | acc | **80.0** | 20 | **80.0** | 45 | 50.0 | 67.87 | PROVEN_80_BOTH |
| `held ∧ not_extreme ∧ clear15 ∧ tier_ab ∧ di_ge8 ∧ after1100` | acc | **80.0** | 20 | **80.0** | 45 | 50.0 | 67.87 | PROVEN_80_BOTH |
| `held ∧ not_extreme ∧ tier_ab ∧ di_ge8 ∧ after1100 ∧ ctrl_clear` | acc | **80.0** | 20 | **80.0** | 45 | 50.0 | 67.87 | PROVEN_80_BOTH |
| `held ∧ not_extreme ∧ clear15 ∧ ctrl_sweep ∧ di_ge8 ∧ after1100` | dom | **80.0** | 20 | **80.0** | 45 | 50.0 | 67.87 | PROVEN_80_BOTH |
| `held ∧ not_extreme ∧ clear15 ∧ tier_ab ∧ di_ge8 ∧ after1100` | dom | **80.0** | 20 | **80.0** | 45 | 50.0 | 67.87 | PROVEN_80_BOTH |
| `held ∧ not_extreme ∧ tier_ab ∧ di_ge8 ∧ after1100 ∧ ctrl_clear` | dom | **80.0** | 20 | **80.0** | 45 | 50.0 | 67.87 | PROVEN_80_BOTH |
| `held ∧ not_extreme ∧ clear15 ∧ ctrl_sweep ∧ di_ge8 ∧ after1100` | dom20 | **80.0** | 20 | **80.0** | 45 | 50.0 | 67.87 | PROVEN_80_BOTH |
| `held ∧ not_extreme ∧ clear15 ∧ tier_ab ∧ di_ge8 ∧ after1100` | dom20 | **80.0** | 20 | **80.0** | 45 | 50.0 | 67.87 | PROVEN_80_BOTH |
| `held ∧ not_extreme ∧ tier_ab ∧ di_ge8 ∧ after1100 ∧ ctrl_clear` | dom20 | **80.0** | 20 | **80.0** | 45 | 50.0 | 67.87 | PROVEN_80_BOTH |

## NEAR (≥70 both, or ≥80 on 2m only)

| Gate | Metric | 2m% | n2 | 6m% | n6 | status |
|---|---|---:|---:|---:|---:|---|
| `held ∧ not_extreme ∧ clear15 ∧ sweep_with ∧ di_ge8 ∧ mid_slot` | acc | 83.33 | 12 | 77.27 | 22 | NEAR_70_BOTH |
| `held ∧ not_extreme ∧ clear15 ∧ sweep_with ∧ di_ge8 ∧ mid_slot` | dom | 83.33 | 12 | 77.27 | 22 | NEAR_70_BOTH |
| `held ∧ not_extreme ∧ clear15 ∧ sweep_with ∧ di_ge8 ∧ mid_slot` | dom20 | 83.33 | 12 | 77.27 | 22 | NEAR_70_BOTH |
| `held ∧ not_extreme ∧ clear15 ∧ ctrl_sweep ∧ di_ge8 ∧ after1030` | acc | 80.0 | 20 | 76.47 | 51 | NEAR_70_BOTH |
| `held ∧ not_extreme ∧ clear15 ∧ tier_ab ∧ di_ge8 ∧ after1030` | acc | 80.0 | 20 | 76.47 | 51 | NEAR_70_BOTH |
| `held ∧ not_extreme ∧ tier_ab ∧ di_ge8 ∧ after1030 ∧ ctrl_clear` | acc | 80.0 | 20 | 76.47 | 51 | NEAR_70_BOTH |
| `held ∧ not_extreme ∧ clear30 ∧ control_with ∧ ind_strict3 ∧ mid_slot` | path12_strict | 83.33 | 12 | 76.19 | 21 | NEAR_70_BOTH |
| `held ∧ not_extreme ∧ clear30 ∧ ind_strict3 ∧ mid_slot ∧ ctrl_clear` | path12_strict | 83.33 | 12 | 76.19 | 21 | NEAR_70_BOTH |
| `held ∧ not_extreme ∧ control_with ∧ runway_3atr ∧ ind_strict3 ∧ mid_slot` | path12_strict | 83.33 | 12 | 76.19 | 21 | NEAR_70_BOTH |
| `held ∧ not_extreme ∧ clear15 ∧ ctrl_sweep ∧ di_ge8 ∧ after1030` | dom | 80.0 | 20 | 74.51 | 51 | NEAR_70_BOTH |
| `held ∧ not_extreme ∧ clear15 ∧ tier_ab ∧ di_ge8 ∧ after1030` | dom | 80.0 | 20 | 74.51 | 51 | NEAR_70_BOTH |
| `held ∧ not_extreme ∧ tier_ab ∧ di_ge8 ∧ after1030 ∧ ctrl_clear` | dom | 80.0 | 20 | 74.51 | 51 | NEAR_70_BOTH |
| `held ∧ not_extreme ∧ clear15 ∧ ctrl_sweep ∧ di_ge8 ∧ after1030` | dom20 | 80.0 | 20 | 74.51 | 51 | NEAR_70_BOTH |
| `held ∧ not_extreme ∧ clear15 ∧ tier_ab ∧ di_ge8 ∧ after1030` | dom20 | 80.0 | 20 | 74.51 | 51 | NEAR_70_BOTH |
| `held ∧ not_extreme ∧ tier_ab ∧ di_ge8 ∧ after1030 ∧ ctrl_clear` | dom20 | 80.0 | 20 | 74.51 | 51 | NEAR_70_BOTH |
| `held ∧ not_extreme ∧ clear15 ∧ reg_hold ∧ di_ge8` | acc | 80.0 | 15 | 69.77 | 43 | 80_2m_only |
| `held ∧ not_extreme ∧ clear15 ∧ tier_a ∧ di_ge8` | acc | 80.0 | 15 | 69.77 | 43 | 80_2m_only |
| `held ∧ not_extreme ∧ reg_hold ∧ di_ge8 ∧ ctrl_clear` | acc | 80.0 | 15 | 69.77 | 43 | 80_2m_only |
| `held ∧ not_extreme ∧ tier_a ∧ di_ge8 ∧ ctrl_clear` | acc | 80.0 | 15 | 69.77 | 43 | 80_2m_only |
| `held ∧ not_extreme ∧ clear15 ∧ backed10 ∧ ctrl_sweep ∧ di_ge8` | acc | 80.0 | 15 | 69.77 | 43 | 80_2m_only |
| `held ∧ not_extreme ∧ clear15 ∧ backed10 ∧ reg_hold ∧ di_ge8` | acc | 80.0 | 15 | 69.77 | 43 | 80_2m_only |
| `held ∧ not_extreme ∧ clear15 ∧ backed10 ∧ tier_a ∧ di_ge8` | acc | 80.0 | 15 | 69.77 | 43 | 80_2m_only |
| `held ∧ not_extreme ∧ clear15 ∧ backed10 ∧ tier_ab ∧ di_ge8` | acc | 80.0 | 15 | 69.77 | 43 | 80_2m_only |
| `held ∧ not_extreme ∧ clear15 ∧ control_with ∧ reg_hold ∧ di_ge8` | acc | 80.0 | 15 | 69.77 | 43 | 80_2m_only |
| `held ∧ not_extreme ∧ clear15 ∧ control_with ∧ tier_a ∧ di_ge8` | acc | 80.0 | 15 | 69.77 | 43 | 80_2m_only |
| `held ∧ not_extreme ∧ clear15 ∧ sweep_with ∧ reg_hold ∧ di_ge8` | acc | 80.0 | 15 | 69.77 | 43 | 80_2m_only |
| `held ∧ not_extreme ∧ clear15 ∧ sweep_with ∧ tier_a ∧ di_ge8` | acc | 80.0 | 15 | 69.77 | 43 | 80_2m_only |
| `held ∧ not_extreme ∧ clear15 ∧ ctrl_sweep ∧ reg_hold ∧ di_ge8` | acc | 80.0 | 15 | 69.77 | 43 | 80_2m_only |
| `held ∧ not_extreme ∧ clear15 ∧ ctrl_sweep ∧ tier_a ∧ di_ge8` | acc | 80.0 | 15 | 69.77 | 43 | 80_2m_only |
| `held ∧ not_extreme ∧ clear15 ∧ reg_hold ∧ tier_a ∧ di_ge8` | acc | 80.0 | 15 | 69.77 | 43 | 80_2m_only |
| `held ∧ not_extreme ∧ clear15 ∧ reg_hold ∧ tier_ab ∧ di_ge8` | acc | 80.0 | 15 | 69.77 | 43 | 80_2m_only |
| `held ∧ not_extreme ∧ clear15 ∧ reg_hold ∧ di_ge8 ∧ not_compress` | acc | 80.0 | 15 | 69.77 | 43 | 80_2m_only |
| `held ∧ not_extreme ∧ clear15 ∧ reg_hold ∧ di_ge8 ∧ ctrl_clear` | acc | 80.0 | 15 | 69.77 | 43 | 80_2m_only |
| `held ∧ not_extreme ∧ clear15 ∧ tier_a ∧ tier_ab ∧ di_ge8` | acc | 80.0 | 15 | 69.77 | 43 | 80_2m_only |
| `held ∧ not_extreme ∧ clear15 ∧ tier_a ∧ di_ge8 ∧ not_compress` | acc | 80.0 | 15 | 69.77 | 43 | 80_2m_only |
| `held ∧ not_extreme ∧ clear15 ∧ tier_a ∧ di_ge8 ∧ ctrl_clear` | acc | 80.0 | 15 | 69.77 | 43 | 80_2m_only |
| `held ∧ not_extreme ∧ backed10 ∧ reg_hold ∧ di_ge8 ∧ ctrl_clear` | acc | 80.0 | 15 | 69.77 | 43 | 80_2m_only |
| `held ∧ not_extreme ∧ backed10 ∧ tier_a ∧ di_ge8 ∧ ctrl_clear` | acc | 80.0 | 15 | 69.77 | 43 | 80_2m_only |
| `held ∧ not_extreme ∧ backed10 ∧ tier_ab ∧ di_ge8 ∧ ctrl_clear` | acc | 80.0 | 15 | 69.77 | 43 | 80_2m_only |
| `held ∧ not_extreme ∧ control_with ∧ reg_hold ∧ di_ge8 ∧ ctrl_clear` | acc | 80.0 | 15 | 69.77 | 43 | 80_2m_only |
| `held ∧ not_extreme ∧ control_with ∧ tier_a ∧ di_ge8 ∧ ctrl_clear` | acc | 80.0 | 15 | 69.77 | 43 | 80_2m_only |
| `held ∧ not_extreme ∧ sweep_with ∧ reg_hold ∧ di_ge8 ∧ ctrl_clear` | acc | 80.0 | 15 | 69.77 | 43 | 80_2m_only |
| `held ∧ not_extreme ∧ sweep_with ∧ tier_a ∧ di_ge8 ∧ ctrl_clear` | acc | 80.0 | 15 | 69.77 | 43 | 80_2m_only |
| `held ∧ not_extreme ∧ ctrl_sweep ∧ reg_hold ∧ di_ge8 ∧ ctrl_clear` | acc | 80.0 | 15 | 69.77 | 43 | 80_2m_only |
| `held ∧ not_extreme ∧ ctrl_sweep ∧ tier_a ∧ di_ge8 ∧ ctrl_clear` | acc | 80.0 | 15 | 69.77 | 43 | 80_2m_only |
| `held ∧ not_extreme ∧ reg_hold ∧ tier_a ∧ di_ge8 ∧ ctrl_clear` | acc | 80.0 | 15 | 69.77 | 43 | 80_2m_only |
| `held ∧ not_extreme ∧ reg_hold ∧ tier_ab ∧ di_ge8 ∧ ctrl_clear` | acc | 80.0 | 15 | 69.77 | 43 | 80_2m_only |
| `held ∧ not_extreme ∧ reg_hold ∧ di_ge8 ∧ not_compress ∧ ctrl_clear` | acc | 80.0 | 15 | 69.77 | 43 | 80_2m_only |
| `held ∧ not_extreme ∧ tier_a ∧ tier_ab ∧ di_ge8 ∧ ctrl_clear` | acc | 80.0 | 15 | 69.77 | 43 | 80_2m_only |
| `held ∧ not_extreme ∧ tier_a ∧ di_ge8 ∧ not_compress ∧ ctrl_clear` | acc | 80.0 | 15 | 69.77 | 43 | 80_2m_only |

## Hand stacks — best metric on 6m (diagnostic)

| Gate | n6 | best | Acc | Dom | Dom20 | OneDir | Path12s | Fav1st | Clean | avgMFE | avgMAE |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `trend + ctrl + sweep + clear20` | 10 | acc@80.0 | 80.0 | 70.0 | 70.0 | 60.0 | 40.0 | 50.0 | 30.0 | 110.89 | 31.69 |
| `trend + ctrl + sweep + clear20 + di8` | 10 | acc@80.0 | 80.0 | 70.0 | 70.0 | 60.0 | 40.0 | 50.0 | 30.0 | 110.89 | 31.69 |
| `P6strict: trend+ctrl+sweep+clear20+di8+adx22` | 10 | acc@80.0 | 80.0 | 70.0 | 70.0 | 60.0 | 40.0 | 50.0 | 30.0 | 110.89 | 31.69 |
| `P1strict: bounce+backed08+ctrl+sweep+clear20+di8` | 18 | acc@72.22 | 72.22 | 72.22 | 72.22 | 50.0 | 22.22 | 27.78 | 27.78 | 85.16 | 42.98 |
| `tierAB + clear20 + ctrl + di8 + after1030` | 32 | acc@68.75 | 68.75 | 68.75 | 68.75 | 56.25 | 31.25 | 40.62 | 28.12 | 92.48 | 42.12 |
| `TierAB + clear15` | 96 | acc@62.5 | 62.5 | 55.21 | 55.21 | 42.71 | 42.71 | 41.67 | 30.21 | 69.31 | 44.04 |
| `bounce + backed + ctrl + sweep + clear15` | 46 | acc@60.87 | 60.87 | 54.35 | 54.35 | 39.13 | 36.96 | 34.78 | 26.09 | 62.21 | 50.02 |
| `TierA + clear15` | 65 | acc@60.0 | 60.0 | 53.85 | 53.85 | 40.0 | 40.0 | 40.0 | 27.69 | 61.83 | 47.52 |
| `hold + ctrl + clear15` | 65 | acc@60.0 | 60.0 | 53.85 | 53.85 | 40.0 | 40.0 | 40.0 | 27.69 | 61.83 | 47.52 |
| `hold + ctrl + sweep + clear15` | 65 | acc@60.0 | 60.0 | 53.85 | 53.85 | 40.0 | 40.0 | 40.0 | 27.69 | 61.83 | 47.52 |
| `TierAB + clear20` | 53 | acc@58.49 | 58.49 | 50.94 | 50.94 | 41.51 | 32.08 | 35.85 | 22.64 | 69.17 | 47.2 |
| `HELD + clear30` | 231 | acc@57.14 | 57.14 | 48.92 | 48.92 | 42.86 | 42.42 | 41.99 | 19.48 | 64.8 | 44.68 |
| `bounce + backed + ctrl + sweep + clear20` | 30 | acc@56.67 | 56.67 | 50.0 | 50.0 | 36.67 | 30.0 | 30.0 | 23.33 | 64.31 | 51.64 |
| `bounce + backed08 + ctrl + clear20 + di8` | 138 | acc@56.52 | 56.52 | 52.17 | 51.45 | 41.3 | 44.2 | 45.65 | 23.91 | 64.05 | 46.98 |
| `ULTRA2: hold+backed08+ctrl+sweep+clear20+di12+adx22` | 18 | acc@55.56 | 55.56 | 55.56 | 55.56 | 44.44 | 16.67 | 27.78 | 27.78 | 60.05 | 52.69 |
| `macd_di + clear20 + ctrl + not_extreme` | 299 | acc@55.52 | 55.52 | 48.49 | 48.16 | 42.47 | 46.15 | 44.82 | 23.41 | 64.71 | 45.15 |
| `hold|bounce + ctrl + clear20 + di8` | 148 | acc@55.41 | 55.41 | 50.68 | 50.0 | 40.54 | 43.24 | 45.27 | 22.97 | 63.26 | 47.69 |
| `tierA + clear20 + di12 + adx22` | 22 | acc@54.55 | 54.55 | 50.0 | 50.0 | 40.91 | 27.27 | 36.36 | 22.73 | 59.83 | 49.48 |
| `P3strict: (hold|bounce)+ctrl+clear20+di8+strong` | 106 | acc@53.77 | 53.77 | 50.0 | 49.06 | 41.51 | 50.0 | 50.94 | 23.58 | 64.32 | 48.4 |
| `hold|bounce + ctrl + clear20 + di12 + strong` | 95 | acc@53.68 | 53.68 | 51.58 | 50.53 | 42.11 | 53.68 | 51.58 | 26.32 | 62.23 | 49.48 |
| `TierA + clear20` | 41 | acc@53.66 | 53.66 | 46.34 | 46.34 | 36.59 | 31.71 | 34.15 | 21.95 | 61.33 | 51.83 |
| `hold + ctrl + clear20` | 41 | acc@53.66 | 53.66 | 46.34 | 46.34 | 36.59 | 31.71 | 34.15 | 21.95 | 61.33 | 51.83 |
| `hold + backed + ctrl + clear20` | 41 | acc@53.66 | 53.66 | 46.34 | 46.34 | 36.59 | 31.71 | 34.15 | 21.95 | 61.33 | 51.83 |
| `HELD + clear15` | 862 | acc@53.25 | 53.25 | 46.06 | 45.59 | 39.91 | 40.84 | 40.72 | 21.0 | 58.27 | 47.82 |
| `trend + ctrl + clear20 + adx25 + after1030` | 228 | acc@53.07 | 53.07 | 48.68 | 48.25 | 41.67 | 45.61 | 44.3 | 19.74 | 64.27 | 46.94 |
| `HELD + clear20` | 516 | acc@52.33 | 52.33 | 45.93 | 45.35 | 39.73 | 41.09 | 40.12 | 19.96 | 61.24 | 47.61 |
| `HELD raw` | 8180 | acc@51.6 | 51.6 | 43.64 | 43.48 | 37.43 | 41.06 | 40.72 | 19.52 | 51.4 | 47.15 |
| `hold|bounce + ctrl_sweep + clear20 + adx22` | 37 | acc@51.35 | 51.35 | 45.95 | 45.95 | 37.84 | 29.73 | 32.43 | 24.32 | 52.24 | 50.06 |
| `ind_strict3 + clear20 + ctrl` | 100 | acc@51.0 | 51.0 | 44.0 | 44.0 | 38.0 | 47.0 | 48.0 | 22.0 | 62.77 | 45.04 |
| `ind_strict3 + clear20 + ctrl + bounce|hold` | 56 | acc@50.0 | 50.0 | 46.43 | 46.43 | 37.5 | 42.86 | 48.21 | 19.64 | 61.43 | 45.59 |
| `pm_slot + hold + ctrl + clear20` | 14 | acc@50.0 | 50.0 | 50.0 | 50.0 | 42.86 | 21.43 | 28.57 | 21.43 | 87.11 | 62.57 |
| `vwap_reclaim + clear20 + ctrl + di8` | 8 | fav1st@50.0 | 12.5 | 0.0 | 0.0 | 0.0 | 25.0 | 50.0 | 0.0 | 34.88 | 83.55 |
| `open_slot + bounce + backed + ctrl + clear15` | 81 | acc@48.15 | 48.15 | 43.21 | 43.21 | 37.04 | 39.51 | 40.74 | 19.75 | 38.73 | 42.05 |
| `breakout + ctrl + clear20 + !extreme` | 0 | None@-1 | None | None | None | None | None | None | None | None | None |
| `breakout + ctrl + clear30 + strong_body` | 0 | None@-1 | None | None | None | None | None | None | None | None | None |

## Ceiling — raw HELD base rates (why 80% is hard)

| Pool | n | Acc | Dom | Dom20 | OneDir | Path12s | Fav1st | Clean |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2m HELD | 2656 | 53.95 | 47.33 | 47.33 | 41.83 | 41.68 | 42.51 | 18.86 |
| 6m HELD | 8180 | 51.6 | 43.64 | 43.48 | 37.43 | 41.06 | 40.72 | 19.52 |

## Samples — `held ∧ not_extreme ∧ clear15 ∧ ctrl_sweep ∧ di_ge8 ∧ mid_slot` (2m)

### Hits (Acc)

| Day | HM | Side | Regime | room_fav | MFE | MAE | Dom | Path12s |
|---|---|---|---|---:|---:|---:|---|---|
| 2026-09-22 | 12:02 | SELL | hold_break | 14.5 | 36.9 | 12.1 | True | False |
| 2026-09-24 | 12:31 | SELL | hold_break | 13.0 | 139.8 | 2.1 | True | True |
| 2026-09-29 | 11:18 | BUY | hold_break | 27.5 | 79.25 | 46.5 | True | True |
| 2026-10-01 | 12:16 | SELL | trend | 18.05 | 245.2 | 3.4 | True | True |
| 2026-10-01 | 12:35 | SELL | trend | 16.85 | 257.75 | 10.35 | True | False |
| 2026-10-21 | 11:47 | SELL | hold_break | 20.65 | 131.8 | 1.75 | True | True |
| 2026-11-04 | 11:12 | SELL | flip | 29.45 | 69.5 | 38.6 | True | False |
| 2026-11-05 | 12:20 | BUY | hold_break | 17.15 | 154.85 | 8.7 | True | False |
| 2026-11-05 | 12:21 | BUY | trend | 13.9 | 151.6 | 11.95 | True | False |
| 2026-11-06 | 12:25 | BUY | hold_break | 26.1 | 139.85 | 29.45 | True | True |

### Misses (!Acc) — learn

| Day | HM | Side | Regime | into_ext | clear20 | MFE | MAE |
|---|---|---|---|---|---|---:|---:|
| 2026-09-10 | 12:13 | BUY | hold_break | False | True | 15.9 | 34.85 |
| 2026-09-10 | 12:20 | BUY | trend | False | True | 9.7 | 41.05 |

Elapsed 581s

## Next research steps (still not live)

1. If no ≥80 both-window gate: add **2-bar confirm** (next bar holds favour) as entry delay.
2. Split by **VIX / range-day vs trend-day** — 80% may exist only in one regime.
3. Require **liquidity pool distance** (equal-high/low magnet) tags.
4. Walk-forward month-by-month promotion only when stab_ok.
5. Wire to Scalper **only after** a PROVEN_80_BOTH gate is locked.
