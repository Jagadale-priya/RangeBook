# FINAL NIFTY F&O — 3-book confirm

**Books only:** P2F (day+cap2) · P2G 10m · CHAMP_PLUS_T30SL30_CAP4
**Excluded:** `STACK_PLUS_CROWN_HTF_CAP2` · `AGREE_15M_ANY5`
**UI:** same `(day,side,hm)` → 1 call · all tags · accuracy-first · never block

## Verdict: **PASS**

Passes: 62 · Fails: 0 · Elapsed 47.7s

## Registry

```json
{
  "status": "FINAL",
  "lane": "LIVE",
  "nifty_fno_books_only": [
    {
      "book": "p2f",
      "modes": [
        "day",
        "cap2"
      ],
      "day_desks": [
        "ACC100_MULTI_V11",
        "ACC_WIDE_P92_P2F",
        "ACC_WIDE_P90_P2F",
        "ACC_WIDE_P85_P2F",
        "ACC_WIDE_P85B_P2F",
        "ACC_WIDE_P80_P2F",
        "ACC_WIDE_P75_P2F"
      ],
      "cap2_desks": [
        "ACC100_MULTI_V5_CAP2_P2F",
        "ACC_WIDE_P92_CAP2_P2F",
        "ACC_WIDE_P90_CAP2_P2F",
        "ACC_WIDE_P85_CAP2_P2F"
      ]
    },
    {
      "book": "p2g_10m",
      "modes": [
        "day"
      ],
      "desks": [
        "ACC100_MULTI_V12_P2G_10M",
        "ACC_WIDE_P92_P2G_10M",
        "ACC_WIDE_P90_P2G_10M",
        "ACC_WIDE_P85_P2G_10M",
        "ACC_WIDE_P85B_P2G_10M",
        "ACC_WIDE_P80_P2G_10M",
        "ACC_WIDE_P75_P2G_10M"
      ],
      "expected_5y": {
        "ACC100_MULTI_V12_P2G_10M": {
          "n": 256,
          "hit_pct": 98.05
        },
        "ACC_WIDE_P92_P2G_10M": {
          "n": 174,
          "hit_pct": 92.53
        },
        "ACC_WIDE_P90_P2G_10M": {
          "n": 320,
          "hit_pct": 94.69
        },
        "ACC_WIDE_P85_P2G_10M": {
          "n": 283,
          "hit_pct": 90.11
        },
        "ACC_WIDE_P85B_P2G_10M": {
          "n": 418,
          "hit_pct": 88.76
        },
        "ACC_WIDE_P80_P2G_10M": {
          "n": 431,
          "hit_pct": 83.53
        },
        "ACC_WIDE_P75_P2G_10M": {
          "n": 472,
          "hit_pct": 82.42
        }
      }
    },
    {
      "book": "champ_plus",
      "modes": [
        "cap4"
      ],
      "desks": [
        "CHAMP_PLUS_T30SL30_CAP4"
      ],
      "accuracy_tag": "ACC_RANGE_93_100",
      "expected": {
        "1y": {
          "n": 374,
          "hit_pct": 99.47
        },
        "3y": {
          "n": 1028,
          "hit_pct": 99.61
        },
        "5y": {
          "n": 1689,
          "hit_pct": 93.19
        }
      }
    }
  ],
  "excluded": [
    "STACK_PLUS_CROWN_HTF_CAP2",
    "AGREE_15M_ANY5"
  ],
  "ui": "same (day,side,hm) \u2192 1 call \u00b7 all tags \u00b7 highest accuracy desk first \u00b7 never block",
  "desk_priority": [
    "ACC100_MULTI_V11",
    "ACC100_MULTI_V5_CAP2_P2F",
    "ACC100_MULTI_V12_P2G_10M",
    "CHAMP_PLUS_T30SL30_CAP4",
    "ACC_WIDE_P90_P2G_10M",
    "ACC_WIDE_P92_P2F",
    "ACC_WIDE_P92_CAP2_P2F",
    "ACC_WIDE_P90_P2F",
    "ACC_WIDE_P90_CAP2_P2F",
    "ACC_WIDE_P85B_P2G_10M",
    "ACC_WIDE_P85_P2G_10M",
    "ACC_WIDE_P85_P2F",
    "ACC_WIDE_P85_CAP2_P2F",
    "ACC_WIDE_P85B_P2F",
    "ACC_WIDE_P92_P2G_10M",
    "ACC_WIDE_P80_P2F",
    "ACC_WIDE_P80_P2G_10M",
    "ACC_WIDE_P75_P2F",
    "ACC_WIDE_P75_P2G_10M"
  ]
}
```

## Passes

- PASS champ_1y: got 374@99.47% · exp 374@99.47%
- PASS champ_3y: got 1028@99.61% · exp 1028@99.61%
- PASS champ_5y: got 1689@93.19% · exp 1689@93.19%
- PASS champ_report_1y: got 374@99.47% · exp 374@99.47%
- PASS champ_report_3y: got 1028@99.61% · exp 1028@99.61%
- PASS champ_report_5y: got 1689@93.19% · exp 1689@93.19%
- PASS p2g_report_ACC100_MULTI_V12_P2G_10M_1y: got 61@100.0% · exp 61@100.0%
- PASS p2g_report_ACC100_MULTI_V12_P2G_10M_3y: got 165@100.0% · exp 165@100.0%
- PASS p2g_report_ACC100_MULTI_V12_P2G_10M_5y: got 256@98.05% · exp 256@98.05%
- PASS p2g_report_ACC_WIDE_P92_P2G_10M_1y: got 34@100.0% · exp 34@100.0%
- PASS p2g_report_ACC_WIDE_P92_P2G_10M_3y: got 109@98.17% · exp 109@98.17%
- PASS p2g_report_ACC_WIDE_P92_P2G_10M_5y: got 174@92.53% · exp 174@92.53%
- PASS p2g_report_ACC_WIDE_P90_P2G_10M_1y: got 75@100.0% · exp 75@100.0%
- PASS p2g_report_ACC_WIDE_P90_P2G_10M_3y: got 207@95.65% · exp 207@95.65%
- PASS p2g_report_ACC_WIDE_P90_P2G_10M_5y: got 320@94.69% · exp 320@94.69%
- PASS p2g_report_ACC_WIDE_P85_P2G_10M_1y: got 61@96.72% · exp 61@96.72%
- PASS p2g_report_ACC_WIDE_P85_P2G_10M_3y: got 189@92.06% · exp 189@92.06%
- PASS p2g_report_ACC_WIDE_P85_P2G_10M_5y: got 283@90.11% · exp 283@90.11%
- PASS p2g_report_ACC_WIDE_P85B_P2G_10M_1y: got 104@94.23% · exp 104@94.23%
- PASS p2g_report_ACC_WIDE_P85B_P2G_10M_3y: got 280@88.93% · exp 280@88.93%
- PASS p2g_report_ACC_WIDE_P85B_P2G_10M_5y: got 418@88.76% · exp 418@88.76%
- PASS p2g_report_ACC_WIDE_P80_P2G_10M_1y: got 98@83.67% · exp 98@83.67%
- PASS p2g_report_ACC_WIDE_P80_P2G_10M_3y: got 270@84.81% · exp 270@84.81%
- PASS p2g_report_ACC_WIDE_P80_P2G_10M_5y: got 431@83.53% · exp 431@83.53%
- PASS p2g_report_ACC_WIDE_P75_P2G_10M_1y: got 109@83.49% · exp 109@83.49%
- PASS p2g_report_ACC_WIDE_P75_P2G_10M_3y: got 294@82.99% · exp 294@82.99%
- PASS p2g_report_ACC_WIDE_P75_P2G_10M_5y: got 472@82.42% · exp 472@82.42%
- PASS p2g_rebuild_ACC100_MULTI_V12_P2G_10M_1y: got 61@100.0% · exp 61@100.0%
- PASS p2g_rebuild_ACC100_MULTI_V12_P2G_10M_3y: got 165@100.0% · exp 165@100.0%
- PASS p2g_rebuild_ACC100_MULTI_V12_P2G_10M_5y: got 256@98.05% · exp 256@98.05%
- PASS p2g_rebuild_ACC_WIDE_P92_P2G_10M_1y: got 34@100.0% · exp 34@100.0%
- PASS p2g_rebuild_ACC_WIDE_P92_P2G_10M_3y: got 109@98.17% · exp 109@98.17%
- PASS p2g_rebuild_ACC_WIDE_P92_P2G_10M_5y: got 174@92.53% · exp 174@92.53%
- PASS p2g_rebuild_ACC_WIDE_P90_P2G_10M_1y: got 75@100.0% · exp 75@100.0%
- PASS p2g_rebuild_ACC_WIDE_P90_P2G_10M_3y: got 207@95.65% · exp 207@95.65%
- PASS p2g_rebuild_ACC_WIDE_P90_P2G_10M_5y: got 320@94.69% · exp 320@94.69%
- PASS p2g_rebuild_ACC_WIDE_P85_P2G_10M_1y: got 61@96.72% · exp 61@96.72%
- PASS p2g_rebuild_ACC_WIDE_P85_P2G_10M_3y: got 189@92.06% · exp 189@92.06%
- PASS p2g_rebuild_ACC_WIDE_P85_P2G_10M_5y: got 283@90.11% · exp 283@90.11%
- PASS p2g_rebuild_ACC_WIDE_P85B_P2G_10M_1y: got 104@94.23% · exp 104@94.23%
- PASS p2g_rebuild_ACC_WIDE_P85B_P2G_10M_3y: got 280@88.93% · exp 280@88.93%
- PASS p2g_rebuild_ACC_WIDE_P85B_P2G_10M_5y: got 418@88.76% · exp 418@88.76%
- PASS p2g_rebuild_ACC_WIDE_P80_P2G_10M_1y: got 98@83.67% · exp 98@83.67%
- PASS p2g_rebuild_ACC_WIDE_P80_P2G_10M_3y: got 270@84.81% · exp 270@84.81%
- PASS p2g_rebuild_ACC_WIDE_P80_P2G_10M_5y: got 431@83.53% · exp 431@83.53%
- PASS p2g_rebuild_ACC_WIDE_P75_P2G_10M_1y: got 109@83.49% · exp 109@83.49%
- PASS p2g_rebuild_ACC_WIDE_P75_P2G_10M_3y: got 294@82.99% · exp 294@82.99%
- PASS p2g_rebuild_ACC_WIDE_P75_P2G_10M_5y: got 472@82.42% · exp 472@82.42%
- PASS p2f_day_ACC100_MULTI_V11: got 86@100.0% · exp 86@100.0%
- PASS p2f_day_ACC_WIDE_P92_P2F: got 86@100.0% · exp 86@100.0%
- PASS p2f_day_ACC_WIDE_P90_P2F: got 98@100.0% · exp 98@100.0%
- PASS p2f_day_ACC_WIDE_P85_P2F: got 114@92.98% · exp 114@92.98%
- PASS p2f_day_ACC_WIDE_P85B_P2F: got 116@93.1% · exp 116@93.1%
- PASS p2f_day_ACC_WIDE_P80_P2F: got 123@90.24% · exp 123@90.24%
- PASS p2f_day_ACC_WIDE_P75_P2F: got 127@88.98% · exp 127@88.98%
- PASS p2f_cap2_ACC100_MULTI_V5_CAP2_P2F: got 124@100.0% · exp 124@100.0%
- PASS p2f_cap2_ACC_WIDE_P92_CAP2_P2F: got 123@100.0% · exp 123@100.0%
- PASS p2f_cap2_ACC_WIDE_P90_CAP2_P2F: got 139@99.28% · exp 139@99.28%
- PASS p2f_cap2_ACC_WIDE_P85_CAP2_P2F: got 169@91.12% · exp 169@91.12%
- PASS combine_blocked_distinct=0 · ui=2372 raw=13413 multi=1293
- PASS every distinct raw key appears in UI
- PASS no volume/agree primary tags

## Fails

- (none)

## Combine

| Metric | Value |
|---|---:|
| raw firings | 13413 |
| UI calls | 2372 |
| multi-desk UI | 1293 |
| blocked_distinct | 0 |

