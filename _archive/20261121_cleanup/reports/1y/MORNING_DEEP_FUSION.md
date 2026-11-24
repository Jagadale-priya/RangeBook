# Morning deep fusion validation

**Generated:** `2026-11-15T18:40:24`
**Rows:** 2915 (2015-01-06 → 2026-11-11)
**News PIT coverage:** 1.03%

## Final recommendation

- **Range held:** `pre915_atr35x_dn120` — full containment ~96% on 1y/3y/5y (held)
- **Gap held:** `False` rule=`fuse_us_asia_th6` floor=`0.7`
- **Bias held:** `False` rule=`spx_th150` floor=`0.7`
- **Policy:** `MORNING_FUSION_TIERED_V1`

### Range stats

- **1y:** containment **96.4%** median width 4.10%
- **3y:** containment **96.6%** median width 4.03%
- **5y:** containment **97.2%** median width 4.19%

## Family bests

### gap
- rule `fuse_us_asia_th6` floor=0.7 promote=False walk_min=0.3529 walk_mean=0.5357
  - 1y: spoken **59.1%** cov 8.7% n=22
  - 3y: spoken **54.4%** cov 9.0% n=68
  - 5y: spoken **57.9%** cov 11.1% n=140

| Top train | Train acc | Train cov | Test acc | Test cov |
|---|---:|---:|---:|---:|
| `spx_th200` | 0.7589 | 0.0653 | 0.4583 | 0.0317 |
| `us_extreme_vix` | 0.6888 | 0.1116 | 0.4844 | 0.0847 |
| `spx_th150` | 0.6654 | 0.1232 | 0.4776 | 0.0886 |
| `fuse_us_asia_th8` | 0.625 | 0.0259 | 0.2857 | 0.0185 |
| `spx_th100` | 0.6225 | 0.2515 | 0.4713 | 0.2077 |
| `spx100_agree4` | 0.6208 | 0.2492 | 0.4744 | 0.2063 |
| `fuse_full_th8` | 0.5753 | 0.0676 | 0.45 | 0.0529 |
| `spx_th080` | 0.5633 | 0.333 | 0.4279 | 0.2751 |

### gap_big
- rule `spx_th200` floor=0.7 promote=False walk_min=0.25 walk_mean=0.5295
  - 1y: spoken **40.0%** cov 2.0% n=5
  - 3y: spoken **33.3%** cov 3.2% n=24
  - 5y: spoken **56.8%** cov 5.9% n=74

| Top train | Train acc | Train cov | Test acc | Test cov |
|---|---:|---:|---:|---:|
| `spx_th200` | 0.6383 | 0.0653 | 0.3333 | 0.0317 |
| `us_extreme_vix` | 0.5394 | 0.1116 | 0.3281 | 0.0847 |
| `spx_th150` | 0.5226 | 0.1232 | 0.3284 | 0.0886 |
| `fuse_us_asia_th8` | 0.4286 | 0.0259 | 0.1429 | 0.0185 |
| `fuse_full_th8` | 0.3904 | 0.0676 | 0.25 | 0.0529 |
| `spx_th100` | 0.3831 | 0.2515 | 0.2739 | 0.2077 |
| `spx100_agree4` | 0.381 | 0.2492 | 0.2756 | 0.2063 |
| `fuse_full_th10` | 0.375 | 0.0148 | 0.1 | 0.0132 |

### bias_close
- rule `spx_th150` floor=0.7 promote=False walk_min=0.6222 walk_mean=0.7102
  - 1y: spoken **73.9%** cov 9.1% n=23
  - 3y: spoken **67.2%** cov 8.9% n=67
  - 5y: spoken **72.7%** cov 12.8% n=161

| Top train | Train acc | Train cov | Test acc | Test cov |
|---|---:|---:|---:|---:|
| `spx_th150` | 0.7218 | 0.1232 | 0.6716 | 0.0886 |
| `spx_th080` | 0.6871 | 0.333 | 0.6442 | 0.2751 |
| `fuse_full_th6` | 0.6867 | 0.1774 | 0.6132 | 0.1402 |
| `votes4` | 0.6806 | 0.2654 | 0.5739 | 0.2328 |
| `votes4_fuse_sign` | 0.6806 | 0.2654 | 0.5739 | 0.2328 |
| `spx_th100` | 0.6796 | 0.2515 | 0.6497 | 0.2077 |
| `ovn_th11` | 0.6691 | 0.1246 | 0.6481 | 0.0714 |
| `ovn5_struct_rsi` | 0.6659 | 0.1913 | 0.5693 | 0.1812 |

### bias_big
- rule `spx_th150` floor=0.7 promote=False walk_min=0.3778 walk_mean=0.4803
  - 1y: spoken **47.8%** cov 9.1% n=23
  - 3y: spoken **38.8%** cov 8.9% n=67
  - 5y: spoken **48.4%** cov 12.8% n=161

| Top train | Train acc | Train cov | Test acc | Test cov |
|---|---:|---:|---:|---:|
| `spx_th150` | 0.5489 | 0.1232 | 0.3881 | 0.0886 |
| `spx_th100` | 0.4825 | 0.2515 | 0.3567 | 0.2077 |
| `spx_th080` | 0.4743 | 0.333 | 0.351 | 0.2751 |
| `ovn_th11` | 0.4535 | 0.1246 | 0.3704 | 0.0714 |
| `fuse_full_th8` | 0.4452 | 0.0676 | 0.325 | 0.0529 |
| `spx100_struct_sma` | 0.4444 | 0.0792 | 0.2963 | 0.0714 |
| `fuse_full_th6` | 0.436 | 0.1774 | 0.3113 | 0.1402 |
| `votes4` | 0.4258 | 0.2654 | 0.2955 | 0.2328 |

### bias_otc
- rule `fuse_ovn_ta_th6` floor=0.7 promote=False walk_min=0.4518 walk_mean=0.4925
  - 1y: spoken **46.6%** cov 46.8% n=118
  - 3y: spoken **45.8%** cov 45.9% n=347
  - 5y: spoken **48.3%** cov 46.5% n=586

| Top train | Train acc | Train cov | Test acc | Test cov |
|---|---:|---:|---:|---:|
| `ovn_th11` | 0.5539 | 0.1246 | 0.4074 | 0.0714 |
| `fuse_full_th8` | 0.5411 | 0.0676 | 0.4 | 0.0529 |
| `fuse6_us_asia` | 0.5386 | 0.27 | 0.4323 | 0.254 |
| `votes4` | 0.5375 | 0.2654 | 0.4261 | 0.2328 |
| `votes4_fuse_sign` | 0.5375 | 0.2654 | 0.4261 | 0.2328 |
| `fuse_full_th6` | 0.5326 | 0.1774 | 0.3774 | 0.1402 |
| `fuse_full_th4` | 0.5308 | 0.3909 | 0.4184 | 0.373 |
| `spx_th150` | 0.5226 | 0.1232 | 0.3881 | 0.0886 |

## Guarantee statement

Guarantee only applies to HELD rules that cleared windows+walk. Unheld sides use abstain or low-confidence lean, never fake 90%.

Live morning job should emit directional gap/bias **only** via held rules or explicitly marked low-confidence lean.
