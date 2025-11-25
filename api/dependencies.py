from functools import lru_cache
from pathlib import Path

from main import WalletManager


@lru_cache(maxsize=1)
def _manager() -> WalletManager:
    base_dir = Path(__file__).resolve().parent.parent
    return WalletManager(base_dir=base_dir)


def get_manager() -> WalletManager:
    return _manager()
