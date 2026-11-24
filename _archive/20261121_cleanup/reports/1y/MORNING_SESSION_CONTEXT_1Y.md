# Morning session context — 1y bake-off (no calls)

**Report window start (fit before this):** `2025-11-03`
**Generated:** `2026-11-15T15:16:14`

Winners chosen on **train only**. Test = last ~1y held out.
This product emits context only — **no BUY/SELL calls**.

## Frozen recommendation (from NIFTY train winners)

- **Premarket range:** `atr14_1_2x` @ prev_close — train score 25.1019 · test inside 27.4% width_med 1.28%
- **Open-locked range:** `atr14_1_2x` @ session_open — train score 37.0195 · test inside 51.6% width_med 1.28%
- **Bias:** `yesterday_up_continues` — train acc 54.3% lift +0.4% · test acc 51.2% lift +0.4% cov 100%
- **Gap:** `always_natural` — train 61.3% · test 63.1%
- **Vol:** expanding ATR% tercile — test hit 52.0%
- **Chain guidance:** high-vol avoid naked fut test=0.8194

## Per symbol

### NIFTY
- bars train/test: 3367/252 · end 2026-11-11
- range winner (pre): `atr14_1_2x` test inside **27.4%**
- bias winner: `yesterday_up_continues` test **51.2%** (lift +0.4%)
- gap winner: `always_natural` test **63.1%**
- vol test: **52.0%**

### BANKNIFTY
- bars train/test: 1013/222 · end 2026-09-25
- range winner (pre): `atr14_1_2x` test inside **33.8%**
- bias winner: `always_up` test **50.0%** (lift +0.0%)
- gap winner: `always_natural` test **59.0%**
- vol test: **55.4%**

### RELIANCE
- bars train/test: 1013/222 · end 2026-09-25
- range winner (pre): `p80_20_ranges` test inside **37.8%**
- bias winner: `always_up` test **47.3%** (lift -5.4%)
- gap winner: `always_natural` test **50.9%**
- vol test: **40.1%**

### HDFCBANK
- bars train/test: 1013/222 · end 2026-09-25
- range winner (pre): `atr14_1_2x` test inside **34.2%**
- bias winner: `always_up` test **41.0%** (lift -18.0%)
- gap winner: `always_natural` test **36.5%**
- vol test: **41.0%**

### INFY
- bars train/test: 1013/222 · end 2026-09-25
- range winner (pre): `atr14_1_2x` test inside **36.0%**
- bias winner: `yesterday_up_fades` test **45.1%** (lift -11.7%)
- gap winner: `always_natural` test **29.7%**
- vol test: **53.1%**

### TCS
- bars train/test: 1013/222 · end 2026-09-25
- range winner (pre): `atr14_1_2x` test inside **35.1%**
- bias winner: `vote3_unanimous` test **52.5%** (lift -5.9%)
- gap winner: `always_natural` test **47.3%**
- vol test: **58.1%**

### SBIN
- bars train/test: 1013/222 · end 2026-09-25
- range winner (pre): `atr14_1_2x` test inside **38.3%**
- bias winner: `always_up` test **51.8%** (lift +0.0%)
- gap winner: `always_natural` test **58.6%**
- vol test: **45.1%**

### ICICIBANK
- bars train/test: 1013/222 · end 2026-09-25
- range winner (pre): `atr14_1_2x` test inside **31.5%**
- bias winner: `always_up` test **48.6%** (lift -2.7%)
- gap winner: `always_natural` test **48.6%**
- vol test: **48.2%**

### BAJFINANCE
- bars train/test: 1013/222 · end 2026-09-25
- range winner (pre): `atr14_1_2x` test inside **36.5%**
- bias winner: `always_up` test **49.1%** (lift -1.8%)
- gap winner: `always_natural` test **42.8%**
- vol test: **38.3%**

### BHARTIARTL
- bars train/test: 1013/222 · end 2026-09-25
- range winner (pre): `p80_20_ranges` test inside **35.6%**
- bias winner: `always_up` test **50.0%** (lift +0.0%)
- gap winner: `always_natural` test **42.8%**
- vol test: **44.6%**

### AXISBANK
- bars train/test: 1013/222 · end 2026-09-25
- range winner (pre): `p80_20_ranges` test inside **35.6%**
- bias winner: `vote3_unanimous` test **40.5%** (lift -11.2%)
- gap winner: `always_natural` test **45.1%**
- vol test: **46.4%**

### ITC
- bars train/test: 1014/222 · end 2026-09-25
- range winner (pre): `p80_20_ranges` test inside **38.3%**
- bias winner: `above_sma50` test **51.8%** (lift -4.5%)
- gap winner: `always_natural` test **68.0%**
- vol test: **44.6%**

### LT
- bars train/test: 1013/222 · end 2026-09-25
- range winner (pre): `p80_20_ranges` test inside **34.7%**
- bias winner: `always_up` test **48.6%** (lift -2.7%)
- gap winner: `always_natural` test **55.9%**
- vol test: **50.9%**

### TATASTEEL
- bars train/test: 1013/222 · end 2026-09-25
- range winner (pre): `atr14_1_2x` test inside **35.1%**
- bias winner: `always_up` test **48.2%** (lift -3.6%)
- gap winner: `always_natural` test **42.3%**
- vol test: **38.7%**

## Notes

- Gap predictors here are prior-day proxies (true premarket gap needs futures overnight; not in this CSV bake-off).
- Bias lift must beat majority baseline; thin-coverage rules are only winners if coverage ≥ 25% on train.
- Chain guidance is style mapping only (`guide_only`); never a ticket.
