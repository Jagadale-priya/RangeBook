# Models (NIFTY final desk)

Frozen copies for `prod_live`. Do not retrain in place — export a new versioned folder.

| Path | Role | Used by |
|---|---|---|
| `nifty/prod2_15m/fno_NIFTY.pkl` | Issued 15m prod2 (`GOOD_PROD2`) | Stack + agree 15m side |
| `nifty/crown/fno_NIFTY_crown_5m.pkl` | 5m ExtraTrees crown | `CROWN_DUAL_HTF` |
| `nifty/crown/fno_NIFTY_crown_5m_meta.json` | Crown pack meta | load/validate |
| `nifty/dual/fno_NIFTY_BUY_research.pkl` | Dual BUY head | proven / champion |
| `nifty/dual/fno_NIFTY_SELL_research.pkl` | Dual SELL head | proven / champion |
| `nifty/dual/fno_NIFTY_SELL_CONT*.pkl` | Dual SELL continuation variants | proven / champion |

Champion live floors (Final Logic): BUY `p_t1 ≥ 0.55`, SELL `p_t1 ≥ 0.58`.
