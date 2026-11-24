# NIFTY morning range — hunt ≥90% full containment

**Generated:** `2026-11-15T17:38:09`

Accuracy = (Low ≥ lo) AND (High ≤ hi). Fit on train only; promote only if **test ≥ 90%**.

## last_1y  (`2025-11-03` → `2026-11-11`)
Train 3367 · Test 252 · candidates 135 · train≥90% 70 · test≥90% 75

### Train-picked (≥90% then tightest width): `hybrid_atr22_max20__up100_dn110`
- train containment **90.5%** · width 2.90%
- test containment **91.3%** · width 2.74% · high_ok 97.6% · low_ok 93.7%
- **Promote?** YES

- Held V2 on test: **74.6%** contain · width 1.87%

Tightest train≥90% (top):

| Method | Train contain | Train width | Test contain | Test width |
|---|---:|---:|---:|---:|
| `hybrid_atr22_max20__up100_dn110` | 90.5% | 2.90% | 91.3% | 2.74% |
| `max_yday_atr_2_0x__up100_dn120` | 90.0% | 2.91% | 91.3% | 2.72% |
| `atr14_2_2x__up100_dn120` | 91.0% | 2.96% | 92.1% | 2.72% |
| `max_yday_atr_2_0x__up115_dn115` | 91.0% | 3.02% | 92.9% | 2.84% |
| `max20_1_2x__up115_dn115` | 90.1% | 3.02% | 88.9% | 2.84% |
| `hybrid_atr22_max20__up100_dn120` | 91.8% | 3.03% | 92.5% | 2.87% |
| `max_yday_atr_2_2x__up100_dn110` | 91.6% | 3.04% | 93.2% | 2.86% |
| `max_yday_atr_2_2x__up110_dn100` | 90.5% | 3.04% | 90.9% | 2.86% |
| `hybrid_atr25_p95__sym` | 91.6% | 3.05% | 92.1% | 2.81% |
| `atr14_2_5x__sym` | 91.6% | 3.05% | 92.1% | 2.81% |

## last_3y  (`2023-10-16` → `2026-11-11`)
Train 2863 · Test 756 · candidates 135 · train≥90% 72 · test≥90% 66

### Train-picked (≥90% then tightest width): `hybrid_atr22_max20__up100_dn110`
- train containment **90.8%** · width 3.00%
- test containment **89.5%** · width 2.56% · high_ok 95.6% · low_ok 93.9%
- **Promote?** NO — test below 90%

- Held V2 on test: **72.2%** contain · width 1.78%

Tightest train≥90% (top):

| Method | Train contain | Train width | Test contain | Test width |
|---|---:|---:|---:|---:|
| `hybrid_atr22_max20__up100_dn110` | 90.8% | 3.00% | 89.5% | 2.56% |
| `max_yday_atr_2_0x__up100_dn120` | 90.3% | 3.00% | 89.4% | 2.58% |
| `max_yday_atr_2_2x__sym` | 90.1% | 3.00% | 89.4% | 2.58% |
| `atr14_2_4x__sym` | 90.1% | 3.03% | 89.5% | 2.63% |
| `atr14_2_2x__up100_dn120` | 91.4% | 3.05% | 90.0% | 2.65% |
| `max20_1_2x__up115_dn115` | 90.3% | 3.09% | 89.3% | 2.85% |
| `max_yday_atr_2_0x__up115_dn115` | 91.2% | 3.13% | 90.7% | 2.69% |
| `hybrid_atr22_max20__up100_dn120` | 92.2% | 3.14% | 90.7% | 2.68% |
| `hybrid_atr25_p95__sym` | 91.8% | 3.14% | 90.9% | 2.74% |
| `max_yday_atr_2_2x__up100_dn110` | 91.9% | 3.15% | 91.1% | 2.70% |

## last_5y  (`2021-10-04` → `2026-11-11`)
Train 2359 · Test 1260 · candidates 135 · train≥90% 70 · test≥90% 72

### Train-picked (≥90% then tightest width): `hybrid_atr22_max20__up100_dn110`
- train containment **90.8%** · width 3.00%
- test containment **90.2%** · width 2.70% · high_ok 96.4% · low_ok 93.9%
- **Promote?** YES

- Held V2 on test: **72.8%** contain · width 1.87%

Tightest train≥90% (top):

| Method | Train contain | Train width | Test contain | Test width |
|---|---:|---:|---:|---:|
| `hybrid_atr22_max20__up100_dn110` | 90.8% | 3.00% | 90.2% | 2.70% |
| `max_yday_atr_2_0x__up100_dn120` | 90.1% | 3.00% | 90.2% | 2.71% |
| `atr14_2_2x__up100_dn120` | 91.0% | 3.04% | 91.2% | 2.77% |
| `max20_1_2x__up115_dn115` | 90.1% | 3.09% | 89.9% | 2.89% |
| `hybrid_atr22_max20__up100_dn120` | 92.0% | 3.14% | 91.7% | 2.82% |
| `hybrid_atr25_p95__sym` | 91.4% | 3.14% | 92.1% | 2.86% |
| `atr14_2_5x__sym` | 91.3% | 3.14% | 92.1% | 2.86% |
| `max_yday_atr_2_0x__up115_dn115` | 90.9% | 3.14% | 91.6% | 2.82% |
| `max_yday_atr_2_2x__up100_dn110` | 91.7% | 3.15% | 91.8% | 2.84% |
| `max_yday_atr_2_2x__up110_dn100` | 90.3% | 3.15% | 91.0% | 2.84% |

## Recommendation

- method: `hybrid_atr22_max20__up100_dn120`
- promote: **True**
- 1y test: 0.9246
- 3y test: 0.9074
- 5y test: 0.9167

If promote=YES, freeze as MORNING_CTX_V3 range rule.
