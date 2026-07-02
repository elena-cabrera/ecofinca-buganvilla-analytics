"""SQLite persistence for rural reservation analytics."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

import polars as pl

from rural_analytics.parser import ParsedReservation, reservations_to_polars

DEFAULT_DB_PATH = Path("data/rural.db")


def _connect(db_path: Path) -> sqlite3.Connection:
  """
  Open a SQLite connection with row factory enabled.

  Args:
      db_path (Path): Database file path.

  Returns:
      sqlite3.Connection: Open SQLite connection.
  """
  db_path.parent.mkdir(parents=True, exist_ok=True)
  connection = sqlite3.connect(db_path)
  connection.row_factory = sqlite3.Row
  return connection


def init_db(db_path: Path = DEFAULT_DB_PATH) -> None:
  """
  Create database tables when they do not exist.

  Args:
      db_path (Path): Database file path.
  """
  with _connect(db_path) as connection:
    connection.executescript(
      """
      CREATE TABLE IF NOT EXISTS archivos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL UNIQUE,
        mes INTEGER,
        anio INTEGER,
        fecha_importacion TEXT NOT NULL,
        reservas_importadas INTEGER NOT NULL DEFAULT 0,
        contenido BLOB NOT NULL
      );

      CREATE TABLE IF NOT EXISTS reservas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        archivo_id INTEGER NOT NULL,
        archivo_origen TEXT NOT NULL,
        hoja TEXT,
        casa TEXT,
        nombre TEXT,
        entrada TEXT,
        salida TEXT,
        pais TEXT,
        noches INTEGER,
        pax INTEGER,
        descuento REAL,
        precio REAL,
        comision REAL,
        forma_pago TEXT,
        tour_operador TEXT,
        fingerprint TEXT NOT NULL,
        precio_neto REAL,
        precio_por_noche REAL,
        precio_por_pax REAL,
        anio INTEGER,
        mes INTEGER,
        fila INTEGER,
        FOREIGN KEY (archivo_id) REFERENCES archivos(id) ON DELETE CASCADE
      );

      CREATE INDEX IF NOT EXISTS idx_reservas_fingerprint ON reservas(fingerprint);
      CREATE INDEX IF NOT EXISTS idx_reservas_entrada ON reservas(entrada);
      CREATE INDEX IF NOT EXISTS idx_reservas_archivo_id ON reservas(archivo_id);
      """
    )


def get_existing_fingerprints(db_path: Path = DEFAULT_DB_PATH) -> set[str]:
  """
  Load reservation fingerprints already stored in the database.

  Args:
      db_path (Path): Database file path.

  Returns:
      set[str]: Existing reservation fingerprints.
  """
  with _connect(db_path) as connection:
    rows = connection.execute("SELECT fingerprint FROM reservas").fetchall()
  return {row["fingerprint"] for row in rows}


def list_archivos(db_path: Path = DEFAULT_DB_PATH) -> pl.DataFrame:
  """
  Return imported workbook metadata.

  Args:
      db_path (Path): Database file path.

  Returns:
      pl.DataFrame: Imported files table.
  """
  with _connect(db_path) as connection:
    rows = connection.execute(
      """
      SELECT id, nombre, mes, anio, fecha_importacion, reservas_importadas
      FROM archivos
      ORDER BY fecha_importacion DESC
      """
    ).fetchall()
  if not rows:
    return pl.DataFrame(
      {
        "id": pl.Series([], dtype=pl.Int64),
        "nombre": pl.Series([], dtype=pl.Utf8),
        "mes": pl.Series([], dtype=pl.Int64),
        "anio": pl.Series([], dtype=pl.Int64),
        "fecha_importacion": pl.Series([], dtype=pl.Utf8),
        "reservas_importadas": pl.Series([], dtype=pl.Int64),
      }
    )
  return pl.DataFrame([dict(row) for row in rows])


def get_archivo_contenido(archivo_id: int, db_path: Path = DEFAULT_DB_PATH) -> tuple[str, bytes] | None:
  """
  Fetch stored workbook bytes for download.

  Args:
      archivo_id (int): Imported file identifier.
      db_path (Path): Database file path.

  Returns:
      tuple[str, bytes] | None: File name and binary content when found.
  """
  with _connect(db_path) as connection:
    row = connection.execute(
      "SELECT nombre, contenido FROM archivos WHERE id = ?",
      (archivo_id,),
    ).fetchone()
  if row is None:
    return None
  return row["nombre"], row["contenido"]


def delete_archivo(archivo_id: int, db_path: Path = DEFAULT_DB_PATH) -> None:
  """
  Delete an imported workbook and its reservations.

  Args:
      archivo_id (int): Imported file identifier.
      db_path (Path): Database file path.
  """
  with _connect(db_path) as connection:
    connection.execute("DELETE FROM reservas WHERE archivo_id = ?", (archivo_id,))
    connection.execute("DELETE FROM archivos WHERE id = ?", (archivo_id,))


def import_workbook(
  file_bytes: bytes,
  filename: str,
  reservations: list[ParsedReservation],
  *,
  mes: int | None = None,
  anio: int | None = None,
  db_path: Path = DEFAULT_DB_PATH,
) -> tuple[int, int]:
  """
  Persist a workbook and only insert reservations not already stored.

  Args:
      file_bytes (bytes): Raw uploaded workbook content.
      filename (str): Original file name.
      reservations (list[ParsedReservation]): Parsed reservations to import.
      mes (int | None): Optional workbook month metadata.
      anio (int | None): Optional workbook year metadata.
      db_path (Path): Database file path.

  Returns:
      tuple[int, int]: Imported file id and number of inserted reservations.
  """
  existing = get_existing_fingerprints(db_path)
  new_reservations = [item for item in reservations if item.fingerprint not in existing]
  dataframe = reservations_to_polars(new_reservations)

  with _connect(db_path) as connection:
    cursor = connection.execute(
      """
      INSERT INTO archivos (nombre, mes, anio, fecha_importacion, reservas_importadas, contenido)
      VALUES (?, ?, ?, ?, ?, ?)
      ON CONFLICT(nombre) DO UPDATE SET
        fecha_importacion = excluded.fecha_importacion,
        reservas_importadas = excluded.reservas_importadas,
        contenido = excluded.contenido,
        mes = excluded.mes,
        anio = excluded.anio
      """,
      (
        filename,
        mes,
        anio,
        datetime.now().isoformat(timespec="seconds"),
        len(new_reservations),
        file_bytes,
      ),
    )
    archivo_id = cursor.lastrowid
    if archivo_id is None:
      row = connection.execute(
        "SELECT id FROM archivos WHERE nombre = ?",
        (filename,),
      ).fetchone()
      archivo_id = int(row["id"])
      connection.execute("DELETE FROM reservas WHERE archivo_id = ?", (archivo_id,))

    for row in dataframe.iter_rows(named=True):
      connection.execute(
        """
        INSERT INTO reservas (
          archivo_id, archivo_origen, hoja, casa, nombre, entrada, salida, pais,
          noches, pax, descuento, precio, comision, forma_pago, tour_operador,
          fingerprint, precio_neto, precio_por_noche, precio_por_pax, anio, mes, fila
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
          archivo_id,
          row["archivo_origen"],
          row["hoja"],
          row["casa"],
          row["nombre"],
          row["entrada"].isoformat() if row["entrada"] else None,
          row["salida"].isoformat() if row["salida"] else None,
          row["pais"],
          row["noches"],
          row["pax"],
          row["descuento"],
          row["precio"],
          row["comision"],
          row["forma_pago"],
          row["tour_operador"],
          row["fingerprint"],
          row["precio_neto"],
          row["precio_por_noche"],
          row["precio_por_pax"],
          row["anio"],
          row["mes"],
          row["fila"],
        ),
      )

  return archivo_id, len(new_reservations)


def load_reservas(db_path: Path = DEFAULT_DB_PATH) -> pl.DataFrame:
  """
  Load all reservations from SQLite into Polars.

  Args:
      db_path (Path): Database file path.

  Returns:
      pl.DataFrame: Reservation dataframe for dashboard analytics.
  """
  with _connect(db_path) as connection:
    rows = connection.execute(
      """
      SELECT
        id, archivo_origen, hoja, casa, nombre, entrada, salida, pais,
        noches, pax, descuento, precio, comision, forma_pago, tour_operador,
        precio_neto, precio_por_noche, precio_por_pax, anio, mes
      FROM reservas
      ORDER BY entrada
      """
    ).fetchall()

  if not rows:
    return pl.DataFrame()

  dataframe = pl.DataFrame([dict(row) for row in rows])
  return dataframe.with_columns(
    pl.col("entrada").str.to_date(strict=False),
    pl.col("salida").str.to_date(strict=False),
  )
