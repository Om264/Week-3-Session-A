"""
Visualization components for SCS-CN runoff analysis.

Provides:
  - P–Q runoff curve plots for one or more CNs
  - Land-use area pie chart
  - Runoff vs. rainfall bar chart for batch storm events
  - Heatmap of CN across land-use × HSG combinations
  - Full dashboard figure
"""

from __future__ import annotations

import logging
from typing import Optional

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
from matplotlib.axes import Axes
from matplotlib.figure import Figure

from scs_cn.core.calculator import (
    CN_TABLE,
    HydrologicSoilGroup,
    RunoffResult,
    compute_runoff_depth,
    runoff_curve,
)

logger = logging.getLogger(__name__)

# ── Style constants ────────────────────────────────────────────────────────
_PALETTE = ["#2563EB", "#16A34A", "#DC2626", "#D97706", "#7C3AED",
            "#0891B2", "#BE185D", "#65A30D"]
_GRID_KW  = dict(color="#E5E7EB", linewidth=0.7, linestyle="--")
_SPINE_COLOR = "#9CA3AF"

plt.rcParams.update({
    "font.family":      "DejaVu Sans",
    "axes.spines.top":  False,
    "axes.spines.right": False,
    "figure.dpi":        110,
})


def _style_axes(ax: Axes) -> None:
    """Apply shared styling to an Axes object."""
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.1f"))
    ax.grid(True, axis="y", **_GRID_KW)
    ax.grid(True, axis="x", **_GRID_KW)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_color(_SPINE_COLOR)
    ax.tick_params(colors="#374151")


# ---------------------------------------------------------------------------
# 1. P–Q Runoff Curves
# ---------------------------------------------------------------------------

def plot_runoff_curves(
    curve_numbers: list[int | float],
    rainfall_max_mm: float = 200.0,
    lambda_: float = 0.2,
    ax: Optional[Axes] = None,
    figsize: tuple[float, float] = (9, 5),
) -> Figure:
    """Plot P–Q runoff curves for one or more Curve Numbers.

    Args:
        curve_numbers: List of CN values to plot.
        rainfall_max_mm: Maximum rainfall on the x-axis (mm).
        lambda_: Initial abstraction ratio.
        ax: Optional existing Axes to plot into.
        figsize: Figure size (width, height) in inches.

    Returns:
        Matplotlib Figure.
    """
    fig, ax = (ax.get_figure(), ax) if ax else plt.subplots(figsize=figsize)

    for i, cn in enumerate(curve_numbers):
        df = runoff_curve(float(cn), (0, rainfall_max_mm), 300, lambda_)
        color = _PALETTE[i % len(_PALETTE)]
        ax.plot(df["rainfall_mm"], df["runoff_mm"],
                color=color, linewidth=2, label=f"CN = {cn}")
        # Mark Ia
        s_mm = (25_400 / cn) - 254
        ia_mm = lambda_ * s_mm
        ax.axvline(x=ia_mm, color=color, linewidth=0.8, linestyle=":", alpha=0.6)

    ax.set_xlabel("Rainfall P (mm)", fontsize=11)
    ax.set_ylabel("Direct Runoff Q (mm)", fontsize=11)
    ax.set_title("SCS-CN Runoff Curves (P–Q)", fontsize=13, fontweight="bold")
    ax.legend(title="Curve Number", frameon=False, fontsize=9)
    _style_axes(ax)
    ax.set_xlim(left=0)
    ax.set_ylim(bottom=0)
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# 2. Land-Use Pie Chart
# ---------------------------------------------------------------------------

def plot_land_use_pie(
    result: RunoffResult,
    ax: Optional[Axes] = None,
    figsize: tuple[float, float] = (7, 5),
    max_slices: int = 8,
) -> Figure:
    """Pie chart showing the area distribution of land-use types.

    Args:
        result: RunoffResult from :func:`~scs_cn.core.calculator.analyze_watershed`.
        ax: Optional existing Axes.
        figsize: Figure size.
        max_slices: Land-use types beyond this are merged into 'Other'.

    Returns:
        Matplotlib Figure.
    """
    fig, ax = (ax.get_figure(), ax) if ax else plt.subplots(figsize=figsize)

    df = result.land_use_breakdown.groupby("land_use")["area_ha"].sum().reset_index()
    df = df.sort_values("area_ha", ascending=False)

    if len(df) > max_slices:
        top   = df.iloc[:max_slices - 1]
        other = pd.DataFrame({"land_use": ["Other"], "area_ha": [df.iloc[max_slices - 1:]["area_ha"].sum()]})
        df    = pd.concat([top, other], ignore_index=True)

    labels = [lu.replace("_", " ").title() for lu in df["land_use"]]
    wedges, texts, autotexts = ax.pie(
        df["area_ha"],
        labels=None,
        autopct="%1.1f%%",
        startangle=90,
        colors=_PALETTE[: len(df)],
        pctdistance=0.82,
        wedgeprops={"linewidth": 1, "edgecolor": "white"},
    )
    for at in autotexts:
        at.set_fontsize(8)

    ax.legend(
        wedges, labels,
        title=f"Total: {result.total_area_ha:.1f} ha",
        loc="center left",
        bbox_to_anchor=(1.0, 0.5),
        fontsize=9,
        frameon=False,
    )
    ax.set_title("Watershed Land-Use Distribution", fontsize=13, fontweight="bold")
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# 3. Runoff Bar Chart (batch storms)
# ---------------------------------------------------------------------------

def plot_storm_runoff_bars(
    storms_df: pd.DataFrame,
    composite_cn: float,
    lambda_: float = 0.2,
    ax: Optional[Axes] = None,
    figsize: tuple[float, float] = (10, 5),
) -> Figure:
    """Bar chart comparing rainfall vs. runoff for multiple storm events.

    Args:
        storms_df: DataFrame with columns 'event_id' and 'rainfall_mm'.
        composite_cn: Composite CN to use for runoff computation.
        lambda_: Initial abstraction ratio.
        ax: Optional existing Axes.
        figsize: Figure size.

    Returns:
        Matplotlib Figure.
    """
    fig, ax = (ax.get_figure(), ax) if ax else plt.subplots(figsize=figsize)

    df = storms_df.copy()
    df["runoff_mm"] = df["rainfall_mm"].apply(
        lambda p: compute_runoff_depth(float(p), composite_cn, lambda_)
    )
    df["retention_mm"] = df["rainfall_mm"] - df["runoff_mm"]

    x = np.arange(len(df))
    w = 0.35

    bars1 = ax.bar(x - w / 2, df["rainfall_mm"],  w, label="Rainfall (P)", color="#BFDBFE", edgecolor="#2563EB")
    bars2 = ax.bar(x + w / 2, df["runoff_mm"],    w, label="Runoff (Q)",   color="#2563EB", edgecolor="#1E40AF")

    ax.set_xticks(x)
    ax.set_xticklabels(df["event_id"] if "event_id" in df.columns else df.index, fontsize=9)
    ax.set_xlabel("Storm Event", fontsize=11)
    ax.set_ylabel("Depth (mm)", fontsize=11)
    ax.set_title(f"Rainfall vs. Direct Runoff  (CN = {composite_cn:.1f})", fontsize=13, fontweight="bold")
    ax.legend(frameon=False, fontsize=9)
    _style_axes(ax)

    # Annotate Q/P ratio
    for bar1, bar2 in zip(bars1, bars2):
        p = bar1.get_height()
        q = bar2.get_height()
        ratio = q / p if p > 0 else 0
        ax.text(
            bar2.get_x() + bar2.get_width() / 2,
            q + 1,
            f"{ratio:.0%}",
            ha="center", va="bottom", fontsize=7.5, color="#374151",
        )

    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# 4. CN Heatmap
# ---------------------------------------------------------------------------

def plot_cn_heatmap(
    land_uses: Optional[list[str]] = None,
    ax: Optional[Axes] = None,
    figsize: tuple[float, float] = (14, 8),
) -> Figure:
    """Heatmap of Curve Numbers across land-use types and HSG classes.

    Args:
        land_uses: Subset of land-use keys to display. Defaults to all.
        ax: Optional existing Axes.
        figsize: Figure size.

    Returns:
        Matplotlib Figure.
    """
    from scs_cn.core.calculator import LAND_USE_TYPES

    fig, ax = (ax.get_figure(), ax) if ax else plt.subplots(figsize=figsize)

    all_lu = land_uses or LAND_USE_TYPES
    hsgs = ["A", "B", "C", "D"]

    matrix = np.zeros((len(all_lu), len(hsgs)), dtype=float)
    for i, lu in enumerate(all_lu):
        for j, hsg in enumerate(hsgs):
            matrix[i, j] = CN_TABLE.get((lu, hsg), np.nan)

    im = ax.imshow(matrix, cmap="RdYlGn_r", aspect="auto", vmin=25, vmax=100)

    ax.set_xticks(range(len(hsgs)))
    ax.set_xticklabels([f"HSG {h}" for h in hsgs], fontsize=10, fontweight="bold")
    ax.set_yticks(range(len(all_lu)))
    ax.set_yticklabels(
        [lu.replace("_", " ").title() for lu in all_lu], fontsize=8
    )
    ax.set_title("SCS Curve Numbers by Land Use and Hydrologic Soil Group",
                 fontsize=13, fontweight="bold", pad=14)

    # Annotate cells
    for i in range(len(all_lu)):
        for j in range(len(hsgs)):
            val = matrix[i, j]
            if not np.isnan(val):
                ax.text(j, i, f"{int(val)}", ha="center", va="center",
                        fontsize=7.5, color="white" if val > 75 else "#111827")

    plt.colorbar(im, ax=ax, label="Curve Number", shrink=0.7)
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# 5. Full dashboard
# ---------------------------------------------------------------------------

def plot_dashboard(
    result: RunoffResult,
    storms_df: Optional[pd.DataFrame] = None,
    lambda_: float = 0.2,
    figsize: tuple[float, float] = (15, 10),
) -> Figure:
    """Four-panel analysis dashboard for a watershed RunoffResult.

    Panels:
        1. P–Q runoff curves (composite CN ± 10)
        2. Land-use area pie chart
        3. Rainfall vs. runoff bar chart (if storms_df provided)
        4. CN breakdown table by polygon

    Args:
        result: RunoffResult from analyze_watershed.
        storms_df: Optional batch storm events DataFrame.
        lambda_: Initial abstraction ratio.
        figsize: Figure size.

    Returns:
        Matplotlib Figure.
    """
    fig = plt.figure(figsize=figsize, constrained_layout=True)
    fig.suptitle("SCS-CN Watershed Runoff Dashboard", fontsize=16, fontweight="bold", y=1.01)

    gs = fig.add_gridspec(2, 2, hspace=0.38, wspace=0.35)

    ax1 = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[0, 1])
    ax3 = fig.add_subplot(gs[1, 0])
    ax4 = fig.add_subplot(gs[1, 1])

    # Panel 1 – Runoff curves
    cn = result.adjusted_cn
    cns = [max(1, round(cn - 10)), round(cn), min(99, round(cn + 10))]
    plot_runoff_curves(cns, ax=ax1)
    ax1.axvline(x=result.rainfall_mm, color="#DC2626", linewidth=1.5, linestyle="--",
                label=f"P = {result.rainfall_mm:.0f} mm")
    ax1.axhline(y=result.runoff_mm, color="#16A34A", linewidth=1.5, linestyle="--",
                label=f"Q = {result.runoff_mm:.1f} mm")
    ax1.legend(frameon=False, fontsize=8)

    # Panel 2 – Land use pie
    plot_land_use_pie(result, ax=ax2)

    # Panel 3 – Storm bars or retention info
    if storms_df is not None and not storms_df.empty:
        plot_storm_runoff_bars(storms_df, result.composite_cn, lambda_, ax=ax3)
    else:
        _plot_summary_bars(result, ax3)

    # Panel 4 – CN breakdown table
    _plot_breakdown_table(result, ax4)

    return fig


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _plot_summary_bars(result: RunoffResult, ax: Axes) -> None:
    """Mini summary bar: Rainfall partitioning."""
    labels = ["Rainfall (P)", "Runoff (Q)", "Retention"]
    values = [result.rainfall_mm, result.runoff_mm,
              result.rainfall_mm - result.runoff_mm]
    colors = ["#BFDBFE", "#2563EB", "#16A34A"]
    bars = ax.bar(labels, values, color=colors, edgecolor="white", linewidth=1.2)
    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
                f"{val:.1f} mm", ha="center", va="bottom", fontsize=9)
    ax.set_ylabel("Depth (mm)", fontsize=10)
    ax.set_title("Rainfall Partitioning", fontsize=12, fontweight="bold")
    _style_axes(ax)


def _plot_breakdown_table(result: RunoffResult, ax: Axes) -> None:
    """Render land-use CN breakdown as a table."""
    ax.axis("off")
    df = result.land_use_breakdown.copy()
    df["land_use"] = df["land_use"].str.replace("_", " ").str.title().str[:28]
    display_cols = ["land_use", "hsg", "area_ha", "cn_ii", "cn_adjusted"]
    col_labels   = ["Land Use", "HSG", "Area (ha)", "CN II", "CN (adj)"]
    table = ax.table(
        cellText=df[display_cols].values.tolist(),
        colLabels=col_labels,
        cellLoc="center",
        loc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(8)
    table.scale(1, 1.35)
    # Header row styling
    for j in range(len(col_labels)):
        table[0, j].set_facecolor("#2563EB")
        table[0, j].set_text_props(color="white", fontweight="bold")
    ax.set_title("Land-Use CN Breakdown", fontsize=12, fontweight="bold", pad=12)
