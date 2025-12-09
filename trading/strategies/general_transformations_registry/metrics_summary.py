import math
import polars as pl
from ..base import BaseStage


class MetricsSummary(BaseStage):
    def __init__(
        self,
        output_format: str = "dict",
        annualization_factor: float | None = None,
    ):
        """
        output_format: "dict" (default) o "dataframe"
        annualization_factor: p. ej. 252 para sharpe/vol anualizada; si None, se usa std simple.
        """
        self.output_format = output_format
        self.annualization_factor = annualization_factor

    def _as_output(self, metrics: dict):
        if self.output_format == "dataframe":
            return pl.DataFrame([metrics])
        return metrics

    def _safe(self, value):
        if value is None:
            return None
        try:
            return float(value)
        except Exception:
            return None

    def transform(self, frame: pl.DataFrame):
        if not isinstance(frame, pl.DataFrame):
            return self._as_output({})
        if frame.is_empty() or "strategy_return" not in frame.columns:
            return self._as_output({})

        returns = frame["strategy_return"].fill_null(0.0)
        equity = (1.0 + returns).cum_prod()
        total_return = float(equity[-1] - 1.0) if equity.len() else 0.0

        roll_max = equity.cum_max()
        drawdown = (equity / roll_max) - 1.0
        max_drawdown = float(drawdown.min()) if drawdown.len() else 0.0

        mean_ret = self._safe(returns.mean()) if returns.len() else 0.0
        std_ret = self._safe(returns.std()) if returns.len() else 0.0
        if self.annualization_factor and self.annualization_factor > 0:
            vol = std_ret * math.sqrt(self.annualization_factor)
            sharpe = (
                (mean_ret * self.annualization_factor) / vol
                if vol
                else None
            )
        else:
            vol = std_ret
            sharpe = (mean_ret / vol) if vol else None

        # trades
        exits = frame.filter(pl.col("trade_event"))
        wins = exits.filter(pl.col("trade_label") == "win") if exits.height else pl.DataFrame()
        losses = exits.filter(pl.col("trade_label") == "loss") if exits.height else pl.DataFrame()

        sum_wins = self._safe(wins["strategy_return"].sum()) if wins.height else 0.0
        sum_losses = self._safe(losses["strategy_return"].sum()) if losses.height else 0.0
        profit_factor = (
            (sum_wins / abs(sum_losses)) if sum_losses < 0 else None
        )

        avg_win = self._safe(wins["strategy_return"].mean()) if wins.height else None
        avg_loss = self._safe(losses["strategy_return"].mean()) if losses.height else None
        payoff_ratio = (
            (avg_win / abs(avg_loss)) if (avg_win is not None and avg_loss not in (None, 0)) else None
        )

        expectancy = self._safe(exits["strategy_return"].mean()) if exits.height else None
        win_rate = (wins.height / exits.height) if exits.height else None

        # tiempo
        span = frame.select(
            pl.col("open_time").min().alias("min_time"),
            pl.col("open_time").max().alias("max_time"),
        ).to_dicts()[0]
        min_time = span["min_time"]
        max_time = span["max_time"]
        if min_time and max_time:
            days = (max_time - min_time).days or 0
        else:
            days = 0
        return_per_day = (total_return / days) if days > 0 else None
        years = days / 365.0 if days > 0 else 0.0
        cagr = ((1 + total_return) ** (1 / years) - 1) if years > 0 else None
        calmar = (cagr / abs(max_drawdown)) if (cagr is not None and max_drawdown < 0) else None

        metrics = {
            "total_return": total_return,
            "cagr": cagr,
            "volatility": vol,
            "sharpe": sharpe,
            "max_drawdown": max_drawdown,
            "calmar": calmar,
            "n_trades": exits.height,
            "win_rate": win_rate,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "payoff_ratio": payoff_ratio,
            "profit_factor": profit_factor,
            "expectancy": expectancy,
            "time_span_days": days,
            "return_per_day": return_per_day,
        }
        return self._as_output(metrics)


def build(**params):
    return MetricsSummary(**params)
