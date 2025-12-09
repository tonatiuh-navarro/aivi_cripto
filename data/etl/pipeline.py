from __future__ import annotations

from pathlib import Path
from sklearn.pipeline import Pipeline

from data.etl.extraction import ExtractionStage
from data.etl.processing import MarketFrameStage
from data.etl.persist import ParquetUpsertStage


def _default_path(ticker: str, frequency: str) -> str:
    ticker_norm = ticker.lower()
    freq_norm = frequency.lower()
    return str(Path("data") / f"market_data_{ticker_norm}_{freq_norm}.parquet")


def build_market_etl_pipeline(
    ticker: str,
    frequency: str,
    output_path: str | None = None,
    limit: int = 1000,
    start: str | None = None,
    end: str | None = None,
    atr_period: int = 14,
    months: int = 6,
    log_file: str | None = None,
):
    path = output_path or _default_path(ticker, frequency)
    return Pipeline(
        steps=[
            (
                "extract",
                ExtractionStage(
                    ticker=ticker,
                    frequency=frequency,
                    limit=limit,
                    start=start,
                    end=end,
                    cache_path=path,
                    log_file=log_file,
                ),
            ),
            (
                "process",
                MarketFrameStage(
                    atr_period=atr_period,
                    months=months,
                    log_file=log_file,
                ),
            ),
            (
                "persist",
                ParquetUpsertStage(
                    path=path,
                    key="open_time",
                    sort_by="open_time",
                    log_file=log_file,
                ),
            ),
        ]
    )
