from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime


class AIObservationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    business_id: str
    observation_type: str  # peak_hour, fast_mover, anomaly, stock_prediction, customer_churn, pattern
    title: str
    description: str
    confidence: float  # 0.0 to 1.0
    data: Optional[dict] = None  # Flexible payload
    is_dismissed: bool = False
    created_at: datetime


class AIObservationListResponse(BaseModel):
    items: List[AIObservationResponse]
    total: int


class PeakHoursResponse(BaseModel):
    peak_hours: List[dict]  # [{hour: 12, day: "Monday", avg_sales: 5}]


class FastMoversResponse(BaseModel):
    items: List[dict]  # [{product_id, product_name, velocity, reorder_day}]


class AnomalyResponse(BaseModel):
    anomalies: List[dict]  # [{type, severity, description, date, value}]


class InsightResponse(BaseModel):
    id: str
    type: str
    title: str
    body: str
    confidence: float
    icon: str  # insight type icon name
    action_label: Optional[str] = None
    action_url: Optional[str] = None
    dismissed: bool = False
    created_at: datetime
