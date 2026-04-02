"""
Microsimulation utilities for the Working Parents Tax Relief Act.

This module provides functions to run aggregate impact calculations
using PolicyEngine's Microsimulation class.
"""

from typing import Any, Dict, List, Optional
import numpy as np


def calculate_aggregate_impact(
    year: int,
    dataset: Optional[str] = None,
    verbose: bool = True,
) -> Dict[str, Any]:
    """
    Calculate aggregate impact of the Working Parents Tax Relief Act for a given year.

    Args:
        year: The tax year to simulate (e.g., 2026)
        dataset: Optional dataset name (defaults to enhanced_cps)
        verbose: Whether to print progress messages

    Returns:
        Dictionary containing all aggregate impact metrics including:
        - budgetary_impact: Total cost/savings of the reform
        - winners/losers: Number of households gaining/losing
        - poverty_impact: Changes in poverty rates
        - distributional_impact: Impact by income decile
        - income_brackets: Impact by income bracket
    """
    try:
        from policyengine_us import Microsimulation
    except ImportError:
        raise ImportError(
            "policyengine_us is required for calculate_aggregate_impact. "
            "Install it with: pip install policyengine-us"
        )

    from .reforms import build_reform_dict

    if verbose:
        print(f"Running microsimulation for year {year}...")

    # Run baseline
    if verbose:
        print("  Running baseline simulation...")
    baseline = Microsimulation(dataset=dataset)

    # Run reform
    if verbose:
        print("  Running reform simulation...")
    reform_dict = build_reform_dict(start_year=year)
    reform = Microsimulation(reform=reform_dict, dataset=dataset)

    # Get weights
    household_weight = baseline.calculate("household_weight", year)

    # Calculate net income
    baseline_net_income = baseline.calculate("household_net_income", year)
    reform_net_income = reform.calculate("household_net_income", year)
    net_income_change = reform_net_income - baseline_net_income

    # Budget impact
    budgetary_impact = float(
        np.sum(net_income_change * household_weight)
    )

    # Tax and benefit components
    baseline_tax = baseline.calculate("income_tax", year)
    reform_tax = reform.calculate("income_tax", year)
    tax_revenue_impact = float(
        np.sum((reform_tax - baseline_tax) * household_weight)
    )

    benefit_spending_impact = budgetary_impact - (-tax_revenue_impact)

    # Total households
    total_households = float(np.sum(household_weight))

    # Winners and losers (using $10 threshold)
    threshold = 10
    winners_mask = net_income_change > threshold
    losers_mask = net_income_change < -threshold

    winners = float(np.sum(household_weight[winners_mask]))
    losers = float(np.sum(household_weight[losers_mask]))
    winners_rate = winners / total_households
    losers_rate = losers / total_households

    # Calculate beneficiaries and average benefit for those who gain
    beneficiaries = winners
    if beneficiaries > 0:
        avg_benefit = float(
            np.sum(net_income_change[winners_mask] * household_weight[winners_mask])
            / beneficiaries
        )
    else:
        avg_benefit = 0.0

    total_cost = abs(budgetary_impact)

    # Poverty calculations
    baseline_in_poverty = baseline.calculate("in_poverty", year)
    reform_in_poverty = reform.calculate("in_poverty", year)
    baseline_in_deep_poverty = baseline.calculate("in_deep_poverty", year)
    reform_in_deep_poverty = reform.calculate("in_deep_poverty", year)

    person_weight = baseline.calculate("person_weight", year)
    is_child = baseline.calculate("is_child", year)

    total_persons = float(np.sum(person_weight))
    total_children = float(np.sum(person_weight[is_child]))

    # Overall poverty rates
    poverty_baseline_rate = float(np.sum(baseline_in_poverty * person_weight)) / total_persons
    poverty_reform_rate = float(np.sum(reform_in_poverty * person_weight)) / total_persons
    poverty_rate_change = poverty_reform_rate - poverty_baseline_rate
    poverty_percent_change = (
        (poverty_rate_change / poverty_baseline_rate * 100)
        if poverty_baseline_rate > 0
        else 0.0
    )

    # Child poverty rates
    child_poverty_baseline_rate = (
        float(np.sum(baseline_in_poverty[is_child] * person_weight[is_child]))
        / total_children
        if total_children > 0
        else 0.0
    )
    child_poverty_reform_rate = (
        float(np.sum(reform_in_poverty[is_child] * person_weight[is_child]))
        / total_children
        if total_children > 0
        else 0.0
    )
    child_poverty_rate_change = child_poverty_reform_rate - child_poverty_baseline_rate
    child_poverty_percent_change = (
        (child_poverty_rate_change / child_poverty_baseline_rate * 100)
        if child_poverty_baseline_rate > 0
        else 0.0
    )

    # Deep poverty rates
    deep_poverty_baseline_rate = (
        float(np.sum(baseline_in_deep_poverty * person_weight)) / total_persons
    )
    deep_poverty_reform_rate = (
        float(np.sum(reform_in_deep_poverty * person_weight)) / total_persons
    )
    deep_poverty_rate_change = deep_poverty_reform_rate - deep_poverty_baseline_rate
    deep_poverty_percent_change = (
        (deep_poverty_rate_change / deep_poverty_baseline_rate * 100)
        if deep_poverty_baseline_rate > 0
        else 0.0
    )

    # Deep child poverty rates
    deep_child_poverty_baseline_rate = (
        float(np.sum(baseline_in_deep_poverty[is_child] * person_weight[is_child]))
        / total_children
        if total_children > 0
        else 0.0
    )
    deep_child_poverty_reform_rate = (
        float(np.sum(reform_in_deep_poverty[is_child] * person_weight[is_child]))
        / total_children
        if total_children > 0
        else 0.0
    )
    deep_child_poverty_rate_change = (
        deep_child_poverty_reform_rate - deep_child_poverty_baseline_rate
    )
    deep_child_poverty_percent_change = (
        (deep_child_poverty_rate_change / deep_child_poverty_baseline_rate * 100)
        if deep_child_poverty_baseline_rate > 0
        else 0.0
    )

    # Distributional impact by income decile
    income_decile = baseline.calculate("household_income_decile", year)
    decile_average: Dict[str, float] = {}
    decile_relative: Dict[str, float] = {}

    for d in range(1, 11):
        mask = income_decile == d
        decile_weight = household_weight[mask]
        decile_total_weight = float(np.sum(decile_weight))

        if decile_total_weight > 0:
            decile_change = net_income_change[mask]
            decile_baseline = baseline_net_income[mask]

            avg_change = float(np.sum(decile_change * decile_weight) / decile_total_weight)
            avg_baseline = float(np.sum(decile_baseline * decile_weight) / decile_total_weight)

            decile_average[str(d)] = avg_change
            decile_relative[str(d)] = (
                (avg_change / avg_baseline * 100) if avg_baseline > 0 else 0.0
            )
        else:
            decile_average[str(d)] = 0.0
            decile_relative[str(d)] = 0.0

    # Winners/losers by decile (intra-decile)
    intra_decile_all = _calculate_intra_decile_buckets(
        net_income_change, baseline_net_income, household_weight
    )

    intra_decile_deciles: Dict[str, List[float]] = {
        "gain_more_than_5pct": [],
        "gain_less_than_5pct": [],
        "no_change": [],
        "lose_less_than_5pct": [],
        "lose_more_than_5pct": [],
    }

    for d in range(1, 11):
        mask = income_decile == d
        decile_buckets = _calculate_intra_decile_buckets(
            net_income_change[mask],
            baseline_net_income[mask],
            household_weight[mask],
        )
        for key in intra_decile_deciles:
            intra_decile_deciles[key].append(decile_buckets[key])

    # Income bracket impact
    agi = baseline.calculate("adjusted_gross_income", year)
    income_brackets = _calculate_income_bracket_impact(
        agi, net_income_change, household_weight
    )

    if verbose:
        print(f"  Microsimulation complete. Budgetary impact: ${budgetary_impact/1e9:.2f}B")

    return {
        "year": year,
        "budget": {
            "baseline_net_income": float(np.sum(baseline_net_income * household_weight)),
            "budgetary_impact": budgetary_impact,
            "tax_revenue_impact": tax_revenue_impact,
            "benefit_spending_impact": benefit_spending_impact,
            "households": total_households,
        },
        "decile": {
            "average": decile_average,
            "relative": decile_relative,
        },
        "intra_decile": {
            "all": intra_decile_all,
            "deciles": intra_decile_deciles,
        },
        "poverty": {
            "poverty": {
                "all": {"baseline": poverty_baseline_rate, "reform": poverty_reform_rate},
                "child": {"baseline": child_poverty_baseline_rate, "reform": child_poverty_reform_rate},
            },
            "deep_poverty": {
                "all": {"baseline": deep_poverty_baseline_rate, "reform": deep_poverty_reform_rate},
                "child": {"baseline": deep_child_poverty_baseline_rate, "reform": deep_child_poverty_reform_rate},
            },
        },
        "total_cost": total_cost,
        "beneficiaries": beneficiaries,
        "avg_benefit": avg_benefit,
        "winners": winners,
        "losers": losers,
        "winners_rate": winners_rate,
        "losers_rate": losers_rate,
        "poverty_baseline_rate": poverty_baseline_rate,
        "poverty_reform_rate": poverty_reform_rate,
        "poverty_rate_change": poverty_rate_change,
        "poverty_percent_change": poverty_percent_change,
        "child_poverty_baseline_rate": child_poverty_baseline_rate,
        "child_poverty_reform_rate": child_poverty_reform_rate,
        "child_poverty_rate_change": child_poverty_rate_change,
        "child_poverty_percent_change": child_poverty_percent_change,
        "deep_poverty_baseline_rate": deep_poverty_baseline_rate,
        "deep_poverty_reform_rate": deep_poverty_reform_rate,
        "deep_poverty_rate_change": deep_poverty_rate_change,
        "deep_poverty_percent_change": deep_poverty_percent_change,
        "deep_child_poverty_baseline_rate": deep_child_poverty_baseline_rate,
        "deep_child_poverty_reform_rate": deep_child_poverty_reform_rate,
        "deep_child_poverty_rate_change": deep_child_poverty_rate_change,
        "deep_child_poverty_percent_change": deep_child_poverty_percent_change,
        "by_income_bracket": income_brackets,
    }


def _calculate_intra_decile_buckets(
    net_income_change: np.ndarray,
    baseline_net_income: np.ndarray,
    weights: np.ndarray,
) -> Dict[str, float]:
    """Calculate the proportion of households in each change bucket."""
    total_weight = float(np.sum(weights))
    if total_weight == 0:
        return {
            "gain_more_than_5pct": 0.0,
            "gain_less_than_5pct": 0.0,
            "no_change": 1.0,
            "lose_less_than_5pct": 0.0,
            "lose_more_than_5pct": 0.0,
        }

    # Calculate percentage change (avoid division by zero)
    with np.errstate(divide="ignore", invalid="ignore"):
        pct_change = np.where(
            baseline_net_income != 0,
            net_income_change / baseline_net_income * 100,
            0,
        )

    # Define buckets
    gain_more_5 = pct_change > 5
    gain_less_5 = (pct_change > 0.01) & (pct_change <= 5)
    no_change = (pct_change >= -0.01) & (pct_change <= 0.01)
    lose_less_5 = (pct_change < -0.01) & (pct_change >= -5)
    lose_more_5 = pct_change < -5

    return {
        "gain_more_than_5pct": float(np.sum(weights[gain_more_5]) / total_weight),
        "gain_less_than_5pct": float(np.sum(weights[gain_less_5]) / total_weight),
        "no_change": float(np.sum(weights[no_change]) / total_weight),
        "lose_less_than_5pct": float(np.sum(weights[lose_less_5]) / total_weight),
        "lose_more_than_5pct": float(np.sum(weights[lose_more_5]) / total_weight),
    }


def _calculate_income_bracket_impact(
    agi: np.ndarray,
    net_income_change: np.ndarray,
    weights: np.ndarray,
) -> List[Dict[str, Any]]:
    """Calculate impact by AGI income bracket."""
    brackets = [
        ("$0 - $25k", 0, 25000),
        ("$25k - $50k", 25000, 50000),
        ("$50k - $75k", 50000, 75000),
        ("$75k - $100k", 75000, 100000),
        ("$100k - $150k", 100000, 150000),
        ("$150k - $200k", 150000, 200000),
        ("$200k+", 200000, float("inf")),
    ]

    results = []
    for label, low, high in brackets:
        mask = (agi >= low) & (agi < high)
        bracket_weight = weights[mask]
        total_weight = float(np.sum(bracket_weight))

        if total_weight > 0:
            bracket_change = net_income_change[mask]
            beneficiaries_mask = bracket_change > 10
            beneficiaries = float(np.sum(bracket_weight[beneficiaries_mask]))
            total_cost = float(np.sum(bracket_change * bracket_weight))
            avg_benefit = total_cost / beneficiaries if beneficiaries > 0 else 0.0
        else:
            beneficiaries = 0.0
            total_cost = 0.0
            avg_benefit = 0.0

        results.append({
            "bracket": label,
            "beneficiaries": beneficiaries,
            "total_cost": total_cost,
            "avg_benefit": avg_benefit,
        })

    return results
