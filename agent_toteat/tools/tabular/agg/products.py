# agent_toteat/tools/tabular/agg/products.py
from __future__ import annotations

from typing import Any, Dict, List
import logging
import numpy as np
import pandas as pd

from ..dto import TabularQuery
from ..loader import DataRepository
from .base import IModeHandler
from ..filters import apply_date_filter, apply_restaurants_filter, apply_products_filter
from ..cache import LRUCache, build_query_key, get_or_compute
from ..validators import resolve_top_k
from ..config import AppConfig
from ..schema import (
    RESTAURANT_ID,
    ORDER_ID,
    PRODUCT_ID,
    DATE,
    GROSS,
    NET,
    TAX,
    TIP,
    QTY,
)

logger = logging.getLogger(__name__)
_CACHE = LRUCache()


class ProductsHandler(IModeHandler):
    """KPIs por producto (nivel línea o (restaurante, producto) si scope='by_restaurant').

    Métricas:
      - qty_total: sum(quantity)
      - gross_total / net_total / tax_total / tip_total: sum
      - orders_distinct: órdenes distintas que incluyeron el producto
      - unit_price_net_avg: net_total / qty_total
    """

    def run(self, repo: DataRepository, q: TabularQuery) -> List[Dict[str, Any]]:
        # Incluir el 'scope' en la clave: 'product' vs 'by_restaurant'
        scope = (q.scope or "product").strip().lower()
        key = build_query_key(q, extra={"handler": "by_product", "scope": scope})

        def _compute() -> List[Dict[str, Any]]:
            # 1) Filtrado en LÍNEAS (para respetar product filters)
            lines = repo.lines
            if lines.empty:
                return []

            date_from = pd.to_datetime(q.date_from) if q.date_from else None
            date_to = pd.to_datetime(q.date_to) if q.date_to else None

            df = apply_date_filter(lines, date_from, date_to)
            df = apply_restaurants_filter(df, q.restaurants)
            df = apply_products_filter(df, q.products)

            if df.empty:
                return []

            # 2) order_uid para contar órdenes distintas por producto
            #    (resistente a 'order_id' repetido entre restaurantes)
            df = df.copy()
            df["order_uid"] = df[RESTAURANT_ID].astype(str) + ":" + df[ORDER_ID].astype(str)

            # 3) Agrupar por grano objetivo
            if scope == "by_restaurant":
                group_cols = [RESTAURANT_ID, PRODUCT_ID]
            else:
                group_cols = [PRODUCT_ID]

            g = df.groupby(group_cols, dropna=False)

            prod = g.agg(
                qty_total=(QTY, "sum"),
                gross_total=(GROSS, "sum"),
                net_total=(NET, "sum"),
                tax_total=(TAX, "sum"),
                tip_total=(TIP, "sum"),
                orders_distinct=("order_uid", "nunique"),
            ).reset_index()

            # 4) Derivados
            prod["unit_price_net_avg"] = np.where(
                prod["qty_total"] > 0, prod["net_total"] / prod["qty_total"], np.nan
            )

            # 5) Orden estable
            sort_by = q.sort_by or "net_total"
            reverse = (q.sort_dir == "desc")
            if scope == "by_restaurant":
                prod = prod.sort_values(
                    by=[sort_by, "orders_distinct", RESTAURANT_ID, PRODUCT_ID],
                    ascending=[not reverse, not reverse, True, True],
                    kind="mergesort",
                )
            else:
                prod = prod.sort_values(
                    by=[sort_by, "orders_distinct", PRODUCT_ID],
                    ascending=[not reverse, not reverse, True],
                    kind="mergesort",
                )

            # 6) top_k (incluye "auto")
            if q.top_k is not None:
                topk = resolve_top_k(q, AppConfig(), unique_n=int(len(prod))).value
                prod = prod.head(topk)

            # 7) Serializar
            return prod.to_dict(orient="records")  # type: ignore[return-value]

        data: List[Dict[str, Any]] = get_or_compute(_CACHE, key, _compute)
        return data
