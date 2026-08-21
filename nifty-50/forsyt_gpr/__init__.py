"""Forsyt GPR modelling package.

Product surface:
  data         -- loaders + the pluggable GPR-frame contract
  dual_signal  -- geo + market_only NIFTY vol + joint stress (product API)
  features     -- GPRT/GPRA/benchmark features, market baseline block
  vol_model    -- XGBoost forward-volatility model (market_only in product)

Note: earlier revisions of this package also had VAR and quantile-regression
research modules under `../research/`; that directory was removed in commit
`eff8091` (2026-08-13) and no longer exists. `vol_model.run_vol_experiment()`
is the current research/backtesting entry point -- see `forsyt_gpr/README.md`.
"""
from . import data, dual_signal, features, vol_model  # noqa: F401

__all__ = ["data", "dual_signal", "features", "vol_model"]
