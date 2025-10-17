# agent_toteat/tools/tabular/dto.py
from __future__ import annotations

from datetime import date
from typing import Annotated, Literal, Optional, Union, List, Dict, Any

from pydantic import BaseModel, Field, field_validator

# —— Literales y tipos ——
ModeLiteral = Literal["over_time", "by_restaurant", "by_product", "tops", "diagnostics"]
TimeGrainLiteral = Literal["day", "iso_week", "month"]
ScopeLiteral = Literal["restaurant", "product"]
SortDirLiteral = Literal["asc", "desc"]
TopKType = Union[int, Literal["auto"], None]

class TabularQuery(BaseModel):
    """Contrato de entrada para la tool tabular."""
    mode: ModeLiteral
    time_grain: Optional[TimeGrainLiteral] = Field(
        default=None, description="Requerido cuando mode='over_time'."
    )
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    restaurants: Optional[List[str]] = None
    products: Optional[List[str]] = None

    # ranking / orden
    sort_by: Optional[str] = None
    sort_dir: SortDirLiteral = "desc"
    top_k: TopKType = None  # None => usar default; "auto" => se resolverá en validators/service
    scope: Optional[ScopeLiteral] = None  # solo para mode="tops"

    # opcionales de salida
    include_partial_period_flag: bool = True
    include_breakdown: Dict[str, bool] = Field(
        default_factory=lambda: {"by_restaurant": False, "by_product": False}
    )

    # locales / meta
    locale: str = "es-MX"
    currency: str = "MXN"

    @field_validator("sort_dir")
    @classmethod
    def _validate_sort_dir(cls, v: str) -> str:
        if v not in ("asc", "desc"):
            raise ValueError("sort_dir debe ser 'asc' o 'desc'.")
        return v

    @field_validator("restaurants", "products")
    @classmethod
    def _normalize_lists(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v is None:
            return None
        out = [s.strip() for s in v if isinstance(s, str) and s.strip()]
        return out or None  # si queda vacío, tratar como None (sin filtro)


class FilterEcho(BaseModel):
    """Se devuelve en la respuesta para transparencia de filtros aplicados."""
    time_grain: Optional[TimeGrainLiteral] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    restaurants: List[str] = Field(default_factory=list)
    products: List[str] = Field(default_factory=list)
    sort_by: Optional[str] = None
    sort_dir: SortDirLiteral = "desc"
    top_k: Optional[int] = None
    scope: Optional[ScopeLiteral] = None
    locale: str = "es-MX"
    currency: str = "MXN"


class MetaInfo(BaseModel):
    row_count: int
    generated_at: str
    currency: str
    locale: str


class TabularResult(BaseModel):
    """Contrato de salida: estable, serializable y amigable para UI."""
    ok: bool
    mode: ModeLiteral
    filters: FilterEcho
    warnings: List[str] = Field(default_factory=list)
    meta: MetaInfo
    data: List[Dict[str, Any]] = Field(default_factory=list)

    @staticmethod
    def empty(mode: ModeLiteral, filters: FilterEcho, meta: MetaInfo, warnings: Optional[List[str]] = None) -> "TabularResult":
        return TabularResult(ok=True, mode=mode, filters=filters, meta=meta, warnings=warnings or [], data=[])
