# agent_toteat/tools/tabular/config.py
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Final

# —— Rutas ——
DATA_DIR: Final[Path] = Path(os.getenv("GASTROSOFT_DATA_DIR", ".")) 
CSV_FILENAME: Final[str] = os.getenv("GASTROSOFT_SALES_CSV", "Prueba Tecnica AI Engineer/gastrosoft_sales_2025.csv")
CSV_PATH: Final[Path] = DATA_DIR / CSV_FILENAME

# —— Localización ——
DEFAULT_LOCALE: Final[str] = os.getenv("TABULAR_LOCALE", "es-MX")
DEFAULT_CURRENCY: Final[str] = os.getenv("TABULAR_CURRENCY", "MXN")

# —— Top-K y orden ——
TOP_K_DEFAULT: Final[int] = int(os.getenv("TABULAR_TOP_K_DEFAULT", "10"))
TOP_K_MIN:     Final[int] = int(os.getenv("TABULAR_TOP_K_MIN", "5"))
TOP_K_MAX:     Final[int] = int(os.getenv("TABULAR_TOP_K_MAX", "100"))

# —— Varios ——
WARN_PARTIAL_PERIODS: Final[bool] = os.getenv("TABULAR_WARN_PARTIALS", "true").lower() == "true"


@dataclass(frozen=True)
class AppConfig:
    """Snapshot inmutable de configuración consumida por el servicio."""
    csv_path: Path = CSV_PATH
    locale: str = DEFAULT_LOCALE
    currency: str = DEFAULT_CURRENCY
    top_k_default: int = TOP_K_DEFAULT
    top_k_min: int = TOP_K_MIN
    top_k_max: int = TOP_K_MAX
    warn_partials: bool = WARN_PARTIAL_PERIODS
