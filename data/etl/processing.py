from __future__ import annotations

import polars as pl
from sklearn.base import BaseEstimator, TransformerMixin

from utils.logging_utils import setup_logger_for_child
from utils.strategy_utils import prepare_market_frame


class MarketFrameStage(BaseEstimator, TransformerMixin):
    def __init__(
        self,
        atr_period: int = 14,
        months: int = 6,
        log_file: str | None = None,
        log=None,
    ):
        self.atr_period = atr_period
        self.months = months
        self.log_file = log_file
        self.log = log

    def fit(self, X=None, y=None):
        return self

    def transform(self, X):
        logger = self.log or setup_logger_for_child(
            parent_name="data_etl",
            child_name="processing",
            log_level="INFO",
            log_file=self.log_file,
            console=False,
        )
        if not isinstance(X, pl.DataFrame):
            raise TypeError("Se esperaba un DataFrame de Polars para procesamiento")
        if X.is_empty():
            logger.warning("DataFrame vacío; se omite procesamiento")
            return X
        rows = X.select(list(X.columns)).to_dicts()
        market_df = prepare_market_frame(
            klines=rows,
            atr_period=self.atr_period,
            months=self.months,
        )
        logger.info(f"Market frame listo: {market_df.height:,} filas")
        return market_df
