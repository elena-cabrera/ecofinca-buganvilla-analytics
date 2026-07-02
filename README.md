# Ecofinca Buganvilla Analytics

POC de dashboard privado para gestionar el histórico de reservas de una casa rural a partir de archivos Excel/ODS mensuales.

## Stack

- Streamlit (UI)
- Polars (análisis)
- SQLite (`data/rural.db`)
- Plotly (gráficos)
- openpyxl + odfpy (lectura `.xlsx` y `.ods`)

## Arranque

```bash
uv sync
uv run streamlit run app.py
```

## Importación

1. Ve a **Archivos** en la barra lateral.
2. Sube un Excel mensual (`.xlsx` o `.ods`).
3. Revisa la vista previa y las advertencias (fechas, duplicados, países desconocidos, etc.).
4. Confirma la importación.

El parser lee **todas las hojas** del archivo (p. ej. `Enero_2026`, `Febrero_2026`, …), detecta la fila de cabecera y omite filas de subtotal.

## Estructura

```
app.py                     # App Streamlit (Dashboard + Archivos)
rural_analytics/
  parser.py                # Lectura multi-hoja y normalización
  db.py                    # Persistencia SQLite
  validators.py            # Advertencias pre-importación
  charts.py                # Gráficos Plotly
  normalization.py         # Fechas, precios, casas, operadores
data/rural.db              # Base de datos local (gitignored)
```

## Formato esperado

Columnas por hoja mensual:

`Casa | Nombre | Entrada | Salida | País | Noches | Pax | Dto. % | Precio | Comisión | F-pago | Tour operador`
