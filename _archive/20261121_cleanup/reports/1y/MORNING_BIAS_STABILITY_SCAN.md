# Bias stability scan

## fuse_us_asia thresholds

| th | 1y | 3y | 5y | walk_min | walk_mean | win70 | stable70 | stable65 |
|---|---:|---:|---:|---:|---:|---|---|---|
| 4.0 | 0.6351 n=74 | 0.6329 n=207 | 0.6596 n=379 | 0.616 | 0.6567 | False | False | False |
| 4.5 | 0.68 n=50 | 0.6387 n=155 | 0.6633 n=300 | 0.6341 | 0.6633 | False | False | False |
| 5.0 | 0.7297 n=37 | 0.6525 n=118 | 0.6856 n=229 | 0.6098 | 0.6752 | False | False | True |
| 5.5 | 0.7931 n=29 | 0.6633 n=98 | 0.6931 n=189 | 0.65 | 0.6865 | False | False | True |
| 6.0 | 0.7273 n=22 | 0.6765 n=68 | 0.6929 n=140 | 0.5588 | 0.6715 | False | False | False |
| 6.5 | 0.75 n=16 | 0.7174 n=46 | 0.7228 n=101 | 0.5217 | 0.686 | True | False | False |
| 7.0 | 0.6923 n=13 | 0.7 n=30 | 0.7273 n=66 | 0.5714 | 0.7046 | False | False | False |
| 7.5 | 0.8333 n=6 | 0.75 n=20 | 0.7143 n=42 | 0.4444 | 0.6631 | False | False | False |
| 8.0 | 0.5 n=2 | 0.6429 n=14 | 0.6774 n=31 | 0.3333 | 0.6002 | False | False | False |
| 8.5 | 0.5 n=2 | 0.6667 n=9 | 0.6 n=20 | 0.4286 | 0.5247 | False | False | False |
| 9.0 | 0.0 n=1 | 0.75 n=4 | 0.6667 n=12 | 0.6 | 0.6125 | False | False | False |
| 9.5 | None n=0 | None n=0 | None n=0 | None | None | False | False | False |
| 10.0 | None n=0 | None n=0 | None n=0 | None | None | False | False | False |
| 10.5 | None n=0 | None n=0 | None n=0 | None | None | False | False | False |
| 11.0 | None n=0 | None n=0 | None n=0 | None | None | False | False | False |
| 11.5 | None n=0 | None n=0 | None n=0 | None | None | False | False | False |
| 12.0 | None n=0 | None n=0 | None n=0 | None | None | False | False | False |

## agree_spx

| rule | 1y | 3y | 5y | walk_min | walk_mean | win70 | stable70 |
|---|---:|---:|---:|---:|---:|---|---|
| agree_spx_0.8 | 0.6667 n=30 | 0.6598 n=97 | 0.6863 n=204 | 0.6364 | 0.6858 | False | False |
| agree_spx_1.0 | 0.6364 n=22 | 0.6575 n=73 | 0.6687 n=160 | 0.6047 | 0.6688 | False | False |
| agree_spx_1.2 | 0.6111 n=18 | 0.6415 n=53 | 0.6949 n=118 | 0.5588 | 0.6766 | False | False |
| agree_spx_1.5 | 0.8333 n=12 | 0.7105 n=38 | 0.7294 n=85 | 0.6316 | 0.7035 | True | False |
| agree_spx_2.0 | 0.6667 n=3 | 0.6 n=15 | 0.6829 n=41 | 0.4444 | 0.6093 | False | False |

**stable70 count:** 0
**stable65 count:** 2

Best stable65 fuse th=5.5 walk_min=0.65 3y={'days_all': 756, 'days_spoken': 98, 'coverage': 0.1296, 'spoken_acc': 0.6633}