"""
SCS-CN Runoff Analysis Package
================================
Production-ready implementation of the USDA-NRCS Curve Number method
for estimating direct runoff from rainfall events.

Quick start::

    from scs_cn import analyze_watershed, WatershedLandUse, HydrologicSoilGroup

    land_uses = [
        WatershedLandUse("residential_1_4acre", HydrologicSoilGroup.B, 45.0),
        WatershedLandUse("woods_good",           HydrologicSoilGroup.A, 30.0),
        WatershedLandUse("impervious_surfaces",  HydrologicSoilGroup.D,  8.0),
    ]
    result = analyze_watershed(land_uses, rainfall_mm=100.0)
    print(result.summary())
"""

__version__ = "1.0.0"
__author__  = "Hydrology Team"

from scs_cn.core import (
    AntecedentMoistureCondition,
    CN_TABLE,
    HydrologicSoilGroup,
    LAND_USE_TYPES,
    RunoffResult,
    WatershedLandUse,
    adjust_cn_for_amc,
    analyze_watershed,
    compute_composite_cn,
    compute_potential_retention,
    compute_runoff_depth,
    lookup_cn,
    runoff_curve,
)
from scs_cn.data import (
    build_sample_csv,
    build_sample_storms_csv,
    export_results_csv,
    load_from_csv,
    load_from_dataframe,
    load_from_json,
    load_storm_events,
)
from scs_cn.visualization import (
    plot_cn_heatmap,
    plot_dashboard,
    plot_land_use_pie,
    plot_runoff_curves,
    plot_storm_runoff_bars,
)

__all__ = [
    # Core
    "AntecedentMoistureCondition",
    "CN_TABLE",
    "HydrologicSoilGroup",
    "LAND_USE_TYPES",
    "RunoffResult",
    "WatershedLandUse",
    "adjust_cn_for_amc",
    "analyze_watershed",
    "compute_composite_cn",
    "compute_potential_retention",
    "compute_runoff_depth",
    "lookup_cn",
    "runoff_curve",
    # Data
    "build_sample_csv",
    "build_sample_storms_csv",
    "export_results_csv",
    "load_from_csv",
    "load_from_dataframe",
    "load_from_json",
    "load_storm_events",
    # Visualization
    "plot_cn_heatmap",
    "plot_dashboard",
    "plot_land_use_pie",
    "plot_runoff_curves",
    "plot_storm_runoff_bars",
]
