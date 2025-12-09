from __future__ import annotations

from datetime import datetime, timedelta, time
from pathlib import Path
from typing import Iterable, Optional

import httpx
import polars as pl
from sklearn.base import BaseEstimator, TransformerMixin

from utils.logging_utils import setup_logger_for_child


_INTERVAL_MAP = {
    "1m": "1m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "45m": "1h",  # Binance no soporta 45m, se aproxima a 1h
    "1h": "1h",
    "4h": "4h",
    "6h": "6h",
    "12h": "12h",
    "1d": "1d",
    "1w": "1w",
    "1month": "1M",
}
_SCHEMA = {
    "open_time": pl.Int64,
    "open": pl.Float64,
    "high": pl.Float64,
    "low": pl.Float64,
    "close": pl.Float64,
    "volume": pl.Float64,
    "close_time": pl.Int64,
    "quote_asset_volume": pl.Float64,
    "number_of_trades": pl.Int64,
    "taker_buy_base_asset_volume": pl.Float64,
    "taker_buy_quote_asset_volume": pl.Float64,
    "ignore": pl.Float64,
}
_DEFAULT_LOOKBACK_DAYS = 90


def _to_ms(value: datetime) -> int:
    return int(value.timestamp() * 1000)


def _parse_date(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _default_end() -> datetime:
    today = datetime.today().date()
    return datetime.combine(today, time.max)


def _iter_chunks(symbol: str, interval: str, start_ms: int, end_ms: int, limit: int) -> Iterable[list]:
    url = "https://api.binance.com/api/v3/klines"
    next_start = start_ms
    with httpx.Client(timeout=60) as client:
        while next_start < end_ms:
            params = {
                "symbol": symbol,
                "interval": interval,
                "startTime": str(next_start),
                "endTime": str(end_ms),
                "limit": str(min(limit, 1000)),
            }
            resp = client.get(url, params=params)
            resp.raise_for_status()
            rows = resp.json()
            if not rows:
                break
            yield rows
            last_close = int(rows[-1][6])
            next_start = last_close + 1
            if len(rows) < min(limit, 1000):
                break


class ExtractionStage(BaseEstimator, TransformerMixin):
    def __init__(
        self,
        ticker: str,
        frequency: str,
        limit: int = 1000,
        start: Optional[str] = None,
        end: Optional[str] = None,
        cache_path: Optional[str] = None,
        log_file: Optional[str] = None,
        log=None,
    ):
        self.ticker = ticker
        self.frequency = frequency.lower()
        self.limit = limit
        self.start = start
        self.end = end
        self.cache_path = cache_path
        self.log_file = log_file
        self.log = log

    def fit(self, X=None, y=None):
        return self

    def _resolve_range(self) -> tuple[int, int]:
        logger = self.log
        interval = _INTERVAL_MAP.get(self.frequency)
        if not interval:
            raise ValueError(f"Frecuencia no soportada: {self.frequency}")
        start_ms = None
        end_ms = None
        if self.start:
            start_ms = _to_ms(_parse_date(self.start))
        if self.end:
            end_ms = _to_ms(_parse_date(self.end))
        path = Path(self.cache_path) if self.cache_path else None
        if start_ms is None and path and path.exists():
            try:
                last_df = pl.read_parquet(path)
                if "open_time" in last_df.columns and last_df.height:
                    last = last_df.select(pl.col("open_time").max()).item()
                    if isinstance(last, datetime):
                        start_ms = _to_ms(last) + 1
                    else:
                        start_ms = int(last) + 1
                    if logger:
                        logger.info(f"Usando start derivado del parquet: {start_ms}")
            except Exception as exc:
                if logger:
                    logger.warning(f"No se pudo leer {path}: {exc}")
        if end_ms is None:
            end_ms = _to_ms(_default_end())
        if start_ms is None:
            end_dt = datetime.fromtimestamp(end_ms / 1000)
            start_ms = _to_ms(end_dt - timedelta(days=_DEFAULT_LOOKBACK_DAYS))
        if start_ms >= end_ms:
            # Si la última vela del parquet está en el futuro, retrocede lookback
            end_dt = datetime.fromtimestamp(end_ms / 1000)
            start_ms = _to_ms(end_dt - timedelta(days=_DEFAULT_LOOKBACK_DAYS))
            if logger:
                logger.warning("Rango inválido; ajustando start por lookback de 90d")
        return start_ms, end_ms

    def transform(self, X=None):
        logger = self.log or setup_logger_for_child(
            parent_name="data_etl",
            child_name="extraction",
            log_level="INFO",
            log_file=self.log_file,
            console=False,
        )
        symbol = self.ticker.upper()
        interval = _INTERVAL_MAP.get(self.frequency)
        if not interval:
            raise ValueError(f"Frecuencia no soportada: {self.frequency}")
        start_ms, end_ms = self._resolve_range()
        all_rows: list[list] = []
        for chunk in _iter_chunks(symbol, interval, start_ms, end_ms, self.limit):
            all_rows.extend(chunk)
        df = pl.DataFrame(all_rows, schema=_SCHEMA) if all_rows else pl.DataFrame(schema=_SCHEMA)
        logger.info(
            f"Extraído {df.height:,} filas de {symbol} {self.frequency} "
            f"rango {start_ms} - {end_ms}"
        )
        return df
