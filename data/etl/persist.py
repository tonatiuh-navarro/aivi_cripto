from __future__ import annotations

from pathlib import Path

import polars as pl
from sklearn.base import BaseEstimator, TransformerMixin

from utils.logging_utils import setup_logger_for_child


class ParquetUpsertStage(BaseEstimator, TransformerMixin):
    def __init__(
        self,
        path: str,
        key: str = "open_time",
        sort_by: str = "open_time",
        log_file: str | None = None,
        log=None,
    ):
        self.path = path
        self.key = key
        self.sort_by = sort_by
        self.log_file = log_file
        self.log = log

    def fit(self, X=None, y=None):
        return self

    def transform(self, X):
        logger = self.log or setup_logger_for_child(
            parent_name="data_etl",
            child_name="persist",
            log_level="INFO",
            log_file=self.log_file,
            console=False,
        )
        if not isinstance(X, pl.DataFrame):
            raise TypeError("Se esperaba un DataFrame de Polars para persistencia")
        path = Path(self.path)
        path.parent.mkdir(parents=True, exist_ok=True)
        existing = pl.DataFrame()
        if path.exists():
            try:
                existing = pl.read_parquet(path)
            except Exception as exc:
                logger.warning(f"No se pudo leer {path}: {exc}")
        if X.is_empty():
            if existing.height:
                logger.info(
                    f"Sin nuevas filas; ya existían {existing.height:,} en {path}"
                )
                return existing
            logger.warning("DataFrame vacío y sin archivo previo; nada que persistir")
            return X
        merged = pl.concat([existing, X], how="vertical", rechunk=True) if existing.height else X
        merged = merged.unique(subset=[self.key], keep="last").sort(self.sort_by)
        merged.write_parquet(path)
        logger.info(
            f"Upsert completado en {path} filas={merged.height:,} "
            f"(nuevas={max(0, merged.height - existing.height):,})"
        )
        return merged
