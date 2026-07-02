"""Value normalization helpers for reservation data."""

from __future__ import annotations

import re
from datetime import date, datetime

from rural_analytics.constants import KNOWN_CASAS, KNOWN_FORMAS_PAGO, KNOWN_OPERADORES, KNOWN_PAISES

_CASA_CANONICAL = {
    "olivo": "El Olivo",
    "el olivo": "El Olivo",
    "guayabo": "El Guayabo",
    "el guayabo": "El Guayabo",
    "almendro": "Almendro",
    "el almendro": "Almendro",
    "buganvilla": "Buganvilla",
    "el buganvilla": "Buganvilla",
}

_OPERADOR_CANONICAL = {
    "privado": "Privado",
    "booking": "Booking",
    "mts": "MTS",
    "airbnb": "Airbnb",
    "expedia": "Expedia",
    "vrbo": "VRBO",
    "directo": "Directo",
}

_PAGO_CANONICAL = {
    "efectivo": "Efectivo",
    "visa": "Visa",
    "transf.bco": "Transf.Bco",
    "transferencia": "Transf.Bco",
    "airbnb": "Airbnb",
    "booking": "Booking",
    "bizum": "Bizum",
    "paypal": "PayPal",
}

_PAISES_CANONICAL = {
    "espana": "España",
    "españa": "España",
    "reino unido": "Reino Unido",
    "paises bajos": "Países Bajos",
    "países bajos": "Países Bajos",
    "francia": "Francia",
    "italia": "Italia",
    "alemania": "Alemania",
    "portugal": "Portugal",
    "croacia": "Croacia",
    "belgica": "Bélgica",
    "bélgica": "Bélgica",
    "suiza": "Suiza",
    "irlanda": "Irlanda",
    "austria": "Austria",
    "polonia": "Polonia",
    "suecia": "Suecia",
    "noruega": "Noruega",
    "dinamarca": "Dinamarca",
    "estados unidos": "Estados Unidos",
    "canada": "Canadá",
    "canadá": "Canadá",
}


def _clean_text(value: object) -> str:
  if value is None:
    return ""
  text = str(value).strip()
  if text.lower() in {"", "nan", "none", "nat"}:
    return ""
  return text


def clean_cell(value: object) -> str:
  """
  Convert a cell value to a trimmed string.

  Args:
      value (object): Raw cell value from spreadsheet parsing.

  Returns:
      str: Trimmed string representation, empty when value is missing.
  """
  return _clean_text(value)


def parse_decimal(value: object) -> float | None:
    """
    Parse Spanish-formatted decimal numbers from spreadsheet cells.

    Args:
        value (object): Raw numeric or text value.

    Returns:
        float | None: Parsed decimal value, or None when parsing fails.
    """
    text = _clean_text(value)
    if not text:
        return None
    text = text.replace("€", "").replace(" ", "")
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def parse_date(value: object) -> date | None:
    """
    Parse reservation dates from common spreadsheet formats.

    Args:
        value (object): Raw date value from spreadsheet parsing.

    Returns:
        date | None: Parsed date, or None when parsing fails.
    """
    if value is None or _clean_text(value) == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = _clean_text(value)
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def normalize_casa(value: object) -> str:
    """
    Normalize house names to canonical labels.

    Args:
        value (object): Raw house name from spreadsheet parsing.

    Returns:
        str: Canonical house name, or title-cased original when unknown.
    """
    text = _clean_text(value)
    if not text:
        return ""
    key = text.lower()
    return _CASA_CANONICAL.get(key, text.strip())


def normalize_operador(value: object) -> str:
    """
    Normalize tour operator names to canonical labels.

    Args:
        value (object): Raw operator name from spreadsheet parsing.

    Returns:
        str: Canonical operator name, or title-cased original when unknown.
    """
    text = _clean_text(value)
    if not text:
        return ""
    key = text.lower()
    return _OPERADOR_CANONICAL.get(key, text.strip())


def normalize_forma_pago(value: object) -> str:
    """
    Normalize payment method labels to canonical values.

    Args:
        value (object): Raw payment method from spreadsheet parsing.

    Returns:
        str: Canonical payment method, or original text when unknown.
    """
    text = _clean_text(value)
    if not text:
        return ""
    key = text.lower()
    return _PAGO_CANONICAL.get(key, text.strip())


def normalize_pais(value: object) -> str:
    """
    Normalize country names to canonical labels.

    Args:
        value (object): Raw country name from spreadsheet parsing.

    Returns:
        str: Canonical country name, or original text when unknown.
    """
    text = _clean_text(value)
    if not text:
        return ""
    key = text.lower()
    return _PAISES_CANONICAL.get(key, text.strip())


def is_known_casa(value: str) -> bool:
    """
    Check whether a normalized house name is in the known catalog.

    Args:
        value (str): House name to validate.

    Returns:
        bool: True when the house is recognized.
    """
    return value.lower() in KNOWN_CASAS or normalize_casa(value).lower() in KNOWN_CASAS


def is_known_operador(value: str) -> bool:
    """
    Check whether a normalized operator name is in the known catalog.

    Args:
        value (str): Operator name to validate.

    Returns:
        bool: True when the operator is recognized.
    """
    return value.lower() in KNOWN_OPERADORES


def is_known_pais(value: str) -> bool:
    """
    Check whether a normalized country name is in the known catalog.

    Args:
        value (str): Country name to validate.

    Returns:
        bool: True when the country is recognized.
    """
    return value.lower() in KNOWN_PAISES or normalize_pais(value).lower() in {
        p.lower() for p in _PAISES_CANONICAL.values()
    }


def is_known_forma_pago(value: str) -> bool:
    """
    Check whether a normalized payment method is in the known catalog.

    Args:
        value (str): Payment method to validate.

    Returns:
        bool: True when the payment method is recognized.
    """
    return value.lower() in KNOWN_FORMAS_PAGO


def looks_like_price(value: object) -> bool:
    """
    Detect whether a cell value likely represents a monetary amount.

    Args:
        value (object): Raw cell value.

    Returns:
        bool: True when the value resembles a price.
    """
    number = parse_decimal(value)
    if number is None:
        return False
    return number >= 50


def looks_like_date(value: object) -> bool:
    """
    Detect whether a cell value likely represents a reservation date.

    Args:
        value (object): Raw cell value.

    Returns:
        bool: True when the value can be parsed as a date.
    """
    return parse_date(value) is not None


def looks_like_small_int(value: object, maximum: int = 60) -> bool:
    """
    Detect whether a cell value likely represents nights or pax.

    Args:
        value (object): Raw cell value.
        maximum (int): Upper bound for acceptable integer values.

    Returns:
        bool: True when the value is a small positive integer.
    """
    number = parse_decimal(value)
    if number is None:
        return False
    return number == int(number) and 0 < int(number) <= maximum


def reservation_fingerprint(
    casa: str,
    nombre: str,
    entrada: date | None,
    salida: date | None,
) -> str:
    """
    Build a stable fingerprint used to detect duplicate reservations.

    Args:
        casa (str): Canonical house name.
        nombre (str): Guest name.
        entrada (date | None): Check-in date.
        salida (date | None): Check-out date.

    Returns:
        str: Lowercase fingerprint string.
    """
    entrada_text = entrada.isoformat() if entrada else ""
    salida_text = salida.isoformat() if salida else ""
    return "|".join(
        [
            normalize_casa(casa).lower(),
            _clean_text(nombre).lower(),
            entrada_text,
            salida_text,
        ]
    )
