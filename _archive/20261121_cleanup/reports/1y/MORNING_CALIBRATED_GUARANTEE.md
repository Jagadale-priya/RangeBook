# Morning calibrated guarantee (deep pass 2)

**Generated:** `2026-11-15T18:43:11`

## Guarantee

GUARANTEED: expected day range containment ~96%+ (ATR×3.5 prior-close box) on 1y/3y/5y. NOT GUARANTEED as hard gap call every day. Best calibrated gap spoken accuracy ~54% (gap_us_asia th=6.0). Use as lean + drivers. GUARANTEED when speaking bias via bias_us_asia |s|>=6.5: >=70% spoken accuracy on 1y+3y+5y. News DB MARKET history is short (~weeks); live news is used for morning analysis and logged for future proof.

## Final policy

- Range held: **YES** `pre915_atr35x_dn120`
- Gap held: **False** `gap_us_asia` th=6.0 floor=0.7
- Bias held: **True** `bias_us_asia` th=6.5 floor=0.7

- 1y gap spoken **59.1%** cov 8.7% | bias spoken **75.0%** cov 6.3%
- 3y gap spoken **54.4%** cov 9.0% | bias spoken **71.7%** cov 6.1%
- 5y gap spoken **57.9%** cov 11.1% | bias spoken **72.3%** cov 8.0%

## News recent validation

```json
{
  "available": true,
  "days": 29,
  "news_speak_days": 27,
  "news_vs_gap_acc": 0.037,
  "news_vs_dir_acc": 0.4815,
  "fuse_full_vs_gap": {
    "days_all": 0,
    "days_spoken": 0,
    "coverage": 0.0,
    "spoken_acc": null
  },
  "fuse_full_vs_dir": {
    "days_all": 0,
    "days_spoken": 0,
    "coverage": 0.0,
    "spoken_acc": null
  }
}
```

## 3y calibration bins (selected families)

### gap_fuse_full
| |score| band | n | spoken_acc | tier |
|---|---:|---:|---|
| 0-2 | 248 | 0.1331 | ABSTAIN |
| 2-4 | 226 | 0.2035 | ABSTAIN |
| 4-6 | 175 | 0.2971 | ABSTAIN |
| 6-8 | 66 | 0.3788 | ABSTAIN |
| 8-10 | 29 | 0.5172 | ABSTAIN |
| 10-999 | 12 | 0.25 | ABSTAIN |

### bias_fuse_full
| |score| band | n | spoken_acc | tier |
|---|---:|---:|---|
| 0-2 | 248 | 0.5806 | ABSTAIN |
| 2-4 | 226 | 0.5487 | ABSTAIN |
| 4-6 | 175 | 0.6057 | LOW |
| 6-8 | 66 | 0.6364 | LOW |
| 8-10 | 29 | 0.5517 | ABSTAIN |
| 10-999 | 12 | 0.6667 | ABSTAIN |

### bias_spx
| |score| band | n | spoken_acc | tier |
|---|---:|---:|---|
| 0-2 | 732 | 0.5669 | ABSTAIN |
| 2-4 | 21 | 0.5238 | ABSTAIN |
| 4-6 | 3 | 0.6667 | ABSTAIN |
| 6-8 | 0 | None |  |
| 8-10 | 0 | None |  |
| 10-999 | 0 | None |  |

### gap_ovn
| |score| band | n | spoken_acc | tier |
|---|---:|---:|---|
| 0-2 | 139 | 0.1727 | ABSTAIN |
| 2-4 | 146 | 0.1918 | ABSTAIN |
| 4-6 | 154 | 0.2078 | ABSTAIN |
| 6-8 | 139 | 0.2518 | ABSTAIN |
| 8-10 | 92 | 0.2609 | ABSTAIN |
| 10-999 | 86 | 0.3837 | ABSTAIN |

## SPX / US+Asia agree snapshots

- `agree_spx_gap_0.5`: 1y 34.9% n=63, 3y 33.9% n=180, 5y 39.8% n=334
- `agree_spx_bias_0.5`: 1y 58.7% n=63, 3y 59.4% n=180, 5y 63.2% n=334
- `agree_spx_gap_0.8`: 1y 46.7% n=30, 3y 46.4% n=97, 5y 50.0% n=204
- `agree_spx_bias_0.8`: 1y 66.7% n=30, 3y 66.0% n=97, 5y 68.6% n=204
- `agree_spx_gap_1.0`: 1y 54.5% n=22, 3y 49.3% n=73, 5y 54.4% n=160
- `agree_spx_bias_1.0`: 1y 63.6% n=22, 3y 65.8% n=73, 5y 66.9% n=160
- `agree_spx_gap_1.5`: 1y 58.3% n=12, 3y 47.4% n=38, 5y 57.6% n=85
- `agree_spx_bias_1.5`: 1y 83.3% n=12, 3y 71.0% n=38, 5y 72.9% n=85