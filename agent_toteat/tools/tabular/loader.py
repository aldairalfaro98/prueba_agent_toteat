# agent_toteat/tools/tabular/loader.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List
import logging
import pandas as pd

from .config import AppConfig
from .schema import (
    ALL_COLS,
    ID_COLS,
    DATE,
    GROSS,
    NET,
    TAX,
    TIP,
    QTY,
    RESTAURANT_ID,
    ORDER_ID,
    CART_ID,
    PRODUCT_ID,
)
from .exceptions import SchemaMismatch
from .time_features import add_time_features

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DataRepository:
    """Repositorio inmutable de dataframes base."""
    lines: pd.DataFrame   # grano línea (del CSV)
    orders: pd.DataFrame  # grano orden (derivado de lines)


class _LazyRepo:
    """Carga única (lazy) del repositorio. Evita recargar CSV en cada query."""
    def __init__(self) -> None:
        self._repo: Optional[DataRepository] = None

    def get(self, cfg: AppConfig) -> DataRepository:
        if self._repo is None:
            self._repo = self._load_repo(cfg.csv_path)
        return self._repo

    # ------------------------- Helpers de carga / coerción ---------------------

    @staticmethod
    def _select_engine() -> Optional[str]:
        """Usa pyarrow si está disponible; si no, deja que pandas elija."""
        try:
            import pyarrow  # noqa: F401
            return "pyarrow"
        except Exception:
            return None

    @staticmethod
    def _validate_schema(df: pd.DataFrame) -> None:
        """Garantiza que el CSV traiga las columnas esperadas."""
        missing = set(ALL_COLS) - set(df.columns)
        if missing:
            raise SchemaMismatch(f"Faltan columnas requeridas: {sorted(missing)}")

    @staticmethod
    def _coerce_types(df: pd.DataFrame) -> pd.DataFrame:
        """Coerción de tipos: IDs como string, fecha a datetime, numéricos seguros."""
        out = df.copy()

        # IDs
        for c in ID_COLS:
            if c in out.columns:
                out[c] = out[c].astype("string").str.strip()

        # Fecha
        if DATE in out.columns:
            out[DATE] = pd.to_datetime(out[DATE], format="%Y-%m-%d", errors="coerce")

        # Numéricos
        for c in [GROSS, NET, TAX, TIP]:
            if c in out.columns:
                out[c] = pd.to_numeric(out[c], errors="coerce")
        if QTY in out.columns:
            out[QTY] = pd.to_numeric(out[QTY], errors="coerce").astype("Int64")

        return out

    # --------------------- Construcción de nivel ORDEN (puro) ------------------

    @staticmethod
    def build_orders_from_lines(lines_df: pd.DataFrame) -> pd.DataFrame:
        """Construye un DataFrame a nivel orden desde un DF de líneas ya tipado.

        Columnas de salida:
        - restaurant_id, order_id
        - date_min, date_max, date (alias = date_min para grains)
        - n_lines, items
        - gross_total, net_total, tax_total, tip_total
        - ticket_net (= net_total)
        - pct_tip_over_net, pct_tax_over_net
        """
        if lines_df.empty:
            return pd.DataFrame(
                columns=[
                    RESTAURANT_ID, ORDER_ID,
                    "date_min", "date_max", DATE,
                    "n_lines", "items",
                    "gross_total", "net_total", "tax_total", "tip_total",
                    "ticket_net", "pct_tip_over_net", "pct_tax_over_net",
                ]
            )

        # Agregación por (restaurant_id, order_id)
        grp = lines_df.groupby([RESTAURANT_ID, ORDER_ID], dropna=False)

        orders = grp.agg(
            date_min=(DATE, "min"),
            date_max=(DATE, "max"),
            n_lines=(CART_ID, "count"),
            items=(QTY, "sum"),
            gross_total=(GROSS, "sum"),
            net_total=(NET, "sum"),
            tax_total=(TAX, "sum"),
            tip_total=(TIP, "sum"),
        ).reset_index()

        # Derivados
        orders["ticket_net"] = orders["net_total"]
        # Evitar divisiones por cero
        orders["pct_tip_over_net"] = orders.apply(
            lambda r: (r["tip_total"] / r["net_total"]) if (r["net_total"] and r["net_total"] != 0) else 0.0,
            axis=1,
        )
        orders["pct_tax_over_net"] = orders.apply(
            lambda r: (r["tax_total"] / r["net_total"]) if (r["net_total"] and r["net_total"] != 0) else 0.0,
            axis=1,
        )

        # Alias de fecha para grains (conveniencia)
        orders[DATE] = orders["date_min"]

        # Features temporales
        orders = add_time_features(orders)

        return orders

    # -------------------------- Carga total del repositorio --------------------

    def _load_repo(self, csv_path: Path) -> DataRepository:
        if not csv_path.exists():
            logger.warning("CSV no encontrado en %s. Repo vacío.", csv_path)
            empty_lines = pd.DataFrame(columns=ALL_COLS)
            empty_orders = self.build_orders_from_lines(empty_lines)
            return DataRepository(lines=empty_lines, orders=empty_orders)

        engine = self._select_engine()
        logger.info("Cargando CSV desde %s (engine=%s)", csv_path, engine or "default")

        # Nota: con engine="pyarrow" no usar low_memory
        lines = pd.read_csv(
            csv_path,
            usecols=ALL_COLS,  # asegura esquema exacto
            dtype={RESTAURANT_ID: "string", ORDER_ID: "string", CART_ID: "string", PRODUCT_ID: "string"},
            parse_dates=[DATE],
            date_format="%Y-%m-%d",
            engine=engine,
        )

        self._validate_schema(lines)
        lines = self._coerce_types(lines)
        lines = add_time_features(lines)

        orders = self.build_orders_from_lines(lines)

        logger.info("Repo cargado: lines=%s, orders=%s", lines.shape, orders.shape)
        return DataRepository(lines=lines, orders=orders)


_lazy_repo = _LazyRepo()


def get_repo(cfg: Optional[AppConfig] = None) -> DataRepository:
    """Punto de acceso al repositorio (singleton perezoso)."""
    cfg = cfg or AppConfig()
    return _lazy_repo.get(cfg)


# API pública reutilizable por handlers (exporta función pura)
build_orders_from_lines = _LazyRepo.build_orders_from_lines
