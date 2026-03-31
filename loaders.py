"""
Data loading utilities for SCS-CN runoff analysis.

Supports loading watershed land-use data from:
  - CSV files
  - JSON files
  - Python dicts / DataFrames
  - Batch storm event tables
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Union

import pandas as pd

from scs_cn.core.calculator import (
    AntecedentMoistureCondition,
    HydrologicSoilGroup,
    WatershedLandUse,
)

logger = logging.getLogger(__name__)

# Required columns when reading from tabular formats
_REQUIRED_COLS = {"land_use", "soil_group", "area_ha"}
_OPTIONAL_COLS = {"amc", "custom_cn"}

PathLike = Union[str, Path]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_amc(value: Any) -> AntecedentMoistureCondition:
    """Parse AMC from string or enum; default to AVERAGE."""
    if isinstance(value, AntecedentMoistureCondition):
        return value
    mapping = {"I": AntecedentMoistureCondition.DRY,
               "II": AntecedentMoistureCondition.AVERAGE,
               "III": AntecedentMoistureCondition.WET,
               "DRY": AntecedentMoistureCondition.DRY,
               "AVERAGE": AntecedentMoistureCondition.AVERAGE,
               "WET": AntecedentMoistureCondition.WET}
    key = str(value).strip().upper()
    if key not in mapping:
        raise ValueError(f"Unknown AMC value '{value}'. Expected one of {list(mapping)}")
    return mapping[key]


def _parse_hsg(value: Any) -> HydrologicSoilGroup:
    """Parse HSG from string or enum."""
    if isinstance(value, HydrologicSoilGroup):
        return value
    key = str(value).strip().upper()
    try:
        return HydrologicSoilGroup(key)
    except ValueError:
        raise ValueError(
            f"Unknown Hydrologic Soil Group '{value}'. Expected one of A, B, C, D."
        )


def _row_to_land_use(row: dict[str, Any]) -> WatershedLandUse:
    """Convert a dict row to a WatershedLandUse object."""
    missing = _REQUIRED_COLS - set(row.keys())
    if missing:
        raise ValueError(f"Row is missing required fields: {missing}. Row: {row}")

    amc_raw    = row.get("amc", "II")
    custom_cn  = row.get("custom_cn")

    return WatershedLandUse(
        land_use=str(row["land_use"]).strip(),
        soil_group=_parse_hsg(row["soil_group"]),
        area_ha=float(row["area_ha"]),
        amc=_parse_amc(amc_raw),
        custom_cn=int(custom_cn) if custom_cn is not None and not _is_na(custom_cn) else None,
    )


def _is_na(value: Any) -> bool:
    """Return True for None / NaN / empty string."""
    if value is None:
        return True
    try:
        import math
        return math.isnan(float(value))
    except (TypeError, ValueError):
        return str(value).strip() == ""


# ---------------------------------------------------------------------------
# Public loaders
# ---------------------------------------------------------------------------

def load_from_csv(path: PathLike, **read_csv_kwargs: Any) -> list[WatershedLandUse]:
    """Load watershed land-use polygons from a CSV file.

    Expected columns:
        land_use  (str)   : Land use description key (see CN_TABLE).
        soil_group (str)  : HSG code A, B, C, or D.
        area_ha   (float) : Area in hectares.
        amc       (str)   : (optional) AMC class I/II/III (default II).
        custom_cn (int)   : (optional) Override CN.

    Args:
        path: Path to the CSV file.
        **read_csv_kwargs: Extra keyword arguments forwarded to pd.read_csv.

    Returns:
        List of WatershedLandUse objects.

    Raises:
        FileNotFoundError: If the CSV file does not exist.
        ValueError: On schema or parsing errors.

    Example::

        land_uses = load_from_csv("my_watershed.csv")
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"CSV file not found: {path}")

    logger.info("Loading land use data from CSV: %s", path)
    df = pd.read_csv(path, **read_csv_kwargs)
    return load_from_dataframe(df)


def load_from_json(path: PathLike) -> list[WatershedLandUse]:
    """Load watershed land-use polygons from a JSON file.

    The file must contain a JSON array of objects with the same fields
    as the CSV format (see :func:`load_from_csv`).

    Args:
        path: Path to the JSON file.

    Returns:
        List of WatershedLandUse objects.

    Raises:
        FileNotFoundError: If the JSON file does not exist.
        json.JSONDecodeError: On invalid JSON.
        ValueError: On schema or parsing errors.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"JSON file not found: {path}")

    logger.info("Loading land use data from JSON: %s", path)
    with open(path, encoding="utf-8") as fh:
        records = json.load(fh)

    if not isinstance(records, list):
        raise ValueError("JSON file must contain a top-level array of land-use records.")

    land_uses = []
    for i, record in enumerate(records):
        try:
            land_uses.append(_row_to_land_use(record))
        except (ValueError, KeyError) as exc:
            raise ValueError(f"Error parsing record {i}: {exc}") from exc

    logger.info("Loaded %d land-use polygons from JSON", len(land_uses))
    return land_uses


def load_from_dataframe(df: pd.DataFrame) -> list[WatershedLandUse]:
    """Load watershed land-use polygons from a pandas DataFrame.

    Args:
        df: DataFrame with columns matching the CSV schema.

    Returns:
        List of WatershedLandUse objects.

    Raises:
        ValueError: If required columns are missing or rows fail validation.
    """
    df.columns = [c.strip().lower() for c in df.columns]
    missing = _REQUIRED_COLS - set(df.columns)
    if missing:
        raise ValueError(
            f"DataFrame is missing required columns: {missing}. "
            f"Found: {list(df.columns)}"
        )

    land_uses = []
    for i, row in df.iterrows():
        try:
            land_uses.append(_row_to_land_use(row.to_dict()))
        except (ValueError, KeyError) as exc:
            raise ValueError(f"Error parsing row {i}: {exc}") from exc

    logger.info("Loaded %d land-use polygons from DataFrame", len(land_uses))
    return land_uses


def load_storm_events(path: PathLike, **read_csv_kwargs: Any) -> pd.DataFrame:
    """Load a batch of storm rainfall events from a CSV file.

    Expected columns:
        event_id  (str/int): Unique storm identifier.
        date      (str)    : (optional) Storm date (ISO 8601).
        rainfall_mm (float): Rainfall depth in mm.
        amc       (str)    : (optional) AMC class (default II).

    Args:
        path: Path to the storms CSV file.
        **read_csv_kwargs: Extra kwargs forwarded to pd.read_csv.

    Returns:
        DataFrame of storm events, with 'rainfall_mm' validated as float ≥ 0.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If 'rainfall_mm' column is missing or has negative values.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Storm events file not found: {path}")

    logger.info("Loading storm events from: %s", path)
    df = pd.read_csv(path, **read_csv_kwargs)
    df.columns = [c.strip().lower() for c in df.columns]

    if "rainfall_mm" not in df.columns:
        raise ValueError("Storm events CSV must contain a 'rainfall_mm' column.")

    df["rainfall_mm"] = pd.to_numeric(df["rainfall_mm"], errors="raise")
    negative_rows = df[df["rainfall_mm"] < 0]
    if not negative_rows.empty:
        raise ValueError(
            f"Negative rainfall_mm values found at rows: {list(negative_rows.index)}"
        )

    if "amc" not in df.columns:
        df["amc"] = "II"

    logger.info("Loaded %d storm events", len(df))
    return df


# ---------------------------------------------------------------------------
# Export helpers
# ---------------------------------------------------------------------------

def export_results_csv(results_df: pd.DataFrame, path: PathLike) -> None:
    """Export a results DataFrame to CSV.

    Args:
        results_df: DataFrame of analysis results (e.g. from a batch run).
        path: Output file path.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    results_df.to_csv(path, index=False)
    logger.info("Results exported to %s", path)


def build_sample_csv(path: PathLike) -> None:
    """Write a sample land-use CSV file to disk (useful for demos/testing).

    Args:
        path: Destination file path.
    """
    sample = pd.DataFrame([
        {"land_use": "residential_1_4acre",        "soil_group": "B", "area_ha": 45.0, "amc": "II"},
        {"land_use": "commercial_business",         "soil_group": "C", "area_ha": 12.5, "amc": "II"},
        {"land_use": "impervious_surfaces",         "soil_group": "D", "area_ha":  8.0, "amc": "II"},
        {"land_use": "open_space_good",             "soil_group": "B", "area_ha": 20.0, "amc": "II"},
        {"land_use": "woods_good",                  "soil_group": "A", "area_ha": 30.0, "amc": "II"},
        {"land_use": "pasture_fair",                "soil_group": "B", "area_ha": 15.0, "amc": "II"},
        {"land_use": "row_crops_straight_rows_good","soil_group": "C", "area_ha": 25.0, "amc": "II"},
        {"land_use": "water_bodies",                "soil_group": "A", "area_ha":  5.0, "amc": "II"},
    ])
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    sample.to_csv(path, index=False)
    logger.info("Sample CSV written to %s", path)


def build_sample_storms_csv(path: PathLike) -> None:
    """Write a sample storm events CSV file to disk.

    Args:
        path: Destination file path.
    """
    storms = pd.DataFrame([
        {"event_id": "T2",   "date": "2023-08-01", "rainfall_mm":  50.0, "amc": "II"},
        {"event_id": "T5",   "date": "2023-08-15", "rainfall_mm":  75.0, "amc": "II"},
        {"event_id": "T10",  "date": "2023-09-01", "rainfall_mm": 100.0, "amc": "II"},
        {"event_id": "T25",  "date": "2023-09-20", "rainfall_mm": 130.0, "amc": "III"},
        {"event_id": "T50",  "date": "2023-10-05", "rainfall_mm": 160.0, "amc": "III"},
        {"event_id": "T100", "date": "2023-10-20", "rainfall_mm": 200.0, "amc": "III"},
    ])
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    storms.to_csv(path, index=False)
    logger.info("Sample storms CSV written to %s", path)
