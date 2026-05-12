"""Modal-based congressional district impact pipeline for Working Parents Tax Relief Act.

This script calculates actual congressional district-level impacts using microsimulation
with district-specific datasets from HuggingFace.

Usage:
    modal run scripts/modal_district_pipeline.py
"""

import os

import modal

# Modal app definition
app = modal.App("wptra-district-pipeline")

# Image with policyengine.py and US dependencies
image = modal.Image.debian_slim(python_version="3.11").pip_install(
    "policyengine[us]==4.4.3",
    "numpy>=1.24.0",
    "pandas>=2.0.0",
    "huggingface_hub",
)

# Number of congressional districts per state (118th Congress)
# Source: https://www.census.gov/programs-surveys/decennial-census/about/rdo/summary-files.html
DISTRICTS_PER_STATE = {
    "AL": 7,
    "AK": 1,
    "AZ": 9,
    "AR": 4,
    "CA": 52,
    "CO": 8,
    "CT": 5,
    "DE": 1,
    "FL": 28,
    "GA": 14,
    "HI": 2,
    "ID": 2,
    "IL": 17,
    "IN": 9,
    "IA": 4,
    "KS": 4,
    "KY": 6,
    "LA": 6,
    "ME": 2,
    "MD": 8,
    "MA": 9,
    "MI": 13,
    "MN": 8,
    "MS": 4,
    "MO": 8,
    "MT": 2,
    "NE": 3,
    "NV": 4,
    "NH": 2,
    "NJ": 12,
    "NM": 3,
    "NY": 26,
    "NC": 14,
    "ND": 1,
    "OH": 15,
    "OK": 5,
    "OR": 6,
    "PA": 17,
    "RI": 2,
    "SC": 7,
    "SD": 1,
    "TN": 9,
    "TX": 38,
    "UT": 4,
    "VT": 1,
    "VA": 11,
    "WA": 10,
    "WV": 2,
    "WI": 8,
    "WY": 1,
    "DC": 1,
}

# Reform dictionary to enable WPTRA
REFORM_DICT = {
    "gov.contrib.congress.mcdonald_rivet.working_parents_tax_relief_act.in_effect": {
        "2020-01-01.2100-12-31": True,
    },
}

YEAR = 2026


def get_all_districts():
    """Generate list of all congressional district IDs."""
    districts = []
    for state, num_districts in DISTRICTS_PER_STATE.items():
        for d in range(1, num_districts + 1):
            districts.append(f"{state}-{d:02d}")
    return districts


@app.function(
    image=image,
    memory=16384,
    timeout=1800,
    retries=2,
)
def calculate_single_district_impact(district_id: str, year: int = YEAR) -> dict:
    """Calculate impact for a single congressional district using district-specific dataset.

    Returns metrics including:
    - Average household income change (absolute and relative)
    - Winners/losers share (% households gaining/losing)
    - Poverty rate change
    - Child poverty rate change
    """
    import policyengine as pe
    from policyengine_core.reforms import Reform

    print(f"Calculating impact for {district_id}...")

    # District datasets are not the default national dataset, but the release
    # should still follow the installed policyengine.py bundle.
    data_release = pe.us.model.release_manifest.data_package.version
    dataset_url = (
        f"hf://policyengine/policyengine-us-data/districts/{district_id}.h5"
        f"@{data_release}"
    )

    try:
        reform = Reform.from_dict(REFORM_DICT, country_id="us")

        # Load district-specific datasets
        sim_baseline = pe.us.managed_microsimulation(
            dataset=dataset_url,
            allow_unmanaged=True,
        )
        sim_reform = pe.us.managed_microsimulation(
            dataset=dataset_url,
            reform=reform,
            allow_unmanaged=True,
        )

        def _calc(sim, variable: str, map_to: str | None = None):
            kwargs = {"period": year}
            if map_to is not None:
                kwargs["map_to"] = map_to
            return sim.calc(variable, **kwargs)

        def _mean_or_zero(series) -> float:
            count = float((series * 0 + 1).sum())
            return float(series.mean()) if count > 0 else 0.0

        # Calculate household-level impacts
        baseline_net_income = _calc(sim_baseline, "household_net_income")
        reform_net_income = _calc(sim_reform, "household_net_income")
        income_change = reform_net_income - baseline_net_income

        total_households = float((income_change * 0 + 1).sum())

        if total_households > 0:
            avg_change = float(income_change.mean())
            avg_baseline = float(baseline_net_income.mean())
            rel_change = avg_change / avg_baseline if avg_baseline > 0 else 0.0

            # Winners/losers analysis (using $1 threshold to avoid floating point noise)
            winners_share = float((income_change > 1).mean())
            losers_share = float((income_change < -1).mean())
        else:
            avg_change = 0.0
            rel_change = 0.0
            winners_share = 0.0
            losers_share = 0.0

        # SPM poverty rates are person-weighted, not SPM-unit-weighted.
        try:
            baseline_in_poverty = _calc(
                sim_baseline, "person_in_poverty", map_to="person"
            )
            reform_in_poverty = _calc(sim_reform, "person_in_poverty", map_to="person")
            baseline_poverty_rate = _mean_or_zero(baseline_in_poverty)
            reform_poverty_rate = _mean_or_zero(reform_in_poverty)
            poverty_pct_change = (
                (reform_poverty_rate - baseline_poverty_rate)
                / baseline_poverty_rate
                * 100
                if baseline_poverty_rate > 0
                else 0.0
            )

            is_child = _calc(sim_baseline, "age", map_to="person") < 18
            baseline_child_poverty_rate = _mean_or_zero(
                baseline_in_poverty[is_child]
            )
            reform_child_poverty_rate = _mean_or_zero(reform_in_poverty[is_child])
            child_poverty_pct_change = (
                (reform_child_poverty_rate - baseline_child_poverty_rate)
                / baseline_child_poverty_rate
                * 100
                if baseline_child_poverty_rate > 0
                else 0.0
            )
        except Exception as poverty_err:
            print(
                f"  Warning: Poverty calculation failed for {district_id}: {poverty_err}"
            )
            poverty_pct_change = 0.0
            child_poverty_pct_change = 0.0

        state = district_id.split("-")[0]
        result = {
            "district": district_id,
            "average_household_income_change": round(float(avg_change), 2),
            "relative_household_income_change": round(float(rel_change), 6),
            "winners_share": round(float(winners_share), 4),
            "losers_share": round(float(losers_share), 4),
            "poverty_pct_change": round(float(poverty_pct_change), 2),
            "child_poverty_pct_change": round(float(child_poverty_pct_change), 2),
            "state": state,
            "year": year,
        }

        print(
            f"  {district_id}: avg=${avg_change:.2f}, winners={winners_share:.1%}, poverty={poverty_pct_change:+.1f}%"
        )
        return result

    except Exception as e:
        print(f"  ERROR for {district_id}: {e}")
        # Return None for failed districts
        return None


@app.local_entrypoint()
def main(year: int = YEAR, batch_size: int = 50):
    """Run the pipeline: compute actual district-level impacts.

    Args:
        year: Tax year for analysis
        batch_size: Number of districts to process in parallel (reduce to avoid rate limits)
    """
    import pandas as pd
    import time

    output_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "frontend",
        "public",
        "data",
    )
    os.makedirs(output_dir, exist_ok=True)

    all_districts = get_all_districts()

    print("Running WPTRA congressional district analysis on Modal...")
    print(f"Year: {year}")
    print(f"Total districts: {len(all_districts)}")
    print(f"Batch size: {batch_size}")
    print(f"Output directory: {output_dir}")

    # Check for existing results to resume from
    output_path = os.path.join(output_dir, "congressional_districts.csv")
    existing_districts = set()
    if os.path.exists(output_path):
        existing_df = pd.read_csv(output_path)
        existing_districts = set(existing_df["district"].tolist())
        print(f"Found {len(existing_districts)} existing districts, resuming...")

    # Filter out already-completed districts
    remaining_districts = [d for d in all_districts if d not in existing_districts]
    print(f"Remaining districts to process: {len(remaining_districts)}")

    if not remaining_districts:
        print("All districts already processed!")
        return

    # Process in batches to avoid HuggingFace rate limits
    all_results = []
    for i in range(0, len(remaining_districts), batch_size):
        batch = remaining_districts[i : i + batch_size]
        print(
            f"\nProcessing batch {i // batch_size + 1}/{(len(remaining_districts) + batch_size - 1) // batch_size} ({len(batch)} districts)..."
        )
        batch_results = list(
            calculate_single_district_impact.map(batch, kwargs={"year": year})
        )
        all_results.extend(batch_results)

        # Small delay between batches to avoid rate limiting
        if i + batch_size < len(remaining_districts):
            print("Waiting 5 seconds before next batch...")
            time.sleep(5)

    # Filter out None results (failed districts)
    new_districts = [r for r in all_results if r is not None]

    failed_count = len(all_results) - len(new_districts)
    if failed_count > 0:
        print(f"WARNING: {failed_count} districts failed to calculate")

    # Combine with existing data
    if existing_districts and new_districts:
        existing_df = pd.read_csv(output_path)
        new_df = pd.DataFrame(new_districts)
        df = pd.concat([existing_df, new_df], ignore_index=True)
    elif new_districts:
        df = pd.DataFrame(new_districts)
    elif existing_districts:
        df = pd.read_csv(output_path)
    else:
        print("ERROR: No district data generated!")
        return

    # Sort and save
    df = df.sort_values(["state", "district"]).reset_index(drop=True)

    # Save to CSV
    filepath = output_path
    df.to_csv(filepath, index=False)
    print(f"\nSaved {len(df)} districts to: {filepath}")

    # Summary stats
    print("\nSummary:")
    print(f"  Total districts: {len(df)}")
    print(f"  Avg income change: ${df['average_household_income_change'].mean():,.2f}")
    print(f"  Min change: ${df['average_household_income_change'].min():,.2f}")
    print(f"  Max change: ${df['average_household_income_change'].max():,.2f}")

    # Show top 10 districts by impact
    print("\nTop 10 districts by average income change:")
    top10 = df.nlargest(10, "average_household_income_change")
    for _, row in top10.iterrows():
        print(f"  {row['district']}: ${row['average_household_income_change']:,.2f}")
