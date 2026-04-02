"""
Pytest configuration and shared fixtures.
"""

import pytest


@pytest.fixture
def sample_household_params():
    """Sample household parameters for testing."""
    return {
        "age_head": 30,
        "age_spouse": None,
        "dependent_ages": [2],
        "income": 20000,
        "year": 2026,
        "max_earnings": 500000,
        "state_code": "CA",
    }


@pytest.fixture
def married_household_params():
    """Sample married household parameters for testing."""
    return {
        "age_head": 32,
        "age_spouse": 30,
        "dependent_ages": [1, 3],
        "income": 30000,
        "year": 2026,
        "max_earnings": 500000,
        "state_code": "TX",
    }
