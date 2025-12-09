import polars as pl
from sklearn.base import BaseEstimator, TransformerMixin
from utils.performance_utils import MetaEngine


class BaseStage(BaseEstimator, TransformerMixin, metaclass=MetaEngine):
    log_level = "INFO"
    log_file: str | None = None

    def fit(self, frame: pl.DataFrame, y=None):  # noqa: D401
        """No-op fit for compatibility with sklearn Pipeline."""
        return self

    def transform(self, frame: pl.DataFrame) -> pl.DataFrame:
        raise NotImplementedError
