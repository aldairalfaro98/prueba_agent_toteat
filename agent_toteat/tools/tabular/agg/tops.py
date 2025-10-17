# agent_toteat/tools/tabular/agg/tops.py
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from ..dto import TabularQuery
from ..loader import DataRepository
from .base import IModeHandler
from .restaurants import RestaurantsHandler
from .products import ProductsHandler
from ..validators import resolve_top_k
from ..config import AppConfig
from ..cache import LRUCache, build_query_key, get_or_compute

logger = logging.getLogger(__name__)
_CACHE = LRUCache()


def _clone_without_sort_and_topk(q: TabularQuery, scope_override: Optional[str] = None) -> TabularQuery:
    """
    Clona una query Pydantic y limpia sort/top_k. Si se pide, cambia el scope.
    Usamos model_copy(update=...) (Pydantic v2).
    """
    update: Dict[str, Any] = {"sort_by": None, "sort_dir": None, "top_k": None}
    if scope_override is not None:
        update["scope"] = scope_override
    return q.model_copy(update=update)


class TopsHandler(IModeHandler):
    """
    Top-N genérico sobre restaurantes o productos. Reutiliza la agregación base:
      - scope='restaurant'   -> KPIs por restaurante
      - scope='product'      -> KPIs por producto (global)
      - scope='by_restaurant'-> KPIs por (restaurante, producto)  [si ProductsHandler lo soporta]

    Aplica sort y top_k al resultado base (orden estable).
    """

    _ALLOWED_SORT_KEYS = {
        "restaurant": {
            "orders", "n_lines", "items", "gross_total", "net_total", "tax_total", "tip_total",
            "ticket_net_avg", "ticket_net_median", "pct_tip_over_net", "pct_tax_over_net"
        },
        "product": {
            "qty_total", "orders_distinct", "gross_total", "net_total", "tax_total", "tip_total",
            "unit_price_net_avg"
        },
        # Si tu ProductsHandler soporta por (restaurante, producto), permitimos mismas métricas de producto:
        "by_restaurant": {
            "qty_total", "orders_distinct", "gross_total", "net_total", "tax_total", "tip_total",
            "unit_price_net_avg"
        },
    }

    def run(self, repo: DataRepository, q: TabularQuery) -> List[Dict[str, Any]]:
        # Normalización defensiva del scope
        raw_scope = (q.scope or "restaurant").strip().lower()
        scope = raw_scope
        if raw_scope in ("by_restaurant", "by-restaurant", "por_restaurante"):
            scope = "by_restaurant"
        elif raw_scope not in ("restaurant", "product", "by_restaurant"):
            logger.warning("Scope no reconocido '%s'; usando 'restaurant'", raw_scope)
            scope = "restaurant"

        # Clave de caché para tops (incluye scope y sort)
        key = build_query_key(q, extra={"handler": "tops", "scope": scope})

        def _compute() -> List[Dict[str, Any]]:
            # 1) Obtenemos base completo SIN sort/top_k para poder reusar caché entre variantes
            if scope == "restaurant":
                base_q = _clone_without_sort_and_topk(q, scope_override="restaurant")
                base = RestaurantsHandler().run(repo, base_q)
                id_keys = ("restaurant_id",)
            elif scope == "by_restaurant":
                # Nota: si tu ProductsHandler NO soporta 'by_restaurant', cambia a 'product' aquí
                base_q = _clone_without_sort_and_topk(q, scope_override="by_restaurant")
                base = ProductsHandler().run(repo, base_q)
                id_keys = ("restaurant_id", "product_id")
            else:  # 'product'
                base_q = _clone_without_sort_and_topk(q, scope_override="product")
                base = ProductsHandler().run(repo, base_q)
                id_keys = ("product_id",)

            if not base:
                return []

            # 2) Determinar métrica de orden
            desired_sort = q.sort_by or ("net_total" if scope != "product" else "net_total")
            allowed = self._ALLOWED_SORT_KEYS.get(scope, set())
            if desired_sort not in allowed:
                logger.warning("sort_by='%s' no válido para scope='%s'; usando 'net_total'", desired_sort, scope)
                desired_sort = "net_total"

            reverse = (q.sort_dir or "desc").lower() == "desc"
            secondary_key = "orders_distinct" if scope != "restaurant" else "orders"

            def _sort_key(row: Dict[str, Any]) -> Any:
                # Orden estable, tratando nulos
                return (
                    row.get(desired_sort) is None,
                    row.get(desired_sort),
                    row.get(secondary_key) is None,
                    row.get(secondary_key),
                    tuple(row.get(k) for k in id_keys),
                )

            base_sorted = sorted(base, key=_sort_key, reverse=reverse)

            # 4) Aplicar top_k (incluye 'auto' si tu resolve_top_k lo maneja)
            topk = resolve_top_k(q, AppConfig(), unique_n=len(base_sorted)).value if q.top_k is not None else len(base_sorted)
            return base_sorted[:topk]

        return get_or_compute(_CACHE, key, _compute)
