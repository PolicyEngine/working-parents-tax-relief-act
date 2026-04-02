"""
Working Parents Tax Relief Act (WPTRA) calculation module.

This module provides utilities for calculating household and aggregate impacts
of the Working Parents Tax Relief Act of 2026, which enhances the EITC for
parents of young children (under age 4).
"""

from .household import build_household_situation, calculate_household_impact
from .reforms import build_reform_dict, REFORM_PARAMETER
from .microsimulation import calculate_aggregate_impact

__all__ = [
    "build_household_situation",
    "calculate_household_impact",
    "build_reform_dict",
    "REFORM_PARAMETER",
    "calculate_aggregate_impact",
]

__version__ = "1.0.0"
