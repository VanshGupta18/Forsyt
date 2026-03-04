"""
SHAP explanations using TreeExplainer (exact, fast for XGBoost).
Returns top-3 feature drivers per prediction for API consumption.
"""

import shap
import joblib
import logging
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from typing import List, Tuple
import xgboost as xgb

logger = logging.getLogger(__name__)

# Module-level cache so explainer is built only once per process
_explainer: shap.TreeExplainer = None


def get_explainer(model: xgb.XGBClassifier) -> shap.TreeExplainer:
    """Return cached TreeExplainer, building it once."""
    global _explainer
    if _explainer is None:
        logger.info("Building TreeExplainer (one-time, ~2 s)")
        _explainer = shap.TreeExplainer(model)
    return _explainer


def compute_shap_for_prediction(
    model, feature_row: pd.DataFrame
) -> List[Tuple[str, float]]:
    """
    Compute SHAP values for a single prediction row.
    Returns top-3 (feature_name, shap_value) tuples sorted by |shap| descending.
    """
    explainer = get_explainer(model)
    shap_values = explainer.shap_values(feature_row)  # shape (1, n_features)

    if isinstance(shap_values, list):
        # Binary XGBoost returns list [class_0, class_1]
        shap_arr = shap_values[1][0]
    else:
        shap_arr = shap_values[0]

    feature_names = list(feature_row.columns)
    pairs = sorted(zip(feature_names, shap_arr.tolist()),
                   key=lambda x: abs(x[1]), reverse=True)
    top3 = pairs[:3]
    logger.debug(f"Top SHAP drivers: {top3}")
    return top3


def plot_global_shap(model, X_test: pd.DataFrame,
                     save_path: str = "shap_summary.png"):
    """Bar plot of mean absolute SHAP values across test set."""
    explainer = get_explainer(model)
    shap_values = explainer.shap_values(X_test)
    if isinstance(shap_values, list):
        shap_arr = shap_values[1]
    else:
        shap_arr = shap_values

    mean_abs = np.abs(shap_arr).mean(axis=0)
    feat     = list(X_test.columns)
    order    = np.argsort(mean_abs)[::-1]

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.barh([feat[i] for i in order][::-1],
            [mean_abs[i] for i in order][::-1], color="#1f77b4")
    ax.set_xlabel("Mean |SHAP value|")
    ax.set_title("Global Feature Importance (XGBoost + SHAP)")
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    fig.savefig(save_path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    logger.info(f"Global SHAP plot saved to {save_path}")


def plot_shap_beeswarm(model, X_test: pd.DataFrame,
                       save_path: str = "shap_beeswarm.png"):
    """Beeswarm plot showing direction + magnitude of feature impacts."""
    explainer = get_explainer(model)
    shap_values = explainer.shap_values(X_test)
    explanation = shap.Explanation(
        values      = shap_values[1] if isinstance(shap_values, list) else shap_values,
        base_values = explainer.expected_value[1] if isinstance(explainer.expected_value, list)
                      else explainer.expected_value,
        data        = X_test.values,
        feature_names = list(X_test.columns),
    )
    fig, ax = plt.subplots(figsize=(9, 6))
    shap.plots.beeswarm(explanation, max_display=10, show=False)
    plt.tight_layout()
    plt.savefig(save_path, dpi=120, bbox_inches="tight")
    plt.close()
    logger.info(f"Beeswarm plot saved to {save_path}")
