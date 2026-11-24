"""Retrain dedicated F&O models from the longest local 15m tape (+ optional Kite refresh)."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import fno_model
import fno_universe
import knowledge_db
import training_store


def run_daily_train(
    symbols: Optional[List[str]] = None,
    *,
    refresh_kite_days: int = 0,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Train on all merged 15m history; log run to knowledge.db."""
    path = training_store.ensure_tables(db_path or knowledge_db.ensure_db_dir())
    syms = [s.strip().upper() for s in (symbols or fno_universe.symbols()) if s.strip()]
    started = datetime.now().isoformat()
    metrics: Dict[str, Any] = {"symbols": {}}
    ok_all = True

    if refresh_kite_days > 0:
        import bar_ingest

        metrics["ingest"] = bar_ingest.ingest_symbols(syms, days=refresh_kite_days)

    for sym in syms:
        tape = fno_model.cached_15m(sym)
        if tape is None or len(tape) < 80:
            metrics["symbols"][sym] = {"ok": False, "error": "no 15m tape"}
            ok_all = False
            continue
        training_store.archive_tape_days(path, sym, tape)
        pack = fno_model.train(tape, symbol=sym, chain_db=path)
        row: Dict[str, Any] = {
            "ok": bool(pack.get("available")),
            "n_train": pack.get("n_train"),
            "holdout_accuracy": pack.get("holdout_accuracy"),
            "holdout_base_hit": pack.get("holdout_base_hit"),
            "bars": int(len(tape)),
            "data_audit": pack.get("data_audit"),
        }
        current = fno_model.load(symbol=sym)
        promote, reason = fno_model.promotion_check(pack, current, symbol=sym)
        row["promotion"] = {"approved": promote, "reason": reason}
        if promote:
            row["pkl"] = fno_model.save(pack, symbol=sym)
        else:
            ok_all = False
            row["reason"] = reason
        metrics["symbols"][sym] = row

    finished = datetime.now().isoformat()
    training_store.log_train_run(
        path,
        "daily_fno_train",
        started_at=started,
        finished_at=finished,
        symbols=syms,
        metrics=metrics,
        ok=ok_all,
    )
    return {"ok": ok_all, "started_at": started, "finished_at": finished, "metrics": metrics}
