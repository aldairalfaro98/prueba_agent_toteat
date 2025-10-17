# agent_toteat/tools/tabular/agg/over_time.py
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


def _resolve_period_col(grain: str) -> str:
    """Mapea el grain lógico al nombre de columna disponible en DF."""
    g = (grain or "month").strip().lower()
    if g in ("day", "daily"):
        return "date"        # DATE (datetime64[ns]), lo convertiremos a date-only string
    if g in ("week", "iso_week", "weekly"):
        return "iso_week"    # ej. '2025-W05'
    # default / 'month'
    return "year_month"      # ej. '2025-03'


class OverTimeHandler(IModeHandler):
    """Agregación por periodo (day | week | month)."""

    def run(self, repo: DataRepository, q: TabularQuery) -> List[Dict[str, Any]]:
        grain = q.time_grain or "month"
        key = build_query_key(q, extra={"handler": "over_time", "grain": grain})

        def _compute() -> List[Dict[str, Any]]:
            # 1) Partimos de LÍNEAS para que los filtros de productos se respeten
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

            # 2) Reconstruimos nivel orden sobre el subconjunto filtrado
            orders = build_orders_from_lines(df)
            if orders.empty:
                return []

            # 3) Determinar columna de periodo
            period_col = _resolve_period_col(grain)

            # Normalizar 'day' a string 'YYYY-MM-DD' amigable (no tz)
            if period_col == "date":
                period_series = pd.to_datetime(orders[DATE], errors="coerce").dt.date.astype(str)
            else:
                period_series = orders[period_col].astype(str)

            orders = orders.assign(period=period_series)

            # 4) Agregar por periodo
            g = orders.groupby("period", dropna=False)
            ot = g.agg(
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
            ot["pct_tip_over_net"] = np.where(
                ot["net_total"] > 0, ot["tip_total"] / ot["net_total"], np.nan
            )
            ot["pct_tax_over_net"] = np.where(
                ot["net_total"] > 0, ot["tax_total"] / ot["net_total"], np.nan
            )

            # 5) Orden CRONOLÓGICO ascendente
            #    Creamos 'period_start' como clave temporal para sort robusto.
            if period_col == "date":
                ot["period_start"] = pd.to_datetime(ot["period"], format="%Y-%m-%d", errors="coerce")
            elif period_col == "year_month":
                ot["period_start"] = pd.to_datetime(ot["period"] + "-01", errors="coerce")
            else:  # iso_week "YYYY-Www" -> tomamos lunes de esa semana ISO
                # Pandas no parsea directo 'YYYY-Www', hacemos pequeño truco:
                # Convertimos a 'YYYY-Www-1' (lunes), y usamos to_datetime con formato ISO week.
                # Nota: requiere pandas >= 1.1 para %G y %V. Alternativa: usar isocalendar manual.
                try:
                    ot["period_start"] = pd.to_datetime(
                        ot["period"].str.replace("W", "-") + "-1",
                        format="%G-%V-%u",
                        errors="coerce",
                    )
                except Exception:
                    # Fallback: ordenar por string si hubiera problemas
                    ot["period_start"] = ot["period"]

            ot = ot.sort_values(by="period_start", ascending=True, kind="mergesort")

            # 6) top_k: si llega, nos quedamos con los ÚLTIMOS N períodos (más recientes)
            if q.top_k is not None:
                topk = resolve_top_k(q, AppConfig(), unique_n=int(len(ot))).value
                ot = ot.tail(topk)

            # 7) Serializar
            return ot.drop(columns=["period_start"]).to_dict(orient="records")  # type: ignore[return-value]

        data: List[Dict[str, Any]] = get_or_compute(_CACHE, key, _compute)
        return data
