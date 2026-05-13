"""Modal-based data generation pipeline for Working Parents Tax Relief Act.

Runs microsimulation for each year (2026-2035) in parallel on Modal's
cloud infrastructure, avoiding local memory issues.

Usage:
    # Run the pipeline (computes all years in parallel on Modal)
    modal run scripts/modal_pipeline.py

    # Deploy as a scheduled job (optional)
    modal deploy scripts/modal_pipeline.py
"""

import os
from math import inf

import modal

# Modal app definition
app = modal.App("wptra-pipeline")

# Image with policyengine.py and US dependencies
# Using a large memory container for microsimulation
image = modal.Image.debian_slim(python_version="3.11").pip_install(
    "policyengine[us]==4.4.4",
    "numpy>=1.24.0",
    "pandas>=2.0.0",
)

YEARS = list(range(2026, 2036))

# Reform dictionary to enable WPTRA
REFORM_DICT = {
    "gov.contrib.congress.mcdonald_rivet.working_parents_tax_relief_act.in_effect": {
        "2020-01-01.2100-12-31": True,
    },
}


@app.function(
    image=image,
    memory=32768,  # 32GB RAM for microsimulation
    timeout=1800,  # 30 min timeout per year
    retries=1,
)
def calculate_year(year: int) -> dict:
    """Calculate aggregate impact for a single year on Modal."""
    import policyengine as pe
    from policyengine_core.reforms import Reform

    print(f"Starting calculation for year {year}...")

    # Intra-decile bounds and labels
    intra_bounds = [-inf, -0.05, -1e-3, 1e-3, 0.05, inf]
    intra_labels = [
        "Lose more than 5%",
        "Lose less than 5%",
        "No change",
        "Gain less than 5%",
        "Gain more than 5%",
    ]

    reform = Reform.from_dict(REFORM_DICT, country_id="us")

    def _calc(sim, variable: str, map_to: str | None = None):
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
        positive_baseline = baseline > 1
        relative_change = change / baseline
        capped_relative_change = change
        return (
            positive_baseline
            & (relative_change > lower)
            & (relative_change <= upper)
        ) | (
            (~positive_baseline)
            & (capped_relative_change > lower)
            & (capped_relative_change <= upper)
        )

    print("  Creating baseline simulation...")
    sim_baseline = pe.us.managed_microsimulation()
    print("  Creating reform simulation...")
    sim_reform = pe.us.managed_microsimulation(reform=reform)

    # ===== FISCAL IMPACT =====
    print("  Calculating fiscal impact...")
    fed_baseline = _calc(sim_baseline, "income_tax", map_to="household")
    fed_reform = _calc(sim_reform, "income_tax", map_to="household")
    federal_tax_revenue_impact = float((fed_reform - fed_baseline).sum())

    state_baseline = _calc(sim_baseline, "state_income_tax", map_to="household")
    state_reform = _calc(sim_reform, "state_income_tax", map_to="household")
    state_tax_revenue_impact = float((state_reform - state_baseline).sum())

    tax_revenue_impact = federal_tax_revenue_impact + state_tax_revenue_impact
    budgetary_impact = tax_revenue_impact

    # Net income for distributional analysis
    baseline_net_income = _calc(
        sim_baseline, "household_net_income", map_to="household"
    )
    reform_net_income = _calc(sim_reform, "household_net_income", map_to="household")
    income_change = reform_net_income - baseline_net_income

    total_households = float((income_change * 0 + 1).sum())

    # ===== WINNERS / LOSERS =====
    print("  Calculating winners/losers...")
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
    print("  Calculating decile analysis...")
    decile = _calc(sim_baseline, "household_income_decile", map_to="household")

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
        sim_baseline, "household_net_income", map_to="person"
    )
    person_reform_net_income = _calc(
        sim_reform, "household_net_income", map_to="person"
    )
    person_income_change = person_reform_net_income - person_baseline_net_income
    person_decile = _calc(
        sim_baseline, "household_income_decile", map_to="person"
    )

    intra_decile_deciles = {label: [] for label in intra_labels}
    for d in range(1, 11):
        dmask = person_decile == d

        for lower, upper, label in zip(
            intra_bounds[:-1], intra_bounds[1:], intra_labels
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
        intra_bounds[:-1], intra_bounds[1:], intra_labels
    ):
        bucket = _relative_change_mask(
            person_income_change,
            person_baseline_net_income,
            lower,
            upper,
        )
        intra_decile_all[label] = _mean_or_zero(bucket)

    # ===== POVERTY IMPACT =====
    print("  Calculating poverty impact...")
    pov_bl = _calc(sim_baseline, "person_in_poverty", map_to="person")
    pov_rf = _calc(sim_reform, "person_in_poverty", map_to="person")
    is_child = _calc(sim_baseline, "age", map_to="person") < 18

    poverty_baseline_rate = _share_pct(pov_bl)
    poverty_reform_rate = _share_pct(pov_rf)
    poverty_rate_change = poverty_reform_rate - poverty_baseline_rate
    poverty_percent_change = (
        poverty_rate_change / poverty_baseline_rate * 100
        if poverty_baseline_rate > 0
        else 0.0
    )

    child_poverty_baseline_rate = _share_pct(pov_bl, is_child)
    child_poverty_reform_rate = _share_pct(pov_rf, is_child)
    child_poverty_rate_change = child_poverty_reform_rate - child_poverty_baseline_rate
    child_poverty_percent_change = (
        child_poverty_rate_change / child_poverty_baseline_rate * 100
        if child_poverty_baseline_rate > 0
        else 0.0
    )

    # Deep poverty
    deep_bl = _calc(sim_baseline, "in_deep_poverty", map_to="person")
    deep_rf = _calc(sim_reform, "in_deep_poverty", map_to="person")
    deep_poverty_baseline_rate = _share_pct(deep_bl)
    deep_poverty_reform_rate = _share_pct(deep_rf)
    deep_poverty_rate_change = deep_poverty_reform_rate - deep_poverty_baseline_rate
    deep_poverty_percent_change = (
        deep_poverty_rate_change / deep_poverty_baseline_rate * 100
        if deep_poverty_baseline_rate > 0
        else 0.0
    )

    deep_child_poverty_baseline_rate = _share_pct(deep_bl, is_child)
    deep_child_poverty_reform_rate = _share_pct(deep_rf, is_child)
    deep_child_poverty_rate_change = (
        deep_child_poverty_reform_rate - deep_child_poverty_baseline_rate
    )
    deep_child_poverty_percent_change = (
        deep_child_poverty_rate_change / deep_child_poverty_baseline_rate * 100
        if deep_child_poverty_baseline_rate > 0
        else 0.0
    )

    # ===== INCOME BRACKET BREAKDOWN (at tax unit level) =====
    print("  Calculating income brackets (tax unit level)...")
    # Use tax unit level for income brackets since EITC is filed at tax unit level
    # Calculate income change as the negative of income tax change (tax reduction = income gain)
    tu_baseline_tax = _calc(sim_baseline, "income_tax")
    tu_reform_tax = _calc(sim_reform, "income_tax")
    tu_income_change = tu_baseline_tax - tu_reform_tax  # Positive when tax is reduced

    # Calculate JCT-style expanded income for bracket assignment
    # Expanded income = AGI + tax-exempt interest + employer FICA + workers' comp
    #                   + nontaxable Social Security + foreign exclusion
    # NOTE: Medicare cost excluded - PolicyEngine's medicare_cost allocates total program
    # spending to all tax units, not just actual Medicare recipient benefits
    tu_agi = _calc(sim_baseline, "adjusted_gross_income")
    tu_tax_exempt_interest = _calc(
        sim_baseline, "tax_exempt_interest_income", map_to="tax_unit"
    )
    tu_employer_payroll_tax = _calc(
        sim_baseline, "employer_payroll_tax", map_to="tax_unit"
    )
    tu_workers_comp = _calc(
        sim_baseline, "workers_compensation", map_to="tax_unit"
    )
    tu_tax_exempt_ss = _calc(sim_baseline, "tax_exempt_social_security")
    tu_foreign_exclusion = _calc(
        sim_baseline, "foreign_earned_income_exclusion", map_to="tax_unit"
    )

    tu_expanded_income = (
        tu_agi
        + tu_tax_exempt_interest
        + tu_employer_payroll_tax
        + tu_workers_comp
        + tu_tax_exempt_ss
        + tu_foreign_exclusion
    )
    tu_affected_mask = (tu_income_change > 1) | (tu_income_change < -1)

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
        mask = (
            (tu_expanded_income >= min_inc)
            & (tu_expanded_income < max_inc)
            & tu_affected_mask
        )
        bracket_affected = float(mask.sum())
        if bracket_affected > 0:
            bracket_cost = float(tu_income_change[mask].sum())
            bracket_avg = float(tu_income_change[mask].mean())
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

    print(f"  Year {year} complete!")

    return {
        "year": year,
        "budget": {
            "budgetary_impact": budgetary_impact,
            "federal_tax_revenue_impact": federal_tax_revenue_impact,
            "state_tax_revenue_impact": state_tax_revenue_impact,
            "tax_revenue_impact": tax_revenue_impact,
            "households": total_households,
        },
        "decile": {"average": decile_average, "relative": decile_relative},
        "intra_decile": {"all": intra_decile_all, "deciles": intra_decile_deciles},
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


@app.local_entrypoint()
def main(years: str = ""):
    """Run the pipeline: compute all years in parallel on Modal, save CSVs locally.

    Args:
        years: Comma-separated list of years to run (e.g., "2028,2030,2033").
               If empty, runs all years 2026-2035.
    """
    import pandas as pd

    output_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "frontend",
        "public",
        "data",
    )
    os.makedirs(output_dir, exist_ok=True)

    # Parse years argument
    if years:
        target_years = [int(y.strip()) for y in years.split(",")]
    else:
        target_years = YEARS

    print(f"Running WPTRA microsimulation for years {target_years} on Modal...")
    print(f"Output directory: {output_dir}")

    # Run specified years in parallel on Modal
    results = list(calculate_year.map(target_years))

    # Sort by year
    results.sort(key=lambda r: r["year"])

    # Extract and save CSVs
    distributional_rows = []
    metrics_rows = []
    winners_losers_rows = []
    income_bracket_rows = []

    for result in results:
        year = result["year"]

        # Distributional impact
        for decile, avg in result["decile"]["average"].items():
            distributional_rows.append(
                {
                    "year": year,
                    "decile": decile,
                    "average_change": round(avg, 2),
                    "relative_change": round(result["decile"]["relative"][decile], 6),
                }
            )

        # Metrics
        metrics = [
            ("budgetary_impact", result["budget"]["budgetary_impact"]),
            (
                "federal_tax_revenue_impact",
                result["budget"]["federal_tax_revenue_impact"],
            ),
            ("state_tax_revenue_impact", result["budget"]["state_tax_revenue_impact"]),
            ("tax_revenue_impact", result["budget"]["tax_revenue_impact"]),
            ("households", result["budget"]["households"]),
            ("total_cost", result["total_cost"]),
            ("beneficiaries", result["beneficiaries"]),
            ("avg_benefit", result["avg_benefit"]),
            ("winners", result["winners"]),
            ("losers", result["losers"]),
            ("winners_rate", result["winners_rate"]),
            ("losers_rate", result["losers_rate"]),
            ("poverty_baseline_rate", result["poverty_baseline_rate"]),
            ("poverty_reform_rate", result["poverty_reform_rate"]),
            ("poverty_rate_change", result["poverty_rate_change"]),
            ("poverty_percent_change", result["poverty_percent_change"]),
            ("child_poverty_baseline_rate", result["child_poverty_baseline_rate"]),
            ("child_poverty_reform_rate", result["child_poverty_reform_rate"]),
            ("child_poverty_rate_change", result["child_poverty_rate_change"]),
            ("child_poverty_percent_change", result["child_poverty_percent_change"]),
            ("deep_poverty_baseline_rate", result["deep_poverty_baseline_rate"]),
            ("deep_poverty_reform_rate", result["deep_poverty_reform_rate"]),
            ("deep_poverty_rate_change", result["deep_poverty_rate_change"]),
            ("deep_poverty_percent_change", result["deep_poverty_percent_change"]),
            (
                "deep_child_poverty_baseline_rate",
                result["deep_child_poverty_baseline_rate"],
            ),
            (
                "deep_child_poverty_reform_rate",
                result["deep_child_poverty_reform_rate"],
            ),
            (
                "deep_child_poverty_rate_change",
                result["deep_child_poverty_rate_change"],
            ),
            (
                "deep_child_poverty_percent_change",
                result["deep_child_poverty_percent_change"],
            ),
        ]
        for metric, value in metrics:
            metrics_rows.append({"year": year, "metric": metric, "value": value})

        # Winners/losers
        intra = result["intra_decile"]
        winners_losers_rows.append(
            {
                "year": year,
                "decile": "All",
                "gain_more_5pct": intra["all"]["Gain more than 5%"],
                "gain_less_5pct": intra["all"]["Gain less than 5%"],
                "no_change": intra["all"]["No change"],
                "lose_less_5pct": intra["all"]["Lose less than 5%"],
                "lose_more_5pct": intra["all"]["Lose more than 5%"],
            }
        )
        for i in range(10):
            winners_losers_rows.append(
                {
                    "year": year,
                    "decile": str(i + 1),
                    "gain_more_5pct": intra["deciles"]["Gain more than 5%"][i],
                    "gain_less_5pct": intra["deciles"]["Gain less than 5%"][i],
                    "no_change": intra["deciles"]["No change"][i],
                    "lose_less_5pct": intra["deciles"]["Lose less than 5%"][i],
                    "lose_more_5pct": intra["deciles"]["Lose more than 5%"][i],
                }
            )

        # Income brackets
        for b in result["by_income_bracket"]:
            income_bracket_rows.append(
                {
                    "year": year,
                    "bracket": b["bracket"],
                    "beneficiaries": b["beneficiaries"],
                    "total_cost": b["total_cost"],
                    "avg_benefit": b["avg_benefit"],
                }
            )

    # Define sort orders for categorical columns
    BRACKET_ORDER = [
        "$0 - $25k",
        "$25k - $50k",
        "$50k - $75k",
        "$75k - $100k",
        "$100k - $150k",
        "$150k - $200k",
        "$200k+",
    ]
    DECILE_ORDER = ["All"] + [str(i) for i in range(1, 11)]

    # Helper to merge new data with existing CSV
    def merge_and_save(new_rows: list, filename: str, years_to_replace: list):
        filepath = os.path.join(output_dir, filename)
        new_df = pd.DataFrame(new_rows)

        # If file exists and we're doing a partial update, merge with existing
        if os.path.exists(filepath) and len(years_to_replace) < 10:
            existing_df = pd.read_csv(filepath)
            # Remove old data for years we're replacing
            existing_df = existing_df[~existing_df["year"].isin(years_to_replace)]
            # Combine
            combined_df = pd.concat([existing_df, new_df], ignore_index=True)
        else:
            combined_df = new_df

        # Sort by year and secondary column if present
        if "bracket" in combined_df.columns:
            combined_df["_sort"] = combined_df["bracket"].map(
                {b: i for i, b in enumerate(BRACKET_ORDER)}
            )
            combined_df = combined_df.sort_values(["year", "_sort"]).drop(
                columns=["_sort"]
            )
        elif "decile" in combined_df.columns:
            combined_df["_sort"] = (
                combined_df["decile"]
                .astype(str)
                .map({d: i for i, d in enumerate(DECILE_ORDER)})
            )
            combined_df = combined_df.sort_values(["year", "_sort"]).drop(
                columns=["_sort"]
            )
        else:
            combined_df = combined_df.sort_values("year")

        combined_df = combined_df.reset_index(drop=True)
        combined_df.to_csv(filepath, index=False)
        print(f"Saved: {filepath}")

    # Save CSVs (merging with existing data if partial update)
    merge_and_save(distributional_rows, "distributional_impact.csv", target_years)
    merge_and_save(metrics_rows, "metrics.csv", target_years)
    merge_and_save(winners_losers_rows, "winners_losers.csv", target_years)
    merge_and_save(income_bracket_rows, "income_brackets.csv", target_years)

    print(f"\nDone! All data saved to {output_dir}/")
