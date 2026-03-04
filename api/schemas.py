"""
Pydantic v2 response schemas for all API endpoints.
"""

from __future__ import annotations
from typing import List, Optional
from datetime import date, datetime
from pydantic import BaseModel, Field


class GPRPoint(BaseModel):
    date:          date
    raw_gpr:       Optional[float] = None
    normalized_gpr: Optional[float] = None
    data_quality_flag: Optional[str] = None
    event_count:   int = 0


class GPRLatestResponse(BaseModel):
    date:            date
    normalized_gpr:  float
    raw_gpr:         Optional[float] = None
    data_quality_flag: Optional[str] = None
    source:          str = Field(default="redis", description="'redis' or 'postgres'")
    updated_at:      Optional[datetime] = None


class GPRHistoryResponse(BaseModel):
    from_date: date
    to_date:   date
    count:     int
    series:    List[GPRPoint]


class ShapDriver(BaseModel):
    feature:    str
    shap_value: float


class VolatilitySignalResponse(BaseModel):
    signal:               str  # "HIGH_VOL" | "LOW_VOL"
    high_vol_probability: float
    model_version:        str
    inference_date:       date
    top_drivers:          List[ShapDriver]
    source:               str = "redis"


class EventInDB(BaseModel):
    event_id:        int
    article_id:      str
    event_type:      str
    severity:        float
    india_exposure:  float
    confidence:      float
    event_date:      Optional[date]
    raw_text:        Optional[str] = None
    created_at:      Optional[datetime] = None


class EventsResponse(BaseModel):
    query_date: Optional[date]
    count:      int
    events:     List[EventInDB]


class HealthResponse(BaseModel):
    status:         str  # "ok" | "degraded"
    postgres:       str
    redis:          str
    latest_gpr_date: Optional[date] = None
    latest_signal_date: Optional[date] = None


class ErrorResponse(BaseModel):
    detail:    str
    error_code: Optional[str] = None


# Corridor risk
class CorridorRiskResponse(BaseModel):
    country:          str
    iso:              str
    gpr:              float
    sanctions:        bool
    sanctions_type:   str
    trade_volume_bn:  float
    trade_rank:       int
    primary_exports:  List[str]
    primary_imports:  List[str]
    risk_level:       str   # "HIGH" | "MEDIUM" | "LOW"
    risk_drivers:     List[str]
    sectors_exposed:  List[str]
    corridor_note:    str


# Portfolio analyser
class Holding(BaseModel):
    ticker: str
    weight: float = Field(..., gt=0.0, le=1.0)


class SectorExposure(BaseModel):
    sector:         str
    total_weight:   float
    gpr_beta:       Optional[float] = None
    risk_contribution: Optional[float] = None


class PortfolioAnalyseResponse(BaseModel):
    portfolio_gpr_score:  float
    signal:               str
    high_vol_probability: Optional[float] = None
    sector_breakdown:     List[SectorExposure]
    unrecognised_tickers: List[str]
    gpr_date:             Optional[date] = None
