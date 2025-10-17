# agent_toteat/tools/tabular/i18n.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping, MutableMapping, Optional


@dataclass(frozen=True)
class LocaleConfig:
    """Configuración mínima de formato.
    No usamos Babel para evitar dependencia; ajusta aquí símbolos y separadores.
    """
    locale: str = "es-MX"
    currency: str = "MXN"
    currency_symbol: str = "MXN$"  # puedes cambiar a "$" si así lo prefieres
    decimal_sep: str = "."
    thousand_sep: str = ","


DEFAULT_LOCALE = LocaleConfig()


def format_currency(value: Optional[float], cfg: LocaleConfig = DEFAULT_LOCALE, ndigits: int = 2) -> str:
    """Formatea un float como moneda. Si value es None, devuelve '-'."""
    if value is None:
        return "-"
    # Sencillo: símbolo + número con miles y decimales (usamos separadores simples)
    # Nota: Si más adelante quieres locale real, este es el punto a adaptar.
    q = round(float(value), ndigits)
    # Insertar separadores de miles de forma básica:
    # "{:,.2f}" usa separador US, lo sustituimos por el deseado si difiere.
    s = f"{q:,.{ndigits}f}"
    if DEFAULT_LOCALE.thousand_sep != "," or DEFAULT_LOCALE.decimal_sep != ".":
        s = s.replace(",", "X").replace(".", cfg.decimal_sep).replace("X", cfg.thousand_sep)
    return f"{cfg.currency_symbol}{s}"


def format_percent(value: Optional[float], ndigits: int = 2) -> str:
    """Formatea un float [0..1] como porcentaje '12.34%'."""
    if value is None:
        return "-"
    q = round(float(value) * 100.0, ndigits)
    return f"{q:.{ndigits}f}%"


def add_formatted_fields(
    row: Mapping[str, object],
    currency_fields: Iterable[str],
    percent_fields: Iterable[str],
    cfg: LocaleConfig = DEFAULT_LOCALE,
    suffix: str = "_fmt",
) -> Dict[str, object]:
    """Devuelve un nuevo dict con campos formateados añadidos para UI.
    Ej.: 'net_total' -> 'net_total_fmt'
    """
    out: Dict[str, object] = dict(row)
    for c in currency_fields:
        v = row.get(c)  # type: ignore[assignment]
        out[f"{c}{suffix}"] = format_currency(v if isinstance(v, (int, float)) else None, cfg=cfg)
    for p in percent_fields:
        v = row.get(p)  # type: ignore[assignment]
        out[f"{p}{suffix}"] = format_percent(v if isinstance(v, (int, float)) else None)
    return out
