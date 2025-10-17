# agent_toteat/tools/tabular/time_features.py
from __future__ import annotations

import logging
import pandas as pd

from .schema import DATE

logger = logging.getLogger(__name__)


def add_time_features(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega columnas: year_month (YYYY-MM) e iso_week (YYYY-Www).
    Seguro de llamar varias veces (idempotente).
    """
    if df.empty or DATE not in df.columns:
        return df

    out = df.copy()
    if not pd.api.types.is_datetime64_any_dtype(out[DATE]):
        with pd.option_context("mode.use_inf_as_na", True):
            out[DATE] = pd.to_datetime(out[DATE], errors="coerce")

    if "year_month" not in out.columns:
        out["year_month"] = out[DATE].dt.to_period("M").astype(str)

    if "iso_week" not in out.columns:
        # ISO calendar: (year, week, weekday)
        iso = out[DATE].dt.isocalendar()
        out["iso_week"] = (iso["year"].astype(str) + "-W" + iso["week"].astype(str).str.zfill(2))

    return out
