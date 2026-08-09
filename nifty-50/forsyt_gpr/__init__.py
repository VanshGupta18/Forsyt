"""Forsyt GPR modelling package.

Product surface:
  data         -- loaders + the pluggable GPR-frame contract
  dual_signal  -- geo + market_only NIFTY vol + joint stress (product API)
  features     -- GPRT/GPRA/benchmark features, market baseline block
  vol_model    -- XGBoost forward-volatility model (market_only in product)

Research modules (VAR, quantile regression) live in ../research/.
"""
from . import data, dual_signal, features, vol_model  # noqa: F401

__all__ = ["data", "dual_signal", "features", "vol_model"]
