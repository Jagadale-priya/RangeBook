"""Smoke live imports after archive cleanup."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "app"), str(ROOT / "app" / "fno"), str(ROOT / "prod_live")]

errors: list[tuple[str, str]] = []
ok: list[str] = []


def check(label: str, fn) -> None:
    try:
        fn()
        ok.append(label)
        print("OK", label)
    except Exception as e:  # noqa: BLE001
        errors.append((label, str(e)))
        print("FAIL", label, "::", e)


def t_paths() -> None:
    need = [
        "prod_live/holding_accurate/champion_plus/t30_sl30_5y_calls.json",
        "prod_live/holding_accurate/sensex_final/champ_plus_t50_sl50_calls.json",
        "prod_live/holding_accurate/phase2f/recipes_research.json",
        "prod_live/holding_accurate/phase2g/recipes_research.json",
        "prod_live/holding_accurate/phase2c/builders.py",
        "prod_live/holding_accurate/replay.py",
        "dashboard/index.html",
    ]
    for p in need:
        assert (ROOT / p).is_file(), p


def t_pa() -> None:
    from prod_live.logic import pa_structure_live as pa

    assert pa.HOLD.is_dir()
    assert (pa.HOLD / "locked_cfg.json").is_file() or (
        pa.HOLD / "live_session_calls.json"
    ).is_file()


def t_champ() -> None:
    from prod_live.logic import champ_plus_live as c

    rows = c.load_held_calls()
    assert len(rows) > 100
    print("  champ held", len(rows))


def t_sensex() -> None:
    from prod_live.logic import sensex_final_live as sx

    rows = sx.load_held_calls()
    assert len(rows) > 100
    print("  sensex held", len(rows))


def t_bn() -> None:
    from prod_live.logic import bn_final_live as bn

    rows = bn.load_held_calls()
    print("  bn held", len(rows))


def t_p2() -> None:
    from prod_live.logic.p2f_cap2_live import LIVE_CAP2_DESKS, load_phase2f_cap2_recipes
    from prod_live.logic.p2f_day_live import LIVE_DAY_DESKS, load_phase2f_day_recipes
    from prod_live.logic.p2g_10m_live import LIVE_P2G_DESKS, load_phase2g_recipes

    r1 = load_phase2f_day_recipes()
    r2 = load_phase2f_cap2_recipes()
    r3 = load_phase2g_recipes()
    print("  p2f day", len(r1), "cap2", len(r2), "p2g", len(r3))
    assert LIVE_DAY_DESKS and LIVE_CAP2_DESKS and LIVE_P2G_DESKS


def t_adapters() -> None:
    from prod_live.adapters import (  # noqa: F401
        live_session_bn,
        live_session_final,
        live_session_pa,
        live_session_p2f,
        live_session_sensex,
    )


def t_scalper() -> None:
    import fno_scalper_1m

    assert hasattr(fno_scalper_1m, "live_scalper_check")


def main() -> int:
    for label, fn in (
        ("paths", t_paths),
        ("pa_structure_live", t_pa),
        ("champ_plus_live", t_champ),
        ("sensex_final_live", t_sensex),
        ("bn_final_live", t_bn),
        ("p2f_p2g", t_p2),
        ("adapters", t_adapters),
        ("fno_scalper_1m", t_scalper),
    ):
        check(label, fn)
    print("---")
    print("ok", len(ok), "fail", len(errors))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
