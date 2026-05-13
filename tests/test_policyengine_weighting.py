from __future__ import annotations

from pathlib import Path

from microdf import MicroSeries

import wptra_calc.microsimulation as microsimulation


def test_policyengine_microsim_code_uses_microseries_aggregation() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    source_roots = [
        repo_root / "scripts",
        repo_root / "wptra_calc",
    ]
    forbidden_names = [
        "household" + "_weight",
        "person" + "_weight",
        "tax_unit" + "_weight",
        "spm_unit" + "_weight",
        "household_count_" + "people",
    ]
    forbidden_stripping_patterns = [
        ".values",
        ".to_numpy(",
        "np.array(",
        "np.asarray(",
    ]

    offenders: list[str] = []
    for source_root in source_roots:
        for path in source_root.rglob("*.py"):
            text = path.read_text()
            for name in forbidden_names:
                for token in (f'"{name}"', f"'{name}'"):
                    if token in text:
                        offenders.append(
                            f"{path.relative_to(repo_root)} contains {token}"
                        )
            for pattern in forbidden_stripping_patterns:
                if pattern in text:
                    offenders.append(
                        f"{path.relative_to(repo_root)} contains {pattern}"
                    )

    assert not offenders, (
        "PolicyEngine microsim code should use MicroSeries .sum()/.mean() "
        "and map_to, not manual weight variables:\n" + "\n".join(offenders)
    )


def test_microsimulation_module_uses_policyengine_py_pe_us() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    source = (repo_root / "wptra_calc" / "microsimulation.py").read_text()

    assert "import policyengine as pe" in source
    assert "pe.us.managed_microsimulation" in source
    assert "policyengine_us" not in source


def test_tiny_microsim_smoke_path_uses_pe_us(monkeypatch) -> None:
    calls = []

    class TinyMicrosimulation:
        def calc(self, variable: str, **kwargs):
            assert variable == "household_net_income"
            assert kwargs == {"period": 2024, "map_to": "person"}
            return MicroSeries([1.0, 3.0], weights=[2.0, 4.0])

    def fake_managed_microsimulation(**kwargs):
        calls.append(kwargs)
        return TinyMicrosimulation()

    monkeypatch.setattr(
        microsimulation.pe.us,
        "managed_microsimulation",
        fake_managed_microsimulation,
    )

    sim = microsimulation._create_microsimulation(
        dataset="tiny://smoke",
        reform=None,
        allow_unmanaged=True,
    )
    result = microsimulation._calc(
        sim,
        "household_net_income",
        2024,
        map_to="person",
    )

    assert calls == [
        {
            "dataset": "tiny://smoke",
            "reform": None,
            "allow_unmanaged": True,
        }
    ]
    assert float(result.sum()) == 14.0
    assert float(result.mean()) == 14.0 / 6.0


def test_aggregate_path_maps_poverty_to_people_and_uses_microseries(
    monkeypatch,
) -> None:
    calls = []
    household_weights = [1.0] * 10
    person_weights = [9.0] + [1.0] * 9

    class TinyMicrosimulation:
        def __init__(self, variant: str):
            self.variant = variant

        def calc(self, variable: str, **kwargs):
            calls.append((self.variant, variable, kwargs))
            map_to = kwargs.get("map_to")
            weights = person_weights if map_to == "person" else household_weights

            if variable in ("income_tax", "state_income_tax"):
                values = [100.0] * 10
                if self.variant == "reform":
                    values = [90.0] * 10
            elif variable == "household_net_income":
                values = [10_000.0 + i * 1_000 for i in range(10)]
                if self.variant == "reform":
                    values = [value + 100.0 for value in values]
            elif variable == "household_income_decile":
                values = list(range(1, 11))
            elif variable == "person_in_poverty":
                values = [1] + [0] * 9
            elif variable == "in_deep_poverty":
                values = [0] * 10
            elif variable == "age":
                values = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
            elif variable == "adjusted_gross_income":
                values = [20_000.0] * 10
            else:
                raise AssertionError(f"Unexpected variable: {variable}")

            return MicroSeries(values, weights=weights)

    def fake_create_microsimulation(**kwargs):
        return TinyMicrosimulation(
            "reform" if kwargs.get("reform") is not None else "baseline"
        )

    monkeypatch.setattr(microsimulation, "create_wptra_reform", lambda: object())
    monkeypatch.setattr(
        microsimulation,
        "_create_microsimulation",
        fake_create_microsimulation,
    )

    result = microsimulation.calculate_aggregate_impact(year=2026)

    person_requests = {
        (variant, variable)
        for variant, variable, kwargs in calls
        if kwargs.get("map_to") == "person"
    }
    assert ("baseline", "person_in_poverty") in person_requests
    assert ("reform", "person_in_poverty") in person_requests
    assert ("baseline", "household_net_income") in person_requests
    assert ("reform", "household_net_income") in person_requests
    assert ("baseline", "household_income_decile") in person_requests

    # Weighted person poverty is 9 / 18 = 50%; unweighted would be 10%.
    assert result["poverty_baseline_rate"] == 50.0


def test_default_microsimulation_uses_policyengine_bundle(monkeypatch) -> None:
    calls = []

    class TinyMicrosimulation:
        pass

    def fake_managed_microsimulation(**kwargs):
        calls.append(kwargs)
        return TinyMicrosimulation()

    monkeypatch.setattr(
        microsimulation.pe.us,
        "managed_microsimulation",
        fake_managed_microsimulation,
    )

    microsimulation._create_microsimulation()

    assert calls == [{"reform": None, "allow_unmanaged": False}]


def test_microsimulation_code_does_not_pin_data_release() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    source_paths = [
        repo_root / "wptra_calc" / "microsimulation.py",
        repo_root / "scripts" / "modal_pipeline.py",
        repo_root / "scripts" / "modal_district_pipeline.py",
    ]

    for path in source_paths:
        assert "enhanced_cps_2024.h5@" not in path.read_text()
        assert "@1.110.12" not in path.read_text()
