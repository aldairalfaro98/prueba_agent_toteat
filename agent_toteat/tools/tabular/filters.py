# agent_toteat/tools/tabular/filters.py
from __future__ import annotations

from typing import Iterable, Optional, Sequence
import pandas as pd

from .schema import DATE, RESTAURANT_ID, PRODUCT_ID


def apply_date_filter(df: pd.DataFrame, date_from: Optional[pd.Timestamp], date_to: Optional[pd.Timestamp]) -> pd.DataFrame:
    if df.empty or DATE not in df.columns:
        return df
    out = df
    if date_from is not None:
        out = out[out[DATE] >= pd.to_datetime(date_from)]
    if date_to is not None:
        out = out[out[DATE] <= pd.to_datetime(date_to)]
    return out


def apply_restaurants_filter(df: pd.DataFrame, restaurants: Optional[Sequence[str]]) -> pd.DataFrame:
    if df.empty or not restaurants or RESTAURANT_ID not in df.columns:
        return df
    return df[df[RESTAURANT_ID].isin(list(restaurants))]


def apply_products_filter(df: pd.DataFrame, products: Optional[Sequence[str]]) -> pd.DataFrame:
    if df.empty or not products or PRODUCT_ID not in df.columns:
        return df
    return df[df[PRODUCT_ID].isin(list(products))]
