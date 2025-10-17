# agent_toteat/tools/tabular/validators.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import ceil
from typing import Dict, Optional

from .config import AppConfig
from .exceptions import BadDateRange, InvalidParam, UnsupportedSort
from .dto import TabularQuery

# Métricas soportadas por modo (extensible)
SUPPORTED_SORTS: Dict[str, set[str]] = {
    "over_time": {"orders", "gross_total", "net_total", "tax_total", "tip_total", "ticket_net_avg", "ticket_net_median"},
    "by_restaurant": {"orders", "gross_total", "net_total", "tax_total", "tip_total", "ticket_net_avg", "ticket_net_median", "pct_tip_over_net", "pct_tax_over_net"},
    "by_product": {"qty_total", "gross_total", "net_total", "tax_total", "tip_total", "orders_distinct", "unit_price_net_avg"},
    "tops": {"orders", "gross_total", "net_total", "tax_total", "tip_total", "ticket_net_avg", "qty_total", "orders_distinct"},
    "diagnostics": set(),
}


def validate_date_range(date_from: Optional[date], date_to: Optional[date]) -> None:
    if date_from and date_to and date_from > date_to:
        raise BadDateRange("date_from no puede ser mayor que date_to.")


def validate_time_grain(q: TabularQuery) -> None:
    if q.mode == "over_time" and not q.time_grain:
        raise InvalidParam("time_grain es requerido cuando mode='over_time'.")


def validate_sort_by_for_mode(q: TabularQuery) -> None:
    sort = q.sort_by
    if not sort:
        # solo obligatorio en tops
        if q.mode == "tops":
            raise UnsupportedSort("sort_by es requerido en mode='tops'.")
        return
    allowed = SUPPORTED_SORTS.get(q.mode, set())
    if sort not in allowed:
        raise UnsupportedSort(f"sort_by='{sort}' no soportado en mode='{q.mode}'.")


@dataclass(frozen=True)
class TopKResolution:
    value: int
    reason: str  # "default" | "clamped" | "auto" | "explicit"


def resolve_top_k(q: TabularQuery, cfg: AppConfig, unique_n: Optional[int] = None) -> TopKResolution:
    """Resuelve top_k aplicando heurística y límites.
    - None => default
    - "auto" => escala con unique_n (si no se provee, cae al default)
    - entero => clamp entre min y max
    """
    tk = q.top_k
    if tk is None:
        return TopKResolution(cfg.top_k_default, "default")
    if tk == "auto":
        if unique_n is None or unique_n <= 0:
            return TopKResolution(cfg.top_k_default, "auto")
        auto_top = int(ceil(0.15 * unique_n))
        auto_top = max(cfg.top_k_min, min(auto_top, cfg.top_k_max))
        return TopKResolution(auto_top, "auto")
    # entero
    try:
        v = int(tk)  # type: ignore[arg-type]
    except Exception as exc:
        raise InvalidParam("top_k debe ser entero o 'auto'.") from exc
    v = max(cfg.top_k_min, min(v, cfg.top_k_max))
    return TopKResolution(v, "clamped" if v != tk else "explicit")


def validate_query(q: TabularQuery) -> None:
    """Valida aspectos semánticos de la query."""
    validate_time_grain(q)
    validate_date_range(q.date_from, q.date_to)
    validate_sort_by_for_mode(q)
