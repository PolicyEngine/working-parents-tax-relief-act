"""
Reform definitions for the Working Parents Tax Relief Act.

The WPTRA is implemented as a contributed reform in policyengine-us (PR #7914).
This module defines the reform parameter path for toggling the reform on/off.
"""

from typing import Dict, Any

# The parameter that toggles the Working Parents Tax Relief Act
REFORM_PARAMETER = (
    "gov.contrib.congress.mcdonald_rivet.working_parents_tax_relief_act.in_effect"
)


def build_reform_dict(start_year: int = 2026, end_year: int = 2100) -> Dict[str, Any]:
    """
    Build a reform dictionary that enables the Working Parents Tax Relief Act.

    This reform enhances the EITC for parents of young children (under age 4):
    - Credit percentage increase of 42.24pp for 1 child under 4
    - Credit percentage increase of 30.07pp per young child (up to 3) for 2+ children
    - Phaseout percentage increase of 5pp per young child (up to 3)

    Args:
        start_year: The year the reform takes effect (default: 2026)
        end_year: The year the reform ends (default: 2100)

    Returns:
        A reform dictionary suitable for PolicyEngine's Reform.from_dict() method.
    """
    return {
        REFORM_PARAMETER: {
            f"{start_year}-01-01.{end_year}-12-31": True,
        },
    }


def get_reform_provisions() -> Dict[str, Dict[str, Any]]:
    """
    Return a dictionary describing the reform provisions.

    Useful for documentation and display purposes.
    """
    return {
        "credit_percentage_increase_one_child": {
            "description": (
                "If child has not attained age 4, increase credit percentage "
                "by 42.24 percentage points"
            ),
            "parameter": (
                "gov.contrib.congress.mcdonald_rivet."
                "working_parents_tax_relief_act.credit_percentage_increase_one_child"
            ),
            "value": 0.4224,
        },
        "credit_percentage_increase_per_young_child": {
            "description": (
                "Increase credit percentage by 30.07 percentage points for each "
                "of youngest 3 children under age 4"
            ),
            "parameter": (
                "gov.contrib.congress.mcdonald_rivet."
                "working_parents_tax_relief_act.credit_percentage_increase_per_young_child"
            ),
            "value": 0.3007,
        },
        "phaseout_percentage_increase_per_young_child": {
            "description": (
                "Increase phaseout percentage by 5 percentage points per young child (max 3)"
            ),
            "parameter": (
                "gov.contrib.congress.mcdonald_rivet."
                "working_parents_tax_relief_act.phaseout_percentage_increase_per_young_child"
            ),
            "value": 0.05,
        },
        "young_child_age_threshold": {
            "description": "Children under age 4 qualify for increased EITC",
            "parameter": (
                "gov.contrib.congress.mcdonald_rivet."
                "working_parents_tax_relief_act.young_child_age_threshold"
            ),
            "value": 4,
        },
        "max_young_children": {
            "description": "Maximum 3 young children count toward bonus",
            "parameter": (
                "gov.contrib.congress.mcdonald_rivet."
                "working_parents_tax_relief_act.max_young_children"
            ),
            "value": 3,
        },
    }
