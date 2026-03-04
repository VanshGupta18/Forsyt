"""
Out-of-sample evaluation: classification metrics, ROC curves, confusion matrix.
"""

import logging
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.metrics import (
    f1_score, roc_auc_score, precision_score, recall_score,
    confusion_matrix, RocCurveDisplay, ConfusionMatrixDisplay,
    classification_report,
)

logger = logging.getLogger(__name__)


def evaluate_model(model, X_test: pd.DataFrame, y_test: pd.Series,
                   model_name: str = "model") -> dict:
    """Return dict of OOS metrics."""
    y_pred  = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]

    metrics = {
        "model":     model_name,
        "f1":        float(f1_score(y_test, y_pred, zero_division=0)),
        "roc_auc":   float(roc_auc_score(y_test, y_proba)),
        "precision": float(precision_score(y_test, y_pred, zero_division=0)),
        "recall":    float(recall_score(y_test, y_pred, zero_division=0)),
        "n_test":    len(y_test),
        "positive_rate": float(y_test.mean()),
    }

    logger.info(
        f"{model_name} OOS | F1={metrics['f1']:.4f} | "
        f"ROC-AUC={metrics['roc_auc']:.4f} | "
        f"Precision={metrics['precision']:.4f} | "
        f"Recall={metrics['recall']:.4f}"
    )
    print(classification_report(y_test, y_pred,
          target_names=["LOW_VOL", "HIGH_VOL"], zero_division=0))
    return metrics


def plot_roc_curves(models: dict, X_test: pd.DataFrame,
                    y_test: pd.Series, save_path: str = "roc_curves.png"):
    """Plot and save ROC curves for all models."""
    fig, ax = plt.subplots(figsize=(7, 6))
    for name, model in models.items():
        RocCurveDisplay.from_estimator(model, X_test, y_test, ax=ax, name=name)
    ax.set_title("ROC Curves — OOS Test Set (2023–present)")
    ax.grid(True, alpha=0.3)
    fig.savefig(save_path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    logger.info(f"ROC curves saved to {save_path}")


def plot_confusion_matrix(model, X_test: pd.DataFrame, y_test: pd.Series,
                           model_name: str = "model",
                           save_path: str = "confusion_matrix.png"):
    """Plot and save confusion matrix."""
    y_pred = model.predict(X_test)
    cm = confusion_matrix(y_test, y_pred)
    disp = ConfusionMatrixDisplay(cm, display_labels=["LOW_VOL", "HIGH_VOL"])
    fig, ax = plt.subplots(figsize=(5, 4))
    disp.plot(ax=ax, cmap="Blues", colorbar=False)
    ax.set_title(f"Confusion Matrix — {model_name}")
    fig.savefig(save_path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    logger.info(f"Confusion matrix saved to {save_path}")
