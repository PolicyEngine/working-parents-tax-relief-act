"""
Household situation builder for the Working Parents Tax Relief Act calculator.

This module provides utilities to build PolicyEngine household situations
for API calls.
"""

from typing import Any, Dict, List, Optional
import numpy as np


GROUP_UNITS = ["families", "spm_units", "tax_units", "households"]


def _add_member_to_units(
    situation: Dict[str, Any], member_id: str
) -> None:
    """Add a member to all group units in the situation."""
    for unit in GROUP_UNITS:
        unit_dict = situation[unit]
        first_key = next(iter(unit_dict))
        unit_dict[first_key]["members"].append(member_id)


def build_household_situation(
    age_head: int,
    age_spouse: Optional[int],
    dependent_ages: List[int],
    income: float,
    year: int,
    max_earnings: float,
    state_code: str,
    include_axes: bool = True,
) -> Dict[str, Any]:
    """
    Build a PolicyEngine household situation dictionary.

    Args:
        age_head: Age of the primary filer
        age_spouse: Age of spouse (None if single)
        dependent_ages: List of ages for each dependent
        income: Employment income
        year: Tax year
        max_earnings: Maximum earnings for axis calculation
        state_code: Two-letter state code (e.g., "CA")
        include_axes: Whether to include axes for parametric calculation

    Returns:
        A household situation dictionary for the PolicyEngine API.
    """
    year_str = str(year)
    axis_max = max(max_earnings, income)

    situation: Dict[str, Any] = {
        "people": {
            "you": {
                "age": {year_str: age_head},
                "employment_income": {year_str: income if not include_axes else None},
            },
        },
        "families": {"your family": {"members": ["you"]}},
        "marital_units": {"your marital unit": {"members": ["you"]}},
        "spm_units": {"your household": {"members": ["you"]}},
        "tax_units": {
            "your tax unit": {
                "members": ["you"],
                "adjusted_gross_income": {year_str: None},
            },
        },
        "households": {
            "your household": {
                "members": ["you"],
                "state_code": {year_str: state_code},
                "household_net_income": {year_str: None},
            },
        },
    }

    if include_axes:
        count = min(4001, max(501, int(axis_max / 500)))
        situation["axes"] = [
            [
                {
                    "name": "employment_income",
                    "min": 0,
                    "max": axis_max,
                    "count": count,
                    "period": year_str,
                    "target": "person",
                },
            ],
        ]

    # Add spouse if married
    if age_spouse is not None:
        situation["people"]["your partner"] = {"age": {year_str: age_spouse}}
        _add_member_to_units(situation, "your partner")
        situation["marital_units"]["your marital unit"]["members"].append("your partner")

    # Add dependents
    for i, age in enumerate(dependent_ages):
        if i == 0:
            child_id = "your first dependent"
        elif i == 1:
            child_id = "your second dependent"
        else:
            child_id = f"dependent_{i + 1}"

        situation["people"][child_id] = {"age": {year_str: age}}
        _add_member_to_units(situation, child_id)
        situation["marital_units"][f"{child_id}'s marital unit"] = {
            "members": [child_id],
        }

    return situation


def calculate_household_impact(
    age_head: int,
    age_spouse: Optional[int],
    dependent_ages: List[int],
    income: float,
    year: int,
    max_earnings: float,
    state_code: str,
) -> Dict[str, Any]:
    """
    Calculate household impact using the PolicyEngine API.

    Note: This function is provided for completeness but the actual API calls
    are handled by the frontend TypeScript code. This Python version can be
    used for testing or batch processing.

    Args:
        age_head: Age of the primary filer
        age_spouse: Age of spouse (None if single)
        dependent_ages: List of ages for each dependent
        income: Employment income
        year: Tax year
        max_earnings: Maximum earnings for chart x-axis
        state_code: Two-letter state code

    Returns:
        Impact analysis results including income_range, net_income_change, etc.
    """
    # Import here to avoid circular dependencies and allow module to be imported
    # without policyengine_us installed (for documentation/type checking)
    try:
        from policyengine_us import Simulation
    except ImportError:
        raise ImportError(
            "policyengine_us is required for calculate_household_impact. "
            "Install it with: pip install policyengine-us"
        )

    from .reforms import build_reform_dict

    situation = build_household_situation(
        age_head=age_head,
        age_spouse=age_spouse,
        dependent_ages=dependent_ages,
        income=income,
        year=year,
        max_earnings=max_earnings,
        state_code=state_code,
        include_axes=True,
    )

    year_str = str(year)

    # Run baseline simulation
    baseline_sim = Simulation(situation=situation)
    baseline_net_income = baseline_sim.calculate(
        "household_net_income", year
    )
    income_range = baseline_sim.calculate("employment_income", year)

    # Run reform simulation
    reform_dict = build_reform_dict(start_year=year)
    reform_sim = Simulation(situation=situation, reform=reform_dict)
    reform_net_income = reform_sim.calculate("household_net_income", year)

    # Calculate change
    net_income_change = reform_net_income - baseline_net_income

    # Interpolate at user's income
    def interpolate(xs: np.ndarray, ys: np.ndarray, x: float) -> float:
        if x <= xs[0]:
            return float(ys[0])
        if x >= xs[-1]:
            return float(ys[-1])
        return float(np.interp(x, xs, ys))

    baseline_at_income = interpolate(income_range, baseline_net_income, income)
    reform_at_income = interpolate(income_range, reform_net_income, income)

    return {
        "income_range": income_range.tolist(),
        "net_income_change": net_income_change.tolist(),
        "benefit_at_income": {
            "baseline": baseline_at_income,
            "reform": reform_at_income,
            "difference": reform_at_income - baseline_at_income,
        },
        "x_axis_max": max_earnings,
    }
