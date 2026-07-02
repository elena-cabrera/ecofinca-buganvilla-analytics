"""Validation warnings for reservation imports."""

from __future__ import annotations

from dataclasses import dataclass

from rural_analytics.normalization import (
    is_known_casa,
    is_known_forma_pago,
    is_known_operador,
    is_known_pais,
)
from rural_analytics.parser import ParsedReservation


@dataclass
class ValidationWarning:
  """Single validation warning raised during import preview."""

  tipo: str
  mensaje: str
  hoja: str
  fila: int
  nombre: str


def validate_reservations(
  reservations: list[ParsedReservation],
  existing_fingerprints: set[str],
) -> list[ValidationWarning]:
  """
  Build validation warnings for parsed reservations before import.

  Args:
      reservations (list[ParsedReservation]): Parsed reservations from workbook.
      existing_fingerprints (set[str]): Fingerprints already stored in SQLite.

  Returns:
      list[ValidationWarning]: Validation warnings to show in the import preview.
  """
  warnings: list[ValidationWarning] = []
  seen_fingerprints: set[str] = set()

  for reservation in reservations:
    base = {
      "hoja": reservation.hoja,
      "fila": reservation.fila,
      "nombre": reservation.nombre,
    }

    if reservation.entrada is None or reservation.salida is None:
      warnings.append(
        ValidationWarning(
          tipo="fecha_invalida",
          mensaje="Fechas de entrada o salida inválidas",
          **base,
        )
      )
    elif reservation.salida < reservation.entrada:
      warnings.append(
        ValidationWarning(
          tipo="salida_anterior",
          mensaje="La salida es anterior a la entrada",
          **base,
        )
      )

    if reservation.precio is None:
      warnings.append(
        ValidationWarning(
          tipo="precio_vacio",
          mensaje="Precio vacío o no reconocido",
          **base,
        )
      )

    if reservation.comision is not None and reservation.comision < 0:
      warnings.append(
        ValidationWarning(
          tipo="comision_negativa",
          mensaje="Comisión negativa",
          **base,
        )
      )

    if reservation.pais and not is_known_pais(reservation.pais):
      warnings.append(
        ValidationWarning(
          tipo="pais_desconocido",
          mensaje=f"País desconocido: {reservation.pais}",
          **base,
        )
      )

    if reservation.tour_operador and not is_known_operador(reservation.tour_operador):
      warnings.append(
        ValidationWarning(
          tipo="operador_desconocido",
          mensaje=f"Operador desconocido: {reservation.tour_operador}",
          **base,
        )
      )

    if reservation.casa and not is_known_casa(reservation.casa):
      warnings.append(
        ValidationWarning(
          tipo="casa_desconocida",
          mensaje=f"Casa desconocida: {reservation.casa}",
          **base,
        )
      )

    if reservation.forma_pago and not is_known_forma_pago(reservation.forma_pago):
      warnings.append(
        ValidationWarning(
          tipo="forma_pago_desconocida",
          mensaje=f"Forma de pago desconocida: {reservation.forma_pago}",
          **base,
        )
      )

    if reservation.fingerprint in existing_fingerprints:
      warnings.append(
        ValidationWarning(
          tipo="duplicada_existente",
          mensaje="Reserva duplicada (ya existe en el histórico)",
          **base,
        )
      )
    elif reservation.fingerprint in seen_fingerprints:
      warnings.append(
        ValidationWarning(
          tipo="duplicada_archivo",
          mensaje="Reserva duplicada dentro del archivo",
          **base,
        )
      )

    seen_fingerprints.add(reservation.fingerprint)

  return warnings
