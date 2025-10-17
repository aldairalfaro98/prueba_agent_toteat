# agent_toteat/tools/tabular/cache.py
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Callable, Dict, Hashable, Iterable, Optional, Tuple

from .dto import TabularQuery


@dataclass(frozen=True)
class CacheConfig:
    max_items: int = 128  # ajustable si hiciera falta


class LRUCache:
    """Cache LRU en memoria con claves hashables. Thread-unsafe por simplicidad."""
    def __init__(self, cfg: CacheConfig | None = None) -> None:
        self._cfg = cfg or CacheConfig()
        self._store: OrderedDict[Hashable, Any] = OrderedDict()

    def get(self, key: Hashable) -> Any:
        if key not in self._store:
            return None
        val = self._store.pop(key)
        self._store[key] = val  # move to end (most-recent)
        return val

    def put(self, key: Hashable, value: Any) -> None:
        if key in self._store:
            self._store.pop(key)
        self._store[key] = value
        if len(self._store) > self._cfg.max_items:
            self._store.popitem(last=False)  # evict least-recently used

    def clear(self) -> None:
        self._store.clear()


def _normalized_list(xs: Optional[Iterable[str]]) -> Tuple[str, ...]:
    """Normaliza listas para construir claves deterministas."""
    if not xs:
        return tuple()
    return tuple(sorted(s.strip() for s in xs if isinstance(s, str) and s.strip()))


def build_query_key(q: TabularQuery, mode_override: Optional[str] = None, extra: Optional[Dict[str, Any]] = None) -> Tuple[Any, ...]:
    """Convierte la query en una clave hashable (tuple) para cachear resultados.
    - No incluye campos irrelevantes para el cálculo (p. ej. locale/currency si no afectan).
    - 'extra' permite añadir parámetros específicos del handler (e.g., agrupaciones).
    """
    key = (
        mode_override or q.mode,
        q.time_grain,
        q.date_from,
        q.date_to,
        _normalized_list(q.restaurants),
        _normalized_list(q.products),
        q.sort_by,
        q.sort_dir,
        q.top_k,    # "auto" se resuelve antes si decides; puedes quitarlo y usar el valor resuelto
        q.scope,
    )
    if extra:
        extra_items = tuple(sorted(extra.items()))
        return key + extra_items
    return key


def get_or_compute(cache: LRUCache, key: Tuple[Any, ...], compute_fn: Callable[[], Any]) -> Any:
    """Devuelve el valor cacheado si existe; si no, lo calcula, lo guarda y lo devuelve."""
    val = cache.get(key)
    if val is not None:
        return val
    val = compute_fn()
    cache.put(key, val)
    return val
