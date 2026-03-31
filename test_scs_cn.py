"""
Comprehensive test suite for the SCS-CN runoff package.

Run with:
    pytest tests/ -v --tb=short
    pytest tests/ -v --cov=scs_cn --cov-report=term-missing
"""

from __future__ import annotations

import json
import math
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from scs_cn.core.calculator import (
    AntecedentMoistureCondition,
    HydrologicSoilGroup,
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
from scs_cn.data.loaders import (
    build_sample_csv,
    build_sample_storms_csv,
    load_from_csv,
    load_from_dataframe,
    load_from_json,
    load_storm_events,
)


# ===========================================================================
# Fixtures
# ===========================================================================

@pytest.fixture
def simple_watershed() -> list[WatershedLandUse]:
    """A minimal two-polygon watershed for quick tests."""
    return [
        WatershedLandUse("residential_1_4acre", HydrologicSoilGroup.B, 50.0),
        WatershedLandUse("woods_good",           HydrologicSoilGroup.A, 50.0),
    ]


@pytest.fixture
def urban_watershed() -> list[WatershedLandUse]:
    """High-imperviousness urban watershed."""
    return [
        WatershedLandUse("impervious_surfaces",  HydrologicSoilGroup.D, 40.0),
        WatershedLandUse("commercial_business",  HydrologicSoilGroup.C, 30.0),
        WatershedLandUse("residential_1_8acre",  HydrologicSoilGroup.B, 30.0),
    ]


@pytest.fixture
def sample_csv(tmp_path: Path) -> Path:
    path = tmp_path / "watershed.csv"
    build_sample_csv(path)
    return path


@pytest.fixture
def sample_storms_csv(tmp_path: Path) -> Path:
    path = tmp_path / "storms.csv"
    build_sample_storms_csv(path)
    return path


# ===========================================================================
# 1. lookup_cn
# ===========================================================================

class TestLookupCN:
    def test_known_combination_returns_correct_cn(self):
        cn = lookup_cn("impervious_surfaces", HydrologicSoilGroup.A)
        assert cn == 98

    def test_woods_good_hsg_a(self):
        cn = lookup_cn("woods_good", HydrologicSoilGroup.A)
        assert cn == 30

    def test_woods_good_hsg_d(self):
        cn = lookup_cn("woods_good", HydrologicSoilGroup.D)
        assert cn == 77

    def test_unknown_land_use_raises_key_error(self):
        with pytest.raises(KeyError, match="No CN found"):
            lookup_cn("nonexistent_land_use", HydrologicSoilGroup.B)

    def test_cn_range_valid(self):
        """All table values must be 0–100."""
        from scs_cn.core.calculator import CN_TABLE
        for (lu, hsg), cn in CN_TABLE.items():
            assert 0 <= cn <= 100, f"Invalid CN {cn} for {lu}/{hsg}"


# ===========================================================================
# 2. adjust_cn_for_amc
# ===========================================================================

class TestAdjustCNForAMC:
    def test_amc_ii_returns_same(self):
        assert adjust_cn_for_amc(75.0, AntecedentMoistureCondition.AVERAGE) == 75.0

    def test_amc_i_lower_than_ii(self):
        cn_i = adjust_cn_for_amc(75.0, AntecedentMoistureCondition.DRY)
        assert cn_i < 75.0

    def test_amc_iii_higher_than_ii(self):
        cn_iii = adjust_cn_for_amc(75.0, AntecedentMoistureCondition.WET)
        assert cn_iii > 75.0

    def test_amc_ordering(self):
        cn_i   = adjust_cn_for_amc(75.0, AntecedentMoistureCondition.DRY)
        cn_ii  = adjust_cn_for_amc(75.0, AntecedentMoistureCondition.AVERAGE)
        cn_iii = adjust_cn_for_amc(75.0, AntecedentMoistureCondition.WET)
        assert cn_i < cn_ii < cn_iii

    def test_invalid_cn_raises(self):
        with pytest.raises(ValueError, match="CN must be in"):
            adjust_cn_for_amc(105.0, AntecedentMoistureCondition.AVERAGE)

    def test_boundary_values(self):
        """CN 0 and 100 edge cases."""
        assert adjust_cn_for_amc(0.0, AntecedentMoistureCondition.AVERAGE) == 0.0
        assert adjust_cn_for_amc(100.0, AntecedentMoistureCondition.AVERAGE) == 100.0

    @pytest.mark.parametrize("cn", [30, 50, 70, 90])
    def test_amc_adjustment_continuity(self, cn):
        """AMC III CN must always be > AMC II > AMC I for valid CNs."""
        cn_i   = adjust_cn_for_amc(cn, AntecedentMoistureCondition.DRY)
        cn_iii = adjust_cn_for_amc(cn, AntecedentMoistureCondition.WET)
        assert cn_i < cn < cn_iii


# ===========================================================================
# 3. compute_potential_retention
# ===========================================================================

class TestComputePotentialRetention:
    def test_cn_100_gives_zero_s(self):
        s, ia = compute_potential_retention(100.0)
        assert s == pytest.approx(0.0, abs=1e-6)
        assert ia == pytest.approx(0.0, abs=1e-6)

    def test_cn_72_approx_s(self):
        """S ≈ 98.9 mm for CN=72."""
        s, ia = compute_potential_retention(72.0)
        expected_s = (25_400 / 72) - 254
        assert s == pytest.approx(expected_s, rel=1e-6)
        assert ia == pytest.approx(0.2 * expected_s, rel=1e-6)

    def test_custom_lambda(self):
        s, ia = compute_potential_retention(75.0, lambda_=0.05)
        assert ia == pytest.approx(0.05 * s, rel=1e-6)

    def test_zero_cn_raises(self):
        with pytest.raises(ValueError, match="CN must be > 0"):
            compute_potential_retention(0.0)


# ===========================================================================
# 4. compute_runoff_depth
# ===========================================================================

class TestComputeRunoffDepth:
    def test_zero_rainfall_gives_zero_runoff(self):
        assert compute_runoff_depth(0.0, 75.0) == 0.0

    def test_rainfall_below_ia_gives_zero(self):
        """Rainfall ≤ Ia → no runoff."""
        s, ia = compute_potential_retention(75.0)
        q = compute_runoff_depth(ia * 0.99, 75.0)
        assert q == 0.0

    def test_runoff_less_than_rainfall(self):
        q = compute_runoff_depth(100.0, 75.0)
        assert 0 < q < 100.0

    def test_cn_98_mostly_runoff(self):
        """CN 98 (impervious) should yield runoff ≈ rainfall."""
        q = compute_runoff_depth(100.0, 98.0)
        assert q > 90.0

    def test_cn_30_low_runoff(self):
        """CN 30 (dense forest) should yield very low runoff."""
        q = compute_runoff_depth(100.0, 30.0)
        assert q < 10.0

    def test_negative_rainfall_raises(self):
        with pytest.raises(ValueError, match="rainfall_mm must be"):
            compute_runoff_depth(-5.0, 75.0)

    def test_runoff_increases_with_rainfall(self):
        """Runoff must be monotonically non-decreasing with rainfall."""
        rainfalls = [0, 10, 25, 50, 100, 150, 200]
        runoffs   = [compute_runoff_depth(p, 70.0) for p in rainfalls]
        for i in range(1, len(runoffs)):
            assert runoffs[i] >= runoffs[i - 1]

    def test_runoff_increases_with_cn(self):
        """Higher CN → higher runoff for same rainfall."""
        cns = [40, 60, 75, 90]
        runoffs = [compute_runoff_depth(80.0, cn) for cn in cns]
        for i in range(1, len(runoffs)):
            assert runoffs[i] > runoffs[i - 1]


# ===========================================================================
# 5. compute_composite_cn
# ===========================================================================

class TestComputeCompositeCN:
    def test_single_polygon(self):
        lu = WatershedLandUse("impervious_surfaces", HydrologicSoilGroup.B, 10.0)
        cn = compute_composite_cn([lu])
        assert cn == 98.0

    def test_equal_areas_returns_mean(self):
        lus = [
            WatershedLandUse("woods_good",          HydrologicSoilGroup.A, 50.0),
            WatershedLandUse("impervious_surfaces", HydrologicSoilGroup.A, 50.0),
        ]
        cn = compute_composite_cn(lus)
        assert cn == pytest.approx((30 + 98) / 2, rel=1e-6)

    def test_empty_list_raises(self):
        with pytest.raises(ValueError, match="must not be empty"):
            compute_composite_cn([])

    def test_weighted_correctly(self):
        lus = [
            WatershedLandUse("impervious_surfaces", HydrologicSoilGroup.B, 90.0),  # CN=98
            WatershedLandUse("woods_good",          HydrologicSoilGroup.A, 10.0),  # CN=30
        ]
        expected = (98 * 90 + 30 * 10) / 100
        assert compute_composite_cn(lus) == pytest.approx(expected, rel=1e-6)

    def test_custom_cn_override(self):
        lu = WatershedLandUse("impervious_surfaces", HydrologicSoilGroup.B, 10.0, custom_cn=55)
        cn = compute_composite_cn([lu])
        assert cn == 55.0


# ===========================================================================
# 6. analyze_watershed
# ===========================================================================

class TestAnalyzeWatershed:
    def test_returns_runoff_result(self, simple_watershed):
        result = analyze_watershed(simple_watershed, rainfall_mm=80.0)
        assert isinstance(result, RunoffResult)

    def test_zero_rainfall(self, simple_watershed):
        result = analyze_watershed(simple_watershed, rainfall_mm=0.0)
        assert result.runoff_mm == 0.0
        assert result.runoff_volume_m3 == 0.0

    def test_runoff_ratio_within_bounds(self, simple_watershed):
        result = analyze_watershed(simple_watershed, rainfall_mm=100.0)
        assert 0.0 <= result.runoff_ratio <= 1.0

    def test_urban_watershed_higher_runoff_ratio(self, simple_watershed, urban_watershed):
        p = 80.0
        r_simple = analyze_watershed(simple_watershed, p)
        r_urban  = analyze_watershed(urban_watershed, p)
        assert r_urban.runoff_ratio > r_simple.runoff_ratio

    def test_amc_wet_increases_runoff(self, simple_watershed):
        p = 80.0
        r_avg = analyze_watershed(simple_watershed, p, AntecedentMoistureCondition.AVERAGE)
        r_wet = analyze_watershed(simple_watershed, p, AntecedentMoistureCondition.WET)
        assert r_wet.runoff_mm > r_avg.runoff_mm

    def test_amc_dry_decreases_runoff(self, simple_watershed):
        p = 80.0
        r_avg = analyze_watershed(simple_watershed, p, AntecedentMoistureCondition.AVERAGE)
        r_dry = analyze_watershed(simple_watershed, p, AntecedentMoistureCondition.DRY)
        assert r_dry.runoff_mm < r_avg.runoff_mm

    def test_total_area_correct(self, simple_watershed):
        result = analyze_watershed(simple_watershed, rainfall_mm=50.0)
        expected = sum(lu.area_ha for lu in simple_watershed)
        assert result.total_area_ha == pytest.approx(expected, rel=1e-6)

    def test_volume_consistent_with_depth(self, simple_watershed):
        result = analyze_watershed(simple_watershed, rainfall_mm=80.0)
        expected_vol = result.runoff_mm / 1000.0 * result.total_area_ha * 10_000
        assert result.runoff_volume_m3 == pytest.approx(expected_vol, rel=1e-4)

    def test_breakdown_dataframe_has_correct_rows(self, simple_watershed):
        result = analyze_watershed(simple_watershed, rainfall_mm=80.0)
        assert len(result.land_use_breakdown) == len(simple_watershed)

    def test_negative_rainfall_raises(self, simple_watershed):
        with pytest.raises(ValueError, match="rainfall_mm must be"):
            analyze_watershed(simple_watershed, rainfall_mm=-10.0)

    def test_empty_land_uses_raises(self):
        with pytest.raises(ValueError, match="at least one"):
            analyze_watershed([], rainfall_mm=50.0)

    def test_summary_string_format(self, simple_watershed):
        result = analyze_watershed(simple_watershed, rainfall_mm=80.0)
        summary = result.summary()
        assert "SCS-CN Runoff Analysis Summary" in summary
        assert "Direct Runoff" in summary

    def test_runoff_curve_monotonic(self):
        df = runoff_curve(75.0, (0, 200), 100)
        assert df["runoff_mm"].is_monotonic_increasing


# ===========================================================================
# 7. WatershedLandUse validation
# ===========================================================================

class TestWatershedLandUseValidation:
    def test_negative_area_raises(self):
        with pytest.raises(ValueError, match="area_ha must be > 0"):
            WatershedLandUse("woods_good", HydrologicSoilGroup.A, -1.0)

    def test_zero_area_raises(self):
        with pytest.raises(ValueError, match="area_ha must be > 0"):
            WatershedLandUse("woods_good", HydrologicSoilGroup.A, 0.0)

    def test_invalid_custom_cn_raises(self):
        with pytest.raises(ValueError, match="custom_cn must be 0–100"):
            WatershedLandUse("woods_good", HydrologicSoilGroup.A, 10.0, custom_cn=101)

    def test_unknown_land_use_no_custom_cn_raises(self):
        with pytest.raises(ValueError, match="not found in CN table"):
            WatershedLandUse("fantasy_land", HydrologicSoilGroup.B, 10.0)

    def test_unknown_land_use_with_custom_cn_ok(self):
        lu = WatershedLandUse("fantasy_land", HydrologicSoilGroup.B, 10.0, custom_cn=65)
        assert lu.custom_cn == 65


# ===========================================================================
# 8. Data loaders
# ===========================================================================

class TestDataLoaders:
    def test_load_from_csv_roundtrip(self, sample_csv):
        land_uses = load_from_csv(sample_csv)
        assert len(land_uses) > 0
        assert all(isinstance(lu, WatershedLandUse) for lu in land_uses)

    def test_load_from_csv_not_found_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_from_csv(tmp_path / "ghost.csv")

    def test_load_from_json_roundtrip(self, tmp_path):
        records = [
            {"land_use": "woods_good", "soil_group": "A", "area_ha": 20.0, "amc": "II"},
            {"land_use": "pasture_good", "soil_group": "B", "area_ha": 15.0},
        ]
        json_path = tmp_path / "lu.json"
        json_path.write_text(json.dumps(records), encoding="utf-8")
        land_uses = load_from_json(json_path)
        assert len(land_uses) == 2

    def test_load_from_json_not_found_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_from_json(tmp_path / "ghost.json")

    def test_load_from_dataframe(self):
        df = pd.DataFrame([
            {"land_use": "woods_fair", "soil_group": "B", "area_ha": 30.0},
            {"land_use": "pasture_poor", "soil_group": "C", "area_ha": 10.0},
        ])
        land_uses = load_from_dataframe(df)
        assert len(land_uses) == 2

    def test_load_from_dataframe_missing_column_raises(self):
        df = pd.DataFrame([{"land_use": "woods_good", "area_ha": 10.0}])  # missing soil_group
        with pytest.raises(ValueError, match="missing required columns"):
            load_from_dataframe(df)

    def test_load_storm_events(self, sample_storms_csv):
        df = load_storm_events(sample_storms_csv)
        assert "rainfall_mm" in df.columns
        assert (df["rainfall_mm"] >= 0).all()

    def test_load_storm_events_negative_raises(self, tmp_path):
        bad_csv = tmp_path / "bad_storms.csv"
        pd.DataFrame([{"event_id": "X", "rainfall_mm": -5}]).to_csv(bad_csv, index=False)
        with pytest.raises(ValueError, match="Negative rainfall"):
            load_storm_events(bad_csv)

    def test_load_storm_events_missing_col_raises(self, tmp_path):
        bad_csv = tmp_path / "bad_storms2.csv"
        pd.DataFrame([{"event_id": "X"}]).to_csv(bad_csv, index=False)
        with pytest.raises(ValueError, match="rainfall_mm"):
            load_storm_events(bad_csv)

    def test_csv_case_insensitive_columns(self, tmp_path):
        """Column headers with mixed case should be accepted."""
        csv_path = tmp_path / "mixed.csv"
        pd.DataFrame([{"Land_Use": "woods_good", "Soil_Group": "A", "Area_Ha": 10.0}]).to_csv(
            csv_path, index=False
        )
        land_uses = load_from_csv(csv_path)
        assert len(land_uses) == 1


# ===========================================================================
# 9. Integration tests
# ===========================================================================

class TestIntegration:
    def test_full_pipeline_csv_to_result(self, sample_csv, sample_storms_csv):
        """Load CSV → analyze → batch storms → all consistent."""
        land_uses = load_from_csv(sample_csv)
        storms    = load_storm_events(sample_storms_csv)

        results = []
        for _, row in storms.iterrows():
            amc_val = AntecedentMoistureCondition(row["amc"])
            r = analyze_watershed(land_uses, float(row["rainfall_mm"]), amc_val)
            results.append(r)

        # Runoff should generally increase with rainfall
        runoffs = [r.runoff_mm for r in results]
        assert runoffs == sorted(runoffs), "Runoff should be non-decreasing with rainfall"

    def test_composite_cn_within_valid_range(self, sample_csv):
        land_uses = load_from_csv(sample_csv)
        cn = compute_composite_cn(land_uses)
        assert 0 < cn <= 100

    @pytest.mark.parametrize("rainfall_mm", [25, 50, 75, 100, 150])
    def test_runoff_never_exceeds_rainfall(self, simple_watershed, rainfall_mm):
        result = analyze_watershed(simple_watershed, rainfall_mm=rainfall_mm)
        assert result.runoff_mm <= rainfall_mm
