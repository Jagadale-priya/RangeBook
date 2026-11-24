# 15m × 5m model agreement — deep analysis

**15m:** `good_prod2` (`fno_NIFTY.pkl`, issued_prod, max 2/day)  
**5m:** `proven_100` · `champion` · `crown_5m` (live pool, path-scored)

Research only. Held stack unchanged.

## Baselines (3y)

| Book | N | Hit | Day cov | No-call |
|---|---:|---:|---:|---:|
| `15m_prod2_alone` | 375 | **69.6%** | 45.9% | 344 |
| `5m_proven_alone` | 39 | **100.0%** | 6.0% | 598 |
| `5m_champ_alone` | 110 | **83.64%** | 15.4% | 538 |
| `5m_crown_htf_alone` | 301 | **74.75%** | 24.7% | 479 |
| `5m_union_cap2` | 369 | **79.95%** | 39.5% | 385 |
| `stack_held` | 607 | **75.95%** | 62.9% | 236 |

## 3y board (hit-ranked, n≥12)

| Approach | N | Hit | Day cov | No-call |
|---|---:|---:|---:|---:|
| `5m_proven_alone` | 39 | **100.0%** | 6.0% | 598 |
| `proven_if_15m` | 22 | **100.0%** | 3.5% | 614 |
| `agree_proven_5mentry` | 22 | **100.0%** | 3.5% | 614 |
| `time_any5_60m` | 87 | **91.95%** | 13.7% | 549 |
| `time_any5_15m` | 62 | **91.94%** | 9.7% | 574 |
| `time_any5_30m` | 76 | **90.79%** | 11.9% | 560 |
| `champ_if_15m` | 54 | **90.74%** | 8.5% | 582 |
| `agree_champ_5mentry` | 54 | **90.74%** | 8.5% | 582 |
| `time_champ_60m` | 53 | **90.57%** | 8.3% | 583 |
| `time_champ_30m` | 50 | **90.0%** | 7.9% | 586 |
| `time_champ_15m` | 46 | **89.13%** | 7.2% | 590 |
| `agree_any5_5mentry` | 133 | **85.71%** | 20.9% | 503 |
| `agree_cap1_any5` | 133 | **85.71%** | 20.9% | 503 |
| `5m_champ_alone` | 110 | **83.64%** | 15.4% | 538 |
| `agree_cap2_any5` | 157 | **83.44%** | 20.9% | 503 |
| `agree_any5all_5mentry` | 174 | **83.33%** | 27.4% | 462 |
| `5m_union_if_15m` | 193 | **81.87%** | 20.8% | 504 |
| `agree_proven_15mentry` | 22 | **81.82%** | 3.5% | 614 |
| `stack_xTF_need_15m` | 259 | **81.08%** | 23.3% | 488 |
| `stack_xTF_both_nonproven` | 259 | **81.08%** | 23.3% | 488 |
| `5m_union_cap2` | 369 | **79.95%** | 39.5% | 385 |
| `agree_champ_15mentry` | 54 | **77.78%** | 8.5% | 582 |
| `15m_if_champ` | 69 | **76.81%** | 8.5% | 582 |
| `agree_crown_htf_15mentry` | 81 | **76.54%** | 12.7% | 555 |
| `time_crown_60m` | 17 | **76.47%** | 2.7% | 619 |
| `agree_any5all_15mentry` | 174 | **76.44%** | 27.4% | 462 |
| `stack_held` | 607 | **75.95%** | 62.9% | 236 |
| `stack_plus_empty_agree_any5` | 607 | **75.95%** | 62.9% | 236 |
| `stack_plus_empty_agree_crown` | 607 | **75.95%** | 62.9% | 236 |
| `stack_plus_empty_15m` | 607 | **75.95%** | 62.9% | 236 |
| `agree_any5_15mentry` | 133 | **75.19%** | 20.9% | 503 |
| `crown_htf_if_15m` | 165 | **75.15%** | 12.7% | 555 |
| `15m_if_proven` | 28 | **75.0%** | 3.5% | 614 |
| `time_crown_30m` | 12 | **75.0%** | 1.9% | 624 |
| `5m_crown_htf_alone` | 301 | **74.75%** | 24.7% | 479 |
| `15m_if_crown_all` | 191 | **74.35%** | 21.9% | 497 |
| `agree_crown_htf_5mentry` | 81 | **74.07%** | 12.7% | 555 |
| `15m_if_any5_htf` | 172 | **73.84%** | 20.9% | 503 |
| `15m_if_crown_htf` | 106 | **73.58%** | 12.7% | 555 |
| `15m_if_any5_all` | 233 | **73.39%** | 27.4% | 462 |
| `5m_crown_all_alone` | 454 | **71.37%** | 37.4% | 398 |
| `agree_crown_all_5mentry` | 139 | **71.22%** | 21.9% | 497 |
| `15m_prod2_alone` | 375 | **69.6%** | 45.9% | 344 |
| `crown_all_if_15m` | 278 | **69.42%** | 21.9% | 497 |

## Both-year agree (1y≥78% & 3y≥75%, n≥20)

| Approach | 1y hit / n / day | 3y hit / n / day |
|---|---|---|
| `5m_proven_alone` | 100.0% / 24 / 11.1% | **100.0%** / 39 / 6.0% |
| `proven_if_15m` | 100.0% / 16 / 7.4% | **100.0%** / 22 / 3.5% |
| `agree_proven_5mentry` | 100.0% / 16 / 7.4% | **100.0%** / 22 / 3.5% |
| `time_any5_60m` | 97.37% / 38 / 17.5% | **91.95%** / 87 / 13.7% |
| `time_any5_15m` | 100.0% / 25 / 11.5% | **91.94%** / 62 / 9.7% |
| `time_any5_30m` | 96.77% / 31 / 14.3% | **90.79%** / 76 / 11.9% |
| `champ_if_15m` | 100.0% / 19 / 8.8% | **90.74%** / 54 / 8.5% |
| `agree_champ_5mentry` | 100.0% / 19 / 8.8% | **90.74%** / 54 / 8.5% |
| `time_champ_60m` | 100.0% / 19 / 8.8% | **90.57%** / 53 / 8.3% |
| `time_champ_30m` | 100.0% / 17 / 7.8% | **90.0%** / 50 / 7.9% |
| `time_champ_15m` | 100.0% / 15 / 6.9% | **89.13%** / 46 / 7.2% |
| `agree_any5_5mentry` | 90.91% / 55 / 25.3% | **85.71%** / 133 / 20.9% |
| `agree_cap1_any5` | 90.91% / 55 / 25.3% | **85.71%** / 133 / 20.9% |
| `5m_champ_alone` | 92.68% / 41 / 17.1% | **83.64%** / 110 / 15.4% |
| `agree_cap2_any5` | 86.96% / 69 / 25.3% | **83.44%** / 157 / 20.9% |
| `agree_any5all_5mentry` | 90.0% / 70 / 32.3% | **83.33%** / 174 / 27.4% |
| `5m_union_if_15m` | 84.42% / 77 / 24.9% | **81.87%** / 193 / 20.8% |
| `agree_proven_15mentry` | 87.5% / 16 / 7.4% | **81.82%** / 22 / 3.5% |
| `stack_xTF_need_15m` | 81.65% / 109 / 28.6% | **81.08%** / 259 / 23.3% |
| `stack_xTF_both_nonproven` | 81.65% / 109 / 28.6% | **81.08%** / 259 / 23.3% |
| `5m_union_cap2` | 81.17% / 154 / 47.5% | **79.95%** / 369 / 39.5% |
| `agree_champ_15mentry` | 78.95% / 19 / 8.8% | **77.78%** / 54 / 8.5% |
| `15m_if_champ` | 79.17% / 24 / 8.8% | **76.81%** / 69 / 8.5% |
| `agree_crown_htf_15mentry` | 85.29% / 34 / 15.7% | **76.54%** / 81 / 12.7% |
| `agree_any5all_15mentry` | 78.57% / 70 / 32.3% | **76.44%** / 174 / 27.4% |
| `agree_any5_15mentry` | 81.82% / 55 / 25.3% | **75.19%** / 133 / 20.9% |
## Best accuracy (3y, n≥30, day≥20%)

- `agree_any5_5mentry`: **85.71%** n=133 · day 20.9% · no-call 503
- vs stack **75.95%** · vs 15m alone **69.6%**

## Best balance (prefer hit≥78 & day≥35%)

- `5m_union_cap2`: **79.95%** n=369 · day 39.5% · no-call 385
- vs stack **75.95%** · vs 15m alone **69.6%**

## How to read

- `15m_if_*` = take 15m call only when that 5m channel has same side that day
- `*_if_15m` = take 5m call only when 15m has same side
- `agree_*` = day+side intersection; entry from 5m or 15m
- `time_*` = same side and clocks within ±N minutes
- `stack_xTF_*` = filter held stack with cross-TF rules
- `empty_agree_*` = fill stack-silent days only when both TFs agree

## Empty days (why dual-TF fill fails)

Stack empty ⇒ **issued 15m prod2 is also absent** (it is already inside the stack).  
On 236 empty 3y days: raw (non-issued) 15m best-score/day = **36.8%** hit — unusable.  
5m pool rows on empty = **16 days** only (crown HTF-blocked).  
So **15m∩5m cannot fill quiet days**; it only upgrades accuracy when both already fire.

## Recommended accuracy books (research tags, not held)

| Tag candidate | Rule | 3y hit | N | Day cov | vs stack |
|---|---|---:|---:|---:|---|
| `AGREE_15M_ANY5_CAP1` | Same day+side: issued 15m ∩ (proven∪champ∪crown_htf); take **5m** entry; cap1 | **85.7%** | 133 | 21% | +10pp hit, −42pp day |
| `TIME_AGREE_15M_ANY5_60` | Same side and clocks within **±60m** | **92.0%** | 87 | 14% | thinner |
| `STACK_XTF_FILTER` | Keep stack call only if cross-TF same side (proven always kept) | **81.1%** | 259 | 23% | +5pp hit, less cover |
| `5M_UNION_CAP2` | 5m only (no 15m gate) | **80.0%** | 369 | 40% | solid mid |

Prefer **5m entry** on agree (`agree_*_5mentry`) over 15m entry — 3y hit is higher.

## Verdict

Yes — **using both models as a filter raises accuracy** (best practical agree ~**86%** / ~**92%** timed).  
No — it does **not** create everyday calls; coverage drops hard, and empty days stay empty.  
Held stack (~76% / 63% day) stays the volume book. Dual-TF agree is an **accuracy-max sibling**, not a replacement.

Not wired. Stack stays `HELD_FOR_FINAL`.
