"""
Compute national impacts for the Working Parents Tax Relief Act.
Outputs CSV files for the dashboard.

Uses the wptra_calc module which interfaces with policyengine-us.
"""

import sys
import os

# Add parent directory to path so we can import wptra_calc
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from wptra_calc.microsimulation import calculate_aggregate_impact

OUTPUT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "frontend", "public", "data"
)


def results_to_csvs(results: dict, year: int):
    """Convert the results dict to lists for CSV output."""

    # Metrics
    metrics = [
        {"year": year, "metric": "baseline_net_income", "value": results["budget"]["baseline_net_income"]},
        {"year": year, "metric": "budgetary_impact", "value": round(results["budget"]["budgetary_impact"], 0)},
        {"year": year, "metric": "tax_revenue_impact", "value": round(results["budget"]["tax_revenue_impact"], 0)},
        {"year": year, "metric": "benefit_spending_impact", "value": round(results["budget"]["benefit_spending_impact"], 0)},
        {"year": year, "metric": "households", "value": int(results["budget"]["households"])},
        {"year": year, "metric": "total_cost", "value": round(results["total_cost"], 0)},
        {"year": year, "metric": "beneficiaries", "value": int(results["beneficiaries"])},
        {"year": year, "metric": "avg_benefit", "value": round(results["avg_benefit"], 2)},
        {"year": year, "metric": "winners", "value": int(results["winners"])},
        {"year": year, "metric": "losers", "value": int(results["losers"])},
        {"year": year, "metric": "winners_rate", "value": round(results["winners_rate"], 4)},
        {"year": year, "metric": "losers_rate", "value": round(results["losers_rate"], 6)},
        {"year": year, "metric": "poverty_baseline_rate", "value": round(results["poverty_baseline_rate"], 4)},
        {"year": year, "metric": "poverty_reform_rate", "value": round(results["poverty_reform_rate"], 4)},
        {"year": year, "metric": "poverty_rate_change", "value": round(results["poverty_rate_change"], 4)},
        {"year": year, "metric": "poverty_percent_change", "value": round(results["poverty_percent_change"], 2)},
        {"year": year, "metric": "child_poverty_baseline_rate", "value": round(results["child_poverty_baseline_rate"], 4)},
        {"year": year, "metric": "child_poverty_reform_rate", "value": round(results["child_poverty_reform_rate"], 4)},
        {"year": year, "metric": "child_poverty_rate_change", "value": round(results["child_poverty_rate_change"], 4)},
        {"year": year, "metric": "child_poverty_percent_change", "value": round(results["child_poverty_percent_change"], 2)},
        {"year": year, "metric": "deep_poverty_baseline_rate", "value": round(results["deep_poverty_baseline_rate"], 4)},
        {"year": year, "metric": "deep_poverty_reform_rate", "value": round(results["deep_poverty_reform_rate"], 4)},
        {"year": year, "metric": "deep_poverty_rate_change", "value": round(results["deep_poverty_rate_change"], 4)},
        {"year": year, "metric": "deep_poverty_percent_change", "value": round(results["deep_poverty_percent_change"], 2)},
        {"year": year, "metric": "deep_child_poverty_baseline_rate", "value": round(results["deep_child_poverty_baseline_rate"], 4)},
        {"year": year, "metric": "deep_child_poverty_reform_rate", "value": round(results["deep_child_poverty_reform_rate"], 4)},
        {"year": year, "metric": "deep_child_poverty_rate_change", "value": round(results["deep_child_poverty_rate_change"], 4)},
        {"year": year, "metric": "deep_child_poverty_percent_change", "value": round(results["deep_child_poverty_percent_change"], 2)},
    ]

    # Distributional (by decile)
    distributional = []
    for decile_str, avg_change in results["decile"]["average"].items():
        rel_change = results["decile"]["relative"].get(decile_str, 0)
        distributional.append({
            "year": year,
            "decile": int(decile_str),
            "average_change": round(avg_change, 2),
            "relative_change": round(rel_change, 2),
        })

    # Winners/losers
    winners_losers = []

    # All households
    all_data = results["intra_decile"]["all"]
    winners_losers.append({
        "year": year,
        "decile": "All",
        "gain_more_5pct": round(all_data["gain_more_than_5pct"], 4),
        "gain_less_5pct": round(all_data["gain_less_than_5pct"], 4),
        "no_change": round(all_data["no_change"], 4),
        "lose_less_5pct": round(all_data["lose_less_than_5pct"], 4),
        "lose_more_5pct": round(all_data["lose_more_than_5pct"], 4),
    })

    # By decile
    decile_data = results["intra_decile"]["deciles"]
    for i in range(10):
        winners_losers.append({
            "year": year,
            "decile": i + 1,
            "gain_more_5pct": round(decile_data["gain_more_than_5pct"][i], 4),
            "gain_less_5pct": round(decile_data["gain_less_than_5pct"][i], 4),
            "no_change": round(decile_data["no_change"][i], 4),
            "lose_less_5pct": round(decile_data["lose_less_than_5pct"][i], 4),
            "lose_more_5pct": round(decile_data["lose_more_than_5pct"][i], 4),
        })

    # Income brackets
    income_brackets = []
    for bracket in results["by_income_bracket"]:
        income_brackets.append({
            "year": year,
            "bracket": bracket["bracket"],
            "beneficiaries": int(bracket["beneficiaries"]),
            "total_cost": round(bracket["total_cost"], 0),
            "avg_benefit": round(bracket["avg_benefit"], 2),
        })

    return metrics, distributional, winners_losers, income_brackets


def main():
    all_metrics = []
    all_distributional = []
    all_winners_losers = []
    all_income_brackets = []

    # Compute for years 2026-2035
    for year in range(2026, 2036):
        try:
            results = calculate_aggregate_impact(year, verbose=True)
            metrics, distributional, winners_losers, income_brackets = results_to_csvs(results, year)
            all_metrics.extend(metrics)
            all_distributional.extend(distributional)
            all_winners_losers.extend(winners_losers)
            all_income_brackets.extend(income_brackets)
            print(f"  Year {year} complete")
        except Exception as e:
            print(f"  Error for year {year}: {e}")
            import traceback
            traceback.print_exc()

    # Save to CSV
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    pd.DataFrame(all_metrics).to_csv(f"{OUTPUT_DIR}/metrics.csv", index=False)
    pd.DataFrame(all_distributional).to_csv(f"{OUTPUT_DIR}/distributional_impact.csv", index=False)
    pd.DataFrame(all_winners_losers).to_csv(f"{OUTPUT_DIR}/winners_losers.csv", index=False)
    pd.DataFrame(all_income_brackets).to_csv(f"{OUTPUT_DIR}/income_brackets.csv", index=False)

    print(f"\nCSV files written to {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
