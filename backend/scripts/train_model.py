#!/usr/bin/env python3
"""Train the QistEngine scorecard.

Deterministic (seed 42). Two runs produce byte-identical metrics.

Pipeline
--------
- Stratified 70/15/15 train/val/test split.
- StandardScaler on the 26 features (persisted separately).
- LightGBM with early stopping on validation AUC (patience 40).
- LogisticRegression baseline for an honest lift comparison.
- Isotonic calibration (CalibratedClassifierCV, cv=3) -> real probabilities.
- SHAP TreeExplainer on 500 background rows; expected value persisted.
- Refuses to ship: asserts test ROC-AUC >= 0.78.

Artifacts -> app/ml/artifacts/: model.pkl scaler.pkl explainer.pkl metadata.json
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.feature_engineering import FEATURE_ORDER  # noqa: E402

SEED = 42
RAW_CSV = BACKEND_ROOT / "data" / "raw" / "synthetic_profiles.csv"
PROCESSED_DIR = BACKEND_ROOT / "data" / "processed"
ARTIFACT_DIR = BACKEND_ROOT / "app" / "ml" / "artifacts"
VERSION = "qistengine-scorecard-v1.0.0"
MIN_TEST_AUC = 0.78

np.random.seed(SEED)


def stratified_split(df: pd.DataFrame, y_col: str):
    from sklearn.model_selection import train_test_split

    idx = np.arange(len(df))
    train_idx, temp_idx = train_test_split(
        idx, test_size=0.30, random_state=SEED, stratify=df[y_col].to_numpy()
    )
    val_idx, test_idx = train_test_split(
        temp_idx, test_size=0.50, random_state=SEED, stratify=df[y_col].to_numpy()[temp_idx]
    )
    return train_idx, val_idx, test_idx


def ks_statistic(y_true: np.ndarray, y_score: np.ndarray) -> float:
    order = np.argsort(y_score)
    y = y_true[order]
    cum_bad = np.cumsum(y) / max(y.sum(), 1)
    cum_good = np.cumsum(1 - y) / max((1 - y).sum(), 1)
    return float(np.max(np.abs(cum_bad - cum_good)))


def decile_lift(y_true: np.ndarray, y_score: np.ndarray) -> list[dict]:
    df = pd.DataFrame({"y": y_true, "p": y_score})
    df["decile"] = pd.qcut(df["p"].rank(method="first"), 10, labels=False)
    base = df["y"].mean()
    table = []
    for d in range(9, -1, -1):
        grp = df[df["decile"] == d]
        rate = float(grp["y"].mean())
        table.append(
            {
                "decile": 10 - d,
                "n": int(len(grp)),
                "default_rate": round(rate, 4),
                "lift": round(rate / base, 3) if base else 0.0,
            }
        )
    return table


def main() -> None:
    if not RAW_CSV.exists():
        raise SystemExit(f"Missing {RAW_CSV}. Run scripts/generate_synthetic_data.py first.")

    from lightgbm import LGBMClassifier, early_stopping, log_evaluation
    from sklearn.calibration import CalibratedClassifierCV
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import (
        average_precision_score,
        brier_score_loss,
        roc_auc_score,
    )
    from sklearn.preprocessing import StandardScaler

    df = pd.read_csv(RAW_CSV)
    X = df[FEATURE_ORDER].astype(float).to_numpy()
    y = df["default_flag"].astype(int).to_numpy()

    train_idx, val_idx, test_idx = stratified_split(df, "default_flag")
    X_tr, y_tr = X[train_idx], y[train_idx]
    X_va, y_va = X[val_idx], y[val_idx]
    X_te, y_te = X[test_idx], y[test_idx]

    scaler = StandardScaler().fit(X_tr)
    X_tr_s, X_va_s, X_te_s = scaler.transform(X_tr), scaler.transform(X_va), scaler.transform(X_te)

    # --- LightGBM ---
    lgbm = LGBMClassifier(
        n_estimators=400,
        learning_rate=0.045,
        num_leaves=24,
        max_depth=6,
        min_child_samples=40,
        subsample=0.85,
        subsample_freq=1,
        colsample_bytree=0.8,
        reg_lambda=1.2,
        random_state=SEED,
        n_jobs=1,
        deterministic=True,
        force_row_wise=True,
        verbose=-1,
    )
    lgbm.fit(
        X_tr_s,
        y_tr,
        eval_set=[(X_va_s, y_va)],
        eval_metric="auc",
        callbacks=[early_stopping(40, verbose=False), log_evaluation(0)],
    )
    best_iter = lgbm.best_iteration_ or lgbm.n_estimators

    # --- isotonic calibration on top of the fitted LightGBM ---
    calibrated = CalibratedClassifierCV(lgbm, method="isotonic", cv=3)
    calibrated.fit(X_tr_s, y_tr)

    # --- logistic baseline ---
    baseline = LogisticRegression(max_iter=2000, C=1.0, random_state=SEED)
    baseline.fit(X_tr_s, y_tr)

    # --- metrics on the untouched test split ---
    p_te = calibrated.predict_proba(X_te_s)[:, 1]
    p_te_base = baseline.predict_proba(X_te_s)[:, 1]
    p_te_uncal = lgbm.predict_proba(X_te_s)[:, 1]

    auc = float(roc_auc_score(y_te, p_te))
    auc_uncal = float(roc_auc_score(y_te, p_te_uncal))
    pr_auc = float(average_precision_score(y_te, p_te))
    ks = ks_statistic(y_te, p_te)
    gini = 2 * auc - 1
    brier = float(brier_score_loss(y_te, p_te))
    baseline_auc = float(roc_auc_score(y_te, p_te_base))
    lift_table = decile_lift(y_te, p_te)

    print("\n=== QistEngine training report ===")
    print(f"best_iteration        : {best_iter}")
    print(f"test ROC-AUC          : {auc:.4f}   (uncalibrated {auc_uncal:.4f})")
    print(f"test PR-AUC           : {pr_auc:.4f}")
    print(f"test KS               : {ks:.4f}")
    print(f"test Gini             : {gini:.4f}")
    print(f"test Brier            : {brier:.4f}")
    print(f"logistic baseline AUC : {baseline_auc:.4f}   (LightGBM lift {auc - baseline_auc:+.4f})")
    print(f"portfolio base rate   : {y.mean():.4f}")
    print("decile lift table (1 = riskiest decile):")
    for row in lift_table:
        print(f"  d{row['decile']:>2}  n={row['n']:>4}  default={row['default_rate']:.3f}  lift={row['lift']:.2f}")

    assert auc >= MIN_TEST_AUC, (
        f"Test ROC-AUC {auc:.4f} < {MIN_TEST_AUC}. Increase SIGNAL_SCALE in "
        f"generate_synthetic_data.py and regenerate -- do not weaken this assertion."
    )

    # --- SHAP TreeExplainer on the underlying LightGBM booster ---
    import shap

    rng = np.random.default_rng(SEED)
    bg_n = min(500, len(X_tr_s))
    bg_idx = rng.choice(len(X_tr_s), size=bg_n, replace=False)
    background = X_tr_s[bg_idx]
    explainer = shap.TreeExplainer(
        lgbm,
        data=background,
        feature_perturbation="interventional",
        model_output="raw",
    )
    ev = explainer.expected_value
    if isinstance(ev, (list, np.ndarray)):
        ev = float(np.asarray(ev).reshape(-1)[-1])
    else:
        ev = float(ev)

    # sanity: SHAP additivity on a sample
    sample = X_te_s[:50]
    sv = explainer.shap_values(sample)
    if isinstance(sv, list):
        sv = sv[-1]
    sv = np.asarray(sv)
    if sv.ndim == 3:
        sv = sv[:, :, -1]
    margin = lgbm.predict(sample, raw_score=True)
    recon = ev + sv.sum(axis=1)
    max_add_err = float(np.max(np.abs(recon - margin)))
    print(f"SHAP additivity max error (log-odds): {max_add_err:.4e}")

    # --- persist ---
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(calibrated, ARTIFACT_DIR / "model.pkl")
    joblib.dump(scaler, ARTIFACT_DIR / "scaler.pkl")
    joblib.dump(explainer, ARTIFACT_DIR / "explainer.pkl")

    metadata = {
        "version": VERSION,
        "trained_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "feature_order": FEATURE_ORDER,
        "n_features": len(FEATURE_ORDER),
        "base_rate": float(y.mean()),
        "shap_expected_value": ev,
        "best_iteration": int(best_iter),
        "split": {"train": len(train_idx), "val": len(val_idx), "test": len(test_idx)},
        "hyperparameters": lgbm.get_params(),
        "metrics": {
            "roc_auc": round(auc, 4),
            "roc_auc_uncalibrated": round(auc_uncal, 4),
            "pr_auc": round(pr_auc, 4),
            "ks": round(ks, 4),
            "gini": round(gini, 4),
            "brier": round(brier, 4),
            "logistic_baseline_auc": round(baseline_auc, 4),
            "lightgbm_lift_over_baseline": round(auc - baseline_auc, 4),
        },
        "decile_lift": lift_table,
        "shap_additivity_max_error": max_add_err,
    }
    # get_params may include a non-serialisable estimator; coerce.
    metadata["hyperparameters"] = {
        k: (v if isinstance(v, (int, float, str, bool, type(None))) else str(v))
        for k, v in metadata["hyperparameters"].items()
    }
    (ARTIFACT_DIR / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    # processed test set for the fairness audit
    test_df = df.iloc[test_idx].copy()
    test_df["pd_pred"] = p_te
    test_df.to_csv(PROCESSED_DIR / "test_predictions.csv", index=False)

    print(f"\n[train] artifacts -> {ARTIFACT_DIR}")
    print(f"[train] version {VERSION}")


if __name__ == "__main__":
    main()
