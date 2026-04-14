"""Modal-based data generation pipeline for Working Parents Tax Relief Act.

Runs microsimulation for each year (2026-2035) in parallel on Modal's
cloud infrastructure, avoiding local memory issues.

Usage:
    # Run the pipeline (computes all years in parallel on Modal)
    modal run scripts/modal_pipeline.py

    # Deploy as a scheduled job (optional)
    modal deploy scripts/modal_pipeline.py
"""

import json
import os

import modal

# Modal app definition
app = modal.App("wptra-pipeline")

# Image with policyengine-us and dependencies
# Using a large memory container for microsimulation
image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "policyengine-us>=1.150.0",
        "numpy>=1.24.0",
        "pandas>=2.0.0",
    )
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
    import numpy as np
    from policyengine_us import Microsimulation
    from policyengine_core.reforms import Reform

    print(f"Starting calculation for year {year}...")

    # Intra-decile bounds and labels
    intra_bounds = [-np.inf, -0.05, -1e-3, 1e-3, 0.05, np.inf]
    intra_labels = [
        "Lose more than 5%",
        "Lose less than 5%",
        "No change",
        "Gain less than 5%",
        "Gain more than 5%",
    ]

    reform = Reform.from_dict(REFORM_DICT, country_id="us")

    print(f"  Creating baseline simulation...")
    sim_baseline = Microsimulation()
    print(f"  Creating reform simulation...")
    sim_reform = Microsimulation(reform=reform)

    # ===== FISCAL IMPACT =====
    print(f"  Calculating fiscal impact...")
    fed_baseline = sim_baseline.calculate("income_tax", period=year, map_to="household")
    fed_reform = sim_reform.calculate("income_tax", period=year, map_to="household")
    federal_tax_revenue_impact = float((fed_reform - fed_baseline).sum())

    state_baseline = sim_baseline.calculate("state_income_tax", period=year, map_to="household")
    state_reform = sim_reform.calculate("state_income_tax", period=year, map_to="household")
    state_tax_revenue_impact = float((state_reform - state_baseline).sum())

    tax_revenue_impact = federal_tax_revenue_impact + state_tax_revenue_impact
    budgetary_impact = tax_revenue_impact

    # Net income for distributional analysis
    baseline_net_income = sim_baseline.calculate("household_net_income", period=year, map_to="household")
    reform_net_income = sim_reform.calculate("household_net_income", period=year, map_to="household")
    income_change = reform_net_income - baseline_net_income

    total_households = float((income_change * 0 + 1).sum())

    # ===== WINNERS / LOSERS =====
    print(f"  Calculating winners/losers...")
    winners = float((income_change > 1).sum())
    losers = float((income_change < -1).sum())
    beneficiaries = float((income_change > 0).sum())

    affected = abs(income_change) > 1
    affected_count = float(affected.sum())
    avg_benefit = (
        float(income_change[affected].sum() / affected.sum())
        if affected_count > 0
        else 0.0
    )

    winners_rate = winners / total_households * 100
    losers_rate = losers / total_households * 100

    # ===== INCOME DECILE ANALYSIS =====
    print(f"  Calculating decile analysis...")
    decile = sim_baseline.calculate("household_income_decile", period=year, map_to="household")

    decile_average = {}
    decile_relative = {}
    for d in range(1, 11):
        dmask = decile == d
        d_count = float(dmask.sum())
        if d_count > 0:
            d_baseline_sum = float(baseline_net_income[dmask].sum())
            d_change_sum = float(income_change[dmask].sum())
            decile_average[str(d)] = d_change_sum / d_count
            decile_relative[str(d)] = d_change_sum / d_baseline_sum if d_baseline_sum != 0 else 0.0
        else:
            decile_average[str(d)] = 0.0
            decile_relative[str(d)] = 0.0

    # Intra-decile
    household_weight = sim_reform.calculate("household_weight", period=year)
    people_per_hh = sim_baseline.calculate("household_count_people", period=year, map_to="household")
    capped_baseline = np.maximum(np.array(baseline_net_income), 1)
    rel_change_arr = np.array(income_change) / capped_baseline

    decile_arr = np.array(decile)
    weight_arr = np.array(household_weight)
    people_weighted = np.array(people_per_hh) * weight_arr

    intra_decile_deciles = {label: [] for label in intra_labels}
    for d in range(1, 11):
        dmask = decile_arr == d
        d_people = people_weighted[dmask]
        d_total_people = d_people.sum()
        d_rel = rel_change_arr[dmask]

        for lower, upper, label in zip(intra_bounds[:-1], intra_bounds[1:], intra_labels):
            in_group = (d_rel > lower) & (d_rel <= upper)
            proportion = float(d_people[in_group].sum() / d_total_people) if d_total_people > 0 else 0.0
            intra_decile_deciles[label].append(proportion)

    intra_decile_all = {label: sum(intra_decile_deciles[label]) / 10 for label in intra_labels}

    # ===== POVERTY IMPACT =====
    print(f"  Calculating poverty impact...")
    pov_bl = sim_baseline.calculate("in_poverty", period=year, map_to="person")
    pov_rf = sim_reform.calculate("in_poverty", period=year, map_to="person")
    poverty_baseline_rate = float(pov_bl.mean() * 100)
    poverty_reform_rate = float(pov_rf.mean() * 100)
    poverty_rate_change = poverty_reform_rate - poverty_baseline_rate
    poverty_percent_change = poverty_rate_change / poverty_baseline_rate * 100 if poverty_baseline_rate > 0 else 0.0

    # Child poverty
    age_arr = np.array(sim_baseline.calculate("age", period=year))
    is_child = age_arr < 18
    pw_arr = np.array(sim_baseline.calculate("person_weight", period=year))
    child_w = pw_arr[is_child]
    total_child_w = child_w.sum()

    pov_bl_arr = np.array(pov_bl).astype(bool)
    pov_rf_arr = np.array(pov_rf).astype(bool)

    def _child_rate(arr):
        return float((arr[is_child] * child_w).sum() / total_child_w * 100) if total_child_w > 0 else 0.0

    child_poverty_baseline_rate = _child_rate(pov_bl_arr)
    child_poverty_reform_rate = _child_rate(pov_rf_arr)
    child_poverty_rate_change = child_poverty_reform_rate - child_poverty_baseline_rate
    child_poverty_percent_change = (
        child_poverty_rate_change / child_poverty_baseline_rate * 100
        if child_poverty_baseline_rate > 0
        else 0.0
    )

    # Deep poverty
    deep_bl = sim_baseline.calculate("in_deep_poverty", period=year, map_to="person")
    deep_rf = sim_reform.calculate("in_deep_poverty", period=year, map_to="person")
    deep_poverty_baseline_rate = float(deep_bl.mean() * 100)
    deep_poverty_reform_rate = float(deep_rf.mean() * 100)
    deep_poverty_rate_change = deep_poverty_reform_rate - deep_poverty_baseline_rate
    deep_poverty_percent_change = (
        deep_poverty_rate_change / deep_poverty_baseline_rate * 100
        if deep_poverty_baseline_rate > 0
        else 0.0
    )

    deep_bl_arr = np.array(deep_bl).astype(bool)
    deep_rf_arr = np.array(deep_rf).astype(bool)
    deep_child_poverty_baseline_rate = _child_rate(deep_bl_arr)
    deep_child_poverty_reform_rate = _child_rate(deep_rf_arr)
    deep_child_poverty_rate_change = deep_child_poverty_reform_rate - deep_child_poverty_baseline_rate
    deep_child_poverty_percent_change = (
        deep_child_poverty_rate_change / deep_child_poverty_baseline_rate * 100
        if deep_child_poverty_baseline_rate > 0
        else 0.0
    )

    # ===== INCOME BRACKET BREAKDOWN (at tax unit level) =====
    print(f"  Calculating income brackets (tax unit level)...")
    # Use tax unit level for income brackets since EITC is filed at tax unit level
    # Calculate income change as the negative of income tax change (tax reduction = income gain)
    tu_baseline_tax = np.array(sim_baseline.calculate("income_tax", period=year))
    tu_reform_tax = np.array(sim_reform.calculate("income_tax", period=year))
    tu_income_change = tu_baseline_tax - tu_reform_tax  # Positive when tax is reduced
    tu_weight = np.array(sim_baseline.calculate("tax_unit_weight", period=year))

    # Calculate JCT-style expanded income for bracket assignment
    # Expanded income = AGI + tax-exempt interest + employer FICA + workers' comp
    #                   + nontaxable Social Security + foreign exclusion
    # NOTE: Medicare cost excluded - PolicyEngine's medicare_cost allocates total program
    # spending to all tax units, not just actual Medicare recipient benefits
    tu_agi = np.array(sim_baseline.calculate("adjusted_gross_income", period=year))
    tu_tax_exempt_interest = np.array(sim_baseline.calculate("tax_exempt_interest_income", period=year, map_to="tax_unit"))
    tu_employer_payroll_tax = np.array(sim_baseline.calculate("employer_payroll_tax", period=year, map_to="tax_unit"))
    tu_workers_comp = np.array(sim_baseline.calculate("workers_compensation", period=year, map_to="tax_unit"))
    # Nontaxable SS: total SS (aggregated to tax unit) minus taxable portion
    # taxable_social_security is natively at tax_unit level, so we get total SS at same level
    tu_taxable_ss = np.array(sim_baseline.calculate("taxable_social_security", period=year))
    tu_total_ss = np.array(sim_baseline.calculate("social_security", period=year, map_to="tax_unit"))
    # Ensure arrays match by padding if needed (microdata edge case)
    if len(tu_total_ss) != len(tu_taxable_ss):
        # Use zeros for nontaxable SS if shapes don't match
        tu_nontaxable_ss = np.zeros_like(tu_agi)
    else:
        tu_nontaxable_ss = tu_total_ss - tu_taxable_ss
    tu_foreign_exclusion = np.array(sim_baseline.calculate("foreign_earned_income_exclusion", period=year, map_to="tax_unit"))

    tu_expanded_income = (
        tu_agi
        + tu_tax_exempt_interest
        + tu_employer_payroll_tax
        + tu_workers_comp
        + np.maximum(tu_nontaxable_ss, 0)  # Ensure non-negative
        + tu_foreign_exclusion
    )
    tu_affected_mask = np.abs(tu_income_change) > 1

    income_brackets = [
        (0, 25_000, "$0 - $25k"),
        (25_000, 50_000, "$25k - $50k"),
        (50_000, 75_000, "$50k - $75k"),
        (75_000, 100_000, "$75k - $100k"),
        (100_000, float("inf"), "$100k+"),
    ]

    by_income_bracket = []
    for min_inc, max_inc, label in income_brackets:
        mask = (tu_expanded_income >= min_inc) & (tu_expanded_income < max_inc) & tu_affected_mask
        bracket_affected = float(tu_weight[mask].sum())
        if bracket_affected > 0:
            bracket_cost = float((tu_income_change[mask] * tu_weight[mask]).sum())
            bracket_avg = float(np.average(tu_income_change[mask], weights=tu_weight[mask]))
        else:
            bracket_cost = 0.0
            bracket_avg = 0.0
        by_income_bracket.append({
            "bracket": label,
            "beneficiaries": bracket_affected,
            "total_cost": bracket_cost,
            "avg_benefit": bracket_avg,
        })

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
            distributional_rows.append({
                "year": year,
                "decile": decile,
                "average_change": round(avg, 2),
                "relative_change": round(result["decile"]["relative"][decile], 6),
            })

        # Metrics
        metrics = [
            ("budgetary_impact", result["budget"]["budgetary_impact"]),
            ("federal_tax_revenue_impact", result["budget"]["federal_tax_revenue_impact"]),
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
            ("deep_child_poverty_baseline_rate", result["deep_child_poverty_baseline_rate"]),
            ("deep_child_poverty_reform_rate", result["deep_child_poverty_reform_rate"]),
            ("deep_child_poverty_rate_change", result["deep_child_poverty_rate_change"]),
            ("deep_child_poverty_percent_change", result["deep_child_poverty_percent_change"]),
        ]
        for metric, value in metrics:
            metrics_rows.append({"year": year, "metric": metric, "value": value})

        # Winners/losers
        intra = result["intra_decile"]
        winners_losers_rows.append({
            "year": year,
            "decile": "All",
            "gain_more_5pct": intra["all"]["Gain more than 5%"],
            "gain_less_5pct": intra["all"]["Gain less than 5%"],
            "no_change": intra["all"]["No change"],
            "lose_less_5pct": intra["all"]["Lose less than 5%"],
            "lose_more_5pct": intra["all"]["Lose more than 5%"],
        })
        for i in range(10):
            winners_losers_rows.append({
                "year": year,
                "decile": str(i + 1),
                "gain_more_5pct": intra["deciles"]["Gain more than 5%"][i],
                "gain_less_5pct": intra["deciles"]["Gain less than 5%"][i],
                "no_change": intra["deciles"]["No change"][i],
                "lose_less_5pct": intra["deciles"]["Lose less than 5%"][i],
                "lose_more_5pct": intra["deciles"]["Lose more than 5%"][i],
            })

        # Income brackets
        for b in result["by_income_bracket"]:
            income_bracket_rows.append({
                "year": year,
                "bracket": b["bracket"],
                "beneficiaries": b["beneficiaries"],
                "total_cost": b["total_cost"],
                "avg_benefit": b["avg_benefit"],
            })

    # Define sort orders for categorical columns
    BRACKET_ORDER = ["$0 - $25k", "$25k - $50k", "$50k - $75k", "$75k - $100k",
                     "$100k - $150k", "$150k - $200k", "$200k+"]
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
            combined_df = combined_df.sort_values(["year", "_sort"]).drop(columns=["_sort"])
        elif "decile" in combined_df.columns:
            combined_df["_sort"] = combined_df["decile"].astype(str).map(
                {d: i for i, d in enumerate(DECILE_ORDER)}
            )
            combined_df = combined_df.sort_values(["year", "_sort"]).drop(columns=["_sort"])
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
