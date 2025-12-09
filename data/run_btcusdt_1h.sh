#!/usr/bin/env bash
set -e
python -m data.etl.cli --ticker BTCUSDT --freq 1h
