"""Explanation contract shared across services ("Why this number").

Almost every headline number on this platform is a transparent additive formula
(portfolio exposure, corridor risk, joint stress, geo z-score). For an additive
model the exact term-by-term breakdown IS the Shapley decomposition — there is no
need for SHAP or LIME here (SHAP would only reproduce it; LIME would approximate
it worse). Real SHAP is reserved for the one black box, the XGBoost forward-vol
model — see nifty-50/forsyt_gpr/vol_model.py::shap_importance.

This module builds the small, JSON-friendly `explanation` dict the frontend's
ExplainPopover renders:

    {
      "output": float,
      "method": "additive" | "shap",
      "formula": str,
      "caveat": str | None,
      "terms": [{"label", "value", "weight", "contribution", "note"}]  # |contribution| desc
    }
"""

from __future__ import annotations


def term(label: str, value: float, weight: float, note: str | None = None) -> dict:
    """One additive term: contribution = value x weight."""
    v, w = float(value), float(weight)
    return {
        "label": label,
        "value": round(v, 3),
        "weight": round(w, 3),
        "contribution": round(v * w, 3),
        "note": note,
    }


def additive_explanation(
    output: float, terms: list[dict], formula: str, caveat: str | None = None
) -> dict:
    """Wrap terms into the explanation contract, sorted by |contribution|."""
    ordered = sorted(terms, key=lambda t: abs(t.get("contribution", 0.0)), reverse=True)
    return {
        "output": round(float(output), 2),
        "method": "additive",
        "formula": formula,
        "caveat": caveat,
        "terms": ordered,
    }


def demo() -> None:
    """Self-check: contributions are value x weight and sum to the stated output."""
    ts = [term("A", 10, 0.6), term("B", 20, 0.4)]  # 6 + 8 = 14
    assert ts[0]["contribution"] == 6.0 and ts[1]["contribution"] == 8.0, ts
    exp = additive_explanation(14.0, ts, "out = Σ value×weight")
    assert abs(sum(t["contribution"] for t in exp["terms"]) - exp["output"]) < 1e-9
    assert exp["terms"][0]["label"] == "B"  # sorted by |contribution| desc
    print("explain self-check OK")


if __name__ == "__main__":
    demo()
