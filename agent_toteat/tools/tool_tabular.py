# agent_toteat/tools/tool_tabular.py
from __future__ import annotations

from typing import Optional, Literal, List, Dict, Any
import dataclasses
from datetime import date, datetime
from decimal import Decimal
import math

# === Capa de dominio =========================================================
from .tabular.config import AppConfig
from .tabular.service import run_tabular_query
from .tabular.dto import TabularQuery

# Config por defecto
DEFAULT_CFG = AppConfig()

try:
    import numpy as np  
except Exception:  
    np = None  


# ------------------------------- Helpers -------------------------------------
def _norm_mode(x: Optional[str]) -> Optional[str]:
    if not x:
        return x
    v = x.lower().strip()
    # Normalizamos parametros
    mapping = {
        # tops
        "top": "tops",
        "ranking": "tops",
        "rank": "tops",
        "tops": "tops",
        # over_time
        "over_time": "over_time",
        "overtime": "over_time",
        "over-time": "over_time",
        "temporal": "over_time",
        # by_product / by_restaurant: 
        "by-product": "by_product",
        "por_producto": "by_product",
        "by-restaurant": "by_restaurant",
        "por_restaurante": "by_restaurant",
    }
    return mapping.get(v, v)


def _norm_scope(x: Optional[str]) -> Optional[str]:
    if x is None:
        return None
    v = x.lower().strip()
    mapping = {
        "restaurant": "restaurant",
        "restaurante": "restaurant",
        "by_restaurant": "restaurant",
        "by-restaurant": "restaurant",
        "por_restaurante": "restaurant",
        "product": "product",
        "producto": "product",
        "by_product": "product",
        "by-product": "product",
    }
    return mapping.get(v, v)


def _json_safe(obj: Any) -> Any:
    """Convierte recursivamente a tipos JSON-serializables."""
    # escalares especiales
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None

    # numpy
    if np is not None:
        if isinstance(obj, np.generic):
            return obj.item()
        if isinstance(obj, np.ndarray):
            return [_json_safe(x) for x in obj.tolist()]

    # estructuras
    if isinstance(obj, dict):
        return {str(k): _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_json_safe(v) for v in obj]

    # dataclass
    if dataclasses.is_dataclass(obj):
        return _json_safe(dataclasses.asdict(obj))

    # pydantic v2
    model_dump = getattr(obj, "model_dump", None)
    if callable(model_dump):
        return _json_safe(model_dump())

    # objetos con isoformat disponible
    iso = getattr(obj, "isoformat", None)
    if callable(iso):
        try:
            return iso()
        except Exception:
            pass

    return obj


def _normalize_result(result_obj: Any) -> Dict[str, Any]:
    """Normaliza y asegura JSON-safe para el payload de salida."""
    if isinstance(result_obj, dict):
        return _json_safe(result_obj)

    model_dump = getattr(result_obj, "model_dump", None)
    if callable(model_dump):
        return _json_safe(model_dump())

    if dataclasses.is_dataclass(result_obj):
        return _json_safe(dataclasses.asdict(result_obj))

    # fallback amable
    return _json_safe({
        "ok": False,
        "data": [],
        "error": f"Unserializable result: {type(result_obj).__name__}",
    })


# --------------------------- Tool pública (AFC) -------------------------------
def tabular_insights(
    mode: Literal["by_restaurant", "by_product", "over_time", "tops"],
    scope: Optional[Literal["restaurant", "product", "by_restaurant"]] = None,
    time_grain: Optional[Literal["day", "week", "month"]] = None,
    sort_by: Optional[str] = None,
    sort_dir: Literal["asc", "desc"] = "desc",
    top_k: Optional[int] = None,
    date_from: Optional[str] = None,   # "YYYY-MM-DD"
    date_to: Optional[str] = None,     # "YYYY-MM-DD"
    restaurants: Optional[List[str]] = None,
    products: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Tool pública AFC-friendly: devuelve KPIs/TOPs desde el CSV de órdenes.

    Parámetros:
      - mode: "tops" (ranking), "over_time" (series), "by_product"/"by_restaurant" (interpretados como KPIs).
      - scope: "restaurant" | "product". Se aceptan sinónimos como "by_restaurant" / "by_product".
      - time_grain: "day" | "iso_week" | "month" (solo para "over_time").
      - sort_by/sort_dir/top_k: criterio de ranking (para "tops" o cuando aplique).
      - date_from/date_to: rango "YYYY-MM-DD".
      - restaurants/products: filtros por id.

    Retorna:
      dict JSON-serializable con llaves: ok, mode, filters/meta, data, warnings, error.
    """
    # Normalizaciones para robustez frente al LLM
    mode_norm = _norm_mode(mode)
    scope_norm = _norm_scope(scope)

    # Validaciones ligeras
    if sort_dir not in ("asc", "desc"):
        return {"ok": False, "mode": mode_norm, "data": [], "error": f"sort_dir inválido: {sort_dir}"}
    if top_k is not None and (not isinstance(top_k, int) or top_k <= 0):
        return {"ok": False, "mode": mode_norm, "data": [], "error": f"top_k inválido: {top_k}"}

    # Mapear modos
    internal_mode = mode_norm

    # Construimos el DTO interno Pydantic (usa los valores normalizados)
    q = TabularQuery(
        mode=internal_mode,
        scope=scope_norm,         
        time_grain=time_grain,
        sort_by=sort_by,
        sort_dir=sort_dir,
        top_k=top_k,
        date_from=date_from,
        date_to=date_to,
        restaurants=restaurants or [],
        products=products or [],
    )

    try:
        result_obj = run_tabular_query(q=q, app_cfg=DEFAULT_CFG)
        return _normalize_result(result_obj)
    except Exception as exc:  
        return {
            "ok": False,
            "mode": internal_mode,
            "data": [],
            "error": f"{type(exc).__name__}: {exc}",
        }
