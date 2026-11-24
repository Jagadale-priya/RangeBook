"""Smoke-test live F&O path for NIFTY + SENSEX after BANKNIFTY removal.

  python -u prod_live/tests/builders/_smoke_nifty_sensex_live.py
"""
from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [
    str(ROOT),
    str(ROOT / "app"),
    str(ROOT / "app" / "fno"),
    str(ROOT / "app" / "market"),
    str(ROOT / "app" / "api"),
    str(ROOT / "prod_live"),
]


def _ok(name: str, cond: bool, detail: str = "") -> bool:
    mark = "PASS" if cond else "FAIL"
    print(f"  [{mark}] {name}" + (f" — {detail}" if detail else ""), flush=True)
    return cond


def main() -> int:
    fails = 0
    print("=== Config / universe ===", flush=True)
    import fno_live_config
    import fno_universe
    import fno_live_watch

    fails += not _ok(
        "live indexes",
        fno_live_config.fno_live_indexes() == ("NIFTY", "SENSEX"),
        str(fno_live_config.fno_live_indexes()),
    )
    fails += not _ok("NIFTY live", fno_live_config.is_fno_live_index("NIFTY"))
    fails += not _ok("SENSEX live", fno_live_config.is_fno_live_index("SENSEX"))
    fails += not _ok("BANKNIFTY not live", not fno_live_config.is_fno_live_index("BANKNIFTY"))
    fails += not _ok("BN final off", not fno_live_config.enable_bn_final_live())
    fails += not _ok("Sensex final on", fno_live_config.enable_sensex_final_live())
    fails += not _ok(
        "NIFTY afternoon thrust ON",
        fno_live_config.enable_nifty_afternoon_thrust(),
    )
    fails += not _ok(
        "NIFTY morning strong thrust ON",
        fno_live_config.enable_nifty_morning_strong_thrust(),
    )
    fails += not _ok(
        "watch CORE",
        tuple(fno_live_watch.CORE_SYMBOLS) == ("NIFTY", "SENSEX"),
        str(fno_live_watch.CORE_SYMBOLS),
    )
    fails += not _ok(
        "universe default",
        "BANKNIFTY" not in fno_universe.symbols() and "NIFTY" in fno_universe.symbols() and "SENSEX" in fno_universe.symbols(),
        str(fno_universe.symbols()),
    )

    print("=== Sensex desk lock ===", flush=True)
    from prod_live.logic import sensex_final_live as sx

    fails += not _ok("desk", sx.DESK_CHAMP == "SENSEX_DUAL_FB_BF20_T50", sx.DESK_CHAMP)
    fails += not _ok("brackets ±50", sx.BRACKETS.get("sl") == 50 and sx.BRACKETS.get("target") == 50, str(sx.BRACKETS))
    fails += not _ok("suppress bypass", not fno_live_config.suppress_dual_list_for("SENSEX"))

    print("=== Dual dispatch (no BN load) ===", flush=True)
    import fno_live_dual_track as disp

    bn = disp.apply_to_analyze_result(
        "BANKNIFTY", {}, bars=None, asof=None, session_ticket=None, price=0
    )
    fails += not _ok("BN dispatch None", bn is None)

    print("=== Live scheduled_refresh NIFTY + SENSEX ===", flush=True)
    import kite_data
    import market_symbols
    import fno_ws_rescore

    stocks = dict(getattr(market_symbols, "INDIAN_STOCKS", {}) or {})
    if not stocks:
        stocks = {"NIFTY": "^NSEI", "SENSEX": "^BSESN"}

    if not kite_data.kite_enabled():
        print("  [SKIP] Kite not enabled — cannot refresh live", flush=True)
    else:
        for sym in ("NIFTY", "SENSEX"):
            print(f"--- {sym} ---", flush=True)
            try:
                result, err = fno_ws_rescore.scheduled_refresh(sym, stocks)
                ok = err is None and isinstance(result, dict)
                fails += not _ok(f"{sym} refresh", ok, err or "ok")
                if not ok or not result:
                    continue
                dec = str(result.get("decision") or "HOLD")
                fa = result.get("fno_analysis") or {}
                dual = fa.get("dual_track_call") or result.get("dual_track_call")
                print(f"      decision={dec}", flush=True)
                if sym == "SENSEX":
                    brackets = (fa.get("sensex_final_live") or {}).get("brackets") or sx.BRACKETS
                    desk = (fa.get("sensex_final_live") or {}).get("desk") or ""
                    fails += not _ok(
                        "SENSEX ±50 stamped",
                        float((brackets or {}).get("sl") or 0) == 50
                        and float((brackets or {}).get("target") or 0) == 50,
                        str(brackets),
                    )
                    # desk may be empty if dual silent — book registry still present
                    book = fa.get("final_sensex_fno") or result.get("final_sensex_fno") or {}
                    fails += not _ok(
                        "SENSEX book present",
                        bool(book) or bool(fa.get("sensex_final_live")),
                        f"desk={desk} book_keys={list(book)[:5] if isinstance(book, dict) else book}",
                    )
                    if isinstance(dual, dict) and dual.get("decision") in ("BUY", "SELL"):
                        fails += not _ok(
                            "SENSEX dual SL/T1",
                            abs(float(dual.get("sl_pts") or 0) - 50) < 1e-6
                            or abs(
                                abs(float(dual.get("entry") or 0) - float(dual.get("stop_loss") or 0))
                                - 50
                            )
                            < 1.5,
                            f"sl_pts={dual.get('sl_pts')} entry={dual.get('entry')} sl={dual.get('stop_loss')} t1={dual.get('target_1')}",
                        )
                if sym == "NIFTY":
                    fails += not _ok(
                        "NIFTY path alive",
                        "decision" in result,
                        f"keys={sorted(result.keys())[:12]}",
                    )
            except Exception as exc:
                fails += 1
                print(f"  [FAIL] {sym} exception: {exc}", flush=True)
                traceback.print_exc()

        print("--- BANKNIFTY should not refresh as primary ---", flush=True)
        # universe.contains may still allow if someone forced; refresh message for non-primary
        try:
            result, err = fno_ws_rescore.scheduled_refresh("BANKNIFTY", stocks)
            # If somehow runs, dual should not load BN packs via dispatcher
            print(f"      BN refresh err={err!r} result_type={type(result).__name__}", flush=True)
        except Exception as exc:
            print(f"      BN refresh raised (ok to skip): {exc}", flush=True)

    out = {
        "fails": fails,
        "indexes": list(fno_live_config.fno_live_indexes()),
        "desk": sx.DESK_CHAMP,
        "brackets": dict(sx.BRACKETS),
    }
    path = ROOT / "prod_live" / "reports" / "1y" / "SMOKE_NIFTY_SENSEX_LIVE.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\n{'PASS' if fails == 0 else 'FAIL'} · fails={fails} · wrote {path}", flush=True)
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
