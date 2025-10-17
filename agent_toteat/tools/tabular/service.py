# agent_toteat/tools/tabular/service.py
from __future__ import annotations

from typing import List, Dict, Any, Optional
import logging

from .config import AppConfig
from .dto import TabularQuery, TabularResult
from .exceptions import TabularError
from .formatters import build_filter_echo, to_result
from .loader import get_repo
from .validators import resolve_top_k, validate_query
from .agg.base import get_handler

logger = logging.getLogger(__name__)


def run_tabular_query(q: TabularQuery, app_cfg: Optional[AppConfig] = None) -> TabularResult:
    """
    Punto de entrada del core. Orquesta:
    validación -> repo -> handler -> payload (TabularResult).
    """
    cfg = app_cfg or AppConfig()
    try:
        validate_query(q)

        # Nota: para 'auto' real necesitaríamos unique_n por scope; se puede mejorar más adelante.
        topk = resolve_top_k(q, cfg, unique_n=None).value
        filters = build_filter_echo(q, top_k_resolved=topk)

        repo = get_repo(cfg)
        handler = get_handler(q.mode)

        data: List[Dict[str, Any]] = handler.run(repo, q)
        return to_result(mode=q.mode, filters=filters, data=data, warnings=[])

    except TabularError as te:
        logger.exception("Error de dominio en tabular service.")
        return TabularResult(
            ok=False,
            mode=q.mode,
            filters=build_filter_echo(q, top_k_resolved=None),
            warnings=[],
            meta=to_result(q.mode, build_filter_echo(q, None), []).meta,
            data=[{"error": str(te)}],
        )
    except NotImplementedError:
        logger.warning("Handler no implementado aún para mode=%s", q.mode)
        return to_result(
            mode=q.mode,
            filters=build_filter_echo(q, top_k_resolved=None),
            data=[],
            warnings=[f"Handler '{q.mode}' aún no implementado (stub)."],
        )
    except Exception as ex:
        logger.exception("Fallo no controlado en tabular service.")
        return TabularResult(
            ok=False,
            mode=q.mode,
            filters=build_filter_echo(q, top_k_resolved=None),
            warnings=[],
            meta=to_result(q.mode, build_filter_echo(q, None), []).meta,
            data=[{"error": "Unexpected error", "detail": str(ex)}],
        )
