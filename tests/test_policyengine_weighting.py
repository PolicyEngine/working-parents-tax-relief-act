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
            assert variable == "household_count_people"
            assert kwargs == {"period": 2024, "map_to": "household"}
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
        "household_count_people",
        2024,
        map_to="household",
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
