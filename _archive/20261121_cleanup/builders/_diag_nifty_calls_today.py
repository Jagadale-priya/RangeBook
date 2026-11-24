import json
import urllib.request

c = json.load(
    urllib.request.urlopen(
        "http://127.0.0.1:5000/fno/scalper/chart?stock=NIFTY&days=2&chart_days=1&mode=oracle_t15&refresh=1",
        timeout=180,
    )
)
tc = [x for x in (c.get("calls") or []) if x.get("day") == "2026-11-18"]
print("n_calls_today", len(tc), "gap", c.get("gap_mins"), "payload_n_calls", c.get("n_calls"))
for x in tc:
    print(
        x.get("hm"),
        x.get("decision"),
        x.get("primary"),
        "entry",
        x.get("entry"),
        "exit",
        x.get("exit_hm"),
        x.get("reason"),
        "pts",
        x.get("pts"),
    )
live = c.get("live") or {}
print("live", live.get("hm"), live.get("decision"), live.get("primary"), "n_setup", live.get("n_setup_today"))
