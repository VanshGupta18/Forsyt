"""
Daily ML inference runner.
Loads saved XGBoost model, builds today's feature vector,
predicts volatility signal, computes SHAP drivers,
and writes output to PostgreSQL and Redis.
"""

import os
import json
import joblib
import logging
import datetime
import psycopg2
import redis

from ml_inference.feature_engineering import (
    FEATURE_COLS, build_feature_matrix, load_gpr_series,
)
from ml_inference.market_data import fetch_market_data
from ml_inference.shap_explainer import compute_shap_for_prediction

logger = logging.getLogger(__name__)

MODEL_DIR  = "models/"
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
PG_DSN     = os.getenv("PG_DSN", "postgresql://india_ai:secret@localhost:5432/india_ai_gpr")
SIGNAL_TTL = 86400  # 24 hours


def run_daily_inference(target_date: datetime.date = None) -> dict:
    if target_date is None:
        target_date = datetime.date.today()

    logger.info(f"--- ML Inference for {target_date} ---")

    # 1. Load model + metadata
    xgb_model = joblib.load(f"{MODEL_DIR}xgboost_v1.pkl")
    meta       = joblib.load(f"{MODEL_DIR}metadata_v1.pkl")

    # 2. Fetch market data and GPR series (end = target_date + 1 to include today)
    conn = psycopg2.connect(PG_DSN)
    market_df  = fetch_market_data(start_date="2010-01-01",
                                   end_date=(target_date + datetime.timedelta(days=1)).isoformat())
    gpr_series = load_gpr_series(conn)

    # 3. Build full feature matrix, grab today's row
    features = build_feature_matrix(gpr_series, market_df)
    today_ts = datetime.datetime.combine(target_date, datetime.time())

    if today_ts not in features.index:
        logger.warning(f"Feature row for {target_date} not available — skipping inference")
        conn.close()
        return {}

    feature_row = features.loc[[today_ts]][FEATURE_COLS].dropna()
    if feature_row.empty:
        logger.warning(f"Feature row for {target_date} has NaN values — skipping inference")
        conn.close()
        return {}

    # 4. Predict
    prob   = float(xgb_model.predict_proba(feature_row)[0][1])
    label  = int(xgb_model.predict(feature_row)[0])
    signal = "HIGH_VOL" if label == 1 else "LOW_VOL"

    # 5. SHAP top-3 drivers
    raw_drivers = compute_shap_for_prediction(xgb_model, feature_row)
    drivers = [{"feature": f, "shap_value": round(v, 6)} for f, v in raw_drivers]

    # 6. Persist to PostgreSQL
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO ml_predictions
                (prediction_date, model_version, signal, high_vol_probability,
                 top_features, feature_values, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (prediction_date, model_version)
            DO UPDATE SET
                signal               = EXCLUDED.signal,
                high_vol_probability = EXCLUDED.high_vol_probability,
                top_features         = EXCLUDED.top_features,
                feature_values       = EXCLUDED.feature_values,
                created_at           = NOW()
        """, (
            target_date, "xgboost_v1", signal, prob,
            json.dumps(drivers),
            json.dumps(feature_row.iloc[0].to_dict()),
        ))
    conn.commit()
    conn.close()

    # 7. Write to Redis
    r = redis.Redis(host=REDIS_HOST, port=6379, decode_responses=True)
    payload = {
        "signal": signal, "high_vol_probability": round(prob, 4),
        "model_version": "xgboost_v1",
        "top_drivers": drivers,
        "inference_date": target_date.isoformat(),
    }
    r.set("volatility_signal:latest", json.dumps(payload), ex=SIGNAL_TTL)
    r.close()

    logger.info(
        f"ML Inference complete: {signal} | prob={prob:.4f} | "
        f"top driver={drivers[0]['feature'] if drivers else 'N/A'}"
    )
    return payload


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    d = datetime.date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else None
    run_daily_inference(d)
