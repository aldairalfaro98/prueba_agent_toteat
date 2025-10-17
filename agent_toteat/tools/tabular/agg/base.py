# agent_toteat/tools/tabular/agg/base.py
from __future__ import annotations

from typing import Protocol, List, Dict, Any
import logging

from ..dto import TabularQuery
from ..loader import DataRepository

logger = logging.getLogger(__name__)


class IModeHandler(Protocol):
    """Contratos de los agregadores por modo."""
    def run(self, repo: DataRepository, q: TabularQuery) -> List[Dict[str, Any]]: ...


def get_handler(mode: str) -> IModeHandler:
    """Devuelve el handler adecuado para el modo."""
    if mode == "over_time":
        from .over_time import OverTimeHandler
        return OverTimeHandler()
    if mode == "by_restaurant":
        from .restaurants import RestaurantsHandler
        return RestaurantsHandler()
    if mode == "by_product":
        from .products import ProductsHandler
        return ProductsHandler()
    if mode == "tops":
        from .tops import TopsHandler
        return TopsHandler()
    if mode == "diagnostics":
        from ..diagnostics import DiagnosticsHandler  # type: ignore[assignment]
        return DiagnosticsHandler()  # type: ignore[return-value]
    raise ValueError(f"Modo no soportado: {mode}")
