# Module 3 — ML Inference Service
## Step-by-Step Build Guide

---

## What This Module Does
Trains Logistic Regression, XGBoost, and optionally LSTM models to predict whether Nifty 50 will be in a HIGH_VOL or NORMAL volatility regime the next trading day. Uses India AI-GPR features plus market data. Runs daily inference at 20:40 IST (after Module 2 completes) and caches predictions in Redis with SHAP explanations.

---

## Prerequisites
- Module 2 must have been running long enough to have GPR data from **2010 onwards** (use Caldara seed data if needed — see Module 2, Step 2, Option B)
- An internet connection for yfinance market data pulls
- Python packages:

```bash
pip install \
  pandas numpy scikit-learn xgboost shap \
  yfinance psycopg2-binary redis \
  torch torchvision \
  matplotlib seaborn \
  joblib python-dotenv
```

---

## Step 1 — Pull and Store Market Data (`ml_inference/market_data.py`)

```python
# ml_inference/market_data.py

import yfinance as yf
import pandas as pd
import psycopg2
import os
import logging
from datetime import date, timedelta

logger = logging.getLogger(__name__)

# yfinance tickers
TICKERS = {
    "nifty":   "^NSEI",     # Nifty 50 Index
    "inrusd":  "USDINR=X",  # INR/USD spot (note: inverted — USD per INR)
    "crude":   "CL=F",      # WTI Crude Oil front-month futures
}

# NSE is closed on these additional Indian holidays (partial list — update annually)
# Full list: https://www.nseindia.com/market-data/holiday-calendar
NSE_HOLIDAYS_2024 = [
    date(2024, 1, 22), date(2024, 3, 29), date(2024, 4, 14),
    date(2024, 4, 17), date(2024, 5, 23), date(2024, 8, 15),
    date(2024, 10, 2), date(2024, 11, 1), date(2024, 11, 15),
    date(2024, 12, 25),
]


def fetch_market_data(start_date: str = "2010-01-01",
                      end_date: str = None) -> pd.DataFrame:
    """
    Download price data for Nifty, INR/USD, and Crude Oil via yfinance.
    Returns a single DataFrame with one row per date.
    
    Handles missing data (holidays) via forward-fill with max 1-day gap.
    """
    if end_date is None:
        import datetime
        end_date = datetime.date.today().isoformat()
    
    logger.info(f"Fetching market data {start_date} to {end_date}")
    
    dfs = {}
    for name, ticker in TICKERS.items():
        try:
            df = yf.download(ticker, start=start_date, end=end_date, 
                             auto_adjust=True, progress=False)
            if df.empty:
                raise ValueError(f"No data returned for {ticker}")
            dfs[name] = df['Close'].rename(name)
        except Exception as e:
            logger.error(f"Failed to fetch {ticker}: {e}")
            raise
    
    # Combine on date index
    combined = pd.concat(dfs.values(), axis=1)
    combined.index = pd.to_datetime(combined.index).date
    combined.index.name = 'date'
    
    # Sanity checks
    _validate_prices(combined)
    
    # Forward-fill missing values (NSE holidays, data gaps) — max 1 day
    combined = combined.fillna(method='ffill', limit=1)
    
    # Drop any remaining NaN rows (e.g., 2+ consecutive holidays)
    rows_before = len(combined)
    combined = combined.dropna()
    dropped = rows_before - len(combined)
    if dropped > 0:
        logger.warning(f"Dropped {dropped} rows with NaN after 1-day forward-fill")
    
    logger.info(f"Market data: {len(combined)} trading days")
    return combined


def _validate_prices(df: pd.DataFrame):
    """Basic sanity checks on price data."""
    for col in df.columns:
        if col == 'nifty':
            assert df[col].min() > 1000, f"Nifty below 1000 — likely data error"
            assert df[col].max() < 100000, f"Nifty above 100000 — likely data error"
        elif col == 'inrusd':
            assert df[col].min() > 50, f"INR/USD below 50 — data error"
            assert df[col].max() < 200, f"INR/USD above 200 — data error"


def compute_returns(market_df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute daily percentage returns from price levels.
    
    return[t] = (price[t] - price[t-1]) / price[t-1]
    """
    returns = pd.DataFrame(index=market_df.index)
    
    for col in ['nifty', 'inrusd', 'crude']:
        returns[f'{col}_return'] = market_df[col].pct_change()
    
    return returns.dropna()
```

---

## Step 2 — Feature Engineering (`ml_inference/feature_engineering.py`)

**Critical:** Every feature must use only data available before market open on day $t$. We use lag-1 at minimum for all features.

```python
# ml_inference/feature_engineering.py

import pandas as pd
import numpy as np
import psycopg2
import os
import logging
from datetime import date

logger = logging.getLogger(__name__)


def load_gpr_series(conn: psycopg2.extensions.connection,
                    start_date: str = "2010-01-01") -> pd.Series:
    """
    Load the full GPR index series from PostgreSQL.
    Returns a pandas Series indexed by date.
    """
    df = pd.read_sql("""
        SELECT index_date, normalized_gpr
        FROM gpr_index
        WHERE index_date >= %s
          AND normalized_gpr IS NOT NULL
        ORDER BY index_date
    """, conn, params=(start_date,))
    
    df['index_date'] = pd.to_datetime(df['index_date'])
    s = df.set_index('index_date')['normalized_gpr']
    return s


def build_feature_matrix(gpr_series: pd.Series,
                          market_df: pd.DataFrame) -> pd.DataFrame:
    """
    Build the full feature matrix aligned on trading dates.
    
    All features are POINT-IN-TIME SAFE:
    - Every feature at date t uses only data from t-1 or earlier
    - The model is run AFTER market close on t-1 to predict t
    
    Feature naming convention: _t{N} means N days ago from prediction date
    """
    # Align market and GPR data on their common dates
    market_returns = compute_returns_from_df(market_df)
    
    # Combined date range (intersection)
    all_dates = gpr_series.index.intersection(market_returns.index)
    all_dates = sorted(all_dates)
    
    features = pd.DataFrame(index=all_dates)
    
    # ── GPR Features ────────────────────────────────────────────────────────
    # GPR[t-1]: most recent GPR value available before prediction
    features['india_ai_gpr_t1'] = gpr_series.reindex(features.index).shift(1)
    
    # GPR[t-3]: 3-day lag
    features['india_ai_gpr_t3'] = gpr_series.reindex(features.index).shift(3)
    
    # GPR[t-7]: 7-day lag (weekly trend)
    features['india_ai_gpr_t7'] = gpr_series.reindex(features.index).shift(7)
    
    # GPR shock flag: 1 if GPR[t-1] was > 2 std above its 252-day rolling mean
    gpr_rolling_mean = gpr_series.rolling(252).mean()
    gpr_rolling_std  = gpr_series.rolling(252).std()
    gpr_upper_band   = gpr_rolling_mean + 2 * gpr_rolling_std
    features['gpr_shock_flag'] = (
        (gpr_series >= gpr_upper_band).astype(int).reindex(features.index).shift(1)
    )
    
    # 7-day rolling mean of GPR (lagged by 1 to be safe)
    features['gpr_rolling_mean_7'] = (
        gpr_series.rolling(7).mean().reindex(features.index).shift(1)
    )
    
    # ── Market Features ──────────────────────────────────────────────────────
    # INR/USD return yesterday
    features['inr_usd_return'] = market_returns['inrusd_return'].reindex(features.index).shift(1)
    
    # Crude oil return yesterday
    features['crude_oil_return'] = market_returns['crude_return'].reindex(features.index).shift(1)
    
    # Nifty return yesterday
    features['nifty_return_t1'] = market_returns['nifty_return'].reindex(features.index).shift(1)
    
    # Nifty return 5 days ago
    features['nifty_return_t5'] = market_returns['nifty_return'].reindex(features.index).shift(5)
    
    # Realized volatility yesterday: std of returns over t-11 to t-1 (10-day window, lagged 1)
    # IMPORTANT: window is [t-11, t-1] NOT [t-10, t]
    # This avoids overlap with the target variable window [t-9, t]
    # The 1-day separation is sufficient to prevent lookahead bias
    nifty_returns = market_returns['nifty_return'].reindex(features.index)
    features['nifty_vol_lag1'] = (
        nifty_returns
        .shift(1)           # lag by 1 so we don't use t
        .rolling(10)        # 10-day rolling std
        .std()
    )
    
    logger.info(f"Feature matrix: {len(features)} rows × {len(features.columns)} features")
    logger.info(f"Date range: {features.index[0]} to {features.index[-1]}")
    
    return features


def build_target_variable(market_df: pd.DataFrame, 
                           train_end_date: str = "2022-12-31") -> pd.Series:
    """
    Construct binary volatility regime labels.
    
    rolling_vol[t] = std(nifty_daily_returns, window=10 days ending at t)
    threshold      = 75th percentile of rolling_vol (computed on TRAIN SET ONLY)
    label[t]       = HIGH_VOL (1) if rolling_vol[t] > threshold, else NORMAL (0)
    
    CRITICAL: threshold is computed on train set only, then applied to all dates.
    Computing threshold on full dataset = data leakage.
    """
    returns = compute_returns_from_df(market_df)
    nifty_returns = returns['nifty_return']
    
    # 10-day realized volatility
    rolling_vol = nifty_returns.rolling(window=10).std()
    
    # Compute threshold on training period only
    train_mask = rolling_vol.index <= pd.Timestamp(train_end_date)
    train_vol   = rolling_vol[train_mask].dropna()
    
    threshold = float(np.percentile(train_vol, 75))
    logger.info(
        f"Volatility threshold (75th pct of train set): {threshold:.6f}"
        f" | Train mean: {train_vol.mean():.6f}"
    )
    
    # Apply threshold to all dates
    labels = (rolling_vol > threshold).astype(int)
    labels.name = 'label'  # 1 = HIGH_VOL, 0 = NORMAL
    
    # Log class balance
    full_balance = labels.value_counts(normalize=True)
    logger.info(f"Overall class balance: {full_balance.to_dict()}")
    
    train_balance = labels[train_mask].value_counts(normalize=True)
    logger.info(f"Train class balance: {train_balance.to_dict()}")
    
    return labels, threshold


def compute_returns_from_df(market_df: pd.DataFrame) -> pd.DataFrame:
    """Compute daily returns from price DataFrame."""
    returns = pd.DataFrame(index=market_df.index)
    for col in market_df.columns:
        returns[f'{col}_return'] = market_df[col].pct_change()
    return returns.dropna()
```

---

## Step 3 — Model Training (`ml_inference/train.py`)

```python
# ml_inference/train.py

import os
import joblib
import logging
import numpy as np
import pandas as pd
from datetime import date

from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import f1_score, roc_auc_score

import xgboost as xgb

logger = logging.getLogger(__name__)

TRAIN_END   = "2022-12-31"
TEST_START  = "2023-01-01"
MODEL_DIR   = "models/"
FEATURE_COLS = [
    'india_ai_gpr_t1', 'india_ai_gpr_t3', 'india_ai_gpr_t7',
    'gpr_shock_flag', 'gpr_rolling_mean_7',
    'inr_usd_return', 'crude_oil_return',
    'nifty_return_t1', 'nifty_return_t5', 'nifty_vol_lag1'
]


def split_data(features: pd.DataFrame, labels: pd.Series):
    """
    Split into train and test sets using strict temporal split.
    NO shuffling — time series ordering must be preserved.
    """
    # Align features and labels
    common_idx = features.index.intersection(labels.index)
    X = features.loc[common_idx][FEATURE_COLS].dropna()
    y = labels.loc[X.index]
    
    train_mask = X.index <= pd.Timestamp(TRAIN_END)
    test_mask  = X.index >= pd.Timestamp(TEST_START)
    
    X_train, y_train = X[train_mask], y[train_mask]
    X_test,  y_test  = X[test_mask],  y[test_mask]
    
    logger.info(f"Train: {len(X_train)} samples ({y_train.mean():.1%} HIGH_VOL)")
    logger.info(f"Test:  {len(X_test)} samples ({y_test.mean():.1%} HIGH_VOL)")
    
    return X_train, X_test, y_train, y_test


def train_logistic_regression(X_train, y_train) -> Pipeline:
    """
    Train Logistic Regression baseline.
    class_weight='balanced' handles the ~25/75 class imbalance automatically.
    StandardScaler applied inside pipeline (prevents data leakage from scaler fit).
    """
    model = Pipeline([
        ('scaler', StandardScaler()),
        ('clf', LogisticRegression(
            C=1.0,
            solver='lbfgs',
            class_weight='balanced',
            max_iter=1000,
            random_state=42
        ))
    ])
    
    model.fit(X_train, y_train)
    logger.info("Logistic Regression trained")
    
    # Log coefficients for interpretability
    coefs = dict(zip(
        FEATURE_COLS,
        model.named_steps['clf'].coef_[0]
    ))
    logger.info(f"LR coefficients: {coefs}")
    
    return model


def train_xgboost(X_train, y_train) -> xgb.XGBClassifier:
    """
    Train XGBoost with TimeSeriesSplit cross-validation for HPO.
    scale_pos_weight handles class imbalance natively.
    """
    n_neg = (y_train == 0).sum()
    n_pos = (y_train == 1).sum()
    scale_pos_weight = n_neg / n_pos
    logger.info(f"XGBoost scale_pos_weight = {scale_pos_weight:.2f} ({n_neg} neg / {n_pos} pos)")
    
    # TimeSeriesSplit — critical for time series, NOT regular k-fold
    tscv = TimeSeriesSplit(n_splits=5)
    
    best_params = None
    best_val_f1 = -1.0
    
    # Grid search (simplified — use optuna for production HPO)
    param_grid = [
        {'max_depth': d, 'learning_rate': lr, 'n_estimators': n}
        for d  in [3, 4, 5]
        for lr in [0.01, 0.05, 0.10]
        for n  in [100, 200, 300]
    ]
    
    logger.info(f"Running HPO over {len(param_grid)} parameter combinations...")
    
    for params in param_grid:
        fold_f1s = []
        
        for train_idx, val_idx in tscv.split(X_train):
            X_fold_train, X_fold_val = X_train.iloc[train_idx], X_train.iloc[val_idx]
            y_fold_train, y_fold_val = y_train.iloc[train_idx], y_train.iloc[val_idx]
            
            candidate = xgb.XGBClassifier(
                **params,
                scale_pos_weight=scale_pos_weight,
                eval_metric='logloss',
                use_label_encoder=False,
                random_state=42,
                verbosity=0
            )
            candidate.fit(
                X_fold_train, y_fold_train,
                eval_set=[(X_fold_val, y_fold_val)],
                verbose=False
            )
            
            y_pred = candidate.predict(X_fold_val)
            fold_f1s.append(f1_score(y_fold_val, y_pred, zero_division=0))
        
        mean_f1 = np.mean(fold_f1s)
        if mean_f1 > best_val_f1:
            best_val_f1 = mean_f1
            best_params = params
    
    logger.info(f"Best XGBoost params: {best_params} (val F1: {best_val_f1:.4f})")
    
    # Train final model on full training set with best params
    final_model = xgb.XGBClassifier(
        **best_params,
        scale_pos_weight=scale_pos_weight,
        eval_metric='logloss',
        use_label_encoder=False,
        random_state=42,
        verbosity=0
    )
    final_model.fit(X_train, y_train)
    
    logger.info("XGBoost final model trained")
    return final_model


def save_models(lr_model, xgb_model, threshold: float, feature_cols: list):
    """Save trained models and metadata to disk."""
    os.makedirs(MODEL_DIR, exist_ok=True)
    
    joblib.dump(lr_model,  f"{MODEL_DIR}logistic_regression_v1.pkl")
    joblib.dump(xgb_model, f"{MODEL_DIR}xgboost_v1.pkl")
    
    joblib.dump({
        'volatility_threshold': threshold,
        'feature_cols': feature_cols,
        'train_end': TRAIN_END,
        'test_start': TEST_START
    }, f"{MODEL_DIR}metadata_v1.pkl")
    
    logger.info(f"Models saved to {MODEL_DIR}")


def run_training_pipeline(features: pd.DataFrame, 
                           labels: pd.Series, 
                           threshold: float):
    """
    Full training pipeline.
    Call this from a notebook or script after building features.
    """
    X_train, X_test, y_train, y_test = split_data(features, labels)
    
    # Train both models
    lr_model  = train_logistic_regression(X_train, y_train)
    xgb_model = train_xgboost(X_train, y_train)
    
    # Save everything
    save_models(lr_model, xgb_model, threshold, FEATURE_COLS)
    
    return X_train, X_test, y_train, y_test, lr_model, xgb_model
```

---

## Step 4 — Evaluate Models (`ml_inference/evaluate.py`)

```python
# ml_inference/evaluate.py

import logging
import numpy as np
import pandas as pd
from sklearn.metrics import (
    classification_report,
    f1_score,
    roc_auc_score,
    confusion_matrix,
    RocCurveDisplay
)
import matplotlib.pyplot as plt
import seaborn as sns

logger = logging.getLogger(__name__)


def evaluate_model(model, X_test: pd.DataFrame, y_test: pd.Series, 
                   model_name: str) -> dict:
    """
    Full evaluation of a trained model on the OOS test set.
    Prints classification report and returns metrics dict.
    """
    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]
    
    f1     = f1_score(y_test, y_pred, zero_division=0)
    auc    = roc_auc_score(y_test, y_prob)
    cm     = confusion_matrix(y_test, y_pred)
    
    print(f"\n{'='*60}")
    print(f"MODEL: {model_name}")
    print(f"{'='*60}")
    print(f"Test period: 2023-01-01 to present")
    print(f"F1 Score (HIGH_VOL class): {f1:.4f}  (target: > 0.65)")
    print(f"ROC-AUC:                   {auc:.4f}  (target: > 0.70)")
    print(f"\nClassification Report:")
    print(classification_report(y_test, y_pred, 
                                 target_names=['NORMAL', 'HIGH_VOL']))
    
    print(f"\nConfusion Matrix:")
    print(f"                Pred NORMAL  Pred HIGH_VOL")
    print(f"Actual NORMAL   {cm[0,0]:>11d}  {cm[0,1]:>13d}  (FP = missed calm days)")
    print(f"Actual HIGH_VOL {cm[1,0]:>11d}  {cm[1,1]:>13d}  (FN = missed risk days)")
    
    # Baseline comparison: predict all NORMAL
    naive_f1 = f1_score(y_test, np.zeros(len(y_test)), zero_division=0)
    print(f"\nNaive baseline (always NORMAL) F1: {naive_f1:.4f}")
    print(f"Improvement over naive: +{(f1 - naive_f1):.4f} F1 points")
    
    passed = f1 >= 0.65 and auc >= 0.70
    print(f"\nTargets met: {'YES ✓' if passed else 'NO ✗'}")
    
    return {
        "model": model_name,
        "f1_high_vol": f1,
        "roc_auc": auc,
        "targets_met": passed,
        "confusion_matrix": cm.tolist()
    }


def plot_roc_curves(models: dict, X_test: pd.DataFrame, y_test: pd.Series):
    """Plot ROC curves for all models on the same axes."""
    fig, ax = plt.subplots(figsize=(8, 6))
    
    for name, model in models.items():
        y_prob = model.predict_proba(X_test)[:, 1]
        auc = roc_auc_score(y_test, y_prob)
        RocCurveDisplay.from_predictions(
            y_test, y_prob, 
            name=f"{name} (AUC={auc:.3f})", 
            ax=ax
        )
    
    ax.plot([0, 1], [0, 1], 'k--', label='Random (AUC=0.50)')
    ax.set_title("ROC Curves — OOS Test Set (2023–present)")
    ax.legend()
    ax.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig("docs/roc_curves.png", dpi=150)
    plt.show()


def plot_confusion_matrix(model, X_test, y_test, model_name: str):
    """Visualize confusion matrix as heatmap."""
    y_pred = model.predict(X_test)
    cm = confusion_matrix(y_test, y_pred)
    
    fig, ax = plt.subplots(figsize=(6, 5))
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues',
                xticklabels=['NORMAL', 'HIGH_VOL'],
                yticklabels=['NORMAL', 'HIGH_VOL'], ax=ax)
    ax.set_xlabel('Predicted')
    ax.set_ylabel('Actual')
    ax.set_title(f'Confusion Matrix — {model_name} (OOS Test)')
    plt.tight_layout()
    plt.savefig(f"docs/confusion_matrix_{model_name.lower().replace(' ', '_')}.png", dpi=150)
    plt.show()
```

---

## Step 5 — SHAP Explainability (`ml_inference/shap_explainer.py`)

```python
# ml_inference/shap_explainer.py

import shap
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

# Cache the explainer to avoid reloading for every prediction
_explainer = None


def get_explainer(xgb_model):
    """Lazy-load SHAP TreeExplainer (exact, fast for XGBoost)."""
    global _explainer
    if _explainer is None:
        logger.info("Initializing SHAP TreeExplainer...")
        _explainer = shap.TreeExplainer(xgb_model)
    return _explainer


def compute_shap_for_prediction(xgb_model,
                                  feature_row: pd.Series,
                                  feature_names: List[str]) -> List[Dict]:
    """
    Compute SHAP values for a single prediction row.
    Returns top 3 features by |SHAP value|.
    
    Args:
        xgb_model: trained XGBoost model
        feature_row: pd.Series with feature values (one row from feature matrix)
        feature_names: list of feature column names
    
    Returns:
        List of dicts: [{"feature", "shap_value", "feature_value"}]
    """
    explainer = get_explainer(xgb_model)
    
    X = feature_row.values.reshape(1, -1)
    shap_values = explainer.shap_values(X)[0]   # shape: (n_features,)
    
    # Sort by absolute SHAP value (descending)
    ranked = sorted(
        zip(feature_names, shap_values, feature_row.values),
        key=lambda x: abs(x[1]),
        reverse=True
    )
    
    top_3 = [
        {
            "feature": feat,
            "shap_value": round(float(shap_val), 4),
            "feature_value": round(float(feat_val), 6)
        }
        for feat, shap_val, feat_val in ranked[:3]
    ]
    
    return top_3


def plot_global_shap(xgb_model, X_test: pd.DataFrame, feature_names: List[str]):
    """
    Plot global SHAP feature importance (mean |SHAP| over test set).
    Shows which features are most important overall.
    """
    explainer = get_explainer(xgb_model)
    shap_values = explainer.shap_values(X_test.values)
    
    plt.figure(figsize=(10, 6))
    shap.summary_plot(
        shap_values,
        X_test,
        feature_names=feature_names,
        plot_type="bar",
        show=False
    )
    plt.title("Global SHAP Feature Importance (XGBoost)")
    plt.tight_layout()
    plt.savefig("docs/shap_global_importance.png", dpi=150, bbox_inches='tight')
    plt.show()
    logger.info("Global SHAP plot saved")


def plot_shap_beeswarm(xgb_model, X_test: pd.DataFrame, feature_names: List[str]):
    """
    Beeswarm plot showing direction and distribution of SHAP values.
    Red = high feature value pushes prediction toward HIGH_VOL.
    Blue = high feature value pushes prediction toward NORMAL.
    """
    explainer = get_explainer(xgb_model)
    shap_values = explainer.shap_values(X_test.values)
    
    plt.figure(figsize=(10, 7))
    shap.summary_plot(
        shap_values,
        X_test,
        feature_names=feature_names,
        show=False
    )
    plt.title("SHAP Value Distribution — XGBoost (OOS Test Set)")
    plt.tight_layout()
    plt.savefig("docs/shap_beeswarm.png", dpi=150, bbox_inches='tight')
    plt.show()
```

---

## Step 6 — Daily Inference Runner (`ml_inference/run_daily.py`)

```python
# ml_inference/run_daily.py

import os
import json
import joblib
import logging
import psycopg2
import redis as redis_lib
from datetime import date, datetime

from ml_inference.feature_engineering import (
    load_gpr_series, build_feature_matrix, 
    compute_returns_from_df
)
from ml_inference.market_data import fetch_market_data
from ml_inference.shap_explainer import compute_shap_for_prediction

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MODEL_DIR    = "models/"
FEATURE_COLS = [
    'india_ai_gpr_t1', 'india_ai_gpr_t3', 'india_ai_gpr_t7',
    'gpr_shock_flag', 'gpr_rolling_mean_7',
    'inr_usd_return', 'crude_oil_return',
    'nifty_return_t1', 'nifty_return_t5', 'nifty_vol_lag1'
]


def run_daily_inference(target_date: date = None):
    """
    Run daily ML inference for the given date.
    Triggered automatically after Module 2 (GPR index builder) completes.
    """
    if target_date is None:
        target_date = date.today()
    
    logger.info(f"=== Running ML inference for {target_date} ===")
    
    # Load trained model and metadata
    xgb_model = joblib.load(f"{MODEL_DIR}xgboost_v1.pkl")
    metadata   = joblib.load(f"{MODEL_DIR}metadata_v1.pkl")
    
    # Connect to data stores
    conn = psycopg2.connect(
        host=os.environ['POSTGRES_HOST'],
        dbname=os.environ['POSTGRES_DB'],
        user=os.environ['POSTGRES_USER'],
        password=os.environ['POSTGRES_PASSWORD']
    )
    r = redis_lib.Redis(
        host=os.environ['REDIS_HOST'],
        port=int(os.environ['REDIS_PORT']),
        decode_responses=True
    )
    
    # Load GPR and market data
    gpr_series = load_gpr_series(conn)
    market_df  = fetch_market_data(start_date="2009-01-01")   # Extra year for lags
    
    # Build feature matrix for today
    features = build_feature_matrix(gpr_series, market_df)
    
    if target_date not in features.index:
        logger.error(f"No features available for {target_date} — market holiday or data gap")
        return None
    
    feature_row = features.loc[target_date][FEATURE_COLS]
    
    if feature_row.isna().any():
        logger.warning(f"NaN features for {target_date}: {feature_row[feature_row.isna()].index.tolist()}")
        return None
    
    # Predict
    X = feature_row.values.reshape(1, -1)
    prob_high_vol = float(xgb_model.predict_proba(X)[0][1])
    regime = "HIGH_VOL" if prob_high_vol >= 0.5 else "NORMAL"
    
    # SHAP explanations
    top_drivers = compute_shap_for_prediction(
        xgb_model, feature_row, FEATURE_COLS
    )
    
    logger.info(
        f"Prediction: {regime} (prob_high_vol={prob_high_vol:.4f}) | "
        f"Top driver: {top_drivers[0]['feature']} (SHAP={top_drivers[0]['shap_value']})"
    )
    
    # Store in PostgreSQL
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO ml_predictions
            (prediction_date, regime, prob_high_vol, top_drivers, 
             model_version, features_snapshot)
        VALUES (%s, %s, %s, %s::jsonb, %s, %s::jsonb)
        ON CONFLICT (prediction_date) DO UPDATE SET
            regime             = EXCLUDED.regime,
            prob_high_vol      = EXCLUDED.prob_high_vol,
            top_drivers        = EXCLUDED.top_drivers,
            model_version      = EXCLUDED.model_version,
            features_snapshot  = EXCLUDED.features_snapshot,
            predicted_at       = now()
    """, (
        target_date,
        regime,
        prob_high_vol,
        json.dumps(top_drivers),
        "xgboost_v1",
        json.dumps(feature_row.to_dict())
    ))
    conn.commit()
    
    # Update Redis hot cache
    payload = json.dumps({
        "prediction_date": str(target_date),
        "regime": regime,
        "probability_high_vol": round(prob_high_vol, 4),
        "top_drivers": top_drivers,
        "model_version": "xgboost_v1",
        "predicted_at": datetime.utcnow().isoformat() + "Z"
    })
    r.set("volatility_signal:latest", payload, ex=86400)
    
    conn.close()
    r.close()
    
    return {"regime": regime, "prob_high_vol": prob_high_vol, "top_drivers": top_drivers}


if __name__ == "__main__":
    result = run_daily_inference()
    print(result)
```

---

## Step 7 — Train the Models (Run This Once)

```bash
# From project root, with Module 1 + 2 data already populated:
python -c "
import psycopg2, os
from ml_inference.market_data import fetch_market_data
from ml_inference.feature_engineering import (
    load_gpr_series, build_feature_matrix, build_target_variable
)
from ml_inference.train import run_training_pipeline
from ml_inference.evaluate import evaluate_model, plot_roc_curves

conn = psycopg2.connect(
    host=os.environ['POSTGRES_HOST'],
    dbname=os.environ['POSTGRES_DB'],
    user=os.environ['POSTGRES_USER'],
    password=os.environ['POSTGRES_PASSWORD']
)

# Load all data
market_df  = fetch_market_data(start_date='2009-01-01')
gpr_series = load_gpr_series(conn)

# Build features and labels
features          = build_feature_matrix(gpr_series, market_df)
labels, threshold = build_target_variable(market_df)

# Train
X_train, X_test, y_train, y_test, lr, xgb = run_training_pipeline(features, labels, threshold)

# Evaluate on OOS test set
lr_metrics  = evaluate_model(lr,  X_test, y_test, 'Logistic Regression')
xgb_metrics = evaluate_model(xgb, X_test, y_test, 'XGBoost')

# Plot
plot_roc_curves({'Logistic Regression': lr, 'XGBoost': xgb}, X_test, y_test)
"
```

---

## Verification Checklist

- [ ] Feature matrix has no NaN values in the post-2010 period
- [ ] `label` class balance is approximately 25% HIGH_VOL (verify with `labels.mean()`)
- [ ] XGBoost F1 (HIGH_VOL) on OOS test set ≥ 0.65
- [ ] XGBoost ROC-AUC on OOS test set ≥ 0.70
- [ ] XGBoost outperforms Logistic Regression by ≥ 2 F1 points (else LR may suffice)
- [ ] `top_drivers` response contains exactly 3 SHAP drivers with non-zero values
- [ ] Redis `volatility_signal:latest` key exists after daily inference runs
- [ ] `ml_predictions` table in PostgreSQL has a row for today
- [ ] SHAP global importance plot shows `nifty_vol_lag1` and `india_ai_gpr_t1` in top 3

---

## Common Errors & Fixes

| Error | Cause | Fix |
|---|---|---|
| `KeyError: feature not in index` | Feature matrix doesn't have data for target date | Check if that date's GPR and market data both exist |
| XGBoost F1 < 0.50 | Not enough historical GPR data (< 2 years) | Add more historical data via Module 2 backfill |
| `shap.TreeExplainer` slow | Computing for entire test set | Normal for first call; cached after that |
| `scale_pos_weight` warning | Class imbalance extreme | Expected; `scale_pos_weight` handles this correctly |
| Nifty data gaps > 1 day | Multi-day market holiday | These rows are dropped; check `features.isna().sum()` |
