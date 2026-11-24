# Dual `champion` vs research `CHAMP_PLUS` — not the same logic

The high numbers you remember are **CHAMP_PLUS_T30SL30_CAP4**, not raw dual-track `champion` (and not 5m/10m champion).

## Side-by-side

| Name | What it is | Last 1y |
|---|---|---|
| **CHAMP_PLUS** | Champion **seed** + **ticket-fill** streams · ±30 · **cap 4** same-side · FINAL live desk | **374 @ 99.47%** |
| Dual `champion` 15m | Live dual pack gate only (BUY p≥0.55 · SELL p≥0.58) · OR-break tickets | ~39–41 @ **~92–93%** |
| Dual `champion` 5m | Same packs on 5m OR-breaks | ~17 @ **~35%** |
| Dual `champion` 10m | Same packs on 10m OR-breaks | ~11 @ **~36%** |

Yesterday’s `research/nifty_fno` champion improve run scored **raw dual champion caches** (esp. 5m/10m). That is why it looked “not high” — **different logic**.

## CHAMP_PLUS locked research (the high one)

| Window | N | Hit |
|---|---:|---:|
| 1y | **374** | **99.47%** |
| 3y | **1028** | **99.61%** |
| 5y | **1689** | **93.19%** |

- Tag: `CHAMP_PLUS_T30SL30_CAP4` · `ACC_RANGE_93_100`
- Code: `prod_live/logic/champ_plus_live.py` · `champ_plus_engine.py`
- Reports:
  - `prod_live/reports/5y/CHAMPION_PLUS_T30_SL30_5Y.md`
  - `prod_live/reports/3y/CHAMPION_PLUS_T30_SL30_3Y.md`
  - `prod_live/reports/1y/CHAMP_PLUS_LIVE_ENGINE_CONFIRM.md`
  - seed-only: `prod_live/reports/1y/CHAMPION_ONLY_1Y.md` (41 @ 92.7% before fill)

## Dual champion seed (without PLUS fill)

`prod_live/reports/1y/CHAMPION_ONLY_1Y.md` — **40–41 @ ~92.5%** (15m dual champion pool, cap2).

## Takeaway for accurate NIFTY F&O research folder

- Keep **proven_15 (+ proven_10 fill)** as the sparse high-accuracy dual book.
- For the **dense high-accuracy** champion family, use **CHAMP_PLUS** (not raw 5m/10m champion).
- Do not mix “champion” labels — always say **dual champion** vs **CHAMP_PLUS**.
