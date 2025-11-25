from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any, Dict, List

import polars as pl
import yaml

CONFIG_PATH = Path(__file__).parent / "config" / "features.yaml"
DATA_DIR = Path("data")


def _load_config(path: Path) -> List[Dict[str, Any]]:
    content = yaml.safe_load(path.read_text())
    return content.get("features", [])


def _load_ohlcv(symbol: str) -> pl.DataFrame:
    base = DATA_DIR / "spot" / symbol.lower() / "ohlcv_1m"
    files = sorted(base.glob("year=*/month=*/data.parquet"))
    if not files:
        raise FileNotFoundError("no ohlcv files found")
    frames = [pl.read_parquet(file) for file in files]
    return pl.concat(frames, how="vertical").sort("open_time")


def _write_feature(df: pl.DataFrame, name: str, symbol: str) -> None:
    target = DATA_DIR / "features" / name / symbol.lower()
    target.mkdir(parents=True, exist_ok=True)
    target_file = target / "data.parquet"
    df.write_parquet(target_file)


def run(symbol: str, config: Path = CONFIG_PATH) -> None:
    ohlcv = _load_ohlcv(symbol)
    for entry in _load_config(config):
        name = entry["name"]
        module = importlib.import_module(f"src.features.{name}")
        func = getattr(module, "apply")
        params = {k: v for k, v in entry.items() if k != "name"}
        enriched = func(ohlcv, **params)
        feature_cols = [col for col in enriched.columns if col not in ohlcv.columns]
        if not feature_cols:
            continue
        payload = enriched.select(["open_time", *feature_cols])
        _write_feature(payload, name, symbol)


def main(symbol: str, config: str = str(CONFIG_PATH)) -> None:
    run(symbol, Path(config))


if __name__ == "__main__":
    import typer

    typer.run(main)
