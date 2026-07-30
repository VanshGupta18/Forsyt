"""Forsyt GPR modelling package.

Implements the application note (application.md) against any geopolitical-risk
index that conforms to the canonical GPR frame in `data.as_gpr_frame`.

  data       -- loaders + the pluggable GPR-frame contract
  features   -- MD 1: GPRT/GPRA/benchmark features, market baseline block
  vol_model  -- MD 2: XGBoost forward-volatility model, purged walk-forward
  macro_var  -- MD A: VAR -> investment & employment impulse responses
  downside   -- MD A: quantile regression -> downside/disaster risk
"""
from . import data, features, vol_model, macro_var, downside  # noqa: F401

__all__ = ["data", "features", "vol_model", "macro_var", "downside"]
