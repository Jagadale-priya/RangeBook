# Rangebook — final-hold production

Lean production tree for the **NIFTY final desk** (`STACK_PLUS_CROWN_HTF_CAP2` + `AGREE_15M_ANY5`).

Research / analysis: https://github.com/Jagadale-priya/research-and-analysis

## Layout

```
app/api/        Flask server
app/fno/        Final-hold F&O desk
app/market/     Kite / quotes
app/desk/       Notifications
app/core/       Secrets
app/legacy/     Still required by live/API imports (optional OFF channels)
prod_live/      Frozen logic + models + golden confirm
dashboard/      UI
tools/research/ CalibratedHead unpickle only
```

See `docs/STRUCTURE.md`.

## Run

```powershell
python -m pip install -r requirements.txt
python kite_login.py
python stock_signal_ml.py
```

Flags: `.env.example` / `prod_live/config/live.env.example`

## Confirm 1y golden

```powershell
python -u prod_live/tests/confirm_final_hold_1y_match.py --notify
```

Expect **229 @ 75.11%** · Acc **54 @ 90.74%**.
