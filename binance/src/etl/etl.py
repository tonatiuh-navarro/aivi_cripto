from __future__ import annotations

import io
import math
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable, Literal, Optional

import httpx
import polars as pl

TIMEZONE = "UTC"
VISION_URL = (
    "https://data.binance.vision/data/spot/monthly/klines/{symbol}/1m/"
    "{symbol}-1m-{year}-{month:02d}.zip"
)
REST_URL = "https://api.binance.com/api/v3/klines"
COLUMNS = [
    "open_time",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "close_time",
    "quote_asset_volume",
    "number_of_trades",
    "taker_buy_base_asset_volume",
    "taker_buy_quote_asset_volume",
    "ignore",
]
Mode = Literal["history", "incremental"]


def _target_dir(symbol: str) -> Path:
    base = Path("data") / "spot" / symbol.lower() / "ohlcv_1m"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _ingestion_log() -> Path:
    path = Path("data") / "ingestion_log.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        pl.DataFrame(schema={
            "symbol": pl.Utf8,
            "source": pl.Utf8,
            "month": pl.Utf8,
            "rows": pl.Int64,
            "hash": pl.Utf8,
            "started_at": pl.Datetime(time_zone=TIMEZONE),
            "ended_at": pl.Datetime(time_zone=TIMEZONE),
            "status": pl.Utf8,
        }).write_parquet(path)
    return path


def _append_log(record: dict) -> None:
    log_path = _ingestion_log()
    df = pl.DataFrame(record)
    existing = pl.read_parquet(log_path)
    pl.concat([existing, df], how="vertical", rechunk=True).write_parquet(log_path)


def _download(url: str) -> bytes:
    with httpx.Client(timeout=120) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.content


def _parse_zip(payload: bytes) -> pl.DataFrame:
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        name = archive.namelist()[0]
        with archive.open(name) as file_obj:
            data = file_obj.read()
    return pl.read_csv(
        io.BytesIO(data),
        has_header=False,
        new_columns=COLUMNS,
        try_parse_dates=False,
    )


def _write_month(df: pl.DataFrame, symbol: str, year: int, month: int) -> None:
    target = _target_dir(symbol) / f"year={year}" / f"month={month:02d}"
    target.mkdir(parents=True, exist_ok=True)
    out = target / "data.parquet"
    df.write_parquet(out)


def _month_range(start: datetime, end: datetime) -> Iterable[tuple[int, int]]:
    current = datetime(start.year, start.month, 1)
    stop = datetime(end.year, end.month, 1)
    while current <= stop:
        yield current.year, current.month
        if current.month == 12:
            current = datetime(current.year + 1, 1, 1)
        else:
            current = datetime(current.year, current.month + 1, 1)


def run_history(symbol: str, start: datetime, end: datetime) -> None:
    for year, month in _month_range(start, end):
        started_at = datetime.utcnow()
        status = "success"
        rows = 0
        digest = ""
        try:
            url = VISION_URL.format(symbol=symbol.upper(), year=year, month=month)
            payload = _download(url)
            df = _parse_zip(payload)
            rows = df.height
            digest = pl.util.hash_rows(df.select("open_time"))
            _write_month(df, symbol, year, month)
        except Exception:
            status = "failed"
            raise
        finally:
            ended_at = datetime.utcnow()
            record = {
                "symbol": [symbol.upper()],
                "source": ["vision"],
                "month": [f"{year}-{month:02d}"],
                "rows": [rows],
                "hash": [str(digest)],
                "started_at": [started_at.replace(tzinfo=None)],
                "ended_at": [ended_at.replace(tzinfo=None)],
                "status": [status],
            }
            _append_log(record)


def _fetch_rest(symbol: str, start: int, end: int) -> list[list]:
    out: list[list] = []
    next_start = start
    with httpx.Client(timeout=60) as client:
        while next_start < end:
            params = {
                "symbol": symbol.upper(),
                "interval": "1m",
                "startTime": str(next_start),
                "endTime": str(end),
                "limit": "1000",
            }
            resp = client.get(REST_URL, params=params)
            resp.raise_for_status()
            klines = resp.json()
            if not klines:
                break
            out.extend(klines)
            last_close = klines[-1][6]
            next_start = int(last_close) + 1
            if len(klines) < 1000:
                break
    return out


def _merge_incremental(symbol: str, rows: list[list]) -> None:
    if not rows:
        return
    df = pl.DataFrame(rows, schema=COLUMNS)
    df = df.with_columns(pl.col("open_time").cast(pl.Int64))
    target_dir = _target_dir(symbol)
    partition_map = df.with_columns(
        year=pl.from_epoch(pl.col("open_time") // 1000, time_unit="s").dt.year(),
        month=pl.from_epoch(pl.col("open_time") // 1000, time_unit="s").dt.month(),
    )
    for (year, month), part in partition_map.group_by(["year", "month"], maintain_order=True):
        year_dir = target_dir / f"year={int(year)}" / f"month={int(month):02d}"
        year_dir.mkdir(parents=True, exist_ok=True)
        out = year_dir / "data.parquet"
        if out.exists():
            existing = pl.read_parquet(out)
            merged = pl.concat([existing, part.drop(["year", "month"])], how="vertical")
            merged = merged.unique(subset=["open_time"], keep="last").sort("open_time")
        else:
            merged = part.drop(["year", "month"]).sort("open_time")
        merged.write_parquet(out)


def run_incremental(symbol: str, lookback: timedelta) -> None:
    now = datetime.utcnow()
    start = int((now - lookback).timestamp() * 1000)
    end = int(now.timestamp() * 1000)
    rows = _fetch_rest(symbol, start, end)
    _merge_incremental(symbol, rows)


def parse_month(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m")


def parse_lookback(value: str) -> timedelta:
    unit = value[-1]
    amount = int(value[:-1])
    if unit == "m":
        return timedelta(minutes=amount)
    if unit == "h":
        return timedelta(hours=amount)
    if unit == "d":
        return timedelta(days=amount)
    raise ValueError("invalid lookback")


def run(symbol: str, mode: Mode, start: Optional[str] = None, end: Optional[str] = None, lookback: Optional[str] = None) -> None:
    if mode == "history":
        if not start or not end:
            raise ValueError("start and end required for history")
        run_history(symbol, parse_month(start), parse_month(end))
        return
    if mode == "incremental":
        if not lookback:
            raise ValueError("lookback required for incremental")
        run_incremental(symbol, parse_lookback(lookback))
        return
    raise ValueError("unknown mode")


__all__ = ["run", "run_history", "run_incremental"]
