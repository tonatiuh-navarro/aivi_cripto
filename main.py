import datetime as dt
import json
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import polars as pl


def _empty_events_df() -> pl.DataFrame:
    return pl.DataFrame(
        schema={
            "date": pl.Date,
            "amount": pl.Float64,
            "concept": pl.Utf8,
        }
    )


class CashFlow(ABC):
    def __init__(self, name: str, amount: float) -> None:
        # amount > 0 = ingreso, amount < 0 = gasto
        self.name = name
        self.amount = amount

    @abstractmethod
    def generate_df(
        self,
        start_date: dt.date,
        end_date: dt.date,
    ) -> pl.DataFrame:
        """
        Regresa un DataFrame con columnas:
        - date (pl.Date)
        - amount (float, +ingreso, -gasto)
        - concept (str)
        """
        ...


class OneTimeCashFlow(CashFlow):
    def __init__(self, name: str, amount: float, date: dt.date) -> None:
        super().__init__(name, amount)
        self.date = date

    def generate_df(
        self,
        start_date: dt.date,
        end_date: dt.date,
    ) -> pl.DataFrame:
        in_range = start_date <= self.date <= end_date
        if not in_range:
            return _empty_events_df()

        return pl.DataFrame(
            {
                "date": [self.date],
                "amount": [self.amount],
                "concept": [self.name],
            }
        )


class WeeklyCashFlow(CashFlow):
    def __init__(
        self,
        name: str,
        amount: float,
        first_date: dt.date,
        end_date: Optional[dt.date] = None,
    ) -> None:
        """
        first_date: primera fecha en la que se aplica
        end_date: última fecha opcional en la que aplica
        """
        super().__init__(name, amount)
        self.first_date = first_date
        self.end_date = end_date

    def generate_df(
        self,
        start_date: dt.date,
        end_date: dt.date,
    ) -> pl.DataFrame:
        limit_end = end_date
        if self.end_date is not None and self.end_date < limit_end:
            limit_end = self.end_date

        if self.first_date > limit_end:
            return _empty_events_df()

        date_series = pl.date_range(
            start=self.first_date,
            end=limit_end,
            interval="1w",
            closed="both",
            eager=True,
        )

        df = (
            date_series.to_frame("date")
            .filter(pl.col("date") >= start_date)
            .with_columns(
                [
                    pl.lit(self.amount).alias("amount"),
                    pl.lit(self.name).alias("concept"),
                ]
            )
        )
        return df


class MonthlyCashFlow(CashFlow):
    def __init__(
        self,
        name: str,
        amount: float,
        first_date: dt.date,
        end_date: Optional[dt.date] = None,
    ) -> None:
        """
        first_date: primera fecha en la que se aplica (p. ej. renta el 10)
        """
        super().__init__(name, amount)
        self.first_date = first_date
        self.end_date = end_date

    def generate_df(
        self,
        start_date: dt.date,
        end_date: dt.date,
    ) -> pl.DataFrame:
        limit_end = end_date
        if self.end_date is not None and self.end_date < limit_end:
            limit_end = self.end_date

        if self.first_date > limit_end:
            return _empty_events_df()

        date_series = pl.date_range(
            start=self.first_date,
            end=limit_end,
            interval="1mo",
            closed="both",
            eager=True,
        )

        df = (
            date_series.to_frame("date")
            .filter(pl.col("date") >= start_date)
            .with_columns(
                [
                    pl.lit(self.amount).alias("amount"),
                    pl.lit(self.name).alias("concept"),
                ]
            )
        )
        return df


class Wallet:
    def __init__(
        self,
        initial_balance: float = 0.0,
        reference_date: Optional[dt.date] = None,
        cash_flows: Optional[List[CashFlow]] = None,
    ) -> None:
        """
        reference_date: fecha a la que corresponde el saldo inicial.
        Si no se pasa, se usa la fecha de hoy.
        """
        self.initial_balance = initial_balance
        self.reference_date = reference_date or dt.date.today()
        self.cash_flows: List[CashFlow] = list(cash_flows) if cash_flows else []

    # ---------- alta de flujos ----------

    def add_one_time_income(
        self,
        name: str,
        amount: float,
        date: dt.date,
    ) -> None:
        self.cash_flows.append(
            OneTimeCashFlow(name, abs(amount), date)
        )

    def add_one_time_expense(
        self,
        name: str,
        amount: float,
        date: dt.date,
    ) -> None:
        self.cash_flows.append(
            OneTimeCashFlow(name, -abs(amount), date)
        )

    def add_weekly_income(
        self,
        name: str,
        amount: float,
        first_date: dt.date,
        end_date: Optional[dt.date] = None,
    ) -> None:
        self.cash_flows.append(
            WeeklyCashFlow(name, abs(amount), first_date, end_date)
        )

    def add_weekly_expense(
        self,
        name: str,
        amount: float,
        first_date: dt.date,
        end_date: Optional[dt.date] = None,
    ) -> None:
        self.cash_flows.append(
            WeeklyCashFlow(name, -abs(amount), first_date, end_date)
        )

    def add_monthly_income(
        self,
        name: str,
        amount: float,
        first_date: dt.date,
        end_date: Optional[dt.date] = None,
    ) -> None:
        self.cash_flows.append(
            MonthlyCashFlow(name, abs(amount), first_date, end_date)
        )

    def add_monthly_expense(
        self,
        name: str,
        amount: float,
        first_date: dt.date,
        end_date: Optional[dt.date] = None,
    ) -> None:
        self.cash_flows.append(
            MonthlyCashFlow(name, -abs(amount), first_date, end_date)
        )

    # ---------- eventos en bruto ----------

    def _events_df(
        self,
        start_date: dt.date,
        end_date: dt.date,
    ) -> pl.DataFrame:
        if not self.cash_flows:
            return _empty_events_df()

        frames = list(
            map(
                lambda cf: cf.generate_df(start_date, end_date),
                self.cash_flows,
            )
        )

        df_all = pl.concat(frames, how="vertical", rechunk=True).sort("date")
        return df_all

    # ---------- reporte por evento ----------

    def events_report(
        self,
        start_date: dt.date,
        end_date: dt.date,
    ) -> pl.DataFrame:
        """
        Un renglón por evento.
        Columnas: date, expenses, income, concept.
        """
        df_events = self._events_df(start_date, end_date)

        if df_events.is_empty():
            return pl.DataFrame(
                schema={
                    "date": pl.Date,
                    "expenses": pl.Float64,
                    "income": pl.Float64,
                    "concept": pl.Utf8,
                }
            )

        report = (
            df_events
            .with_columns(
                [
                    # gasto como valor positivo
                    pl.when(pl.col("amount") < 0)
                    .then(-pl.col("amount"))
                    .otherwise(0.0)
                    .alias("expenses"),
                    # ingreso como valor positivo
                    pl.when(pl.col("amount") > 0)
                    .then(pl.col("amount"))
                    .otherwise(0.0)
                    .alias("income"),
                ]
            )
            .select(
                [
                    pl.col("date"),
                    pl.col("expenses"),
                    pl.col("income"),
                    pl.col("concept"),
                ]
            )
        )
        return report

    # ---------- saldo esperado en una fecha ----------

    def expected_balance(self, as_of: dt.date) -> float:
        """
        Saldo esperado en la fecha as_of,
        partiendo de initial_balance en reference_date.
        """
        start = as_of
        end = self.reference_date
        if self.reference_date <= as_of:
            start = self.reference_date
            end = as_of

        events = self.events_report(start, end)

        if events.is_empty():
            net = 0.0
        else:
            net_series = (
                events
                .select(
                    (pl.col("income") - pl.col("expenses"))
                    .sum()
                    .alias("net")
                )
                .to_series()
            )
            net = float(net_series.item())

        if as_of >= self.reference_date:
            return self.initial_balance + net

        return self.initial_balance - net

    # ---------- resumen diario / semanal / mensual ----------

    def summary_report(
        self,
        start_date: dt.date,
        end_date: dt.date,
        freq: str = "daily",
    ) -> pl.DataFrame:
        """
        freq: "daily", "weekly" o "monthly"
        Regresa columnas:
        date (fin de periodo), income, expenses, net, balance, concepts
        """
        freq_norm = freq.lower()
        freq_map = {
            "d": "1d",
            "daily": "1d",
            "w": "1w",
            "weekly": "1w",
            "m": "1mo",
            "monthly": "1mo",
        }
        every = freq_map.get(freq_norm, "1d")

        events = self.events_report(start_date, end_date)

        if events.is_empty():
            return pl.DataFrame(
                schema={
                    "date": pl.Date,
                    "income": pl.Float64,
                    "expenses": pl.Float64,
                    "net": pl.Float64,
                    "balance": pl.Float64,
                    "concepts": pl.Utf8,
                }
            )

        start_balance = self.expected_balance(start_date)

        grouped = (
            events
            .group_by_dynamic(
                index_column="date",
                every=every,
                period=every,
                closed="right",
                label="right",
            )
            .agg(
                [
                    pl.col("income").sum().alias("income"),
                    pl.col("expenses").sum().alias("expenses"),
                    pl.col("concept")
                    .str.concat(delimiter=", ")
                    .alias("concepts"),
                ]
            )
            .with_columns(
                [
                    pl.col("income").fill_null(0.0),
                    pl.col("expenses").fill_null(0.0),
                ]
            )
            .sort("date")
            .with_columns(
                (pl.col("income") - pl.col("expenses")).alias("net")
            )
            .with_columns(
                (
                    pl.lit(start_balance) + pl.col("net").cum_sum()
                ).alias("balance")
            )
        )

        return grouped.select(
            [
                "date",
                "income",
                "expenses",
                "net",
                "balance",
                "concepts",
            ]
        )


EVENT_SCHEMA = {
    "id": pl.Utf8,
    "concept": pl.Utf8,
    "amount": pl.Float64,
    "frequency": pl.Utf8,
    "start_date": pl.Date,
    "end_date": pl.Date,
    "metadata": pl.Utf8,
}


@dataclass(frozen=True)
class CashFlowSpec:
    id: str
    concept: str
    amount: float
    frequency: str
    start_date: dt.date
    end_date: Optional[dt.date] = None
    metadata: Dict[str, str] = field(default_factory=dict)

    def to_cash_flow(self) -> CashFlow:
        if self.frequency == "once":
            return OneTimeCashFlow(
                name=self.concept,
                amount=self.amount,
                date=self.start_date,
            )
        if self.frequency == "weekly":
            return WeeklyCashFlow(
                name=self.concept,
                amount=self.amount,
                first_date=self.start_date,
                end_date=self.end_date,
            )
        if self.frequency == "monthly":
            return MonthlyCashFlow(
                name=self.concept,
                amount=self.amount,
                first_date=self.start_date,
                end_date=self.end_date,
            )
        raise ValueError("Unsupported frequency")

    def to_record(self) -> Dict[str, object]:
        return {
            "id": self.id,
            "concept": self.concept,
            "amount": self.amount,
            "frequency": self.frequency,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "metadata": json.dumps(
                obj=self.metadata,
                ensure_ascii=False,
            ),
        }

    @classmethod
    def from_record(cls, record: Dict[str, object]) -> "CashFlowSpec":
        metadata_raw = record.get("metadata") or "{}"
        metadata = (
            json.loads(metadata_raw)
            if isinstance(metadata_raw, str)
            else metadata_raw
        )
        return cls(
            id=str(record["id"]),
            concept=str(record["concept"]),
            amount=float(record["amount"]),
            frequency=str(record["frequency"]),
            start_date=record["start_date"],
            end_date=record.get("end_date"),
            metadata=metadata or {},
        )


@dataclass(frozen=True)
class FlowDelta:
    id: str
    amount_delta: float = 0.0
    remove: bool = False
    replacement: Optional[CashFlowSpec] = None


@dataclass(frozen=True)
class Scenario:
    name: str
    parent: Optional[str] = None
    deltas: List[FlowDelta] = field(default_factory=list)


@dataclass(frozen=True)
class ComparisonResult:
    base: str
    variant: str
    events: pl.DataFrame
    summary: pl.DataFrame


class EventRepository:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> pl.DataFrame:
        if self.path.exists():
            return pl.read_parquet(source=str(self.path))
        return pl.DataFrame(schema=EVENT_SCHEMA)

    def save(self, df: pl.DataFrame) -> pl.DataFrame:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        df.rechunk().write_parquet(file=str(self.path))
        return df

    def add_or_update(self, spec: CashFlowSpec) -> pl.DataFrame:
        df = self.load()
        filtered = df.filter(pl.col("id") != spec.id)
        row = pl.DataFrame(
            data=[spec.to_record()],
            schema=EVENT_SCHEMA,
        )
        return self.save(
            df=pl.concat(
                items=[filtered, row],
                how="vertical",
                rechunk=True,
            )
        )

    def remove(self, event_id: str) -> pl.DataFrame:
        df = self.load().filter(pl.col("id") != event_id)
        return self.save(df=df)

    def specs(self) -> List[CashFlowSpec]:
        df = self.load()
        if df.is_empty():
            return []
        return [
            CashFlowSpec.from_record(record=record)
            for record in df.to_dicts()
        ]


class ScenarioLoader:
    def __init__(
        self,
        repo: EventRepository,
        scenarios: Dict[str, Scenario],
    ) -> None:
        self.repo = repo
        self.scenarios = scenarios

    def specs_for(self, name: str) -> List[CashFlowSpec]:
        scenario = self.scenarios[name]
        base_specs = (
            self.specs_for(name=scenario.parent)
            if scenario.parent
            else self.repo.specs()
        )
        spec_map = {spec.id: spec for spec in base_specs}
        return list(
            self._apply_deltas(
                spec_map=spec_map,
                deltas=scenario.deltas,
            ).values()
        )

    def cash_flows_for(self, name: str) -> List[CashFlow]:
        return [
            spec.to_cash_flow()
            for spec in self.specs_for(name=name)
        ]

    def _apply_deltas(
        self,
        spec_map: Dict[str, CashFlowSpec],
        deltas: Iterable[FlowDelta],
    ) -> Dict[str, CashFlowSpec]:
        updated = dict(spec_map)
        for delta in deltas:
            if delta.remove:
                updated.pop(delta.id, None)
                continue
            if delta.replacement:
                updated[delta.replacement.id] = delta.replacement
                continue
            if delta.amount_delta and delta.id in updated:
                updated[delta.id] = replace(
                    updated[delta.id],
                    amount=updated[delta.id].amount + delta.amount_delta,
                )
            elif delta.amount_delta and delta.id not in updated:
                continue
        return updated


class ScenarioReporter:
    def __init__(self, service: "ScenarioService") -> None:
        self.service = service

    def events_many(
        self,
        names: List[str],
        start_date: dt.date,
        end_date: dt.date,
    ) -> Dict[str, pl.DataFrame]:
        return {
            name: self.service.wallet_for(name=name).events_report(
                start_date=start_date,
                end_date=end_date,
            )
            for name in names
        }

    def summary_many(
        self,
        names: List[str],
        start_date: dt.date,
        end_date: dt.date,
        freq: str,
    ) -> Dict[str, pl.DataFrame]:
        return {
            name: self.service.wallet_for(name=name).summary_report(
                start_date=start_date,
                end_date=end_date,
                freq=freq,
            )
            for name in names
        }


class ScenarioService:
    def __init__(
        self,
        repo: EventRepository,
        scenarios: List[Scenario],
        initial_balance: float,
        reference_date: dt.date,
    ) -> None:
        self.repo = repo
        self.scenarios = {scenario.name: scenario for scenario in scenarios}
        self.loader = ScenarioLoader(
            repo=repo,
            scenarios=self.scenarios,
        )
        self.initial_balance = initial_balance
        self.reference_date = reference_date
        self.reporter = ScenarioReporter(service=self)

    def wallet_for(self, name: str) -> Wallet:
        flows = self.loader.cash_flows_for(name=name)
        return Wallet(
            initial_balance=self.initial_balance,
            reference_date=self.reference_date,
            cash_flows=flows,
        )

    def compare(
        self,
        base: str,
        variant: str,
        start_date: dt.date,
        end_date: dt.date,
        freq: str = "weekly",
    ) -> ComparisonResult:
        events_frames = self.reporter.events_many(
            names=[base, variant],
            start_date=start_date,
            end_date=end_date,
        )
        summary_frames = self.reporter.summary_many(
            names=[base, variant],
            start_date=start_date,
            end_date=end_date,
            freq=freq,
        )
        events = _align_events(
            base_name=base,
            variant_name=variant,
            base_df=events_frames[base],
            variant_df=events_frames[variant],
        )
        summary = _align_summary(
            base_name=base,
            variant_name=variant,
            base_df=summary_frames[base],
            variant_df=summary_frames[variant],
        )
        return ComparisonResult(
            base=base,
            variant=variant,
            events=events,
            summary=summary,
        )

    def add_event(self, spec: CashFlowSpec) -> pl.DataFrame:
        return self.repo.add_or_update(spec=spec)

    def remove_event(self, event_id: str) -> pl.DataFrame:
        return self.repo.remove(event_id=event_id)


def _align_events(
    base_name: str,
    variant_name: str,
    base_df: pl.DataFrame,
    variant_df: pl.DataFrame,
) -> pl.DataFrame:
    left = base_df.rename(
        mapping={
            "income": f"income_{base_name}",
            "expenses": f"expenses_{base_name}",
        }
    )
    right = variant_df.rename(
        mapping={
            "income": f"income_{variant_name}",
            "expenses": f"expenses_{variant_name}",
        }
    )
    merged = left.join(
        other=right,
        on=["date", "concept"],
        how="full",
    )
    filled = merged.with_columns(
        [
            pl.col(f"income_{base_name}").fill_null(0.0),
            pl.col(f"income_{variant_name}").fill_null(0.0),
            pl.col(f"expenses_{base_name}").fill_null(0.0),
            pl.col(f"expenses_{variant_name}").fill_null(0.0),
        ]
    )
    return filled.with_columns(
        [
            (
                pl.col(f"income_{variant_name}")
                - pl.col(f"income_{base_name}")
            ).alias("income_delta"),
            (
                pl.col(f"expenses_{variant_name}")
                - pl.col(f"expenses_{base_name}")
            ).alias("expenses_delta"),
        ]
    ).sort(by=["date", "concept"])


def _align_summary(
    base_name: str,
    variant_name: str,
    base_df: pl.DataFrame,
    variant_df: pl.DataFrame,
) -> pl.DataFrame:
    left = base_df.rename(
        mapping={
            "income": f"income_{base_name}",
            "expenses": f"expenses_{base_name}",
            "net": f"net_{base_name}",
            "balance": f"balance_{base_name}",
            "concepts": f"concepts_{base_name}",
        }
    )
    right = variant_df.rename(
        mapping={
            "income": f"income_{variant_name}",
            "expenses": f"expenses_{variant_name}",
            "net": f"net_{variant_name}",
            "balance": f"balance_{variant_name}",
            "concepts": f"concepts_{variant_name}",
        }
    )
    merged = left.join(
        other=right,
        on="date",
        how="full",
    )
    filled = merged.with_columns(
        [
            pl.col(f"income_{base_name}").fill_null(0.0),
            pl.col(f"income_{variant_name}").fill_null(0.0),
            pl.col(f"expenses_{base_name}").fill_null(0.0),
            pl.col(f"expenses_{variant_name}").fill_null(0.0),
            pl.col(f"net_{base_name}").fill_null(0.0),
            pl.col(f"net_{variant_name}").fill_null(0.0),
            pl.col(f"balance_{base_name}").fill_null(0.0),
            pl.col(f"balance_{variant_name}").fill_null(0.0),
        ]
    )
    return filled.with_columns(
        [
            (
                pl.col(f"income_{variant_name}")
                - pl.col(f"income_{base_name}")
            ).alias("income_delta"),
            (
                pl.col(f"expenses_{variant_name}")
                - pl.col(f"expenses_{base_name}")
            ).alias("expenses_delta"),
            (
                pl.col(f"net_{variant_name}")
                - pl.col(f"net_{base_name}")
            ).alias("net_delta"),
            (
                pl.col(f"balance_{variant_name}")
                - pl.col(f"balance_{base_name}")
            ).alias("balance_delta"),
        ]
    ).sort(by="date")


def _seed_events(repo: EventRepository) -> None:
    df = repo.load()
    if not df.is_empty():
        return
    specs = [
        CashFlowSpec(
            id="weekly_salary",
            concept="Sueldo semanal",
            amount=8250.0,
            frequency="weekly",
            start_date=dt.date(year=2025, month=11, day=7),
        ),
        CashFlowSpec(
            id="monthly_rent",
            concept="Renta",
            amount=-6500.0,
            frequency="monthly",
            start_date=dt.date(year=2025, month=11, day=1),
        ),
    ]
    repo.save(
        df=pl.DataFrame(
            data=[spec.to_record() for spec in specs],
            schema=EVENT_SCHEMA,
        )
    )


@dataclass(frozen=True)
class WalletConfig:
    id: str
    name: str
    events_path: str
    initial_balance: float
    reference_date: dt.date

    def to_dict(self) -> Dict[str, object]:
        return {
            "id": self.id,
            "name": self.name,
            "events_path": self.events_path,
            "initial_balance": self.initial_balance,
            "reference_date": self.reference_date.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, object]) -> "WalletConfig":
        return cls(
            id=str(data["id"]),
            name=str(data["name"]),
            events_path=str(data["events_path"]),
            initial_balance=float(data["initial_balance"]),
            reference_date=dt.date.fromisoformat(str(data["reference_date"])),
        )


class WalletManager:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.config_path = base_dir / "wallets.json"
        self.configs = self._load_configs()
        self.services: Dict[str, ScenarioService] = {}

    def _load_configs(self) -> Dict[str, WalletConfig]:
        if not self.config_path.exists():
            default = WalletConfig(
                id="default",
                name="Default wallet",
                events_path="events.parquet",
                initial_balance=5000.0,
                reference_date=dt.date.today(),
            )
            self._write_configs([default])
            return {default.id: default}
        data = json.loads(self.config_path.read_text())
        configs = {
            item["id"]: WalletConfig.from_dict(item)
            for item in data
        }
        if not configs:
            default = WalletConfig(
                id="default",
                name="Default wallet",
                events_path="events.parquet",
                initial_balance=5000.0,
                reference_date=dt.date.today(),
            )
            configs = {default.id: default}
            self._write_configs([default])
        return configs

    def _write_configs(self, configs: List[WalletConfig]) -> None:
        self.config_path.write_text(
            json.dumps([cfg.to_dict() for cfg in configs], indent=2)
        )

    def list_wallets(self) -> List[WalletConfig]:
        return list(self.configs.values())

    def service(self, wallet_id: str) -> ScenarioService:
        if wallet_id not in self.configs:
            raise KeyError(wallet_id)
        if wallet_id not in self.services:
            config = self.configs[wallet_id]
            repo = EventRepository(
                path=self.base_dir / config.events_path
            )
            _seed_events(repo=repo)
            self.services[wallet_id] = ScenarioService(
                repo=repo,
                scenarios=_default_scenarios(),
                initial_balance=config.initial_balance,
                reference_date=config.reference_date,
            )
        return self.services[wallet_id]

    def create_wallet(
        self,
        name: str,
        initial_balance: float,
        reference_date: dt.date,
    ) -> WalletConfig:
        wallet_id = uuid.uuid4().hex[:8]
        events_file = f"events_{wallet_id}.parquet"
        config = WalletConfig(
            id=wallet_id,
            name=name,
            events_path=events_file,
            initial_balance=initial_balance,
            reference_date=reference_date,
        )
        repo = EventRepository(path=self.base_dir / events_file)
        repo.save(df=pl.DataFrame(schema=EVENT_SCHEMA))
        _seed_events(repo=repo)
        self.configs[wallet_id] = config
        self._write_configs(self.list_wallets())
        return config

    def update_wallet(
        self,
        wallet_id: str,
        name: Optional[str] = None,
        initial_balance: Optional[float] = None,
        reference_date: Optional[dt.date] = None,
    ) -> WalletConfig:
        if wallet_id not in self.configs:
            raise KeyError(wallet_id)
        current = self.configs[wallet_id]
        updated = WalletConfig(
            id=wallet_id,
            name=name or current.name,
            events_path=current.events_path,
            initial_balance=(
                initial_balance
                if initial_balance is not None
                else current.initial_balance
            ),
            reference_date=(
                reference_date or current.reference_date
            ),
        )
        self.configs[wallet_id] = updated
        self._write_configs(self.list_wallets())
        self.services.pop(wallet_id, None)
        return updated

    def delete_wallet(self, wallet_id: str) -> None:
        if wallet_id not in self.configs:
            raise KeyError(wallet_id)
        self.configs.pop(wallet_id)
        self.services.pop(wallet_id, None)
        self._write_configs(self.list_wallets())


def _default_scenarios() -> List[Scenario]:
    baseline = Scenario(name="baseline")
    raise_plan = Scenario(
        name="raise_plan",
        parent="baseline",
        deltas=[
            FlowDelta(id="weekly_salary", amount_delta=750.0),
            FlowDelta(
                id="holiday_bonus",
                replacement=CashFlowSpec(
                    id="holiday_bonus",
                    concept="Bono fin de año",
                    amount=12000.0,
                    frequency="once",
                    start_date=dt.date(year=2025, month=12, day=20),
                ),
            ),
        ],
    )
    return [baseline, raise_plan]


def build_default_service(path: Path) -> ScenarioService:
    manager = WalletManager(base_dir=path.parent)
    return manager.service("default")


if __name__ == "__main__":
    manager = WalletManager(base_dir=Path(__file__).parent)
    service = manager.service("default")
    comparison = service.compare(
        base="baseline",
        variant="raise_plan",
        start_date=dt.date(year=2025, month=11, day=8),
        end_date=dt.date(year=2026, month=1, day=31),
        freq="weekly",
    )
    events = comparison.events
    summary = comparison.summary
