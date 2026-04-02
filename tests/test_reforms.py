"""
Tests for wptra_calc reforms module.

These tests verify that reform dictionaries are built correctly.
"""

import pytest
from wptra_calc.reforms import (
    REFORM_PARAMETER,
    build_reform_dict,
    get_reform_provisions,
)


class TestReformParameter:
    """Tests for the reform parameter constant."""

    def test_reform_parameter_path(self):
        """Test that the reform parameter path is correct."""
        assert REFORM_PARAMETER == (
            "gov.contrib.congress.mcdonald_rivet."
            "working_parents_tax_relief_act.in_effect"
        )


class TestBuildReformDict:
    """Tests for build_reform_dict function."""

    def test_default_years(self):
        """Test reform dict with default years (2026-2100)."""
        reform = build_reform_dict()

        assert REFORM_PARAMETER in reform
        assert "2026-01-01.2100-12-31" in reform[REFORM_PARAMETER]
        assert reform[REFORM_PARAMETER]["2026-01-01.2100-12-31"] is True

    def test_custom_years(self):
        """Test reform dict with custom start and end years."""
        reform = build_reform_dict(start_year=2027, end_year=2030)

        assert REFORM_PARAMETER in reform
        assert "2027-01-01.2030-12-31" in reform[REFORM_PARAMETER]
        assert reform[REFORM_PARAMETER]["2027-01-01.2030-12-31"] is True

    def test_reform_dict_structure_for_policyengine(self):
        """Test that the reform dict structure is valid for PolicyEngine."""
        reform = build_reform_dict()

        # Must be a dict with parameter paths as keys
        assert isinstance(reform, dict)

        # Each value must be a dict with period strings as keys
        for param_path, periods in reform.items():
            assert isinstance(param_path, str)
            assert isinstance(periods, dict)
            for period_str, value in periods.items():
                # Period string must be in "YYYY-MM-DD.YYYY-MM-DD" format
                assert "." in period_str
                start, end = period_str.split(".")
                assert len(start) == 10
                assert len(end) == 10


class TestGetReformProvisions:
    """Tests for get_reform_provisions function."""

    def test_returns_all_provisions(self):
        """Test that all expected provisions are returned."""
        provisions = get_reform_provisions()

        expected_keys = [
            "credit_percentage_increase_one_child",
            "credit_percentage_increase_per_young_child",
            "phaseout_percentage_increase_per_young_child",
            "young_child_age_threshold",
            "max_young_children",
        ]

        for key in expected_keys:
            assert key in provisions
            assert "description" in provisions[key]
            assert "parameter" in provisions[key]
            assert "value" in provisions[key]

    def test_provision_values(self):
        """Test that provision values match the bill."""
        provisions = get_reform_provisions()

        # Credit percentage increase for 1 child: 42.24pp
        assert provisions["credit_percentage_increase_one_child"]["value"] == 0.4224

        # Credit percentage increase per young child (2+): 30.07pp
        assert provisions["credit_percentage_increase_per_young_child"]["value"] == 0.3007

        # Phaseout percentage increase: 5pp per young child
        assert provisions["phaseout_percentage_increase_per_young_child"]["value"] == 0.05

        # Young child age threshold: under 4
        assert provisions["young_child_age_threshold"]["value"] == 4

        # Max young children: 3
        assert provisions["max_young_children"]["value"] == 3
