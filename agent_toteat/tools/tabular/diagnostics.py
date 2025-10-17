# agent_toteat/tools/tabular/diagnostics.py
from __future__ import annotations

from typing import Any, Dict, List
import logging
import pandas as pd

from .dto import TabularQuery
from .loader import DataRepository

logger = logging.getLogger(__name__)


class DiagnosticsHandler:
    """Devuelve diagnóstico básico del repositorio (stub)."""

    def run(self, repo: DataRepository, q: TabularQuery) -> List[Dict[str, Any]]:
        lines = repo.lines
        if lines.empty:
            return [{"message": "Repositorio vacío o CSV no cargado."}]
        out: Dict[str, Any] = {
            "rows": int(len(lines)),
            "columns": list(lines.columns),
        }
        # cardinalidades, claves, cobertura temporal real
        return [out]
