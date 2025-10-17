# agent_toteat/tools/tabular/agg/restaurants.py
from __future__ import annotations

from typing import Any, Dict, List
import logging
import numpy as np
import pandas as pd

from ..dto import TabularQuery
from ..loader import DataRepository, build_orders_from_lines
from .base import IModeHandler
from ..filters import apply_date_filter, apply_restaurants_filter, apply_products_filter
from ..cache import LRUCache, build_query_key, get_or_compute
from ..validators import resolve_top_k
from ..config import AppConfig
from ..schema import RESTAURANT_ID, ORDER_ID, DATE

logger = logging.getLogger(__name__)
_CACHE = LRUCache()


class RestaurantsHandler(IModeHandler):
    """KPIs por restaurante (nivel orden) con soporte de filtros y top_k.

    Métricas:
      - orders: número de órdenes (distinct)
      - n_lines: suma de líneas por restaurante
      - items: suma de quantities
      - gross_total / net_total / tax_total / tip_total (sum)
      - ticket_net_avg: promedio del neto por orden
      - ticket_net_median: mediana del neto por orden
      - pct_tip_over_net, pct_tax_over_net: ratios agregados (sum(tip)/sum(net))
    """

    def run(self, repo: DataRepository, q: TabularQuery) -> List[Dict[str, Any]]:
        key = build_query_key(q, extra={"handler": "by_restaurant"})

        def _compute() -> List[Dict[str, Any]]:
            # 1) Aplicar filtros en LÍNEAS para respetar product filters también
            lines = repo.lines
            if lines.empty:
                return []

            # Fechas
            date_from = pd.to_datetime(q.date_from) if q.date_from else None
            date_to = pd.to_datetime(q.date_to) if q.date_to else None
            lines_f = apply_date_filter(lines, date_from, date_to)

            # Restaurantes / Productos
            lines_f = apply_restaurants_filter(lines_f, q.restaurants)
            lines_f = apply_products_filter(lines_f, q.products)

            if lines_f.empty:
                return []

            # 2) Construir nivel orden sobre el subconjunto filtrado
            orders_f = build_orders_from_lines(lines_f)

            # 3) Agregar a nivel restaurante
            g = orders_f.groupby(RESTAURANT_ID, dropna=False)

            rest = g.agg(
                orders=(ORDER_ID, "nunique"),
                n_lines=("n_lines", "sum"),
                items=("items", "sum"),
                gross_total=("gross_total", "sum"),
                net_total=("net_total", "sum"),
                tax_total=("tax_total", "sum"),
                tip_total=("tip_total", "sum"),
                ticket_net_avg=("ticket_net", "mean"),
                ticket_net_median=("ticket_net", "median"),
            ).reset_index()

            # Ratios agregados: sum(tip)/sum(net), sum(tax)/sum(net)
            rest["pct_tip_over_net"] = np.where(
                rest["net_total"] > 0, rest["tip_total"] / rest["net_total"], np.nan
            )
            rest["pct_tax_over_net"] = np.where(
                rest["net_total"] > 0, rest["tax_total"] / rest["net_total"], np.nan
            )

            # 4) Orden estable por defecto 
            sort_by = q.sort_by or "net_total"
            reverse = (q.sort_dir == "desc")
            rest = rest.sort_values(
                by=[sort_by, "orders", RESTAURANT_ID],
                ascending=[not reverse, not reverse, True],
                kind="mergesort",  # orden estable
            )

            # 5) top_k (incluye "auto")
            topk = None
            if q.top_k is not None:
                topk = resolve_top_k(q, AppConfig(), unique_n=int(len(rest))).value
                rest = rest.head(topk)

            # 6) Serializar a lista de dicts (valores crudos; la UI puede formatear)
            return rest.to_dict(orient="records") 

        data: List[Dict[str, Any]] = get_or_compute(_CACHE, key, _compute)
        return data
