"""Adapter registry: source.key -> adapter instance.

`fetch_source` looks the adapter up by the source's key. A new source registers
its adapter here; that is the only wiring step.
"""

from app.modules.ingestion.adapters.base import Adapter
from app.modules.ingestion.adapters.worldbank import WorldBankAdapter

ADAPTERS: dict[str, Adapter] = {
    WorldBankAdapter.key: WorldBankAdapter(),
}


def get_adapter(key: str) -> Adapter:
    try:
        return ADAPTERS[key]
    except KeyError:
        raise KeyError(f"no adapter registered for source '{key}'") from None
