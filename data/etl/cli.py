from __future__ import annotations

import argparse
from pathlib import Path

import polars as pl

from data.etl.pipeline import build_market_etl_pipeline
from utils.logging_utils import setup_logger_for_child


def parse_args():
    parser = argparse.ArgumentParser(description="ETL de mercado parametrizable.")
    parser.add_argument("--ticker", required=True, help="Símbolo, ej. BTCUSDT")
    parser.add_argument(
        "--freq",
        required=True,
        help="Frecuencia: 1m,5m,15m,30m,45m,1h,4h,6h,12h,1d,1w,1month",
    )
    parser.add_argument("--start", help="Inicio ISO8601, ej. 2024-01-01")
    parser.add_argument("--end", help="Fin ISO8601, ej. 2024-02-01")
    parser.add_argument("--limit", type=int, default=1000, help="Límite por request")
    parser.add_argument("--atr-period", type=int, default=14, help="ATR period")
    parser.add_argument("--months", type=int, default=6, help="Meses de ventana reciente")
    parser.add_argument("--output", help="Ruta de parquet destino")
    return parser.parse_args()


def main():
    args = parse_args()
    logger = setup_logger_for_child(
        parent_name="data_etl",
        child_name="cli",
        log_level="INFO",
        console=True,
    )
    output = args.output or None
    target_path = output or f"data/market_data_{args.ticker.lower()}_{args.freq.lower()}.parquet"
    existing_rows = 0
    if Path(target_path).exists():
        try:
            existing_rows = pl.read_parquet(target_path).height
        except Exception as exc:
            logger.warning(f"No se pudo leer {target_path}: {exc}")
    pipeline = build_market_etl_pipeline(
        ticker=args.ticker,
        frequency=args.freq,
        output_path=output,
        limit=args.limit,
        start=args.start,
        end=args.end,
        atr_period=args.atr_period,
        months=args.months,
    )
    result = pipeline.fit_transform(None)
    final_rows = result.height if hasattr(result, "height") else 0
    delta = max(0, final_rows - existing_rows)
    if delta == 0 and final_rows == existing_rows and final_rows > 0:
        logger.info(
            "Sin nuevas velas; ticker=%s freq=%s ya estaba actualizado en %s",
            args.ticker,
            args.freq,
            target_path,
        )
    logger.info(
        f"ETL completado ticker={args.ticker} freq={args.freq} "
        f"filas nuevas={delta:,} total={final_rows:,} path={target_path}"
    )


if __name__ == "__main__":
    main()
