# NIFTY-50 Research (Internal QA)

Academic validation scripts — **not part of the product surface**.

Run from the `nifty-50/` directory:

```bash
cd nifty-50
python research/run_application.py
python research/analysis/02_india_nifty.py
python research/analysis/03_backtest.py
```

Product API and dashboard use `forsyt_gpr/dual_signal.py` with `market_only` NIFTY vol.
See [`docs/PRODUCT.md`](../../docs/PRODUCT.md) for the shippable product definition.
