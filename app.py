"""Streamlit POC for rural house reservation analytics."""

from __future__ import annotations

import io
import re

import polars as pl
import streamlit as st

from rural_analytics import charts, db
from rural_analytics.constants import MONTH_NAMES
from rural_analytics.parser import parse_workbook
from rural_analytics.validators import validate_reservations

st.set_page_config(
  page_title="Ecofinca Buganvilla Analytics",
  page_icon="🏡",
  layout="wide",
)

MONTH_LABELS = {value: name.capitalize() for name, value in MONTH_NAMES.items()}


def _infer_workbook_period(filename: str, sheet_summaries: list[dict[str, object]]) -> tuple[int | None, int | None]:
  """
  Infer workbook month and year from filename or sheet names.

  Args:
      filename (str): Uploaded workbook file name.
      sheet_summaries (list[dict[str, object]]): Parsed sheet summaries.

  Returns:
      tuple[int | None, int | None]: Inferred month and year.
  """
  year_match = re.search(r"(20\d{2})", filename)
  anio = int(year_match.group(1)) if year_match else None

  mes = None
  for summary in sheet_summaries:
    sheet_month = summary.get("mes")
    if isinstance(sheet_month, int):
      mes = sheet_month
      break

  if mes is None:
    lowered = filename.lower()
    for month_name, month_number in MONTH_NAMES.items():
      if month_name in lowered:
        mes = month_number
        break

  return mes, anio


def _apply_filters(dataframe: pl.DataFrame) -> pl.DataFrame:
  """
  Apply sidebar filters to the reservation dataframe.

  Args:
      dataframe (pl.DataFrame): Full reservation dataframe.

  Returns:
      pl.DataFrame: Filtered reservation dataframe.
  """
  if dataframe.is_empty():
    return dataframe

  filtered = dataframe

  min_date = filtered.select(pl.col("entrada").min()).item()
  max_date = filtered.select(pl.col("salida").max()).item()
  if min_date and max_date:
    date_range = st.sidebar.date_input(
      "Rango de fechas (entrada/salida)",
      value=(min_date, max_date),
      min_value=min_date,
      max_value=max_date,
    )
    if isinstance(date_range, tuple) and len(date_range) == 2:
      start, end = date_range
      filtered = filtered.filter(
        (pl.col("entrada") >= start) | (pl.col("salida") >= start)
      ).filter(
        (pl.col("entrada") <= end) | (pl.col("salida") <= end)
      )

  years = sorted(filtered.select("anio").drop_nulls().unique().to_series().to_list())
  if years:
    selected_years = st.sidebar.multiselect("Año", options=years, default=years)
    if selected_years:
      filtered = filtered.filter(pl.col("anio").is_in(selected_years))

  months = sorted(filtered.select("mes").drop_nulls().unique().to_series().to_list())
  if months:
    month_options = {MONTH_LABELS.get(month, str(month)): month for month in months}
    selected_month_labels = st.sidebar.multiselect(
      "Mes",
      options=list(month_options.keys()),
      default=list(month_options.keys()),
    )
    selected_months = [month_options[label] for label in selected_month_labels]
    if selected_months:
      filtered = filtered.filter(pl.col("mes").is_in(selected_months))

  for label, column in [
    ("Casa", "casa"),
    ("Tour operador", "tour_operador"),
    ("Nacionalidad", "pais"),
  ]:
    values = sorted(
      filtered.select(column)
      .drop_nulls()
      .filter(pl.col(column) != "")
      .unique()
      .to_series()
      .to_list()
    )
    if values:
      selected = st.sidebar.multiselect(label, options=values, default=values)
      if selected:
        filtered = filtered.filter(pl.col(column).is_in(selected))

  return filtered


def _render_kpis(dataframe: pl.DataFrame) -> None:
  """
  Render dashboard KPI cards.

  Args:
      dataframe (pl.DataFrame): Filtered reservation dataframe.
  """
  total_reservas = dataframe.height
  total_noches = dataframe.select(pl.col("noches").fill_null(0).sum()).item() or 0
  total_pax = dataframe.select(pl.col("pax").fill_null(0).sum()).item() or 0
  ingresos = dataframe.select(pl.col("precio").fill_null(0).sum()).item() or 0.0
  comision = dataframe.select(pl.col("comision").fill_null(0).sum()).item() or 0.0
  neto = dataframe.select(pl.col("precio_neto").fill_null(0).sum()).item() or 0.0
  precio_medio_noche = (
    dataframe.filter(pl.col("precio_por_noche").is_not_null())
    .select(pl.col("precio_por_noche").mean())
    .item()
  )
  estancia_media = (
    dataframe.filter(pl.col("noches").is_not_null())
    .select(pl.col("noches").mean())
    .item()
  )
  pax_medio = (
    dataframe.filter(pl.col("pax").is_not_null()).select(pl.col("pax").mean()).item()
  )

  row1 = st.columns(5)
  row1[0].metric("Reservas", f"{total_reservas:,}")
  row1[1].metric("Noches", f"{total_noches:,}")
  row1[2].metric("Pax", f"{total_pax:,}")
  row1[3].metric("Ingresos brutos", f"€{ingresos:,.2f}")
  row1[4].metric("Comisión total", f"€{comision:,.2f}")

  row2 = st.columns(4)
  row2[0].metric("Ingresos netos", f"€{neto:,.2f}")
  row2[1].metric(
    "Precio medio / noche",
    f"€{precio_medio_noche:,.2f}" if precio_medio_noche else "—",
  )
  row2[2].metric(
    "Estancia media",
    f"{estancia_media:.1f}" if estancia_media else "—",
  )
  row2[3].metric("Pax medio / reserva", f"{pax_medio:.1f}" if pax_medio else "—")


def page_dashboard() -> None:
  """Render the analytics dashboard page."""
  st.title("Dashboard")
  st.caption("Histórico de reservas de Ecofinca Buganvilla")

  dataframe = db.load_reservas()
  if dataframe.is_empty():
    st.info("No hay reservas importadas todavía. Ve a Archivos para subir un Excel.")
    return

  filtered = _apply_filters(dataframe)
  _render_kpis(filtered)

  st.subheader("Evolución temporal")
  col1, col2 = st.columns(2)
  col1.plotly_chart(charts.monthly_bar(filtered, "precio", "Ingresos por mes"), width="stretch")
  col2.plotly_chart(charts.monthly_bar(filtered, "noches", "Noches por mes"), width="stretch")
  col3, col4 = st.columns(2)
  col3.plotly_chart(charts.monthly_count(filtered, "Reservas por mes"), width="stretch")
  col4.plotly_chart(
    charts.yearly_comparison(filtered, "precio", "Comparativa ingresos entre años"),
    width="stretch",
  )

  st.subheader("Distribuciones")
  col1, col2, col3 = st.columns(3)
  col1.plotly_chart(charts.distribution_bar(filtered, "pais", "Nacionalidades"), width="stretch")
  col2.plotly_chart(charts.distribution_bar(filtered, "casa", "Casas"), width="stretch")
  col3.plotly_chart(
    charts.distribution_bar(filtered, "tour_operador", "Tour operadores"),
    width="stretch",
  )
  col4, col5 = st.columns(2)
  col4.plotly_chart(
    charts.distribution_bar(filtered, "forma_pago", "Forma de pago"),
    width="stretch",
  )
  col5.plotly_chart(charts.distribution_bar(filtered, "noches", "Duración estancias"), width="stretch")
  st.plotly_chart(charts.distribution_bar(filtered, "pax", "Tamaño de grupos (Pax)"), width="stretch")

  st.subheader("Rentabilidad")
  col1, col2 = st.columns(2)
  col1.plotly_chart(charts.revenue_by_dimension(filtered, "casa", "Ingresos por casa"), width="stretch")
  col2.plotly_chart(
    charts.revenue_by_dimension(filtered, "tour_operador", "Ingresos por operador"),
    width="stretch",
  )
  col3, col4 = st.columns(2)
  col3.plotly_chart(charts.commission_by_operator(filtered), width="stretch")
  col4.plotly_chart(
    charts.avg_price_by_dimension(filtered, "casa", "Precio medio/noche por casa"),
    width="stretch",
  )
  st.plotly_chart(
    charts.avg_price_by_dimension(filtered, "tour_operador", "Precio medio/noche por operador"),
    width="stretch",
  )

  st.subheader("Tabla de reservas")
  table = filtered.select(
    "casa",
    "nombre",
    "entrada",
    "salida",
    "pais",
    "noches",
    "pax",
    "precio",
    "comision",
    "precio_neto",
    "tour_operador",
  )
  st.dataframe(table.to_pandas(), width="stretch", hide_index=True)

  excel_buffer = io.BytesIO()
  table.to_pandas().to_excel(excel_buffer, index=False, engine="openpyxl")
  st.download_button(
    "Exportar filtrado a Excel",
    data=excel_buffer.getvalue(),
    file_name="reservas_filtradas.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  )


def _render_import_preview(filename: str, file_bytes: bytes) -> None:
  """
  Render import preview with validation warnings and confirmation.

  Args:
      filename (str): Uploaded workbook file name.
      file_bytes (bytes): Raw workbook bytes.
  """
  result = parse_workbook(file_bytes, filename)
  existing = db.get_existing_fingerprints()
  warnings = validate_reservations(result.reservations, existing)

  st.subheader("Vista previa de importación")
  st.write(f"**Archivo:** {filename}")
  st.write(f"**Reservas detectadas:** {len(result.reservations)}")
  st.write(f"**Filas omitidas:** {result.skipped_rows}")

  if result.sheet_summaries:
    st.dataframe(pl.DataFrame(result.sheet_summaries).to_pandas(), width="stretch", hide_index=True)

  if result.reservations:
    preview = reservations_preview_table(result.reservations)
    st.dataframe(preview.to_pandas(), width="stretch", hide_index=True)

  if warnings:
    st.warning(f"Se detectaron {len(warnings)} advertencias")
    warning_rows = [
      {
        "tipo": item.tipo,
        "mensaje": item.mensaje,
        "hoja": item.hoja,
        "fila": item.fila,
        "nombre": item.nombre,
      }
      for item in warnings
    ]
    st.dataframe(pl.DataFrame(warning_rows).to_pandas(), width="stretch", hide_index=True)
  else:
    st.success("No se detectaron advertencias")

  mes, anio = _infer_workbook_period(filename, result.sheet_summaries)
  if st.button("Confirmar importación", type="primary"):
    _, inserted = db.import_workbook(
      file_bytes,
      filename,
      result.reservations,
      mes=mes,
      anio=anio,
    )
    st.success(f"Importación completada. {inserted} reservas nuevas añadidas al histórico.")
    st.rerun()


def reservations_preview_table(reservations) -> pl.DataFrame:
  """
  Build a preview table for parsed reservations.

  Args:
      reservations: Parsed reservation objects.

  Returns:
      pl.DataFrame: Preview dataframe for Streamlit display.
  """
  rows = [
    {
      "hoja": item.hoja,
      "fila": item.fila,
      "casa": item.casa,
      "nombre": item.nombre,
      "entrada": item.entrada,
      "salida": item.salida,
      "pais": item.pais,
      "noches": item.noches,
      "pax": item.pax,
      "precio": item.precio,
      "comision": item.comision,
      "forma_pago": item.forma_pago,
      "tour_operador": item.tour_operador,
    }
    for item in reservations
  ]
  return pl.DataFrame(rows)


def page_archivos() -> None:
  """Render workbook management and import page."""
  st.title("Archivos")
  st.caption("Gestión de Excels mensuales importados")

  uploaded = st.file_uploader(
    "Subir Excel mensual (.xlsx o .ods)",
    type=["xlsx", "xlsm", "ods"],
    accept_multiple_files=False,
  )
  if uploaded is not None:
    _render_import_preview(uploaded.name, uploaded.getvalue())

  st.divider()
  archivos = db.list_archivos()
  if archivos.is_empty():
    st.info("Todavía no hay archivos importados.")
    return

  st.subheader("Histórico de importaciones")
  display = archivos.with_columns(
    pl.col("mes").map_elements(
      lambda value: MONTH_LABELS.get(value, "—") if value is not None else "—",
      return_dtype=pl.Utf8,
    ).alias("mes_nombre")
  )
  st.dataframe(
    display.select(
      "nombre",
      "mes_nombre",
      "anio",
      "fecha_importacion",
      "reservas_importadas",
    ).rename(
      {
        "nombre": "Archivo",
        "mes_nombre": "Mes",
        "anio": "Año",
        "fecha_importacion": "Fecha importación",
        "reservas_importadas": "Reservas",
      }
    ).to_pandas(),
    width="stretch",
    hide_index=True,
  )

  archivo_ids = archivos.select("id").to_series().to_list()
  archivo_labels = {
    int(row["id"]): f"{row['nombre']} ({row['fecha_importacion']})"
    for row in archivos.iter_rows(named=True)
  }
  selected_id = st.selectbox(
    "Selecciona un archivo para acciones",
    options=archivo_ids,
    format_func=lambda value: archivo_labels.get(value, str(value)),
  )

  col1, col2, col3 = st.columns(3)
  with col1:
    downloaded = db.get_archivo_contenido(selected_id)
    if downloaded:
      name, content = downloaded
      st.download_button(
        "Descargar Excel",
        data=content,
        file_name=name,
      )
  with col2:
    if st.button("Eliminar archivo"):
      db.delete_archivo(selected_id)
      st.success("Archivo y reservas asociadas eliminados.")
      st.rerun()
  with col3:
    if st.button("Reimportar"):
      downloaded = db.get_archivo_contenido(selected_id)
      if downloaded:
        name, content = downloaded
        _render_import_preview(name, content)


def main() -> None:
  """Run the Streamlit multi-page application."""
  db.init_db()

  page = st.sidebar.radio("Navegación", ["Dashboard", "Archivos"], index=0)
  if page == "Dashboard":
    page_dashboard()
  else:
    page_archivos()


if __name__ == "__main__":
  main()
