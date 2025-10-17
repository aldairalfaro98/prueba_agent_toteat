# agent_toteat/tools/tabular/exceptions.py
from __future__ import annotations

class TabularError(Exception):
    """Base para errores del dominio de la tool tabular."""

class InvalidParam(TabularError):
    """Parámetro inválido o faltante."""

class BadDateRange(TabularError):
    """date_from > date_to u otro rango inválido."""

class UnsupportedSort(TabularError):
    """sort_by no está soportado por el modo/handler actual."""

class SchemaMismatch(TabularError):
    """El CSV no cumple el esquema esperado."""
