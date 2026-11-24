"""Point-in-time daily audit: replay ML + TA + news/memory on history, store outcomes."""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

import analysis_engine
import analysis_store
import news_data
import pattern_memory

FLAT_THRESHOLD_PCT = pattern_memory.FLAT_THRESHOLD_PCT


def side_from_return(pct: Optional[float], threshold: float) -> str:
    if pct is None or (isinstance(pct, float) and np.isnan(pct)):
        return "UNKNOWN"
    if pct > threshold * 100:
        return "UP"
    if pct < -threshold * 100:
        return "DOWN"
    return "FLAT"


def side_from_decision(decision: str) -> str:
    d = (decision or "").upper()
    if "BUY" in d:
        return "UP"
    if "SELL" in d:
        return "DOWN"
    return "FLAT"


def label_correct(predicted_side: str, actual_side: str) -> bool:
    if predicted_side == "FLAT" or actual_side in ("FLAT", "UNKNOWN"):
        return predicted_side == actual_side
    return predicted_side == actual_side


def failure_reason(
    predicted_side: str,
    actual_side: str,
    ml_proba: float,
    signals_agree: bool,
    signal_quality: str,
    actual_return_pct: float,
    threshold: float,
) -> str:
    if label_correct(predicted_side, actual_side):
        return "correct"
    # High-confidence errors are the most actionable, so they must be reported
    # before the broader borderline/disagreement buckets can absorb them.
    if signal_quality == "HIGH":
        return "high_conf_wrong"
    if abs(actual_return_pct) <= threshold * 100 * 1.2:
        return "borderline_move"
    if not signals_agree and predicted_side != "FLAT":
        return "ml_ta_disagree"
    if ml_proba >= 0.55 and actual_side == "DOWN":
        return "ml_bull_false"
    if ml_proba <= 0.45 and actual_side == "UP":
        return "ml_bear_false"
    if predicted_side == "FLAT" and actual_side in ("UP", "DOWN"):
        return "missed_move"
    return "direction_wrong"


def _unpack_training(pack):
    if pack is None:
        return None, None, None, None
    if len(pack) >= 4:
        return pack[0], pack[1], pack[2], pack[3]
    return pack[0], pack[1], pack[2], None


def _predict_sides(model, X_s) -> Tuple[float, Optional[float]]:
    if isinstance(model, dict):
        p_up = float(model["up"].predict_proba(X_s)[0, 1])
        down = model.get("down")
        p_down = float(down.predict_proba(X_s)[0, 1]) if down is not None else None
        return p_up, p_down
    if hasattr(model, "predict_proba"):
        return float(model.predict_proba(X_s)[0, 1]), None
    return 0.5, None


def _fit_fast_head(X_tr, y, probe_inner: int):
    from sklearn.ensemble import HistGradientBoostingClassifier

    model = HistGradientBoostingClassifier(max_depth=6, max_iter=120, random_state=42)
    model.fit(X_tr, y)
    val_acc, hc_acc = 0.0, 0.0
    if probe_inner < len(y):
        probe = HistGradientBoostingClassifier(max_depth=6, max_iter=120, random_state=42)
        probe.fit(X_tr[:probe_inner], y.iloc[:probe_inner])
        p_val = probe.predict_proba(X_tr[probe_inner:])[:, 1]
        y_val = y.iloc[probe_inner:].values
        base = float(y.iloc[:probe_inner].mean())
        pred = (p_val >= base).astype(int)
        val_acc = float((pred == y_val).mean())
        hc = (p_val >= 0.62) | (p_val <= 0.38)
        if hc.sum() > 0:
            hc_acc = float(((p_val[hc] >= base).astype(int) == y_val[hc]).mean())
    return model, val_acc, hc_acc


def _audit_train_model(
    X: pd.DataFrame,
    y: pd.Series,
    feature_cols: List[str],
    train_models_fn: Callable,
    y_down: Optional[pd.Series] = None,
):
    if os.environ.get("AUDIT_FAST", "").strip() == "1":
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.preprocessing import StandardScaler

        if len(X) < 100 or y.nunique() < 2:
            return None, None, {}, feature_cols

        # Rank features by importance on an inner split, then train on every row
        # available before the decision date. Taking feature_cols[:40] by position
        # and holding back 25% of history both made the audit unrepresentative.
        inner = max(80, int(len(X) * 0.8))
        Xf = X.fillna(0)
        ranker = RandomForestClassifier(
            n_estimators=80, max_depth=7, min_samples_leaf=8,
            class_weight="balanced", random_state=42, n_jobs=-1,
        )
        ranker.fit(Xf.iloc[:inner], y.iloc[:inner])
        k = min(40, len(feature_cols))
        order = np.argsort(ranker.feature_importances_)[::-1][:k]
        sel = [feature_cols[i] for i in sorted(order)]

        Xs = Xf[sel]
        scaler = StandardScaler()
        X_tr = scaler.fit_transform(Xs)
        up_model, val_acc, hc_acc = _fit_fast_head(X_tr, y, inner)
        metrics = {
            "walk_forward_accuracy": val_acc or 0.5,
            "high_confidence_accuracy": hc_acc or val_acc or 0.5,
            "ensemble_accuracy": val_acc or 0.5,
            "base_rate": float(y.mean()),
            "train_samples": int(len(Xs)),
            "heads": ["up"],
        }
        pack: Dict[str, Any] = {"up": up_model, "down": None}
        if y_down is not None:
            y_dn = y_down.reindex(y.index)
            if y_dn is not None and y_dn.nunique() >= 2:
                down_model, d_acc, d_hc = _fit_fast_head(X_tr, y_dn, inner)
                pack["down"] = down_model
                metrics["base_rate_down"] = float(y_dn.mean())
                metrics["ensemble_accuracy_down"] = d_acc or 0.5
                metrics["heads"].append("down")
        return pack, scaler, metrics, sel
    return train_models_fn(X, y, feature_cols, y_down=y_down)


def _knowledge_adjust_at_date(
    db_path: str,
    model_dir: str,
    df: pd.DataFrame,
    i: int,
    stock_key: str,
    news_db: str,
    as_of: pd.Timestamp,
) -> Tuple[float, int, List[str]]:
    window = df.iloc[max(0, i - 2) : i + 1]
    det = analysis_engine.detect_candlestick_three_bars(window)
    patterns = det.get("patterns") or []
    news = news_data.get_news_as_of(news_db, stock_key, as_of, limit=8)
    knowledge = pattern_memory.apply_knowledge_to_prediction(
        db_path,
        model_dir,
        stock_key,
        patterns,
        news,
        None,
        as_of=as_of,
    )
    return float(knowledge.get("combined_adjust") or 0), len(news), patterns


def _row_technical_score(feat_row: pd.Series, close: float, compute_tech_fn: Callable) -> float:
    ind: Dict[str, Any] = {"close": close}
    for k in feat_row.index:
        if pd.notna(feat_row[k]):
            ind[k] = float(feat_row[k])
    return compute_tech_fn(ind)


def run_stock_daily_audit(
    stock_key: str,
    symbol: str,
    df: pd.DataFrame,
    *,
    db_path: str,
    news_db_path: str,
    model_dir: str,
    holdout_start: str,
    target_min_return: float,
    compute_features_fn: Callable,
    build_training_data_fn: Callable,
    train_models_fn: Callable,
    generate_decision_fn: Callable,
    compute_technical_score_fn: Callable,
    audit_run_id: int,
    retrain_every: int = 42,
    step_days: int = 1,
) -> Dict[str, Any]:
    pattern_memory.setup_knowledge_database(db_path)
    if df is None or len(df) < 200:
        return {"stock": stock_key, "error": "insufficient OHLCV", "evaluated": 0}

    cut = pd.Timestamp(holdout_start).normalize()
    if getattr(cut, "tz", None) is not None:
        cut = cut.tz_localize(None)
    feat, _ = compute_features_fn(df)
    import regime_features

    feat = regime_features.attach_regime_features(feat)
    old_thr = os.environ.get("TARGET_MIN_RETURN")
    os.environ["TARGET_MIN_RETURN"] = str(target_min_return)
    try:
        X, y, feature_cols, y_down = _unpack_training(build_training_data_fn(df, feat))
    finally:
        if old_thr is None:
            os.environ.pop("TARGET_MIN_RETURN", None)
        else:
            os.environ["TARGET_MIN_RETURN"] = old_thr

    if X is None or len(X) < 100:
        return {"stock": stock_key, "error": "insufficient labeled samples", "evaluated": 0}

    close = df["Close"]
    idx_norm = pd.to_datetime(X.index)
    if getattr(idx_norm, "tz", None) is not None:
        idx_norm = idx_norm.tz_localize(None)
    idx_norm = pd.Series(idx_norm.normalize(), index=X.index)
    test_mask = idx_norm >= cut
    test_indices = [i for i in range(len(X)) if bool(test_mask.iloc[i])]
    if step_days > 1:
        test_indices = test_indices[::step_days]

    model, scaler, metrics, selected_cols = None, None, {}, feature_cols
    last_train_at = -10**9
    evaluated = 0
    correct = 0
    reason_counts: Dict[str, int] = {}

    import sqlite3

    conn = sqlite3.connect(db_path, timeout=60)
    conn.execute("PRAGMA busy_timeout=60000")
    for i in test_indices:
        if i < 100 or i >= len(X) - 1:
            continue
        ix = X.index[i]
        if i - last_train_at >= retrain_every or model is None:
            X_tr = X.iloc[:i]
            y_tr = y.iloc[:i]
            y_tr_down = y_down.iloc[:i] if y_down is not None else None
            if len(X_tr) < 100:
                continue
            model, scaler, metrics, selected_cols = _audit_train_model(
                X_tr, y_tr, feature_cols, train_models_fn, y_down=y_tr_down
            )
            last_train_at = i
            if model is None or scaler is None:
                continue

        cols = [c for c in selected_cols if c in X.columns]
        row = X.iloc[[i]][cols].dropna(axis=1)
        if row.empty:
            continue
        use_cols = list(row.columns)
        X_s = scaler.transform(row[use_cols])
        ml_proba, ml_proba_down = _predict_sides(model, X_s)

        price = float(close.loc[ix])
        tech_score = _row_technical_score(feat.loc[ix], price, compute_technical_score_fn)
        as_of = pd.Timestamp(ix).normalize()
        df_i = df.index.get_loc(ix)
        know_adj, news_n, _patterns = _knowledge_adjust_at_date(
            db_path, model_dir, df, df_i, stock_key, news_db_path, as_of
        )
        atr_val = float(feat.loc[ix].get("atr_14") or price * 0.02)
        decision_info = generate_decision_fn(
            ml_proba, tech_score, price, atr_val, metrics or {}, know_adj,
            ml_proba_down=ml_proba_down,
        )
        decision = decision_info["decision"]
        pred_side = side_from_decision(decision)

        if df_i + 1 >= len(close):
            continue
        fwd = (float(close.iloc[df_i + 1]) / float(close.iloc[df_i]) - 1.0) * 100.0
        act_side = side_from_return(fwd, target_min_return)
        ok = label_correct(pred_side, act_side)
        evaluated += 1
        if ok:
            correct += 1
        reason = failure_reason(
            pred_side,
            act_side,
            ml_proba,
            decision_info.get("signals_agree", False),
            decision_info.get("signal_quality", "LOW"),
            fwd,
            target_min_return,
        )
        reason_counts[reason] = reason_counts.get(reason, 0) + 1

        conn.execute(
            """
            INSERT INTO daily_audit_outcomes
            (audit_run_id, stock, as_of_date, predicted_decision, predicted_side,
             ml_probability, technical_score, combined_score, knowledge_adjust,
             news_count, signals_agree, signal_quality,
             actual_return_1d, actual_side, label_correct, failure_reason,
             base_rate, confidence_lift)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(audit_run_id, stock, as_of_date) DO UPDATE SET
              label_correct=excluded.label_correct,
              failure_reason=excluded.failure_reason
            """,
            (
                audit_run_id,
                stock_key.upper(),
                as_of.strftime("%Y-%m-%d"),
                decision,
                pred_side,
                ml_proba,
                tech_score,
                decision_info.get("combined_score"),
                know_adj,
                news_n,
                1 if decision_info.get("signals_agree") else 0,
                decision_info.get("signal_quality"),
                fwd,
                act_side,
                1 if ok else 0,
                reason,
                decision_info.get("base_rate"),
                decision_info.get("ml_confidence_lift"),
            ),
        )
    conn.commit()
    conn.close()

    acc = (correct / evaluated) if evaluated else 0.0
    return {
        "stock": stock_key,
        "evaluated": evaluated,
        "correct": correct,
        "accuracy": round(acc, 4),
        "failure_breakdown": reason_counts,
    }


def suggest_tuning_from_audit(db_path: str, audit_run_id: int) -> Dict[str, Any]:
    import sqlite3

    if not os.path.isfile(db_path):
        return {}
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        """
        SELECT failure_reason, COUNT(*) AS n FROM daily_audit_outcomes
        WHERE audit_run_id = ? AND label_correct = 0
        GROUP BY failure_reason ORDER BY n DESC
        """,
        (audit_run_id,),
    ).fetchall()
    acc_row = conn.execute(
        """
        SELECT AVG(label_correct) AS acc, COUNT(*) AS n FROM daily_audit_outcomes
        WHERE audit_run_id = ?
        """,
        (audit_run_id,),
    ).fetchone()
    conn.close()
    acc = float(acc_row[0] or 0)
    n = int(acc_row[1] or 0)
    suggestions: List[str] = []
    breakdown = {r[0]: r[1] for r in rows}
    if acc < 0.52 and n > 50:
        suggestions.append("Aggregate accuracy below 52% — run --train-watchlist after prefetch; consider raising HIGH confidence bar.")
    if breakdown.get("ml_bull_false", 0) + breakdown.get("ml_bear_false", 0) > n * 0.15:
        suggestions.append("ML direction errors elevated — tune TARGET_MIN_RETURN or retrain with --retrain.")
    if breakdown.get("ml_ta_disagree", 0) > n * 0.2:
        suggestions.append("Many disagreements while acting — HIGH quality gate is working; avoid lowering TA/ML agreement threshold.")
    if breakdown.get("borderline_move", 0) > n * 0.25:
        suggestions.append("Many borderline moves — consider adjusting TARGET_MIN_RETURN slightly upward.")
    return {
        "accuracy": acc,
        "samples": n,
        "failure_breakdown": breakdown,
        "suggestions": suggestions,
    }


def run_watchlist_audit(
    watchlist: List[Dict[str, Any]],
    *,
    db_path: str,
    news_db_path: str,
    model_dir: str,
    holdout_start: str,
    target_min_return: float,
    download_fn: Callable,
    resolve_fn: Callable,
    compute_features_fn: Callable,
    build_training_data_fn: Callable,
    train_models_fn: Callable,
    generate_decision_fn: Callable,
    compute_technical_score_fn: Callable,
    retrain_every: int = 42,
    step_days: int = 1,
    symbols_filter: Optional[List[str]] = None,
) -> Dict[str, Any]:
    analysis_store.ensure_analysis_tables(db_path)
    import sqlite3

    started = datetime.now().isoformat()
    conn = sqlite3.connect(db_path)
    cur = conn.execute(
        """
        INSERT INTO audit_runs (started_at, holdout_start, symbols_json, notes)
        VALUES (?, ?, ?, ?)
        """,
        (
            started,
            holdout_start,
            json.dumps(symbols_filter or [w.get("symbol") for w in watchlist]),
            f"retrain_every={retrain_every} step_days={step_days}",
        ),
    )
    audit_run_id = cur.lastrowid
    conn.commit()
    conn.close()

    per_stock: List[Dict[str, Any]] = []
    total_eval = 0
    total_ok = 0
    filt = {s.strip().upper() for s in symbols_filter} if symbols_filter else None

    for item in watchlist:
        stock = (item.get("symbol") or "").strip().upper()
        if not stock or (filt and stock not in filt):
            continue
        try:
            yahoo = resolve_fn(stock)
            df = download_fn(yahoo, stock_key=stock)
            summary = run_stock_daily_audit(
                stock,
                yahoo,
                df,
                db_path=db_path,
                news_db_path=news_db_path,
                model_dir=model_dir,
                holdout_start=holdout_start,
                target_min_return=target_min_return,
                compute_features_fn=compute_features_fn,
                build_training_data_fn=build_training_data_fn,
                train_models_fn=train_models_fn,
                generate_decision_fn=generate_decision_fn,
                compute_technical_score_fn=compute_technical_score_fn,
                audit_run_id=audit_run_id,
                retrain_every=retrain_every,
                step_days=step_days,
            )
            per_stock.append(summary)
            total_eval += summary.get("evaluated", 0)
            total_ok += summary.get("correct", 0)
            print(f"  Audit {stock}: acc={summary.get('accuracy')} n={summary.get('evaluated')}")
        except Exception as exc:
            per_stock.append({"stock": stock, "error": str(exc)})

    tuning = suggest_tuning_from_audit(db_path, audit_run_id)
    finished = datetime.now().isoformat()
    acc = (total_ok / total_eval) if total_eval else 0.0

    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        UPDATE audit_runs SET finished_at = ?, total_days = ?, total_correct = ?,
               total_evaluated = ?, accuracy = ?, params_json = ?
        WHERE id = ?
        """,
        (
            finished,
            total_eval,
            total_ok,
            total_eval,
            acc,
            json.dumps(tuning),
            audit_run_id,
        ),
    )
    conn.commit()
    conn.close()

    return {
        "audit_run_id": audit_run_id,
        "holdout_start": holdout_start,
        "accuracy": round(acc, 4),
        "evaluated": total_eval,
        "per_stock": per_stock,
        "tuning": tuning,
        "db_path": db_path,
    }
