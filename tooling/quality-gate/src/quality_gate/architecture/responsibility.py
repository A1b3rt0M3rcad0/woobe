from __future__ import annotations

from pathlib import Path
import tomllib

from .policy import ArchitecturePolicy
from . import responsibility_engine as _engine


RawViolation = _engine.RawViolation
ResponsibilityPolicyError = _engine.ResponsibilityPolicyError


def _load_config(
    project_root: Path,
    policy: ArchitecturePolicy,
) -> dict[str, object] | None:
    fixture_path = (
        project_root
        / "quality_gate"
        / "architecture"
        / "responsibilities"
        / f"{policy.name}.toml"
    )
    package_path = (
        Path(__file__).resolve().parent
        / "responsibilities"
        / f"{policy.name}.toml"
    )

    path = fixture_path if fixture_path.is_file() else package_path
    if not path.is_file():
        return None

    with path.open("rb") as stream:
        data = tomllib.load(stream)
    if not isinstance(data, dict):
        raise ResponsibilityPolicyError(f"{path} must contain TOML tables")
    return data


def check_responsibility_contracts(
    project_root: Path,
    policy: ArchitecturePolicy,
) -> tuple[RawViolation, ...]:
    data = _load_config(project_root, policy)
    if data is None:
        return ()

    violations: list[RawViolation] = []

    layer_surface = _engine._table(data, "layer_surface")
    if layer_surface is not None:
        violations.extend(_engine._check_layer_surface(policy, layer_surface))

    transport_ownership = _engine._table(data, "transport_ownership")
    if transport_ownership is not None:
        violations.extend(_engine._check_transport_ownership(policy, transport_ownership))

    presentation_purity = _engine._table(data, "presentation_purity")
    if presentation_purity is not None:
        violations.extend(_engine._check_presentation_purity(policy, presentation_purity))

    application_runtime_purity = _engine._table(data, "application_runtime_purity")
    if application_runtime_purity is not None:
        violations.extend(
            _engine._check_import_purity(
                policy,
                application_runtime_purity,
                table_name="application_runtime_purity",
                default_rule_id="ARCH066",
                message=(
                    "application runtime must be framework-neutral; import "
                    "{module!r} belongs to an outer layer"
                ),
            )
        )

    runtime_adapter_ownership = _engine._table(data, "runtime_adapter_ownership")
    if runtime_adapter_ownership is not None:
        violations.extend(
            _engine._check_runtime_adapter_ownership(policy, runtime_adapter_ownership)
        )

    composition_behavior = _engine._table(data, "composition_behavior")
    if composition_behavior is not None:
        violations.extend(_engine._check_composition_behavior(policy, composition_behavior))

    responsibility_placement = _engine._table(data, "responsibility_placement")
    if responsibility_placement is not None:
        violations.extend(
            _engine._check_responsibility_placement(policy, responsibility_placement)
        )

    inbound_composition = _engine._table(data, "inbound_composition")
    if inbound_composition is not None:
        violations.extend(
            _engine._check_inbound_composition(project_root, policy, inbound_composition)
        )

    module_api = _engine._table(data, "module_api")
    if module_api is not None:
        violations.extend(_engine._check_module_api(project_root, policy, module_api))

    transport_neutral = _engine._table(data, "transport_neutral")
    if transport_neutral is not None:
        violations.extend(_engine._check_transport_neutral(policy, transport_neutral))

    return tuple(violations)
