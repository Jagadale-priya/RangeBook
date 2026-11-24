"""Why today's scalper calls failed for NIFTY / SENSEX."""
import json
import urllib.request
from collections import Counter


def fetch(sym: str) -> dict:
    url = (
        f"http://127.0.0.1:5000/fno/scalper/chart?stock={sym}"
        f"&days=2&chart_days=1&mode=oracle_t15&refresh=1"
    )
    return json.load(urllib.request.urlopen(url, timeout=180))


def summarize(sym: str) -> None:
    d = fetch(sym)
    today = "2026-11-18"
    calls = [c for c in (d.get("calls") or []) if str(c.get("day") or "") == today]
    print(f"\n=== {sym} today n={len(calls)} hit%={d.get('hit_pct')} live={ (d.get('live') or {}).get('hm')} {(d.get('live') or {}).get('decision')} ===")
    if not calls:
        print("  (no ORACLE_T15 calls today)")
        print("  note", d.get("note"), "err", d.get("error"))
        return
    reasons = Counter(str(c.get("reason") or "?") for c in calls)
    wins = sum(1 for c in calls if c.get("win"))
    print(f"  wins={wins}/{len(calls)}  reasons={dict(reasons)}")
    for c in calls:
        print(
            f"  {c.get('hm')} {c.get('decision'):4} {str(c.get('primary') or ''):16} "
            f"entry={c.get('entry')} exit={c.get('exit_hm')} "
            f"{c.get('reason')} pts={c.get('pts')} win={c.get('win')}"
        )


def main() -> None:
    for sym in ("NIFTY", "SENSEX", "BANKNIFTY"):
        try:
            summarize(sym)
        except Exception as exc:
            print(f"\n=== {sym} FAIL {exc}")


if __name__ == "__main__":
    main()
