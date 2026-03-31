#!/usr/bin/env python3
"""
SCS-CN Runoff Analysis – Example Entry Point
=============================================

Demonstrates a complete analysis workflow:
  1. Define watershed land uses
  2. Load storm events from CSV
  3. Run the SCS-CN analysis
  4. Export results
  5. Generate all visualizations

Usage:
    python main.py
    python main.py --rainfall 120 --amc III --output-dir ./output
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")   # Non-interactive backend for headless runs
import matplotlib.pyplot as plt

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

from scs_cn import (
    AntecedentMoistureCondition,
    HydrologicSoilGroup,
    WatershedLandUse,
    analyze_watershed,
    build_sample_csv,
    build_sample_storms_csv,
    export_results_csv,
    load_from_csv,
    load_storm_events,
    plot_cn_heatmap,
    plot_dashboard,
    plot_runoff_curves,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="SCS-CN Runoff Analysis",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--rainfall",    type=float, default=100.0,
                        help="Design storm rainfall depth (mm)")
    parser.add_argument("--amc",         choices=["I", "II", "III"], default="II",
                        help="Antecedent Moisture Condition")
    parser.add_argument("--lambda",      dest="lambda_", type=float, default=0.2,
                        help="Initial abstraction ratio (λ)")
    parser.add_argument("--output-dir",  type=Path, default=Path("data/output"),
                        help="Directory for output files")
    parser.add_argument("--csv",         type=Path, default=None,
                        help="Path to land-use CSV (uses built-in sample if omitted)")
    parser.add_argument("--storms-csv",  type=Path, default=None,
                        help="Path to storm events CSV")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    out_dir = args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    # ── 1. Land-use data ────────────────────────────────────────────────────
    if args.csv and args.csv.exists():
        logger.info("Loading land use from: %s", args.csv)
        land_uses = load_from_csv(args.csv)
    else:
        logger.info("No CSV provided — generating built-in sample watershed")
        sample_csv = out_dir / "sample_watershed.csv"
        build_sample_csv(sample_csv)
        land_uses = load_from_csv(sample_csv)

    # ── 2. Storm events ──────────────────────────────────────────────────────
    if args.storms_csv and args.storms_csv.exists():
        storms_df = load_storm_events(args.storms_csv)
    else:
        storms_csv = out_dir / "sample_storms.csv"
        build_sample_storms_csv(storms_csv)
        storms_df = load_storm_events(storms_csv)

    # ── 3. Single-event analysis ─────────────────────────────────────────────
    amc = AntecedentMoistureCondition(args.amc)
    logger.info("Running SCS-CN analysis: P=%.1f mm, AMC=%s", args.rainfall, amc.value)

    result = analyze_watershed(land_uses, args.rainfall, amc, args.lambda_)
    print("\n" + result.summary())

    # ── 4. Batch analysis ────────────────────────────────────────────────────
    batch_rows = []
    for _, row in storms_df.iterrows():
        event_amc = AntecedentMoistureCondition(row.get("amc", "II"))
        r = analyze_watershed(land_uses, float(row["rainfall_mm"]), event_amc, args.lambda_)
        batch_rows.append({
            "event_id":          row.get("event_id", "—"),
            "date":              row.get("date", "—"),
            "rainfall_mm":       r.rainfall_mm,
            "composite_cn":      r.composite_cn,
            "adjusted_cn":       r.adjusted_cn,
            "runoff_mm":         r.runoff_mm,
            "runoff_volume_m3":  r.runoff_volume_m3,
            "runoff_ratio":      r.runoff_ratio,
        })

    import pandas as pd
    batch_df = pd.DataFrame(batch_rows)
    csv_out = out_dir / "batch_results.csv"
    export_results_csv(batch_df, csv_out)
    logger.info("Batch results saved to %s", csv_out)
    print("\nBatch storm analysis:")
    print(batch_df.to_string(index=False))

    # ── 5. Visualisations ────────────────────────────────────────────────────
    logger.info("Generating visualizations …")

    # Dashboard
    fig_dash = plot_dashboard(result, storms_df, args.lambda_)
    dash_path = out_dir / "dashboard.png"
    fig_dash.savefig(dash_path, dpi=150, bbox_inches="tight")
    plt.close(fig_dash)
    logger.info("Dashboard saved to %s", dash_path)

    # Runoff curves
    fig_curves = plot_runoff_curves(
        [30, 55, 70, 80, 90, 98],
        rainfall_max_mm=250.0,
        lambda_=args.lambda_,
    )
    curves_path = out_dir / "runoff_curves.png"
    fig_curves.savefig(curves_path, dpi=150, bbox_inches="tight")
    plt.close(fig_curves)
    logger.info("Runoff curves saved to %s", curves_path)

    # CN heatmap
    fig_heatmap = plot_cn_heatmap()
    heatmap_path = out_dir / "cn_heatmap.png"
    fig_heatmap.savefig(heatmap_path, dpi=150, bbox_inches="tight")
    plt.close(fig_heatmap)
    logger.info("CN heatmap saved to %s", heatmap_path)

    print(f"\nAll outputs written to: {out_dir.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
