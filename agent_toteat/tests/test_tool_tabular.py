# agent_toteat/tests/test_tool_tabular.py
from __future__ import annotations

"""
Tests de integración ligera para agent_toteat.tools.tool_tabular.tabular_insights.

Principios:
- Datos sintéticos mínimos (rápidos y deterministas).
- Validación del contrato: ok/count/data y forma básica de los registros.
- Verificación de orden y top_k en modos clave.
- Manejo de errores (modo inválido, esquema inválido).
"""

from pathlib import Path
from typing import Dict, Any, List
import csv
import pytest

from agent_toteat.tools.tool_tabular import tabular_insights
from agent_toteat.tools.tabular.config import AppConfig


# ------------------------------ Helpers --------------------------------------


def _write_csv(path: Path, rows: List[List[Any]]) -> None:
    """Escribe CSV con encabezados esperados."""
    headers = [
        "restaurant_id",
        "order_id",
        "cart_id",
        "product_id",
        "date",
        "gross_sale",
        "net_sale",
        "tax",
        "tip",
        "quantity",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)


@pytest.fixture()
def mini_csv(tmp_path: Path) -> Path:
    """
    CSV sintético con 2 restaurantes, 3 órdenes, 3 productos y 2 meses.
    Propósito: cubrir agregaciones básicas y top_k/orden cronológico.
    """
    p = tmp_path / "mini.csv"
    rows = [
        # rest,   order,     cart,    prod,   date        gross   net     tax   tip    qty
        ["R001", "O001", "C1", "P001", "2025-05-10", 100.00,  85.00,  15.00,  5.00,  1],
        ["R001", "O001", "C2", "P002", "2025-05-10", 200.00, 170.00,  30.00,  8.00,  2],
        ["R001", "O002", "C3", "P001", "2025-06-05", 150.00, 127.50, 22.50,  6.00,  3],
        ["R002", "O010", "C9", "P002", "2025-06-05", 300.00, 255.00, 45.00, 10.00,  4],
        ["R002", "O010", "C8", "P003", "2025-06-05", 120.00, 102.00, 18.00,  2.00,  1],
    ]
    _write_csv(p, rows)
    return p


def _cfg_for(path: Path) -> AppConfig:
    """Configura la tool para leer el CSV sintético temporal."""
    return AppConfig(csv_path=path)


# ------------------------------ Tests: happy paths ----------------------------


def test_by_restaurant_basic(mini_csv: Path) -> None:
    payload: Dict[str, Any] = {
        "mode": "by_restaurant",
        "sort_by": "net_total",
        "sort_dir": "desc",
        "top_k": 5,
    }
    out = tabular_insights(payload, app_cfg=_cfg_for(mini_csv))
    assert out["ok"] is True
    assert out["count"] == len(out["data"]) > 0

    # Debe contener claves agregadas conocidas
    row0 = out["data"][0]
    for key in ("restaurant_id", "orders", "gross_total", "net_total", "ticket_net_avg"):
        assert key in row0

    # Orden no creciente por net_total
    nets = [r["net_total"] for r in out["data"]]
    assert all(nets[i] >= nets[i + 1] for i in range(len(nets) - 1))


def test_by_product_basic(mini_csv: Path) -> None:
    payload = {
        "mode": "by_product",
        "sort_by": "net_total",
        "sort_dir": "desc",
        "top_k": 10,
    }
    out = tabular_insights(payload, app_cfg=_cfg_for(mini_csv))
    assert out["ok"] is True
    assert out["count"] == len(out["data"]) > 0
    row0 = out["data"][0]
    for key in ("product_id", "qty_total", "net_total", "orders_distinct", "unit_price_net_avg"):
        assert key in row0


def test_over_time_month_last_two(mini_csv: Path) -> None:
    payload = {
        "mode": "over_time",
        "time_grain": "month",
        "top_k": 2,  # últimos 2 meses
    }
    out = tabular_insights(payload, app_cfg=_cfg_for(mini_csv))
    assert out["ok"] is True
    assert out["count"] == 2
    periods = [r["period"] for r in out["data"]]
    # Deben venir en orden cronológico ascendente (p.ej. ["2025-05","2025-06"])
    assert periods == sorted(periods)


def test_tops_restaurant_by_net(mini_csv: Path) -> None:
    payload = {
        "mode": "tops",
        "scope": "restaurant",
        "sort_by": "net_total",
        "sort_dir": "desc",
        "top_k": 1,
    }
    out = tabular_insights(payload, app_cfg=_cfg_for(mini_csv))
    assert out["ok"] is True
    assert out["count"] == 1
    assert "restaurant_id" in out["data"][0]


# ------------------------------ Tests: errores/defensivos ---------------------


def test_invalid_mode_returns_ok_false(mini_csv: Path) -> None:
    payload = {"mode": "no_such_mode"}
    out = tabular_insights(payload, app_cfg=_cfg_for(mini_csv))
    assert out["ok"] is False
    assert "error" in out and isinstance(out["error"], str)


def test_invalid_schema_returns_ok_false(tmp_path: Path) -> None:
    # CSV sin columnas requeridas
    bad = tmp_path / "bad.csv"
    with bad.open("w", encoding="utf-8") as f:
        f.write("colA,colB\n1,2\n")
    payload = {"mode": "by_restaurant"}
    out = tabular_insights(payload, app_cfg=_cfg_for(bad))
    assert out["ok"] is False
    assert "error" in out and isinstance(out["error"], str)
