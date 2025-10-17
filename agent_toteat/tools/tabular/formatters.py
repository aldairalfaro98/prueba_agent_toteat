# agent_toteat/tools/tabular/formatters.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from .dto import FilterEcho, MetaInfo, TabularQuery, TabularResult


def build_filter_echo(q: TabularQuery, top_k_resolved: Optional[int]) -> FilterEcho:
    return FilterEcho(
        time_grain=q.time_grain,
        date_from=q.date_from,
        date_to=q.date_to,
        restaurants=q.restaurants or [],
        products=q.products or [],
        sort_by=q.sort_by,
        sort_dir=q.sort_dir,
        top_k=top_k_resolved,
        scope=q.scope,
        locale=q.locale,
        currency=q.currency,
    )


def build_meta(row_count: int, locale: str, currency: str) -> MetaInfo:
    ts = datetime.now(tz=timezone.utc).isoformat(timespec="seconds")
    return MetaInfo(row_count=row_count, generated_at=ts, currency=currency, locale=locale)


def to_result(mode: str, filters: FilterEcho, data: List[Dict[str, Any]], warnings: Optional[List[str]] = None) -> TabularResult:
    meta = build_meta(row_count=len(data), locale=filters.locale, currency=filters.currency)
    return TabularResult(ok=True, mode=mode, filters=filters, warnings=warnings or [], meta=meta, data=data)
