# NIFTY morning strong OR BUY research

Brackets ±30. Holdout last 40 sessions. Path = 5m T1-before-SL.

## Ranking (pass first, then holdout hit, strong-day catch)

| gate | freeze n@hit | holdout n@hit | strong catch | pass |
|---|---:|---:|---:|---:|
| `sx_like_bf15_0945` | 73@31.51 | 9@44.44 | 64.3% | False |
| `sx_like_bf20_0945` | 66@30.3 | 6@33.33 | 42.9% | False |
| `sx_like_bf25_0945` | 56@26.79 | 6@33.33 | 42.9% | False |
| `cont_bf20_green_after_first` | 57@31.58 | 7@28.57 | 50.0% | False |
| `first_bf15_green_0945` | 16@6.25 | 4@25.0 | 28.6% | False |
| `first_bf20_green_0930_1000` | 72@20.83 | 7@0.0 | 42.9% | False |
| `first_bf20_prior2` | 30@26.67 | 4@0.0 | 21.4% | False |
| `first_bf20_prior1` | 23@21.74 | 4@0.0 | 21.4% | False |
| `first_bf22_green_0945` | 13@7.69 | 3@0.0 | 21.4% | False |
| `first_bf20_green_0945` | 14@7.14 | 3@0.0 | 21.4% | False |
| `first_bf20_green_uplift80` | 20@25.0 | 3@0.0 | 14.3% | False |
| `first_bf18_green_width80_220` | 9@0.0 | 2@0.0 | 14.3% | False |
| `first_bf20_green_uplift120` | 10@20.0 | 1@0.0 | 7.1% | False |

## Best accuracy (n floors)

- **sx_like_bf15_0945** holdout 9@44.44% · freeze 73@31.51% · strong catch 64.3%
- params: `{"name": "sx_like_bf15_0945", "min_bf": 0.15, "max_bf": 9.0, "hm_list": ["09:45"], "first_break_only": false, "require_green": false, "min_uplift_from_open": 0.0, "break_prior_highs": 0, "max_or_width": 9999.0, "min_or_width": 0.0, "buy_only": true}`

## Pass gate

- none met freeze≥85% & holdout≥80% with n floors — pick best_accuracy with caution.

JSON: `C:\Users\Priyanka\Agent\prod_live\reports\1y\NIFTY_MORNING_STRONG_OR.json`
