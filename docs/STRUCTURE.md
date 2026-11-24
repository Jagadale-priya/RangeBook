# Prod folder structure (`prod/fno-final-hold`)

```
app/
  api/          Flask server (stock_signal_ml)
  fno/          Final-hold F&O desk (stack, crown, dual, live watch/rescore)
  market/       Kite / NSE / live quotes
  desk/         Notifications
  core/         Secrets vault
  legacy/       Still imported by API/live path (stock tabs, optional OFF channels)
prod_live/      Frozen final logic + models + golden 1y confirm
dashboard/      UI
tools/research/ CalibratedHead unpickle only
tests/          Dual + crown unit tests
scripts/        Ops helpers
```

Research / analysis archive: https://github.com/Jagadale-priya/research-and-analysis

## Run

```powershell
python stock_signal_ml.py
python kite_login.py
```
