# agent_toteat/tools/tabular/schema.py
from __future__ import annotations

from typing import Final, List, Tuple

# Nombres canónicos de columnas (evita strings sueltos en el resto del código)
RESTAURANT_ID: Final[str] = "restaurant_id"
ORDER_ID: Final[str] = "order_id"
CART_ID: Final[str] = "cart_id"
PRODUCT_ID: Final[str] = "product_id"
DATE: Final[str] = "date"
GROSS: Final[str] = "gross_sale"
NET: Final[str] = "net_sale"
TAX: Final[str] = "tax"
TIP: Final[str] = "tip"
QTY: Final[str] = "quantity"

# Conjuntos útiles
ID_COLS: Final[List[str]] = [RESTAURANT_ID, ORDER_ID, CART_ID, PRODUCT_ID]
LINE_NUMERIC_COLS: Final[List[str]] = [GROSS, NET, TAX, TIP, QTY]
ALL_COLS: Final[List[str]] = [*ID_COLS, DATE, *LINE_NUMERIC_COLS]

# Claves candidatas
ROW_KEY: Final[Tuple[str, str, str]] = (RESTAURANT_ID, ORDER_ID, CART_ID)
ORDER_KEY: Final[Tuple[str, str]] = (RESTAURANT_ID, ORDER_ID)

# Reglas contables (documentadas; la verificación vive en validators.py)
ACCOUNTING_RULE: Final[str] = "gross_sale = net_sale + tax"
