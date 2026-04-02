"""
Tests for the precomputed CSV data files.

These tests verify that the CSV files have the correct structure
and can be parsed by the frontend.
"""

import csv
from pathlib import Path

import pytest


DATA_DIR = Path(__file__).parent.parent / "frontend" / "public" / "data"
EXPECTED_YEARS = list(range(2026, 2036))


class TestDistributionalImpactCSV:
    """Tests for distributional_impact.csv."""

    @pytest.fixture
    def data(self):
        """Load the distributional impact CSV."""
        filepath = DATA_DIR / "distributional_impact.csv"
        if not filepath.exists():
            pytest.skip("distributional_impact.csv not generated yet")
        with open(filepath, "r") as f:
            return list(csv.DictReader(f))

    def test_has_required_columns(self, data):
        """Test that all required columns exist."""
        required = ["year", "decile", "average_change", "relative_change"]
        for row in data:
            for col in required:
                assert col in row, f"Missing column: {col}"

    def test_has_all_deciles(self, data):
        """Test that all 10 deciles are present for each year."""
        for year in EXPECTED_YEARS:
            year_data = [r for r in data if int(r["year"]) == year]
            deciles = {r["decile"] for r in year_data}
            expected = {str(d) for d in range(1, 11)}
            assert deciles == expected, f"Missing deciles for year {year}"

    def test_values_are_numeric(self, data):
        """Test that numeric columns can be parsed."""
        for row in data:
            float(row["year"])
            float(row["average_change"])
            float(row["relative_change"])


class TestMetricsCSV:
    """Tests for metrics.csv."""

    @pytest.fixture
    def data(self):
        """Load the metrics CSV."""
        filepath = DATA_DIR / "metrics.csv"
        if not filepath.exists():
            pytest.skip("metrics.csv not generated yet")
        with open(filepath, "r") as f:
            return list(csv.DictReader(f))

    def test_has_required_columns(self, data):
        """Test that all required columns exist."""
        required = ["year", "metric", "value"]
        for row in data:
            for col in required:
                assert col in row, f"Missing column: {col}"

    def test_has_required_metrics(self, data):
        """Test that essential metrics are present for each year."""
        required_metrics = [
            "budgetary_impact",
            "winners",
            "losers",
            "poverty_baseline_rate",
            "poverty_reform_rate",
        ]
        for year in EXPECTED_YEARS:
            year_data = [r for r in data if int(r["year"]) == year]
            metrics = {r["metric"] for r in year_data}
            for metric in required_metrics:
                assert metric in metrics, f"Missing metric '{metric}' for year {year}"


class TestWinnersLosersCSV:
    """Tests for winners_losers.csv."""

    @pytest.fixture
    def data(self):
        """Load the winners/losers CSV."""
        filepath = DATA_DIR / "winners_losers.csv"
        if not filepath.exists():
            pytest.skip("winners_losers.csv not generated yet")
        with open(filepath, "r") as f:
            return list(csv.DictReader(f))

    def test_has_required_columns(self, data):
        """Test that all required columns exist."""
        required = [
            "year", "decile",
            "gain_more_5pct", "gain_less_5pct", "no_change",
            "lose_less_5pct", "lose_more_5pct"
        ]
        for row in data:
            for col in required:
                assert col in row, f"Missing column: {col}"

    def test_has_all_deciles_and_all(self, data):
        """Test that all deciles plus 'All' are present."""
        for year in EXPECTED_YEARS:
            year_data = [r for r in data if int(r["year"]) == year]
            deciles = {r["decile"] for r in year_data}
            expected = {"All"} | {str(d) for d in range(1, 11)}
            assert deciles == expected, f"Missing deciles for year {year}"

    def test_values_sum_to_one(self, data):
        """Test that bucket proportions roughly sum to 1."""
        for row in data:
            total = (
                float(row["gain_more_5pct"])
                + float(row["gain_less_5pct"])
                + float(row["no_change"])
                + float(row["lose_less_5pct"])
                + float(row["lose_more_5pct"])
            )
            assert abs(total - 1.0) < 0.01, f"Row does not sum to 1: {row}"


class TestIncomeBracketsCSV:
    """Tests for income_brackets.csv."""

    @pytest.fixture
    def data(self):
        """Load the income brackets CSV."""
        filepath = DATA_DIR / "income_brackets.csv"
        if not filepath.exists():
            pytest.skip("income_brackets.csv not generated yet")
        with open(filepath, "r") as f:
            return list(csv.DictReader(f))

    def test_has_required_columns(self, data):
        """Test that all required columns exist."""
        required = ["year", "bracket", "beneficiaries", "total_cost", "avg_benefit"]
        for row in data:
            for col in required:
                assert col in row, f"Missing column: {col}"

    def test_has_all_brackets(self, data):
        """Test that expected income brackets are present."""
        expected_brackets = {
            "$0 - $25k",
            "$25k - $50k",
            "$50k - $75k",
            "$75k - $100k",
            "$100k - $150k",
            "$150k - $200k",
            "$200k+",
        }
        for year in EXPECTED_YEARS:
            year_data = [r for r in data if int(r["year"]) == year]
            brackets = {r["bracket"] for r in year_data}
            assert brackets == expected_brackets, f"Missing brackets for year {year}"
