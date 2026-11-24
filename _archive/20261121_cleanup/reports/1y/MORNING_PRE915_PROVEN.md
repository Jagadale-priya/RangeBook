# PRE-9:15 morning context — proven hunt (no calls)

**Generated:** `2026-11-15T18:04:20`

## Scope

Runs **before 9:15 IST**. Uses overnight globals + prior-day NSE TA/trend only.
Does **not** use today's cash open.

## Recommendation

### Gap (premarket)
- rule `spx_th150` · promote **False** · floor 0.9
  - 1y: spoken **56.5%** · cov 9.1% · n=23
  - 3y: spoken **47.8%** · cov 8.9% · n=67
  - 5y: spoken **62.7%** · cov 12.8% · n=161

### Bias close vs prior
- rule `spx_th100` · promote **False** · floor 0.9
  - 1y: spoken **66.0%** · cov 21.0% · n=53
  - 3y: spoken **65.0%** · cov 20.8% · n=157
  - 5y: spoken **68.0%** · cov 27.1% · n=341

### Bias open→close proxy
- rule `ovn_th5` · promote **False** · floor 0.9
  - 1y: spoken **46.6%** · cov 46.0% · n=116
  - 3y: spoken **45.1%** · cov 42.9% · n=324
  - 5y: spoken **47.4%** · cov 42.0% · n=529

### Range (provisional pre-open)
- 3y full containment **89.1%** · width 2.99%
- Premarket provisional (center=prior close). Weaker than open-locked V4.

## Held defaults if promote=False

- gap → **NATURAL** (until open)
- bias → **NEUTRAL**
- still emit expected range width + overnight panel + trend/TA context + news tone

## 3y tops (train spoken)

### Gap
| Rule | Train acc | Train cov | Test acc | Test cov |
|---|---:|---:|---:|---:|
| `spx_th150` | 0.6654 | 0.1232 | 0.4776 | 0.0886 |
| `spx_th100` | 0.6225 | 0.2515 | 0.4713 | 0.2077 |
| `spx_th080` | 0.5633 | 0.333 | 0.4279 | 0.2751 |
| `spx080_struct` | 0.529 | 0.1357 | 0.4125 | 0.1058 |
| `spx_th050` | 0.4757 | 0.4947 | 0.3316 | 0.4947 |
| `ovn_th7` | 0.4505 | 0.2057 | 0.2761 | 0.2156 |
| `ovn5_prior_candle` | 0.4359 | 0.2348 | 0.3216 | 0.2262 |
| `ovn_th5` | 0.4156 | 0.3923 | 0.2932 | 0.4286 |

### Bias
| Rule | Train acc | Train cov | Test acc | Test cov |
|---|---:|---:|---:|---:|
| `spx_th080` | 0.6871 | 0.333 | 0.6442 | 0.2751 |
| `spx_th100` | 0.6796 | 0.2515 | 0.6497 | 0.2077 |
| `ovn5_struct_rsi` | 0.669 | 0.1343 | 0.5794 | 0.1415 |
| `ovn_th7` | 0.6554 | 0.2057 | 0.5951 | 0.2156 |
| `spx100_struct_sma` | 0.655 | 0.0792 | 0.5926 | 0.0714 |
| `ovn5_spx_struct` | 0.6429 | 0.1232 | 0.5824 | 0.1204 |
| `ovn_th5` | 0.6364 | 0.3923 | 0.5895 | 0.4286 |
| `ovn7_struct_candle` | 0.6337 | 0.0468 | 0.4516 | 0.041 |

### Bias OTC
| Rule | Train acc | Train cov | Test acc | Test cov |
|---|---:|---:|---:|---:|
| `ovn_th7` | 0.5405 | 0.2057 | 0.454 | 0.2156 |
| `ovn_th5` | 0.5207 | 0.3923 | 0.4506 | 0.4286 |
| `ovn5_struct_rsi` | 0.5207 | 0.1343 | 0.4019 | 0.1415 |
| `spx_th080` | 0.5188 | 0.333 | 0.4183 | 0.2751 |
| `ovn_th3` | 0.5119 | 0.6614 | 0.4492 | 0.7037 |
| `spx_th100` | 0.5028 | 0.2515 | 0.3949 | 0.2077 |
| `ovn5_spx_struct` | 0.4887 | 0.1232 | 0.4066 | 0.1204 |
| `struct_only` | 0.4799 | 0.7943 | 0.4652 | 0.7593 |
