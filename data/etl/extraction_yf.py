from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd
import polars as pl
import yfinance as yf
from sklearn.base import BaseEstimator, TransformerMixin

from utils.logging_utils import setup_logger_for_child


_INTERVAL_MAP = {
    "1m": "1m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "45m": "60m",  # closest available
    "1h": "60m",
    "1d": "1d",
    "1w": "1wk",
    "1month": "1mo",
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


def _interval_ms(freq: str) -> int:
    match freq:
        case "1m":
            minutes = 1
        case "5m":
            minutes = 5
        case "15m":
            minutes = 15
        case "30m":
            minutes = 30
        case "45m":
            minutes = 60
        case "1h":
            minutes = 60
        case "1d":
            return int(timedelta(days=1).total_seconds() * 1000)
        case "1w":
            return int(timedelta(days=7).total_seconds() * 1000)
        case "1month":
            return int(timedelta(days=30).total_seconds() * 1000)
        case _:
            minutes = 0
    if minutes:
        return minutes * 60 * 1000
    raise ValueError(f"Unsupported yfinance interval for {freq}")


class YFinanceExtractionStage(BaseEstimator, TransformerMixin):
    def __init__(
        self,
        ticker: str,
        frequency: str,
        start: Optional[str] = None,
        end: Optional[str] = None,
        cache_path: Optional[str] = None,
        log_file: Optional[str] = None,
        log=None,
    ):
        self.ticker = ticker
        self.frequency = frequency.lower()
        self.start = start
        self.end = end
        self.cache_path = cache_path
        self.log_file = log_file
        self.log = log

    def fit(self, X=None, y=None):
        return self

    def _resolve_range(self) -> tuple[datetime, datetime]:
        logger = self.log
        start_dt = datetime.fromisoformat(self.start) if self.start else None
        end_dt = datetime.fromisoformat(self.end) if self.end else None

        path = Path(self.cache_path) if self.cache_path else None
        if start_dt is None and path and path.exists():
            try:
                last_df = pl.read_parquet(path)
                if "open_time" in last_df.columns and last_df.height:
                    last = last_df.select(pl.col("open_time").max()).item()
                    if isinstance(last, datetime):
                        start_dt = last + timedelta(milliseconds=1)
                    else:
                        start_dt = datetime.fromtimestamp(int(last) / 1000) + timedelta(milliseconds=1)
                    if logger:
                        logger.info(f"Usando start derivado del parquet: {start_dt.isoformat()}")
            except Exception as exc:
                if logger:
                    logger.warning(f"No se pudo leer {path}: {exc}")

        if end_dt is None:
            end_dt = datetime.utcnow()

        if start_dt is None:
            start_dt = end_dt - timedelta(days=_DEFAULT_LOOKBACK_DAYS)

        if start_dt >= end_dt:
            start_dt = end_dt - timedelta(days=_DEFAULT_LOOKBACK_DAYS)
            if logger:
                logger.warning("Rango inválido; ajustando start por lookback de 90d")

        return start_dt, end_dt

    def transform(self, X=None):
        logger = self.log or setup_logger_for_child(
            parent_name="data_etl",
            child_name="extraction_yfinance",
            log_level="INFO",
            log_file=self.log_file,
            console=False,
        )
        interval = _INTERVAL_MAP.get(self.frequency)
        if not interval:
            raise ValueError(f"Frecuencia no soportada para yfinance: {self.frequency}")

        start_dt, end_dt = self._resolve_range()
        yf_ticker = yf.Ticker(self.ticker)
        hist = yf_ticker.history(
            interval=interval,
            start=start_dt,
            end=end_dt,
            actions=False,
            auto_adjust=False,
        )

        if hist.empty:
            logger.warning(f"yfinance devolvió 0 filas para {self.ticker} {self.frequency}")
            return pl.DataFrame(schema=_SCHEMA)

        hist = hist.reset_index().rename(
            columns={
                "Datetime": "open_time",
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Volume": "volume",
            }
        )
        # Convert open_time to ms since epoch
        hist["open_time"] = (
            pd.to_datetime(hist["open_time"], utc=True)
            .view("int64")
            // 1_000_000
        )
        interval_ms = _interval_ms(self.frequency)
        hist["close_time"] = hist["open_time"] + interval_ms
        hist["quote_asset_volume"] = 0.0
        hist["number_of_trades"] = 0
        hist["taker_buy_base_asset_volume"] = 0.0
        hist["taker_buy_quote_asset_volume"] = 0.0
        hist["ignore"] = 0.0

        df = pl.from_pandas(hist)
        # Cast to expected schema
        df = df.cast(_SCHEMA)
        logger.info(
            f"Extraído {df.height:,} filas de {self.ticker.upper()} {self.frequency} "
            f"rango {start_dt.isoformat()} - {end_dt.isoformat()} via yfinance"
        )
        return df
