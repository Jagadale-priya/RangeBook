"""Fixed holdout backtest — train on dates before cut, test on dates on/after cut."""

from __future__ import annotations

import os
from typing import Any, Dict, Optional, Tuple

import pandas as pd
from sklearn.metrics import accuracy_score, precision_score, recall_score, roc_auc_score

import regime_features


def run_holdout_backtest(
    df: pd.DataFrame,
    compute_features_fn,
    build_training_data_fn,
    train_models_fn,
    holdout_start: str,
    target_min_return: float,
) -> Tuple[Dict[str, Any], Optional[str]]:
    if df is None or len(df) < 150:
        return {}, "Need at least 150 daily bars"

    try:
        cut = pd.Timestamp(holdout_start).normalize()
    except ValueError:
        return {}, f"Invalid holdout_start {holdout_start}"

    idx = pd.to_datetime(df.index)
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_localize(None)
    norm_idx = pd.Series(idx, index=df.index).dt.normalize()
    mask_train = norm_idx < cut
    mask_test = norm_idx >= cut
    if mask_train.sum() < 100 or mask_test.sum() < 20:
        return {}, f"Too few train ({int(mask_train.sum())}) or test ({int(mask_test.sum())}) rows"

    old_thr = os.environ.get("TARGET_MIN_RETURN")
    os.environ["TARGET_MIN_RETURN"] = str(target_min_return)
    try:
        feat, _ = compute_features_fn(df)
        feat = regime_features.attach_regime_features(feat)
        packed = build_training_data_fn(df, feat)
        if packed is None or packed[0] is None:
            return {}, "No labeled samples after feature NaN drop"
        if len(packed) >= 4:
            X_all, y_all, feature_cols, y_down_all = packed
        else:
            X_all, y_all, feature_cols = packed
            y_down_all = None
        if X_all.empty:
            return {}, "No labeled samples after feature NaN drop"

        train_mask = mask_train.reindex(X_all.index, fill_value=False)
        test_mask = mask_test.reindex(X_all.index, fill_value=False)
        X_train = X_all.loc[train_mask]
        y_train = y_all.loc[train_mask]
        X_test = X_all.loc[test_mask]
        y_test = y_all.loc[test_mask]
        y_down_train = y_down_all.loc[train_mask] if y_down_all is not None else None

        if len(X_train) < 80:
            return {}, f"Insufficient training samples after NaN drop ({len(X_train)})"
        if len(X_test) < 10:
            return {}, f"Holdout too small after feature NaN ({len(X_test)})"

        model, scaler, metrics, selected_cols = train_models_fn(
            X_train, y_train, feature_cols, y_down=y_down_train
        )
        cols = [c for c in selected_cols if c in X_test.columns]
        if not cols:
            return {}, "No overlapping features on holdout"
        X_te = X_test[cols].dropna()
        y_te = y_test.loc[X_te.index]
        if len(X_te) < 10:
            return {}, "Holdout too small after feature NaN"
        X_s = scaler.transform(X_te[cols])
        head = model["up"] if isinstance(model, dict) else model
        proba = head.predict_proba(X_s)[:, 1]
        pred = (proba >= 0.5).astype(int)
    finally:
        if old_thr is None:
            os.environ.pop("TARGET_MIN_RETURN", None)
        else:
            os.environ["TARGET_MIN_RETURN"] = old_thr

    out: Dict[str, Any] = {
        "holdout_start": holdout_start,
        "train_bars": int(mask_train.sum()),
        "train_samples": int(len(X_train)),
        "test_bars": int(len(X_te)),
        "target_min_return_pct": target_min_return * 100,
        "accuracy": float(accuracy_score(y_te, pred)),
        "precision": float(precision_score(y_te, pred, zero_division=0)),
        "recall": float(recall_score(y_te, pred, zero_division=0)),
        "train_walk_forward_accuracy": metrics.get("walk_forward_accuracy"),
        "train_ensemble_accuracy": metrics.get("ensemble_accuracy"),
    }
    try:
        out["auc"] = float(roc_auc_score(y_te, proba))
    except ValueError:
        out["auc"] = None
    return out, None
