#!/usr/bin/env python3
"""
Pipeline worker for single-year microsimulation.

This script is called by pipeline.py to process one year at a time.
It runs the microsimulation and appends results to the shared CSV files.

Usage:
    python scripts/_pipeline_worker.py 2026
"""

import csv
import sys
from pathlib import Path
from typing import Any, Dict

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

OUTPUT_DIR = Path(__file__).parent.parent / "frontend" / "public" / "data"


def write_distributional_csv(year: int, decile_data: Dict[str, Any]) -> None:
    """Write distributional impact data to CSV."""
    filepath = OUTPUT_DIR / "distributional_impact.csv"
    file_exists = filepath.exists()

    rows = []
    for decile in range(1, 11):
        rows.append({
            "year": year,
            "decile": str(decile),
            "average_change": decile_data["average"].get(str(decile), 0),
            "relative_change": decile_data["relative"].get(str(decile), 0),
        })

    with open(filepath, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["year", "decile", "average_change", "relative_change"])
        if not file_exists:
            writer.writeheader()
        writer.writerows(rows)


def write_metrics_csv(year: int, data: Dict[str, Any]) -> None:
    """Write aggregate metrics to CSV."""
    filepath = OUTPUT_DIR / "metrics.csv"
    file_exists = filepath.exists()

    metrics = [
        ("baseline_net_income", data["budget"]["baseline_net_income"]),
        ("budgetary_impact", data["budget"]["budgetary_impact"]),
        ("tax_revenue_impact", data["budget"]["tax_revenue_impact"]),
        ("benefit_spending_impact", data["budget"]["benefit_spending_impact"]),
        ("households", data["budget"]["households"]),
        ("total_cost", data["total_cost"]),
        ("beneficiaries", data["beneficiaries"]),
        ("avg_benefit", data["avg_benefit"]),
        ("winners", data["winners"]),
        ("losers", data["losers"]),
        ("winners_rate", data["winners_rate"]),
        ("losers_rate", data["losers_rate"]),
        ("poverty_baseline_rate", data["poverty_baseline_rate"]),
        ("poverty_reform_rate", data["poverty_reform_rate"]),
        ("poverty_rate_change", data["poverty_rate_change"]),
        ("poverty_percent_change", data["poverty_percent_change"]),
        ("child_poverty_baseline_rate", data["child_poverty_baseline_rate"]),
        ("child_poverty_reform_rate", data["child_poverty_reform_rate"]),
        ("child_poverty_rate_change", data["child_poverty_rate_change"]),
        ("child_poverty_percent_change", data["child_poverty_percent_change"]),
        ("deep_poverty_baseline_rate", data["deep_poverty_baseline_rate"]),
        ("deep_poverty_reform_rate", data["deep_poverty_reform_rate"]),
        ("deep_poverty_rate_change", data["deep_poverty_rate_change"]),
        ("deep_poverty_percent_change", data["deep_poverty_percent_change"]),
        ("deep_child_poverty_baseline_rate", data["deep_child_poverty_baseline_rate"]),
        ("deep_child_poverty_reform_rate", data["deep_child_poverty_reform_rate"]),
        ("deep_child_poverty_rate_change", data["deep_child_poverty_rate_change"]),
        ("deep_child_poverty_percent_change", data["deep_child_poverty_percent_change"]),
    ]

    rows = [{"year": year, "metric": name, "value": value} for name, value in metrics]

    with open(filepath, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["year", "metric", "value"])
        if not file_exists:
            writer.writeheader()
        writer.writerows(rows)


def write_winners_losers_csv(year: int, intra_decile: Dict[str, Any]) -> None:
    """Write winners/losers breakdown to CSV."""
    filepath = OUTPUT_DIR / "winners_losers.csv"
    file_exists = filepath.exists()

    rows = []

    # All households
    all_data = intra_decile["all"]
    rows.append({
        "year": year,
        "decile": "All",
        "gain_more_5pct": all_data["gain_more_than_5pct"],
        "gain_less_5pct": all_data["gain_less_than_5pct"],
        "no_change": all_data["no_change"],
        "lose_less_5pct": all_data["lose_less_than_5pct"],
        "lose_more_5pct": all_data["lose_more_than_5pct"],
    })

    # By decile
    deciles = intra_decile["deciles"]
    for i in range(10):
        rows.append({
            "year": year,
            "decile": str(i + 1),
            "gain_more_5pct": deciles["gain_more_than_5pct"][i],
            "gain_less_5pct": deciles["gain_less_than_5pct"][i],
            "no_change": deciles["no_change"][i],
            "lose_less_5pct": deciles["lose_less_than_5pct"][i],
            "lose_more_5pct": deciles["lose_more_than_5pct"][i],
        })

    with open(filepath, "a", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "year", "decile", "gain_more_5pct", "gain_less_5pct",
                "no_change", "lose_less_5pct", "lose_more_5pct"
            ],
        )
        if not file_exists:
            writer.writeheader()
        writer.writerows(rows)


def write_income_brackets_csv(year: int, brackets: list) -> None:
    """Write income bracket impact data to CSV."""
    filepath = OUTPUT_DIR / "income_brackets.csv"
    file_exists = filepath.exists()

    rows = [
        {
            "year": year,
            "bracket": b["bracket"],
            "beneficiaries": b["beneficiaries"],
            "total_cost": b["total_cost"],
            "avg_benefit": b["avg_benefit"],
        }
        for b in brackets
    ]

    with open(filepath, "a", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["year", "bracket", "beneficiaries", "total_cost", "avg_benefit"],
        )
        if not file_exists:
            writer.writeheader()
        writer.writerows(rows)


def main():
    if len(sys.argv) != 2:
        print("Usage: python _pipeline_worker.py YEAR")
        sys.exit(1)

    year = int(sys.argv[1])
    print(f"Running microsimulation for year {year}...")

    # Import here to avoid slow imports when just checking args
    from wptra_calc.microsimulation import calculate_aggregate_impact

    # Run microsimulation
    try:
        results = calculate_aggregate_impact(year, verbose=True)
    except ImportError as e:
        print(f"ERROR: {e}")
        print("Install policyengine-us to run the microsimulation.")
        sys.exit(1)

    # Ensure output directory exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Write outputs
    print("Writing output files...")
    write_distributional_csv(year, results["decile"])
    write_metrics_csv(year, results)
    write_winners_losers_csv(year, results["intra_decile"])
    write_income_brackets_csv(year, results["by_income_bracket"])

    print(f"Year {year} complete.")


if __name__ == "__main__":
    main()
