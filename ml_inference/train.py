"""
Model training: Logistic Regression (baseline) + XGBoost (primary).
Uses TimeSeriesSplit cross-validation — never random k-fold.
"""

import os
import joblib
import logging
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import f1_score
import xgboost as xgb

from ml_inference.feature_engineering import FEATURE_COLS, build_target_variable

logger = logging.getLogger(__name__)

TRAIN_END  = "2022-12-31"
TEST_START = "2023-01-01"
MODEL_DIR  = "models/"


def split_data(features: pd.DataFrame, labels: pd.Series):
    common = features.index.intersection(labels.index)
    X = features.loc[common][FEATURE_COLS].dropna()
    y = labels.loc[X.index]
    X_train = X[X.index <= pd.Timestamp(TRAIN_END)]
    X_test  = X[X.index >= pd.Timestamp(TEST_START)]
    y_train = y.loc[X_train.index]
    y_test  = y.loc[X_test.index]
    logger.info(f"Train: {len(X_train)} | Test: {len(X_test)} | HIGH_VOL rate: {y_train.mean():.1%}")
    return X_train, X_test, y_train, y_test


def train_logistic_regression(X_train, y_train) -> Pipeline:
    model = Pipeline([
        ("scaler", StandardScaler()),
        ("clf", LogisticRegression(C=1.0, class_weight="balanced",
                                   solver="lbfgs", max_iter=1000, random_state=42))
    ])
    model.fit(X_train, y_train)
    logger.info("Logistic Regression trained")
    return model


def train_xgboost(X_train, y_train) -> xgb.XGBClassifier:
    n_neg = (y_train == 0).sum()
    n_pos = (y_train == 1).sum()
    spw   = n_neg / n_pos
    tscv  = TimeSeriesSplit(n_splits=5)

    best_params, best_f1 = None, -1.0
    param_grid = [
        {"max_depth": d, "learning_rate": lr, "n_estimators": n}
        for d  in [3, 4, 5]
        for lr in [0.01, 0.05, 0.10]
        for n  in [100, 200, 300]
    ]

    for params in param_grid:
        fold_f1s = []
        for tr_idx, val_idx in tscv.split(X_train):
            m = xgb.XGBClassifier(**params, scale_pos_weight=spw,
                                   eval_metric="logloss", use_label_encoder=False,
                                   random_state=42, verbosity=0)
            m.fit(X_train.iloc[tr_idx], y_train.iloc[tr_idx])
            fold_f1s.append(f1_score(y_train.iloc[val_idx],
                                     m.predict(X_train.iloc[val_idx]),
                                     zero_division=0))
        mean_f1 = np.mean(fold_f1s)
        if mean_f1 > best_f1:
            best_f1, best_params = mean_f1, params

    logger.info(f"XGBoost best params: {best_params} (val F1={best_f1:.4f})")
    final = xgb.XGBClassifier(**best_params, scale_pos_weight=spw,
                               eval_metric="logloss", use_label_encoder=False,
                               random_state=42, verbosity=0)
    final.fit(X_train, y_train)
    return final


def save_models(lr_model, xgb_model, threshold: float):
    os.makedirs(MODEL_DIR, exist_ok=True)
    joblib.dump(lr_model,  f"{MODEL_DIR}logistic_regression_v1.pkl")
    joblib.dump(xgb_model, f"{MODEL_DIR}xgboost_v1.pkl")
    joblib.dump({"volatility_threshold": threshold,
                 "feature_cols": FEATURE_COLS,
                 "train_end": TRAIN_END,
                 "test_start": TEST_START},
                f"{MODEL_DIR}metadata_v1.pkl")
    logger.info(f"Models saved to {MODEL_DIR}")


def run_training_pipeline(features, labels, threshold):
    X_train, X_test, y_train, y_test = split_data(features, labels)
    lr  = train_logistic_regression(X_train, y_train)
    xgb_model = train_xgboost(X_train, y_train)
    save_models(lr, xgb_model, threshold)
    return X_train, X_test, y_train, y_test, lr, xgb_model
