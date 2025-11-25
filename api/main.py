from datetime import date, timedelta
from typing import Iterable, List, Optional

import polars as pl
from fastapi import Body, Depends, FastAPI, HTTPException, Path, Query
from fastapi.middleware.cors import CORSMiddleware

from main import CashFlowSpec, ScenarioService, WalletConfig, WalletManager
from .dependencies import get_manager
from .schemas import (
    AlertPayload,
    AlertSeverity,
    AlertsResponse,
    BalanceResponse,
    CashFlowSpecPayload,
    ComparisonEventRow,
    ComparisonRequest,
    ComparisonResponse,
    ComparisonSummaryRow,
    ScenarioMeta,
    SummaryFreq,
    WalletCreatePayload,
    WalletPayload,
    WalletUpdatePayload,
)

app = FastAPI(title="Wallet API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _spec_from_payload(payload: CashFlowSpecPayload) -> CashFlowSpec:
    return CashFlowSpec(
        id=payload.id,
        concept=payload.concept,
        amount=payload.amount,
        frequency=payload.frequency.value,
        start_date=payload.start_date,
        end_date=payload.end_date,
        metadata=payload.metadata,
    )


def _spec_to_payload(spec: CashFlowSpec) -> CashFlowSpecPayload:
    return CashFlowSpecPayload(
        id=spec.id,
        concept=spec.concept,
        amount=spec.amount,
        frequency=spec.frequency,
        start_date=spec.start_date,
        end_date=spec.end_date,
        metadata=spec.metadata,
    )


def _wallet_payload(config: WalletConfig) -> WalletPayload:
    return WalletPayload(
        id=config.id,
        name=config.name,
        initial_balance=config.initial_balance,
        reference_date=config.reference_date,
    )


def _service_for(manager: WalletManager, wallet_id: str) -> ScenarioService:
    try:
        return manager.service(wallet_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="wallet not found")


def _comparison_events_payload(
    df: pl.DataFrame,
    base_name: str,
    variant_name: str,
) -> List[ComparisonEventRow]:
    base_income = f"income_{base_name}"
    base_expenses = f"expenses_{base_name}"
    variant_income = f"income_{variant_name}"
    variant_expenses = f"expenses_{variant_name}"
    rows = []
    for row in df.to_dicts():
        date_value = row.get("date")
        if date_value is None:
            continue
        rows.append(
            ComparisonEventRow(
                date=date_value,
                concept=str(row.get("concept") or ""),
                income_base=float(row.get(base_income, 0.0)),
                expenses_base=float(row.get(base_expenses, 0.0)),
                income_variant=float(row.get(variant_income, 0.0)),
                expenses_variant=float(row.get(variant_expenses, 0.0)),
                income_delta=float(row.get("income_delta", 0.0)),
                expenses_delta=float(row.get("expenses_delta", 0.0)),
            )
        )
    return rows


def _comparison_summary_payload(
    df: pl.DataFrame,
    base_name: str,
    variant_name: str,
) -> List[ComparisonSummaryRow]:
    rows = []
    base_income = f"income_{base_name}"
    base_expenses = f"expenses_{base_name}"
    base_net = f"net_{base_name}"
    base_balance = f"balance_{base_name}"
    variant_income = f"income_{variant_name}"
    variant_expenses = f"expenses_{variant_name}"
    variant_net = f"net_{variant_name}"
    variant_balance = f"balance_{variant_name}"
    for row in df.to_dicts():
        rows.append(
            ComparisonSummaryRow(
                date=row["date"],
                income_base=float(row.get(base_income, 0.0)),
                expenses_base=float(row.get(base_expenses, 0.0)),
                net_base=float(row.get(base_net, 0.0)),
                balance_base=float(row.get(base_balance, 0.0)),
                income_variant=float(row.get(variant_income, 0.0)),
                expenses_variant=float(row.get(variant_expenses, 0.0)),
                net_variant=float(row.get(variant_net, 0.0)),
                balance_variant=float(row.get(variant_balance, 0.0)),
                income_delta=float(row.get("income_delta", 0.0)),
                expenses_delta=float(row.get("expenses_delta", 0.0)),
                net_delta=float(row.get("net_delta", 0.0)),
                balance_delta=float(row.get("balance_delta", 0.0)),
            )
        )
    return rows


def _assert_scenario(service: ScenarioService, name: str) -> None:
    if name not in service.scenarios:
        raise HTTPException(status_code=404, detail="scenario not found")


@app.get("/wallets", response_model=List[WalletPayload])
def wallets(manager: WalletManager = Depends(get_manager)) -> List[WalletPayload]:
    return [_wallet_payload(config) for config in manager.list_wallets()]


@app.post("/wallets", response_model=WalletPayload)
def create_wallet(
    payload: WalletCreatePayload = Body(...),
    manager: WalletManager = Depends(get_manager),
) -> WalletPayload:
    config = manager.create_wallet(
        name=payload.name,
        initial_balance=payload.initial_balance,
        reference_date=payload.reference_date,
    )
    return _wallet_payload(config)


@app.put("/wallets/{wallet_id}", response_model=WalletPayload)
def update_wallet(
    wallet_id: str,
    payload: WalletUpdatePayload = Body(...),
    manager: WalletManager = Depends(get_manager),
) -> WalletPayload:
    try:
        config = manager.update_wallet(
            wallet_id=wallet_id,
            name=payload.name,
            initial_balance=payload.initial_balance,
            reference_date=payload.reference_date,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="wallet not found")
    return _wallet_payload(config)


@app.delete("/wallets/{wallet_id}")
def delete_wallet(
    wallet_id: str,
    manager: WalletManager = Depends(get_manager),
) -> dict:
    try:
        manager.delete_wallet(wallet_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="wallet not found")
    return {"status": "ok"}


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/scenarios", response_model=List[ScenarioMeta])
def scenarios(
    wallet_id: str = Query("default"),
    manager: WalletManager = Depends(get_manager),
) -> List[ScenarioMeta]:
    service = _service_for(manager, wallet_id)
    return [
        ScenarioMeta(name=name, parent=scenario.parent)
        for name, scenario in service.scenarios.items()
    ]


@app.get("/scenarios/compare", response_model=ComparisonResponse)
def compare(
    base: str = Query(...),
    variant: str = Query(...),
    start_date: date = Query(...),
    end_date: date = Query(...),
    freq: SummaryFreq = Query(SummaryFreq.weekly),
    wallet_id: str = Query("default"),
    manager: WalletManager = Depends(get_manager),
) -> ComparisonResponse:
    service = _service_for(manager, wallet_id)
    _assert_scenario(service, base)
    _assert_scenario(service, variant)
    result = service.compare(
        base=base,
        variant=variant,
        start_date=start_date,
        end_date=end_date,
        freq=freq.value,
    )
    events = _comparison_events_payload(
        df=result.events,
        base_name=base,
        variant_name=variant,
    )
    summary = _comparison_summary_payload(
        df=result.summary,
        base_name=base,
        variant_name=variant,
    )
    return ComparisonResponse(
        base=base,
        variant=variant,
        events=events,
        summary=summary,
    )


@app.get("/balance", response_model=BalanceResponse)
def balance(
    as_of: date = Query(...),
    scenario: str = Query("baseline"),
    wallet_id: str = Query("default"),
    manager: WalletManager = Depends(get_manager),
) -> BalanceResponse:
    service = _service_for(manager, wallet_id)
    _assert_scenario(service, scenario)
    wallet = service.wallet_for(name=scenario)
    value = wallet.expected_balance(as_of=as_of)
    return BalanceResponse(as_of=as_of, balance=value)


@app.get("/events", response_model=List[CashFlowSpecPayload])
def list_events(
    wallet_id: str = Query("default"),
    manager: WalletManager = Depends(get_manager),
) -> List[CashFlowSpecPayload]:
    service = _service_for(manager, wallet_id)
    return [
        _spec_to_payload(spec)
        for spec in service.repo.specs()
    ]


@app.post("/events", response_model=List[CashFlowSpecPayload])
def create_event(
    payload: CashFlowSpecPayload = Body(...),
    wallet_id: str = Query("default"),
    manager: WalletManager = Depends(get_manager),
) -> List[CashFlowSpecPayload]:
    service = _service_for(manager, wallet_id)
    service.add_event(spec=_spec_from_payload(payload))
    return list_events(wallet_id=wallet_id, manager=manager)


@app.put("/events/{event_id}", response_model=List[CashFlowSpecPayload])
def update_event(
    event_id: str = Path(...),
    payload: CashFlowSpecPayload = Body(...),
    wallet_id: str = Query("default"),
    manager: WalletManager = Depends(get_manager),
) -> List[CashFlowSpecPayload]:
    service = _service_for(manager, wallet_id)
    if payload.id != event_id:
        raise HTTPException(status_code=400, detail="id mismatch")
    service.add_event(spec=_spec_from_payload(payload))
    return list_events(wallet_id=wallet_id, manager=manager)


@app.delete("/events/{event_id}", response_model=List[CashFlowSpecPayload])
def delete_event(
    event_id: str = Path(...),
    wallet_id: str = Query("default"),
    manager: WalletManager = Depends(get_manager),
) -> List[CashFlowSpecPayload]:
    service = _service_for(manager, wallet_id)
    service.remove_event(event_id=event_id)
    return list_events(wallet_id=wallet_id, manager=manager)


def _default_scenario(service: ScenarioService) -> str:
    if "baseline" in service.scenarios:
        return "baseline"
    return next(iter(service.scenarios.keys()))


def _alerts_for(
    service: ScenarioService,
    scenario: str,
    start_date: date,
    end_date: date,
) -> List[AlertPayload]:
    wallet = service.wallet_for(name=scenario)
    summary = wallet.summary_report(
        start_date=start_date,
        end_date=end_date,
        freq="daily",
    )
    events = wallet.events_report(start_date=start_date, end_date=end_date)
    alerts: List[AlertPayload] = []
    alerts.extend(
        _low_balance_alerts(summary=summary),
    )
    alerts.extend(
        _upcoming_expense_alerts(
            events=events,
            start_date=start_date,
        )
    )
    alerts.extend(_expense_ratio_alerts(summary=summary))
    return alerts


def _low_balance_alerts(summary: pl.DataFrame) -> Iterable[AlertPayload]:
    if summary.is_empty():
        return []
    min_balance = summary.select(pl.col("balance").min()).item()
    if min_balance >= 0:
        return []
    date_value = (
        summary.sort("balance")
        .select("date")
        .head(1)
        .to_series()
        .item()
    )
    date_str = date_value.isoformat() if date_value else None
    return [
        AlertPayload(
            id="projected_low_balance",
            title="Saldo proyectado negativo",
            message=f"Saldo estimado {min_balance:.2f}",
            severity=AlertSeverity.danger,
            date=date_str,
        )
    ]


def _upcoming_expense_alerts(
    events: pl.DataFrame,
    start_date: date,
) -> Iterable[AlertPayload]:
    if events.is_empty():
        return []
    window_end = start_date + timedelta(days=7)
    upcoming = (
        events
        .filter(pl.col("date") <= window_end)
        .filter(pl.col("expenses") > 0)
        .sort("date")
        .limit(1)
    )
    if upcoming.is_empty():
        return []
    row = upcoming.to_dicts()[0]
    date_value = row["date"]
    date_str = date_value.isoformat() if date_value else None
    return [
        AlertPayload(
            id="upcoming_expense",
            title="Gasto próximo",
            message=f"{row['concept']} el {row['date']}",
            severity=AlertSeverity.warning,
            date=date_str,
        )
    ]


def _expense_ratio_alerts(summary: pl.DataFrame) -> Iterable[AlertPayload]:
    if summary.is_empty():
        return []
    totals = summary.select(
        [
            pl.col("income").sum().alias("income"),
            pl.col("expenses").sum().alias("expenses"),
        ]
    ).to_dicts()[0]
    income = totals.get("income", 0.0)
    expenses = totals.get("expenses", 0.0)
    if income <= 0:
        return []
    ratio = expenses / income
    if ratio < 0.8:
        return []
    return [
        AlertPayload(
            id="high_expense_ratio",
            title="Gasto elevado",
            message=f"Relación gasto/ingreso {ratio:.2f}",
            severity=AlertSeverity.warning,
        )
    ]


@app.get("/alerts", response_model=AlertsResponse)
def alerts(
    start_date: date = Query(...),
    end_date: date = Query(...),
    scenario: Optional[str] = Query(None),
    wallet_id: str = Query("default"),
    manager: WalletManager = Depends(get_manager),
) -> AlertsResponse:
    service = _service_for(manager, wallet_id)
    selected = scenario or _default_scenario(service)
    _assert_scenario(service, selected)
    payload = _alerts_for(
        service=service,
        scenario=selected,
        start_date=start_date,
        end_date=end_date,
    )
    return AlertsResponse(alerts=payload)
