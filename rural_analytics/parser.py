"""Spreadsheet parsing for monthly reservation workbooks."""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import polars as pl

from rural_analytics.constants import COLUMN_ALIASES, MONTH_NAMES
from rural_analytics.normalization import (
    clean_cell,
    looks_like_date,
    looks_like_price,
    looks_like_small_int,
    normalize_casa,
    normalize_forma_pago,
    normalize_operador,
    normalize_pais,
    parse_date,
    parse_decimal,
    reservation_fingerprint,
)

EXPECTED_FIELDS = list(COLUMN_ALIASES.keys())


@dataclass
class ParsedReservation:
  """Normalized reservation extracted from a monthly sheet."""

  archivo_origen: str
  hoja: str
  casa: str
  nombre: str
  entrada: object
  salida: object
  pais: str
  noches: int | None
  pax: int | None
  descuento: float | None
  precio: float | None
  comision: float | None
  forma_pago: str
  tour_operador: str
  fingerprint: str
  fila: int
  warnings: list[str] = field(default_factory=list)


@dataclass
class ParseResult:
  """Outcome of parsing one uploaded workbook."""

  reservations: list[ParsedReservation]
  sheet_summaries: list[dict[str, object]]
  skipped_rows: int


def _normalize_header(value: object) -> str:
  """
  Normalize spreadsheet header labels for column matching.

  Args:
      value (object): Raw header cell value.

  Returns:
      str: Lowercased and trimmed header label.
  """
  text = "" if value is None else str(value)
  return re.sub(r"\s+", " ", text.strip().lower())


def _match_column(header: str) -> str | None:
  """
  Map a spreadsheet header to an internal field name.

  Args:
      header (str): Normalized header label.

  Returns:
      str | None: Internal field name when recognized.
  """
  for field_name, aliases in COLUMN_ALIASES.items():
    if header in aliases:
      return field_name

  if header.startswith("comisión") or header.startswith("comision"):
    return "comision"
  if header.startswith("dto"):
    return "descuento"
  if header.startswith("f-pago") or header.startswith("f. pago"):
    return "forma_pago"
  if header.startswith("tour operador"):
    return "tour_operador"

  return None


def _engine_for_filename(filename: str) -> str:
  """
  Select the pandas Excel engine based on file extension.

  Args:
      filename (str): Uploaded file name.

  Returns:
      str: Pandas engine identifier.
  """
  suffix = Path(filename).suffix.lower()
  if suffix == ".ods":
    return "odf"
  if suffix in {".xlsx", ".xlsm"}:
    return "openpyxl"
  raise ValueError("Formato no soportado. Usa .xlsx o .ods")


def _read_workbook_sheets(file_bytes: bytes, filename: str) -> dict[str, pd.DataFrame]:
  """
  Read all sheets from an uploaded workbook into pandas DataFrames.

  Args:
      file_bytes (bytes): Raw uploaded file content.
      filename (str): Original file name.

  Returns:
      dict[str, pd.DataFrame]: Sheet name to raw dataframe mapping.
  """
  engine = _engine_for_filename(filename)
  buffer = io.BytesIO(file_bytes)
  return pd.read_excel(buffer, sheet_name=None, header=None, engine=engine, dtype=object)


def _find_header_row(df: pd.DataFrame) -> tuple[int, dict[int, str]] | None:
  """
  Locate the header row and map column indexes to internal field names.

  Args:
      df (pd.DataFrame): Raw sheet dataframe without headers.

  Returns:
      tuple[int, dict[int, str]] | None: Header row index and column mapping.
  """
  for row_idx in range(min(len(df), 20)):
    mapping: dict[int, str] = {}
    for col_idx, value in enumerate(df.iloc[row_idx].tolist()):
      header = _normalize_header(value)
      field_name = _match_column(header)
      if field_name:
        mapping[col_idx] = field_name
    if {"casa", "entrada", "salida"}.issubset(set(mapping.values())):
      return row_idx, mapping
  return None


def _row_values(df: pd.DataFrame, row_idx: int, column_count: int) -> list[object]:
  """
  Extract a full row of cell values with trailing padding.

  Args:
      df (pd.DataFrame): Source sheet dataframe.
      row_idx (int): Row index to read.
      column_count (int): Minimum number of columns to return.

  Returns:
      list[object]: Row values padded to the requested column count.
  """
  values = df.iloc[row_idx].tolist()
  while len(values) < column_count:
    values.append(None)
  return values


def _repair_row(values: dict[str, object]) -> dict[str, object]:
  """
  Repair common column-shift issues found in monthly spreadsheets.

  Args:
      values (dict[str, object]): Parsed row values keyed by field name.

  Returns:
      dict[str, object]: Repaired row values.
  """
  repaired = dict(values)

  if repaired.get("precio") in (None, "") and looks_like_price(repaired.get("descuento")):
    repaired["precio"] = repaired["descuento"]
    repaired["descuento"] = None

  forma_pago = str(repaired.get("forma_pago") or "")
  operador = str(repaired.get("tour_operador") or "")
  if forma_pago.lower() in {"booking", "airbnb", "mts", "privado"} and operador.lower() in {
    "visa",
    "efectivo",
    "transf.bco",
    "transferencia",
    "bizum",
    "paypal",
  }:
    repaired["forma_pago"], repaired["tour_operador"] = operador, forma_pago

  return repaired


def _is_summary_row(values: dict[str, object]) -> bool:
  """
  Detect subtotal or empty rows that should not be imported.

  Args:
      values (dict[str, object]): Parsed row values keyed by field name.

  Returns:
      bool: True when the row should be skipped.
  """
  casa = clean_cell(values.get("casa"))
  nombre = clean_cell(values.get("nombre"))
  entrada = values.get("entrada")
  salida = values.get("salida")

  if casa and (looks_like_date(entrada) or looks_like_date(salida)):
    return False

  if not casa and not nombre:
    if looks_like_price(values.get("precio")) or looks_like_price(values.get("comision")):
      return True
    return True

  if not casa:
    return True

  return False


def _parse_row(
  values: dict[str, object],
  *,
  archivo_origen: str,
  hoja: str,
  fila: int,
) -> ParsedReservation | None:
  """
  Convert a repaired spreadsheet row into a normalized reservation.

  Args:
      values (dict[str, object]): Parsed row values keyed by field name.
      archivo_origen (str): Source workbook file name.
      hoja (str): Sheet name within the workbook.
      fila (int): 1-based spreadsheet row number.

  Returns:
      ParsedReservation | None: Parsed reservation, or None when row is skipped.
  """
  repaired = _repair_row(values)
  if _is_summary_row(repaired):
    return None

  casa = normalize_casa(repaired.get("casa"))
  nombre = clean_cell(repaired.get("nombre"))
  entrada = parse_date(repaired.get("entrada"))
  salida = parse_date(repaired.get("salida"))
  pais = normalize_pais(repaired.get("pais"))

  noches_value = parse_decimal(repaired.get("noches"))
  pax_value = parse_decimal(repaired.get("pax"))
  noches = int(noches_value) if noches_value is not None and noches_value == int(noches_value) else None
  pax = int(pax_value) if pax_value is not None and pax_value == int(pax_value) else None

  if noches is None and entrada and salida:
    noches = (salida - entrada).days

  descuento = parse_decimal(repaired.get("descuento"))
  precio = parse_decimal(repaired.get("precio"))
  comision = parse_decimal(repaired.get("comision"))
  forma_pago = normalize_forma_pago(repaired.get("forma_pago"))
  tour_operador = normalize_operador(repaired.get("tour_operador"))

  if not nombre and not entrada:
    return None

  return ParsedReservation(
    archivo_origen=archivo_origen,
    hoja=hoja,
    casa=casa,
    nombre=nombre,
    entrada=entrada,
    salida=salida,
    pais=pais,
    noches=noches,
    pax=pax,
    descuento=descuento,
    precio=precio,
    comision=comision,
    forma_pago=forma_pago,
    tour_operador=tour_operador,
    fingerprint=reservation_fingerprint(casa, nombre, entrada, salida),
    fila=fila,
  )


def _infer_month_from_sheet(sheet_name: str) -> int | None:
  """
  Infer calendar month number from a sheet name such as 'Marzo_2026'.

  Args:
      sheet_name (str): Workbook sheet name.

  Returns:
      int | None: Month number between 1 and 12 when recognized.
  """
  normalized = sheet_name.lower().replace("-", "_")
  for month_name, month_number in MONTH_NAMES.items():
    if month_name in normalized:
      return month_number
  return None


def parse_workbook(file_bytes: bytes, filename: str) -> ParseResult:
  """
  Parse all monthly sheets from an uploaded workbook.

  Args:
      file_bytes (bytes): Raw uploaded file content.
      filename (str): Original file name.

  Returns:
      ParseResult: Parsed reservations and per-sheet summary metadata.
  """
  sheets = _read_workbook_sheets(file_bytes, filename)
  reservations: list[ParsedReservation] = []
  sheet_summaries: list[dict[str, object]] = []
  skipped_rows = 0

  for sheet_name, df in sheets.items():
    header_info = _find_header_row(df)
    if header_info is None:
      sheet_summaries.append(
        {
          "hoja": sheet_name,
          "reservas": 0,
          "estado": "sin cabecera reconocida",
        }
      )
      continue

    header_row, column_mapping = header_info
    max_col = max(column_mapping.keys()) + 1
    sheet_count = 0

    for row_idx in range(header_row + 1, len(df)):
      raw_values = _row_values(df, row_idx, max_col)
      if not any(clean_cell(value) for value in raw_values):
        continue

      values = {field_name: None for field_name in EXPECTED_FIELDS}
      for col_idx, field_name in column_mapping.items():
        values[field_name] = raw_values[col_idx]

      parsed = _parse_row(
        values,
        archivo_origen=filename,
        hoja=sheet_name,
        fila=row_idx + 1,
      )
      if parsed is None:
        skipped_rows += 1
        continue

      reservations.append(parsed)
      sheet_count += 1

    sheet_summaries.append(
      {
        "hoja": sheet_name,
        "reservas": sheet_count,
        "mes": _infer_month_from_sheet(sheet_name),
        "estado": "ok" if sheet_count else "sin reservas",
      }
    )

  return ParseResult(
    reservations=reservations,
    sheet_summaries=sheet_summaries,
    skipped_rows=skipped_rows,
  )


def reservations_to_polars(reservations: list[ParsedReservation]) -> pl.DataFrame:
  """
  Convert parsed reservations into a Polars dataframe with calculated fields.

  Args:
      reservations (list[ParsedReservation]): Parsed reservation records.

  Returns:
      pl.DataFrame: Reservation dataframe ready for persistence and analytics.
  """
  rows = []
  for item in reservations:
    precio = item.precio or 0.0
    comision = item.comision or 0.0
    noches = item.noches or 0
    pax = item.pax or 0
    precio_neto = precio - comision
    precio_por_noche = precio / noches if noches else None
    precio_por_pax = precio / pax if pax else None
    entrada = item.entrada
    rows.append(
      {
        "archivo_origen": item.archivo_origen,
        "hoja": item.hoja,
        "casa": item.casa,
        "nombre": item.nombre,
        "entrada": entrada,
        "salida": item.salida,
        "pais": item.pais,
        "noches": item.noches,
        "pax": item.pax,
        "descuento": item.descuento,
        "precio": item.precio,
        "comision": item.comision,
        "forma_pago": item.forma_pago,
        "tour_operador": item.tour_operador,
        "fingerprint": item.fingerprint,
        "fila": item.fila,
        "precio_neto": precio_neto,
        "precio_por_noche": precio_por_noche,
        "precio_por_pax": precio_por_pax,
        "anio": entrada.year if entrada else None,
        "mes": entrada.month if entrada else None,
      }
    )

  if not rows:
    return pl.DataFrame(
      {
        "archivo_origen": pl.Series([], dtype=pl.Utf8),
        "hoja": pl.Series([], dtype=pl.Utf8),
        "casa": pl.Series([], dtype=pl.Utf8),
        "nombre": pl.Series([], dtype=pl.Utf8),
        "entrada": pl.Series([], dtype=pl.Date),
        "salida": pl.Series([], dtype=pl.Date),
        "pais": pl.Series([], dtype=pl.Utf8),
        "noches": pl.Series([], dtype=pl.Int64),
        "pax": pl.Series([], dtype=pl.Int64),
        "descuento": pl.Series([], dtype=pl.Float64),
        "precio": pl.Series([], dtype=pl.Float64),
        "comision": pl.Series([], dtype=pl.Float64),
        "forma_pago": pl.Series([], dtype=pl.Utf8),
        "tour_operador": pl.Series([], dtype=pl.Utf8),
        "fingerprint": pl.Series([], dtype=pl.Utf8),
        "fila": pl.Series([], dtype=pl.Int64),
        "precio_neto": pl.Series([], dtype=pl.Float64),
        "precio_por_noche": pl.Series([], dtype=pl.Float64),
        "precio_por_pax": pl.Series([], dtype=pl.Float64),
        "anio": pl.Series([], dtype=pl.Int64),
        "mes": pl.Series([], dtype=pl.Int64),
      }
    )

  return pl.DataFrame(rows)
