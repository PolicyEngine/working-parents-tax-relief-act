"""Modal-based congressional district impact pipeline for Working Parents Tax Relief Act.

Runs microsimulation for each state in parallel on Modal's cloud infrastructure,
extracting congressional district-level impacts.

Usage:
    # Run the pipeline (computes all states in parallel on Modal)
    modal run scripts/modal_district_pipeline.py

    # Run specific states
    modal run scripts/modal_district_pipeline.py --states "CA,NY,TX"
"""

import os

import modal

# Modal app definition
app = modal.App("wptra-district-pipeline")

# Image with policyengine-us and dependencies
image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "policyengine-us>=1.150.0",
        "numpy>=1.24.0",
        "pandas>=2.0.0",
    )
)

# All US states + DC
STATES = [
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
    "DC",
]

# State FIPS codes for congressional district mapping
STATE_FIPS = {
    "AL": "01", "AK": "02", "AZ": "04", "AR": "05", "CA": "06",
    "CO": "08", "CT": "09", "DE": "10", "FL": "12", "GA": "13",
    "HI": "15", "ID": "16", "IL": "17", "IN": "18", "IA": "19",
    "KS": "20", "KY": "21", "LA": "22", "ME": "23", "MD": "24",
    "MA": "25", "MI": "26", "MN": "27", "MS": "28", "MO": "29",
    "MT": "30", "NE": "31", "NV": "32", "NH": "33", "NJ": "34",
    "NM": "35", "NY": "36", "NC": "37", "ND": "38", "OH": "39",
    "OK": "40", "OR": "41", "PA": "42", "RI": "44", "SC": "45",
    "SD": "46", "TN": "47", "TX": "48", "UT": "49", "VT": "50",
    "VA": "51", "WA": "53", "WV": "54", "WI": "55", "WY": "56",
    "DC": "11",
}

# Reform dictionary to enable WPTRA
REFORM_DICT = {
    "gov.contrib.congress.mcdonald_rivet.working_parents_tax_relief_act.in_effect": {
        "2020-01-01.2100-12-31": True,
    },
}

YEAR = 2026  # Default year for district analysis


@app.function(
    image=image,
    memory=32768,  # 32GB RAM for microsimulation
    timeout=3600,  # 60 min timeout per state
    retries=1,
)
def calculate_state_districts(state_code: str, year: int = YEAR) -> list[dict]:
    """Calculate congressional district impacts for a single state."""
    import numpy as np
    from policyengine_us import Microsimulation
    from policyengine_core.reforms import Reform

    print(f"Starting calculation for {state_code}...")

    reform = Reform.from_dict(REFORM_DICT, country_id="us")

    # Create simulations with state-specific dataset
    print(f"  Creating baseline simulation for {state_code}...")
    sim_baseline = Microsimulation(dataset=f"hf://policyengine/policyengine-us-data/enhanced_cps_2024_{state_code.lower()}.h5")
    print(f"  Creating reform simulation for {state_code}...")
    sim_reform = Microsimulation(reform=reform, dataset=f"hf://policyengine/policyengine-us-data/enhanced_cps_2024_{state_code.lower()}.h5")

    # Get congressional district for each household
    cd = sim_baseline.calculate("congressional_district", period=year, map_to="household")
    cd_arr = np.array(cd)

    # Calculate household net income change
    baseline_net_income = sim_baseline.calculate("household_net_income", period=year, map_to="household")
    reform_net_income = sim_reform.calculate("household_net_income", period=year, map_to="household")
    income_change = reform_net_income - baseline_net_income

    # Get household weights
    household_weight = sim_baseline.calculate("household_weight", period=year)
    weight_arr = np.array(household_weight)

    baseline_income_arr = np.array(baseline_net_income)
    change_arr = np.array(income_change)

    # Get unique districts in this state
    unique_districts = np.unique(cd_arr)
    unique_districts = unique_districts[~np.isnan(unique_districts)]

    districts = []
    state_fips = STATE_FIPS.get(state_code, "00")

    for district_num in unique_districts:
        district_num = int(district_num)
        mask = cd_arr == district_num

        # Weighted average income change
        weighted_change = (change_arr[mask] * weight_arr[mask]).sum()
        total_weight = weight_arr[mask].sum()

        if total_weight > 0:
            avg_change = weighted_change / total_weight

            # Weighted baseline income for relative change
            weighted_baseline = (baseline_income_arr[mask] * weight_arr[mask]).sum()
            avg_baseline = weighted_baseline / total_weight
            rel_change = avg_change / avg_baseline if avg_baseline > 0 else 0.0
        else:
            avg_change = 0.0
            rel_change = 0.0

        # Format district ID: "ST-NN" (e.g., "CA-52")
        # Handle single-district states and DC
        if district_num == 0:
            district_str = "01"  # Convert 0 to 01 for at-large districts
        elif district_num == 98:
            district_str = "01"  # DC uses 98 internally, display as 01
        else:
            district_str = f"{district_num:02d}"

        district_id = f"{state_code}-{district_str}"

        districts.append({
            "district": district_id,
            "average_household_income_change": round(avg_change, 2),
            "relative_household_income_change": round(rel_change, 6),
            "state": state_code,
            "year": year,
        })

    print(f"  {state_code}: Found {len(districts)} districts")
    return districts


@app.local_entrypoint()
def main(states: str = "", year: int = YEAR):
    """Run the pipeline: compute all states in parallel on Modal, save CSV locally.

    Args:
        states: Comma-separated list of state codes (e.g., "CA,NY,TX").
                If empty, runs all 51 states.
        year: Year for the analysis (default: 2026).
    """
    import pandas as pd

    output_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "frontend",
        "public",
        "data",
    )
    os.makedirs(output_dir, exist_ok=True)

    # Parse states argument
    if states:
        target_states = [s.strip().upper() for s in states.split(",")]
    else:
        target_states = STATES

    print(f"Running WPTRA congressional district analysis for {len(target_states)} states on Modal...")
    print(f"Year: {year}")
    print(f"Output directory: {output_dir}")

    # Run states in parallel on Modal
    all_districts = []
    for result in calculate_state_districts.map(target_states, kwargs={"year": year}):
        all_districts.extend(result)

    # Create DataFrame and sort by district ID
    df = pd.DataFrame(all_districts)

    # Sort by state then district number
    df["_state"] = df["district"].str.split("-").str[0]
    df["_num"] = df["district"].str.split("-").str[1].astype(int)
    df = df.sort_values(["_state", "_num"]).drop(columns=["_state", "_num"])
    df = df.reset_index(drop=True)

    # Save to CSV
    filepath = os.path.join(output_dir, "congressional_districts.csv")
    df.to_csv(filepath, index=False)
    print(f"\nSaved {len(df)} districts to: {filepath}")

    # Summary stats
    print(f"\nSummary:")
    print(f"  Total districts: {len(df)}")
    print(f"  Avg income change: ${df['average_household_income_change'].mean():,.2f}")
    print(f"  Min change: ${df['average_household_income_change'].min():,.2f}")
    print(f"  Max change: ${df['average_household_income_change'].max():,.2f}")
