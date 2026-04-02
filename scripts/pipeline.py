#!/usr/bin/env python3
"""
Data pipeline for the Working Parents Tax Relief Act calculator.

This script orchestrates the generation of precomputed CSV data for the
National Impact tab. It runs microsimulations for multiple years and
outputs CSV files to frontend/public/data/.

Usage:
    python scripts/pipeline.py           # Run all years, skip existing
    python scripts/pipeline.py --fresh   # Regenerate all data
    python scripts/pipeline.py --year 2026  # Run single year
"""

import argparse
import subprocess
import sys
from pathlib import Path
from typing import List


# Configuration
YEARS = list(range(2026, 2036))  # 2026-2035
OUTPUT_DIR = Path(__file__).parent.parent / "frontend" / "public" / "data"


def run_year(year: int, force: bool = False) -> bool:
    """
    Run the pipeline worker for a single year.

    Args:
        year: The year to process
        force: Whether to force regeneration even if data exists

    Returns:
        True if successful, False otherwise
    """
    worker_script = Path(__file__).parent / "_pipeline_worker.py"

    # Check if data already exists (unless force is True)
    metrics_file = OUTPUT_DIR / "metrics.csv"
    if not force and metrics_file.exists():
        import csv
        with open(metrics_file, "r") as f:
            reader = csv.DictReader(f)
            existing_years = {int(row["year"]) for row in reader}
            if year in existing_years:
                print(f"  Year {year} already exists in metrics.csv, skipping...")
                return True

    # Run worker subprocess
    print(f"  Processing year {year}...")
    try:
        result = subprocess.run(
            [sys.executable, str(worker_script), str(year)],
            capture_output=True,
            text=True,
            check=True,
        )
        if result.stdout:
            print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"  ERROR processing year {year}:")
        print(e.stderr)
        return False


def merge_csv_files(years: List[int]) -> None:
    """
    Merge per-year CSV outputs into consolidated files.

    The worker script appends to shared CSV files, so this function
    just ensures they exist and have proper headers.
    """
    # The worker handles appending, so we just verify files exist
    required_files = [
        "distributional_impact.csv",
        "metrics.csv",
        "winners_losers.csv",
        "income_brackets.csv",
    ]

    for filename in required_files:
        filepath = OUTPUT_DIR / filename
        if not filepath.exists():
            print(f"  WARNING: {filename} not found after pipeline run")


def main():
    parser = argparse.ArgumentParser(
        description="Generate precomputed data for the WPTRA dashboard"
    )
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Regenerate all data from scratch",
    )
    parser.add_argument(
        "--year",
        type=int,
        help="Process only this year",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("Working Parents Tax Relief Act Data Pipeline")
    print("=" * 60)

    # Ensure output directory exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # If fresh, remove existing files
    if args.fresh:
        print("\n[Fresh mode] Removing existing data files...")
        for f in OUTPUT_DIR.glob("*.csv"):
            f.unlink()
            print(f"  Removed {f.name}")

    # Determine years to process
    years_to_process = [args.year] if args.year else YEARS

    print(f"\nProcessing years: {years_to_process}")
    print("-" * 60)

    # Process each year
    successful = 0
    failed = 0
    for year in years_to_process:
        print(f"\n[Year {year}]")
        if run_year(year, force=args.fresh):
            successful += 1
        else:
            failed += 1

    # Merge outputs
    print("\n" + "-" * 60)
    print("Merging outputs...")
    merge_csv_files(years_to_process)

    # Summary
    print("\n" + "=" * 60)
    print(f"Pipeline complete: {successful} successful, {failed} failed")
    print(f"Output directory: {OUTPUT_DIR}")
    print("=" * 60)

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
