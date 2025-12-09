from datetime import date
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class Frequency(str, Enum):
    once = "once"
    weekly = "weekly"
    monthly = "monthly"


class SummaryFreq(str, Enum):
    daily = "daily"
    weekly = "weekly"
    monthly = "monthly"


class WalletPayload(BaseModel):
    id: str
    name: str
    initial_balance: float
    reference_date: date


class WalletCreatePayload(BaseModel):
    name: str
    initial_balance: float
    reference_date: date


class WalletUpdatePayload(BaseModel):
    name: Optional[str] = None
    initial_balance: Optional[float] = None
    reference_date: Optional[date] = None


class ScenarioMeta(BaseModel):
    name: str
    parent: Optional[str] = None


class CashFlowSpecPayload(BaseModel):
    id: str
    concept: str
    amount: float
    frequency: Frequency
    start_date: date
    end_date: Optional[date] = None
    metadata: dict = Field(default_factory=dict)


class ComparisonRequest(BaseModel):
    base: str
    variant: str
    start_date: date
    end_date: date
    freq: SummaryFreq = SummaryFreq.weekly


class ComparisonEventRow(BaseModel):
    date: date
    concept: str
    income_base: float
    expenses_base: float
    income_variant: float
    expenses_variant: float
    income_delta: float
    expenses_delta: float


class ComparisonSummaryRow(BaseModel):
    date: date
    income_base: float
    expenses_base: float
    net_base: float
    balance_base: float
    income_variant: float
    expenses_variant: float
    net_variant: float
    balance_variant: float
    income_delta: float
    expenses_delta: float
    net_delta: float
    balance_delta: float


class ComparisonResponse(BaseModel):
    base: str
    variant: str
    events: List[ComparisonEventRow]
    summary: List[ComparisonSummaryRow]


class BalanceResponse(BaseModel):
    as_of: date
    balance: float


class AlertsResponse(BaseModel):
    alerts: List["AlertPayload"]


class AlertSeverity(str, Enum):
    success = "success"
    warning = "warning"
    danger = "danger"


class AlertPayload(BaseModel):
    id: str
    title: str
    message: str
    severity: AlertSeverity
    date: Optional[str] = None


AlertsResponse.update_forward_refs()


class OptimizeStageCfg(BaseModel):
    kind: str
    name: str
    params: Dict[str, Any] = Field(default_factory=dict)


class OptimizeRequest(BaseModel):
    stage_cfgs: List[OptimizeStageCfg]
    search_space: Dict[str, Any]
    sampler: str = "grid"
    max_iters: Optional[int] = None
    max_time: Optional[float] = None
    seed: Optional[int] = None
    objective: str = "total_return"
    early_stop: Optional[int] = None


class TrialPayload(BaseModel):
    trial_id: int
    params: Dict[str, Any]
    metrics: Dict[str, Any]


class OptimizeResponse(BaseModel):
    best_params: Optional[Dict[str, Any]]
    best_metrics: Optional[Dict[str, Any]]
    trials: List[TrialPayload]


class EvaluateRequest(BaseModel):
    stage_cfgs: List[OptimizeStageCfg]
    split_params: Optional[Dict[str, Any]] = None
    include_data: bool = False
    ticker: str = "BTCUSDT"
    freq: str = "1h"
    start: Optional[str] = None
    end: Optional[str] = None


class EvaluatePayload(BaseModel):
    dataset: str
    metrics: Optional[Dict[str, Any]] = None
    data: Optional[List[Dict[str, Any]]] = None


class EvaluateResponse(BaseModel):
    results: List[EvaluatePayload]


class MarketDataInfo(BaseModel):
    ticker: str
    freq: str
    path: str
    min_time: Optional[str]
    max_time: Optional[str]
    rows: int


class MarketDataList(BaseModel):
    items: List[MarketDataInfo]
