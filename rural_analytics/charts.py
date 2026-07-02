"""Plotly chart builders for the rural analytics dashboard."""

from __future__ import annotations

import polars as pl
import plotly.express as px
import plotly.graph_objects as go


def _empty_figure(title: str) -> go.Figure:
  """
  Build an empty placeholder chart.

  Args:
      title (str): Chart title.

  Returns:
      go.Figure: Empty Plotly figure with title.
  """
  figure = go.Figure()
  figure.update_layout(title=title, xaxis={"visible": False}, yaxis={"visible": False})
  return figure


def monthly_count(dataframe: pl.DataFrame, title: str) -> go.Figure:
  """
  Build a monthly reservation count chart.

  Args:
      dataframe (pl.DataFrame): Filtered reservation dataframe.
      title (str): Chart title.

  Returns:
      go.Figure: Plotly bar chart.
  """
  if dataframe.is_empty():
    return _empty_figure(title)

  grouped = (
    dataframe.filter(pl.col("entrada").is_not_null())
    .with_columns(pl.col("entrada").dt.strftime("%Y-%m").alias("periodo"))
    .group_by("periodo")
    .agg(pl.len().alias("valor"))
    .sort("periodo")
  )
  pdf = grouped.to_pandas()
  return px.bar(pdf, x="periodo", y="valor", title=title)


def monthly_bar(dataframe: pl.DataFrame, value_column: str, title: str) -> go.Figure:
  """
  Build a monthly aggregation bar chart.

  Args:
      dataframe (pl.DataFrame): Filtered reservation dataframe.
      value_column (str): Numeric column to aggregate.
      title (str): Chart title.

  Returns:
      go.Figure: Plotly bar chart.
  """
  if dataframe.is_empty():
    return _empty_figure(title)

  grouped = (
    dataframe.filter(pl.col("entrada").is_not_null())
    .with_columns(pl.col("entrada").dt.strftime("%Y-%m").alias("periodo"))
    .group_by("periodo")
    .agg(pl.col(value_column).sum().alias("valor"))
    .sort("periodo")
  )
  pdf = grouped.to_pandas()
  return px.bar(pdf, x="periodo", y="valor", title=title)


def yearly_comparison(dataframe: pl.DataFrame, value_column: str, title: str) -> go.Figure:
  """
  Build a year-over-year monthly comparison chart.

  Args:
      dataframe (pl.DataFrame): Filtered reservation dataframe.
      value_column (str): Numeric column to aggregate.
      title (str): Chart title.

  Returns:
      go.Figure: Plotly line chart comparing years by month.
  """
  if dataframe.is_empty():
    return _empty_figure(title)

  grouped = (
    dataframe.filter(pl.col("entrada").is_not_null())
    .with_columns(
      pl.col("entrada").dt.year().alias("anio"),
      pl.col("entrada").dt.month().alias("mes"),
    )
    .group_by("anio", "mes")
    .agg(pl.col(value_column).sum().alias("valor"))
    .sort("anio", "mes")
  )
  pdf = grouped.to_pandas()
  return px.line(pdf, x="mes", y="valor", color="anio", markers=True, title=title)


def _filter_dimension_values(dataframe: pl.DataFrame, dimension: str) -> pl.DataFrame:
  """
  Filter rows with a usable value for a chart dimension.

  Args:
      dataframe (pl.DataFrame): Source reservation dataframe.
      dimension (str): Column used as chart dimension.

  Returns:
      pl.DataFrame: Rows where the dimension has a non-empty value.
  """
  column = pl.col(dimension)
  dtype = dataframe.schema[dimension]
  if dtype in {pl.Utf8, pl.String}:
    return dataframe.filter(column.is_not_null() & (column != ""))
  return dataframe.filter(column.is_not_null())


def distribution_bar(dataframe: pl.DataFrame, dimension: str, title: str) -> go.Figure:
  """
  Build a distribution bar chart for a categorical dimension.

  Args:
      dataframe (pl.DataFrame): Filtered reservation dataframe.
      dimension (str): Categorical column name.
      title (str): Chart title.

  Returns:
      go.Figure: Plotly bar chart.
  """
  if dataframe.is_empty() or dimension not in dataframe.columns:
    return _empty_figure(title)

  grouped = (
    _filter_dimension_values(dataframe, dimension)
    .group_by(dimension)
    .agg(pl.len().alias("reservas"))
    .sort("reservas", descending=True)
  )
  pdf = grouped.to_pandas()
  return px.bar(pdf, x=dimension, y="reservas", title=title)


def revenue_by_dimension(dataframe: pl.DataFrame, dimension: str, title: str) -> go.Figure:
  """
  Build a revenue aggregation chart grouped by a dimension.

  Args:
      dataframe (pl.DataFrame): Filtered reservation dataframe.
      dimension (str): Categorical column name.
      title (str): Chart title.

  Returns:
      go.Figure: Plotly bar chart.
  """
  if dataframe.is_empty() or dimension not in dataframe.columns:
    return _empty_figure(title)

  grouped = (
    _filter_dimension_values(dataframe, dimension)
    .group_by(dimension)
    .agg(pl.col("precio").sum().alias("ingresos"))
    .sort("ingresos", descending=True)
  )
  pdf = grouped.to_pandas()
  return px.bar(pdf, x=dimension, y="ingresos", title=title)


def commission_by_operator(dataframe: pl.DataFrame) -> go.Figure:
  """
  Build a commission chart grouped by tour operator.

  Args:
      dataframe (pl.DataFrame): Filtered reservation dataframe.

  Returns:
      go.Figure: Plotly bar chart.
  """
  if dataframe.is_empty():
    return _empty_figure("Comisión por operador")

  grouped = (
    _filter_dimension_values(dataframe, "tour_operador")
    .group_by("tour_operador")
    .agg(pl.col("comision").sum().alias("comision"))
    .sort("comision", descending=True)
  )
  pdf = grouped.to_pandas()
  return px.bar(pdf, x="tour_operador", y="comision", title="Comisión por operador")


def avg_price_by_dimension(dataframe: pl.DataFrame, dimension: str, title: str) -> go.Figure:
  """
  Build an average price-per-night chart grouped by a dimension.

  Args:
      dataframe (pl.DataFrame): Filtered reservation dataframe.
      dimension (str): Categorical column name.
      title (str): Chart title.

  Returns:
      go.Figure: Plotly bar chart.
  """
  if dataframe.is_empty() or dimension not in dataframe.columns:
    return _empty_figure(title)

  grouped = (
    _filter_dimension_values(dataframe, dimension)
    .group_by(dimension)
    .agg(pl.col("precio_por_noche").mean().alias("precio_medio"))
    .sort("precio_medio", descending=True)
  )
  pdf = grouped.to_pandas()
  return px.bar(pdf, x=dimension, y="precio_medio", title=title)
