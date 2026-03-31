# SCS-CN Runoff Analysis

Production-ready Python implementation of the **USDA-NRCS Curve Number (CN) method** for estimating direct runoff from rainfall events across multi-land-use watersheds.

---

## Features

- **Full SCS-CN calculation pipeline** — potential retention (S), initial abstraction (Iₐ), and direct runoff (Q)
- **NRCS Curve Number lookup table** — 35+ land-use types × 4 Hydrologic Soil Groups (HSG A–D)
- **Antecedent Moisture Condition (AMC)** — automatic CN adjustment for dry (I), average (II), and wet (III) conditions
- **Composite CN** — area-weighted multi-polygon watershed analysis
- **Batch storm analysis** — process multiple return-period events in one call
- **Data I/O** — load from CSV, JSON, or pandas DataFrames; export results to CSV
- **Visualization suite** — P–Q curves, land-use pie chart, storm bar chart, CN heatmap, full dashboard
- **Comprehensive tests** — 40+ pytest cases covering edge cases and integration scenarios

---

## Project Structure

```
scs_cn_runoff/
│
├── scs_cn/                         # Main package
│   ├── __init__.py                 # Public API surface
│   ├── core/
│   │   ├── __init__.py
│   │   └── calculator.py           # SCS-CN equations, CN table, dataclasses
│   ├── data/
│   │   ├── __init__.py
│   │   └── loaders.py              # CSV / JSON / DataFrame I/O
│   └── visualization/
│       ├── __init__.py
│       └── plots.py                # Matplotlib figures
│
├── tests/
│   ├── __init__.py
│   └── test_scs_cn.py              # 40+ unit & integration tests
│
├── data/
│   ├── sample/                     # Generated sample inputs
│   └── output/                     # Analysis outputs
│
├── docs/                           # Extended documentation
├── main.py                         # CLI entry point / demo
├── conftest.py                     # pytest fixtures
├── pytest.ini                      # pytest configuration
├── requirements.txt
├── setup.py
└── README.md
```

---

## Quick Start

### 1. Clone and install

```bash
git clone https://github.com/your-org/scs_cn_runoff.git
cd scs_cn_runoff

# Create virtual environment
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# (Optional) Install as editable package
pip install -e .
```

### 2. Run the demo

```bash
python main.py
# With options:
python main.py --rainfall 120 --amc III --output-dir ./results
```

This generates:
- `data/output/batch_results.csv` — runoff for each storm event
- `data/output/dashboard.png` — 4-panel analysis dashboard
- `data/output/runoff_curves.png` — P–Q curves for CNs 30–98
- `data/output/cn_heatmap.png` — CN reference heatmap

---

## API Reference

### Core calculation

```python
from scs_cn import (
    WatershedLandUse,
    HydrologicSoilGroup,
    AntecedentMoistureCondition,
    analyze_watershed,
    compute_runoff_depth,
)

# Define land-use polygons
land_uses = [
    WatershedLandUse("residential_1_4acre", HydrologicSoilGroup.B, area_ha=45.0),
    WatershedLandUse("commercial_business",  HydrologicSoilGroup.C, area_ha=12.5),
    WatershedLandUse("woods_good",           HydrologicSoilGroup.A, area_ha=30.0),
    WatershedLandUse("impervious_surfaces",  HydrologicSoilGroup.D, area_ha= 8.0),
]

# Run analysis
result = analyze_watershed(
    land_uses,
    rainfall_mm=100.0,
    amc=AntecedentMoistureCondition.AVERAGE,  # AMC II
)

print(result.summary())
# Output:
# =======================================================
#   SCS-CN Runoff Analysis Summary
# =======================================================
#   Rainfall (P)            :     100.00 mm
#   Total Watershed Area    :      95.50 ha
#   Composite CN (AMC II)   :      78.43
#   Adjusted CN             :      78.43
#   Potential Retention (S) :      69.80 mm
#   Initial Abstraction (Ia):      13.96 mm
#   Direct Runoff (Q)       :      55.12 mm
#   Runoff Volume           :  526396.60 m³
#   Runoff Ratio (Q/P)      :       0.551
# =======================================================

# Access individual results
print(f"Runoff depth : {result.runoff_mm:.2f} mm")
print(f"Runoff volume: {result.runoff_volume_m3:,.0f} m³")
print(f"Runoff ratio : {result.runoff_ratio:.1%}")
```

### Single-CN runoff

```python
from scs_cn import compute_runoff_depth

q = compute_runoff_depth(rainfall_mm=80.0, cn=75.0)
print(f"Q = {q:.2f} mm")
```

### AMC adjustment

```python
from scs_cn import adjust_cn_for_amc, AntecedentMoistureCondition

cn_wet = adjust_cn_for_amc(cn_ii=75.0, amc=AntecedentMoistureCondition.WET)
cn_dry = adjust_cn_for_amc(cn_ii=75.0, amc=AntecedentMoistureCondition.DRY)
```

### Custom CN override

```python
# Use a field-calibrated CN instead of the table value
lu = WatershedLandUse(
    land_use="any_description",
    soil_group=HydrologicSoilGroup.B,
    area_ha=20.0,
    custom_cn=68,         # Overrides table lookup
)
```

---

## Data I/O

### Loading from CSV

```python
from scs_cn import load_from_csv

land_uses = load_from_csv("my_watershed.csv")
```

**Expected CSV format:**

| land_use | soil_group | area_ha | amc | custom_cn |
|---|---|---|---|---|
| residential_1_4acre | B | 45.0 | II | |
| woods_good | A | 30.0 | II | |
| commercial_business | C | 12.5 | III | |
| custom_area | D | 5.0 | II | 72 |

Columns `amc` and `custom_cn` are optional.

### Loading from JSON

```python
from scs_cn import load_from_json

land_uses = load_from_json("my_watershed.json")
```

```json
[
  {"land_use": "residential_1_4acre", "soil_group": "B", "area_ha": 45.0},
  {"land_use": "woods_good",          "soil_group": "A", "area_ha": 30.0}
]
```

### Batch storm events

```python
from scs_cn import load_storm_events, analyze_watershed

storms = load_storm_events("storm_events.csv")
# CSV: event_id, date, rainfall_mm, amc

for _, storm in storms.iterrows():
    result = analyze_watershed(land_uses, storm["rainfall_mm"])
    print(f"{storm['event_id']}: Q = {result.runoff_mm:.1f} mm")
```

---

## Visualization

```python
from scs_cn import (
    plot_runoff_curves,
    plot_land_use_pie,
    plot_storm_runoff_bars,
    plot_cn_heatmap,
    plot_dashboard,
)
import matplotlib.pyplot as plt

# P–Q runoff curves for multiple CNs
fig = plot_runoff_curves([40, 60, 75, 90], rainfall_max_mm=200)
fig.savefig("runoff_curves.png", dpi=150, bbox_inches="tight")

# Full 4-panel dashboard
fig = plot_dashboard(result, storms_df=storms)
fig.savefig("dashboard.png", dpi=150, bbox_inches="tight")

plt.show()
```

---

## Running Tests

```bash
# All tests
pytest

# With coverage report
pytest --cov=scs_cn --cov-report=term-missing

# Skip slow tests
pytest -m "not slow"

# Verbose output
pytest -v
```

---

## Supported Land-Use Types

| Category | Keys |
|---|---|
| **Agriculture** | `row_crops_straight_rows_poor/good`, `row_crops_contoured_poor/good`, `small_grain_straight_rows_poor/good`, `fallow_bare_soil` |
| **Pasture / Range** | `pasture_poor/fair/good`, `meadow_good` |
| **Forest** | `woods_poor/fair/good` |
| **Urban** | `impervious_surfaces`, `commercial_business`, `industrial`, `residential_1_8acre` … `residential_2acre` |
| **Open Space** | `open_space_poor/fair/good` |
| **Water** | `water_bodies` |

Use `from scs_cn import LAND_USE_TYPES` to get the full list programmatically.

---

## Scientific Background

The SCS-CN method estimates direct runoff Q from storm rainfall P:

```
Q = (P - Iₐ)² / (P - Iₐ + S)    if P > Iₐ
Q = 0                              if P ≤ Iₐ
```

Where:
- **S** = potential maximum retention = (25400/CN) − 254  [mm]
- **Iₐ** = initial abstraction = λS (λ = 0.2 by default)  [mm]
- **CN** = Curve Number (dimensionless, 0–100)

AMC adjustments follow Hawkins et al. (1985):
- **CN_I**  (dry) = 4.2 × CN_II / (10 − 0.058 × CN_II)
- **CN_III** (wet) = 23 × CN_II / (10 + 0.13 × CN_II)

**Reference:** USDA-NRCS (2004). *National Engineering Handbook, Part 630 Hydrology, Chapter 10.*

---

## License

MIT License — see [LICENSE](LICENSE) for details.
