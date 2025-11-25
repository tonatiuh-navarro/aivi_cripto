import hashlib
import hmac
import os
import time
from pathlib import Path
from typing import Dict, Optional

import requests

BASE_URL = "https://api.binance.com"


def load_env() -> None:
    paths = [
        Path(__file__).with_name(".env.local"),
        Path(__file__).with_name(".env"),
        Path(__file__).parent.joinpath("env", ".env.local"),
        Path(__file__).parent.joinpath("env", ".env"),
    ]
    for path in paths:
        if not path.exists():
            continue
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


load_env()

API_KEY = os.getenv("BINANCE_API_KEY", "")
API_SECRET = os.getenv("BINANCE_SECRET_KEY", "")


def _timestamp() -> int:
    return int(time.time() * 1000)


def _sign(params: Dict[str, str]) -> str:
    query = "&".join(f"{key}={value}" for key, value in params.items())
    signature = hmac.new(
        API_SECRET.encode(),
        query.encode(),
        hashlib.sha256,
    ).hexdigest()
    return signature


def _request(method: str, path: str, params: Optional[Dict[str, str]] = None, signed: bool = False) -> dict:
    params = params.copy() if params else {}
    headers = {"X-MBX-APIKEY": API_KEY} if signed else {}
    if signed:
        params["timestamp"] = str(_timestamp())
        params["signature"] = _sign(params)
    response = requests.request(method, f"{BASE_URL}{path}", params=params, headers=headers, timeout=10)
    response.raise_for_status()
    return response.json()


def server_time() -> dict:
    return _request("GET", "/api/v3/time")


def account_info() -> dict:
    return _request("GET", "/api/v3/account", signed=True)


def recent_trades(symbol: str, limit: int = 10) -> dict:
    return _request("GET", "/api/v3/trades", params={"symbol": symbol.upper(), "limit": str(limit)})


def klines(symbol: str, interval: str = "1h", limit: int = 50) -> dict:
    return _request(
        "GET",
        "/api/v3/klines",
        params={"symbol": symbol.upper(), "interval": interval, "limit": str(limit)},
    )


if __name__ == "__main__":
    print("Server time:", server_time())
    if API_KEY and API_SECRET:
        info = account_info()
        balances = [b for b in info.get("balances", []) if float(b.get("free", 0)) > 0]
        print("Balances:", balances[:5])
    else:
        print("API keys not found; skipping private endpoints.")
