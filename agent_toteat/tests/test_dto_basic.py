# agent_toteat/tests/test_dto_basic.py
from __future__ import annotations

from datetime import date
import pytest
from agent_toteat.tools.tabular.dto import TabularQuery

def test_query_parses_and_normalizes():
    q = TabularQuery(
        mode="over_time",
        time_grain="month",
        date_from=date(2025, 1, 1),
        date_to=date(2025, 10, 16),
        restaurants=[" R001 ", "R002", " "],
        products=None,
        sort_by="net_total",
        sort_dir="desc",
        top_k=None,
        scope=None,
        locale="es-MX",
        currency="MXN",
    )
    assert q.mode == "over_time"
    assert q.time_grain == "month"
    assert q.restaurants == ["R001", "R002"]
    assert q.products is None
    assert q.sort_dir == "desc"

def test_sort_dir_invalid():
    with pytest.raises(Exception):
        TabularQuery(mode="by_product", sort_dir="down")  # inválido
