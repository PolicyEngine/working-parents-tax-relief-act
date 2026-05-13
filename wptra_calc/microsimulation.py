"""Aggregate impact calculations using enhanced CPS microsimulation.

Calculates federal income_tax, state_income_tax for budget impacts.
All distributional analysis (winners/losers, deciles, intra-decile) uses
household_net_income, matching app-v2 methodology.

Uses MicroSeries throughout. MicroSeries.sum() and .mean() are
automatically weighted, and boolean masks preserve entity alignment.
"""

from math import inf
from typing import Any

import policyengine as pe
from policyengine_core.reforms import Reform


# API v2 intra-decile bounds and labels
_INTRA_BOUNDS = [-inf, -0.05, -1e-3, 1e-3, 0.05, inf]
_INTRA_LABELS = [
    "Lose more than 5%",
    "Lose less than 5%",
    "No change",
    "Gain less than 5%",
    "Gain more than 5%",
]

# Reform dictionary to enable WPTRA
REFORM_DICT = {
    "gov.contrib.congress.mcdonald_rivet.working_parents_tax_relief_act.in_effect": {
        "2020-01-01.2100-12-31": True,
    },
}


def create_wptra_reform():
    """
    Create the Working Parents Tax Relief Act reform.

    Simply enables the in_effect parameter which activates the WPTRA
    EITC enhancements already coded in the US PolicyEngine model.

    Returns:
        Reform object for PolicyEngine Microsimulation.
    """
    return Reform.from_dict(REFORM_DICT, country_id="us")


def _create_microsimulation(
    *,
    dataset: str | None = None,
    reform: Reform | None = None,
    allow_unmanaged: bool = False,
):
    kwargs = {
        "reform": reform,
        "allow_unmanaged": allow_unmanaged,
    }
    if dataset is not None:
        kwargs["dataset"] = dataset
    return pe.us.managed_microsimulation(**kwargs)


def _calc(sim: Any, variable: str, year: int, map_to: str | None = None):
    kwargs = {"period": year}
    if map_to is not None:
        kwargs["map_to"] = map_to
    return sim.calc(variable, **kwargs)


def _mean_or_zero(series) -> float:
    count = float((series * 0 + 1).sum())
    return float(series.mean()) if count > 0 else 0.0


def _share_pct(series, mask=None) -> float:
    if mask is not None:
        series = series[mask]
    return _mean_or_zero(series) * 100


def _relative_change_mask(change, baseline, lower: float, upper: float):
    """Return a MicroSeries mask for relative-change bucket membership."""
    positive_baseline = baseline > 1
    relative_change = change / baseline
    capped_relative_change = change  # denominator is 1 when baseline <= 1
    return (
        positive_baseline
        & (relative_change > lower)
        & (relative_change <= upper)
    ) | (
        (~positive_baseline)
        & (capped_relative_change > lower)
        & (capped_relative_change <= upper)
    )


def _poverty_metrics(baseline_rate, reform_rate):
    """Return rate change and percent change for a poverty metric."""
    rate_change = reform_rate - baseline_rate
    percent_change = rate_change / baseline_rate * 100 if baseline_rate > 0 else 0.0
    return rate_change, percent_change


def calculate_aggregate_impact(year: int = 2026) -> dict:
    """Calculate aggregate impact of the Working Parents Tax Relief Act.

    Args:
        year: Tax year to calculate impacts for (default: 2026)

    Returns:
        Dictionary with budget, decile, intra_decile, poverty, and bracket data.
    """
    reform = create_wptra_reform()

    sim_baseline = _create_microsimulation()
    sim_reform = _create_microsimulation(reform=reform)

    # ===== FISCAL IMPACT =====
    # Federal income tax
    fed_baseline = _calc(sim_baseline, "income_tax", year, map_to="household")
    fed_reform = _calc(sim_reform, "income_tax", year, map_to="household")
    federal_tax_revenue_impact = float((fed_reform - fed_baseline).sum())

    # State/local income tax
    state_baseline = _calc(sim_baseline, "state_income_tax", year, map_to="household")
    state_reform = _calc(sim_reform, "state_income_tax", year, map_to="household")
    state_tax_revenue_impact = float((state_reform - state_baseline).sum())

    tax_revenue_impact = federal_tax_revenue_impact + state_tax_revenue_impact
    budgetary_impact = tax_revenue_impact  # No benefit spending for EITC reform

    # household_net_income change for all distributional analysis (app-v2 methodology)
    baseline_net_income = _calc(
        sim_baseline, "household_net_income", year, map_to="household"
    )
    reform_net_income = _calc(
        sim_reform, "household_net_income", year, map_to="household"
    )
    income_change = reform_net_income - baseline_net_income

    # Total households via MicroSeries aggregation.
    total_households = float((income_change * 0 + 1).sum())

    # ===== WINNERS / LOSERS =====
    winners = float((income_change > 1).sum())
    losers = float((income_change < -1).sum())
    beneficiaries = float((income_change > 0).sum())

    avg_benefit = (
        float(income_change[income_change > 0].mean())
        if beneficiaries > 0
        else 0.0
    )

    winners_rate = winners / total_households * 100
    losers_rate = losers / total_households * 100

    # ===== INCOME DECILE ANALYSIS =====
    decile = _calc(sim_baseline, "household_income_decile", year, map_to="household")

    decile_average = {}
    decile_relative = {}
    for d in range(1, 11):
        dmask = decile == d
        d_count = float(dmask.sum())
        if d_count > 0:
            d_baseline_sum = float(baseline_net_income[dmask].sum())
            d_change_sum = float(income_change[dmask].sum())
            decile_average[str(d)] = d_change_sum / d_count
            decile_relative[str(d)] = (
                d_change_sum / d_baseline_sum if d_baseline_sum != 0 else 0.0
            )
        else:
            decile_average[str(d)] = 0.0
            decile_relative[str(d)] = 0.0

    person_baseline_net_income = _calc(
        sim_baseline, "household_net_income", year, map_to="person"
    )
    person_reform_net_income = _calc(
        sim_reform, "household_net_income", year, map_to="person"
    )
    person_income_change = person_reform_net_income - person_baseline_net_income
    person_decile = _calc(
        sim_baseline, "household_income_decile", year, map_to="person"
    )

    intra_decile_deciles = {label: [] for label in _INTRA_LABELS}
    for d in range(1, 11):
        dmask = person_decile == d

        for lower, upper, label in zip(
            _INTRA_BOUNDS[:-1], _INTRA_BOUNDS[1:], _INTRA_LABELS
        ):
            bucket = _relative_change_mask(
                person_income_change,
                person_baseline_net_income,
                lower,
                upper,
            )
            intra_decile_deciles[label].append(_mean_or_zero(bucket[dmask]))

    intra_decile_all = {}
    for lower, upper, label in zip(
        _INTRA_BOUNDS[:-1], _INTRA_BOUNDS[1:], _INTRA_LABELS
    ):
        bucket = _relative_change_mask(
            person_income_change,
            person_baseline_net_income,
            lower,
            upper,
        )
        intra_decile_all[label] = _mean_or_zero(bucket)

    # ===== POVERTY IMPACT =====
    pov_bl = _calc(sim_baseline, "person_in_poverty", year, map_to="person")
    pov_rf = _calc(sim_reform, "person_in_poverty", year, map_to="person")
    is_child = _calc(sim_baseline, "age", year, map_to="person") < 18

    poverty_baseline_rate = _share_pct(pov_bl)
    poverty_reform_rate = _share_pct(pov_rf)
    poverty_rate_change, poverty_percent_change = _poverty_metrics(
        poverty_baseline_rate, poverty_reform_rate
    )

    child_poverty_baseline_rate = _share_pct(pov_bl, is_child)
    child_poverty_reform_rate = _share_pct(pov_rf, is_child)
    child_poverty_rate_change, child_poverty_percent_change = _poverty_metrics(
        child_poverty_baseline_rate, child_poverty_reform_rate
    )

    deep_bl = _calc(sim_baseline, "in_deep_poverty", year, map_to="person")
    deep_rf = _calc(sim_reform, "in_deep_poverty", year, map_to="person")
    deep_poverty_baseline_rate = _share_pct(deep_bl)
    deep_poverty_reform_rate = _share_pct(deep_rf)
    deep_poverty_rate_change, deep_poverty_percent_change = _poverty_metrics(
        deep_poverty_baseline_rate, deep_poverty_reform_rate
    )

    deep_child_poverty_baseline_rate = _share_pct(deep_bl, is_child)
    deep_child_poverty_reform_rate = _share_pct(deep_rf, is_child)
    deep_child_poverty_rate_change, deep_child_poverty_percent_change = (
        _poverty_metrics(
            deep_child_poverty_baseline_rate,
            deep_child_poverty_reform_rate,
        )
    )

    # ===== INCOME BRACKET BREAKDOWN =====
    agi = _calc(sim_reform, "adjusted_gross_income", year, map_to="household")
    affected = (income_change > 1) | (income_change < -1)

    income_brackets = [
        (0, 25_000, "$0 - $25k"),
        (25_000, 50_000, "$25k - $50k"),
        (50_000, 75_000, "$50k - $75k"),
        (75_000, 100_000, "$75k - $100k"),
        (100_000, 150_000, "$100k - $150k"),
        (150_000, 200_000, "$150k - $200k"),
        (200_000, float("inf"), "$200k+"),
    ]

    by_income_bracket = []
    for min_inc, max_inc, label in income_brackets:
        mask = (agi >= min_inc) & (agi < max_inc) & affected
        bracket_affected = float(mask.sum())
        if bracket_affected > 0:
            bracket_cost = float(income_change[mask].sum())
            bracket_avg = float(income_change[mask].mean())
        else:
            bracket_cost = 0.0
            bracket_avg = 0.0
        by_income_bracket.append(
            {
                "bracket": label,
                "beneficiaries": bracket_affected,
                "total_cost": bracket_cost,
                "avg_benefit": bracket_avg,
            }
        )

    return {
        "budget": {
            "budgetary_impact": budgetary_impact,
            "federal_tax_revenue_impact": federal_tax_revenue_impact,
            "state_tax_revenue_impact": state_tax_revenue_impact,
            "tax_revenue_impact": tax_revenue_impact,
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
        "total_cost": -budgetary_impact,
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
        "by_income_bracket": by_income_bracket,
    }
