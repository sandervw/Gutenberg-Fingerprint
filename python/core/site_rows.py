# Site rows: query results as compact JavaScript Object Notation text.

from __future__ import annotations

import polars

DECIMAL_PLACES: int = 4


def rows_as_text(dataframe: polars.DataFrame) -> str:
    """Rows as a JSON array: decimals as rounded floats, dates as text."""
    as_floats = dataframe.with_columns(polars.col(polars.Decimal).cast(polars.Float64))
    rounded = as_floats.with_columns(
        polars.col(polars.Float32, polars.Float64).round(DECIMAL_PLACES),
        polars.col(polars.Date, polars.Datetime).cast(polars.String),
    )
    return rounded.write_json()
