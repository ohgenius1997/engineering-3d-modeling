#!/usr/bin/env python3
"""Audit current/handoff consistency across model-project artifacts."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import sys
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import iteration_utils


SCHEMA = "engineering-3d-modeling.project_consistency_audit.v1"
PROJECT_PHASES = {"draft_review", "accepted_current", "release_handoff", "backend_override"}
STEP_REQUIRED_PHASES: set[str] = set()
STEP_PROMOTION_SCRIPT = "scripts/promote_model_project.py"
LEGACY_BACKEND_RE = re.compile(r"\b(fusion\s*360|fusion360|fusion api|legacy)\b", re.IGNORECASE)
FUSION_RE = re.compile(r"\bfusion(?:\s*360|360)?\b", re.IGNORECASE)
NUMBER_RE = re.compile(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)")
TOKEN_STOPWORDS = {
    "current",
    "parameter",
    "parameters",
    "value",
    "values",
    "mm",
    "deg",
    "ratio",
    "unit",
    "units",
}


def load_yaml_module():
    try:
        import yaml  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "PyYAML is required for consistency audit. "
            "Run scripts/check_environment.py --install with this Python runtime."
        ) from exc
    return yaml


def load_yaml(path: Path, errors: list[dict[str, Any]]) -> Any | None:
    try:
        yaml = load_yaml_module()
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        errors.append(issue("error", "missing_yaml", f"missing YAML file: {path}"))
    except Exception as exc:
        errors.append(issue("error", "invalid_yaml", f"invalid YAML in {path}: {exc}"))
    return None


def load_json(path: Path, errors: list[dict[str, Any]], *, missing_severity: str = "error") -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        errors.append(issue(missing_severity, "missing_json", f"missing JSON file: {path}"))
    except json.JSONDecodeError as exc:
        errors.append(issue("error", "invalid_json", f"invalid JSON in {path}: {exc}"))
    return None


def issue(severity: str, code: str, message: str, **details: Any) -> dict[str, Any]:
    out: dict[str, Any] = {"severity": severity, "code": code, "message": message}
    if details:
        out["details"] = details
    return out


def add_issue(issues: list[dict[str, Any]], severity: str, code: str, message: str, **details: Any) -> None:
    issues.append(issue(severity, code, message, **details))


def numeric(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return float(value)
    if isinstance(value, str):
        match = NUMBER_RE.search(value)
        if match:
            try:
                return float(match.group(0))
            except ValueError:
                return None
    return None


def same_value(left: Any, right: Any) -> bool:
    left_number = numeric(left)
    right_number = numeric(right)
    if left_number is not None and right_number is not None:
        return abs(left_number - right_number) <= max(1e-6, abs(right_number) * 1e-6)
    return left == right


def parameter_value(data: Any) -> Any:
    if isinstance(data, dict):
        return data.get("value")
    return data


def parameter_unit(data: Any) -> Any:
    if isinstance(data, dict):
        return data.get("unit")
    return None


def parameter_preview(data: Any) -> dict[str, Any]:
    if isinstance(data, dict) and isinstance(data.get("preview"), dict):
        return data["preview"]
    return {}


def parameter_ui(data: Any) -> dict[str, Any]:
    if isinstance(data, dict) and isinstance(data.get("ui"), dict):
        return data["ui"]
    return {}


def file_sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_relative(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def resolve_from(base: Path, value: Any) -> Path | None:
    if not isinstance(value, str) or not value:
        return None
    path = Path(value)
    if path.is_absolute():
        return path.resolve()
    return (base / path).resolve()


def resolve_project_path(project: Path, value: Any) -> Path | None:
    return resolve_from(project, value)


def phase_from_spec(spec: Any) -> tuple[str | None, str]:
    if not isinstance(spec, dict):
        return None, "missing"
    lifecycle = spec.get("lifecycle")
    if isinstance(lifecycle, dict) and isinstance(lifecycle.get("phase"), str):
        return lifecycle["phase"], "spec.lifecycle.phase"
    return None, "missing"


def backend_override(spec: Any) -> tuple[bool, str | None, str | None]:
    if not isinstance(spec, dict):
        return False, None, None
    backend = spec.get("backend")
    override = backend.get("override") if isinstance(backend, dict) else None
    if not isinstance(override, dict) or not override:
        return False, None, None
    name = override.get("backend") or override.get("name")
    reason = override.get("reason")
    return True, name if isinstance(name, str) else None, reason if isinstance(reason, str) else None


def severity_for_current(phase: str, mode: str) -> str:
    if mode == "strict":
        return "error"
    return "warning"


def severity_for_snapshot(phase: str, mode: str) -> str:
    if mode == "strict":
        return "error"
    return "warning"


def severity_for_missing_phase(mode: str) -> str:
    return "error" if mode == "strict" else "warning"


def normalize_tokens(value: str) -> list[str]:
    return [token for token in re.split(r"[^a-z0-9]+", value.lower()) if token]


def significant_tokens(*values: Any) -> set[str]:
    tokens: set[str] = set()
    for value in values:
        if not isinstance(value, str):
            continue
        for token in normalize_tokens(value):
            if token not in TOKEN_STOPWORDS and len(token) > 1:
                tokens.add(token.rstrip("s"))
    return tokens


def token_match(haystack: str, tokens: set[str]) -> bool:
    if not tokens:
        return False
    haystack_tokens = {token.rstrip("s") for token in normalize_tokens(haystack)}
    matched = tokens & haystack_tokens
    if len(tokens) == 1:
        return bool(matched)
    return len(matched) >= min(2, len(tokens))


def parameter_alias_tokens(parameter_id: str, data: Any) -> set[str]:
    if isinstance(data, dict):
        return significant_tokens(parameter_id, data.get("source_symbol"), data.get("role"))
    return significant_tokens(parameter_id)


def iter_leaf_values(value: Any, path: tuple[str, ...] = ()) -> list[tuple[tuple[str, ...], Any]]:
    out: list[tuple[tuple[str, ...], Any]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            out.extend(iter_leaf_values(item, path + (str(key),)))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            out.extend(iter_leaf_values(item, path + (str(index),)))
    else:
        out.append((path, value))
    return out


def collect_hashes(report: Any) -> dict[str, list[str]]:
    hashes: dict[str, list[str]] = {}
    if report is None:
        return hashes
    for path, value in iter_leaf_values(report):
        if not isinstance(value, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", value):
            continue
        key = ".".join(path).lower()
        if "sha256" not in key and "hash" not in key:
            continue
        hashes.setdefault(key, []).append(value.lower())
    return hashes


def matching_hash_values(hashes: dict[str, list[str]], aliases: list[str]) -> list[str]:
    values: list[str] = []
    for key, key_values in hashes.items():
        normalized = key.replace("_", ".").replace("-", ".")
        if any(alias in normalized for alias in aliases):
            values.extend(key_values)
    return values


def report_phase(report: Any) -> str | None:
    if not isinstance(report, dict):
        return None
    phase = report.get("phase")
    if isinstance(phase, str):
        return phase
    if isinstance(phase, dict) and isinstance(phase.get("value"), str):
        return phase["value"]
    snapshot = report.get("snapshot")
    if isinstance(snapshot, dict):
        phase = snapshot.get("phase")
        if isinstance(phase, str):
            return phase
        if isinstance(phase, dict) and isinstance(phase.get("value"), str):
            return phase["value"]
    return None


def report_has_string(report: Any, needle: str) -> bool:
    if not needle:
        return False
    for _, value in iter_leaf_values(report):
        if isinstance(value, str) and needle in value:
            return True
    return False


def generated_at_value(report: Any) -> str | None:
    if not isinstance(report, dict):
        return None
    value = report.get("generated_at")
    if isinstance(value, str):
        return value
    snapshot = report.get("snapshot")
    if isinstance(snapshot, dict) and isinstance(snapshot.get("generated_at"), str):
        return snapshot["generated_at"]
    return None


def validate_generated_at(value: str) -> bool:
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def current_source_from_spec(project: Path, spec: Any) -> Path | None:
    if isinstance(spec, dict):
        source = spec.get("source")
        if isinstance(source, dict):
            path = resolve_project_path(project, source.get("entrypoint"))
            if path is not None:
                return path
    fallback = project / "source" / "model.py"
    return fallback.resolve() if fallback.exists() else fallback.resolve()


def spec_step_path(project: Path, spec: Any) -> Path | None:
    if not isinstance(spec, dict):
        return None
    outputs = spec.get("outputs")
    if isinstance(outputs, dict):
        return resolve_project_path(project, outputs.get("assembly_step"))
    return None


def manifest_current(manifest: Any) -> dict[str, Any]:
    if not isinstance(manifest, dict):
        return {}
    versions = manifest.get("versions")
    current = versions.get("current") if isinstance(versions, dict) else None
    return current if isinstance(current, dict) else {}


def manifest_preview(manifest: Any) -> dict[str, Any]:
    if isinstance(manifest, dict) and isinstance(manifest.get("preview"), dict):
        return manifest["preview"]
    return {}


def manifest_parameter_map(manifest: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(manifest, dict) or not isinstance(manifest.get("parameters"), list):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for parameter in manifest["parameters"]:
        if isinstance(parameter, dict) and isinstance(parameter.get("id"), str):
            out[parameter["id"]] = parameter
    return out


def step_files(project: Path) -> list[Path]:
    root = project / "outputs" / "step"
    return sorted(root.glob("*.step")) + sorted(root.glob("*.stp"))


def load_step_manifest(project: Path, issues: list[dict[str, Any]]) -> dict[str, Any] | None:
    path = project / iteration_utils.STEP_MANIFEST_REL
    if not path.is_file():
        return None
    data = load_json(path, issues)
    return data if isinstance(data, dict) else None


def is_legacy_fusion_text(value: str) -> bool:
    return bool(LEGACY_BACKEND_RE.search(value))


def is_legacy_fusion_path(path: Path) -> bool:
    text = str(path).lower()
    return "fusion" in text or f"{path.anchor}legacy{path.anchor}" in text or "/legacy/" in text


def compare_manifest_source(
    project: Path,
    spec: Any,
    manifest: Any,
    issues: list[dict[str, Any]],
    checks: list[dict[str, Any]],
    *,
    phase: str,
    mode: str,
    override_allowed: bool,
) -> None:
    source = current_source_from_spec(project, spec)
    current = manifest_current(manifest)
    manifest_source = resolve_from(project / "review", current.get("source"))
    severity = severity_for_current(phase, mode)

    if manifest_source is None:
        add_issue(
            issues,
            "error" if severity == "error" else "warning",
            "manifest_current_source_missing",
            "review/manifest.json versions.current.source is missing; cannot prove review artifacts point at the current authoring source",
        )
        return

    if source is not None and manifest_source != source.resolve():
        add_issue(
            issues,
            severity,
            "manifest_current_source_mismatch",
            "review/manifest.json versions.current.source does not point at the current authoring source",
            manifest_source=safe_relative(manifest_source, project),
            authoring_source=safe_relative(source, project),
        )
    elif source is not None:
        checks.append({"check": "manifest-current-source", "status": "pass", "path": safe_relative(source, project)})

    if is_legacy_fusion_path(manifest_source) and not override_allowed:
        add_issue(
            issues,
            severity,
            "manifest_current_source_legacy_backend",
            "review/manifest.json versions.current.source points at a Fusion/legacy source without a recorded backend override",
            manifest_source=safe_relative(manifest_source, project),
        )


def compare_step_state(
    project: Path,
    spec: Any,
    manifest: Any,
    report: Any,
    issues: list[dict[str, Any]],
    checks: list[dict[str, Any]],
    *,
    phase: str,
    mode: str,
) -> list[Path]:
    iteration_utils.refresh_step_freshness(project, updated_by="scripts/audit_project_consistency.py")
    files = step_files(project)
    expected = spec_step_path(project, spec)
    manifest_step = resolve_from(project / "review", manifest_current(manifest).get("step"))
    step_manifest = load_step_manifest(project, issues)
    required = mode == "strict" or phase in STEP_REQUIRED_PHASES
    severity = severity_for_current(phase, mode)

    if files:
        checks.append({"check": "step-files-present", "status": "pass", "count": len(files)})
    elif required:
        add_issue(issues, "error", "step_missing_required_phase", f"phase {phase} requires STEP/STP output under outputs/step")
    else:
        add_issue(
            issues,
            "warning",
            "step_missing_draft",
            f"phase {phase} allows missing STEP/STP, but this state must not be handed off as current",
        )

    if expected is not None and files and expected.resolve() not in [path.resolve() for path in files]:
        add_issue(
            issues,
            severity,
            "spec_step_path_missing",
            "spec/current.yaml outputs.assembly_step is not present under outputs/step",
            expected=safe_relative(expected, project),
            step_files=[safe_relative(path, project) for path in files],
        )
    if manifest_step is None:
        add_issue(
            issues,
            "warning" if not required and mode != "strict" else "error",
            "manifest_current_step_missing",
            "review/manifest.json versions.current.step is missing",
        )
    elif expected is not None and manifest_step.resolve() != expected.resolve():
        add_issue(
            issues,
            severity,
            "manifest_current_step_mismatch",
            "review/manifest.json versions.current.step does not match spec/current.yaml outputs.assembly_step",
            manifest_step=safe_relative(manifest_step, project),
            spec_step=safe_relative(expected, project),
        )

    if (required or mode == "strict") and files and isinstance(report, dict):
        recorded = any(report_has_string(report, safe_relative(path, project)) for path in files)
        if not recorded:
            add_issue(
                issues,
                "error",
                "step_not_recorded_in_validation_report",
                "outputs/step contains STEP/STP, but validation/report.json does not record the current STEP output",
                step_files=[safe_relative(path, project) for path in files],
            )

    if step_manifest is None:
        if files:
            add_issue(
                issues,
                severity if required or mode == "strict" else "warning",
                "step_manifest_missing",
                "outputs/step contains STEP/STP files but outputs/step/manifest.json is missing",
            )
        return files

    if step_manifest.get("schema") != iteration_utils.STEP_MANIFEST_SCHEMA:
        add_issue(issues, "error", "step_manifest_schema", "outputs/step/manifest.json schema is missing or unexpected")
    state = step_manifest.get("state")
    if state not in {"draft", "exported", "accepted_current", "release_handoff"}:
        add_issue(issues, "error", "step_manifest_state_invalid", "outputs/step/manifest.json has an invalid state", state=state)
    elif required:
        if state not in {"exported", "accepted_current", "release_handoff"}:
            add_issue(
                issues,
                "error",
                "step_manifest_state_mismatch",
                "strict delivery audit requires a fresh exported or legacy promoted STEP manifest state",
                state=state,
            )
        if state in {"accepted_current", "release_handoff"} and step_manifest.get("promoted_by") != STEP_PROMOTION_SCRIPT:
            add_issue(
                issues,
                "error",
                "step_manifest_not_promoted",
                "accepted/release STEP manifest was not written by the promotion gate",
                promoted_by=step_manifest.get("promoted_by"),
            )
        if step_manifest.get("stale") is True:
            add_issue(issues, "error", "step_manifest_stale", "accepted/release STEP manifest is marked stale")
    elif state in STEP_REQUIRED_PHASES:
        add_issue(
            issues,
            severity_for_current(phase, mode),
            "step_manifest_promoted_in_draft",
            "draft project still carries accepted/release STEP manifest semantics",
            state=state,
        )
    elif step_manifest.get("stale") is True:
        add_issue(
            issues,
            "error" if mode == "strict" else "warning",
            "step_manifest_stale",
            "outputs/step/manifest.json is stale relative to current authoring truth or preview mesh",
            state=state,
            stale_reason=step_manifest.get("stale_reason"),
        )
    else:
        checks.append({"check": "step-manifest-state", "status": "pass", "state": state})

    actual_by_rel = {safe_relative(path, project): path for path in files}
    recorded = step_manifest.get("step_files")
    if isinstance(recorded, list):
        recorded_paths = {
            item.get("path")
            for item in recorded
            if isinstance(item, dict) and isinstance(item.get("path"), str)
        }
        missing = sorted(set(actual_by_rel) - recorded_paths)
        if missing:
            add_issue(
                issues,
                severity,
                "step_manifest_file_missing",
                "outputs/step/manifest.json does not record current STEP file(s)",
                step_files=missing,
            )
        for item in recorded:
            if not isinstance(item, dict):
                continue
            rel = item.get("path")
            if not isinstance(rel, str) or rel not in actual_by_rel:
                continue
            expected_hash = file_sha256(actual_by_rel[rel])
            if expected_hash and item.get("sha256") and str(item["sha256"]).lower() != expected_hash.lower():
                add_issue(
                    issues,
                    "error",
                    "step_manifest_hash_mismatch",
                    "outputs/step/manifest.json hash does not match current STEP file",
                    step_file=rel,
                )
    else:
        add_issue(issues, "error", "step_manifest_files_invalid", "outputs/step/manifest.json step_files must be a list")
    return files


def compare_manifest_parameters(
    parameters: dict[str, Any],
    manifest: Any,
    issues: list[dict[str, Any]],
    checks: list[dict[str, Any]],
    *,
    phase: str,
    mode: str,
) -> None:
    manifest_by_id = manifest_parameter_map(manifest)
    severity = severity_for_current(phase, mode)
    for parameter_id, record in manifest_by_id.items():
        if parameter_id not in parameters:
            add_issue(issues, severity, "manifest_parameter_missing_in_parameters_yaml", "manifest exposes a parameter missing from parameters.yaml", parameter_id=parameter_id)
            continue
        data = parameters[parameter_id]
        if "value" in record and not same_value(record.get("value"), parameter_value(data)):
            add_issue(
                issues,
                severity,
                "manifest_parameter_value_mismatch",
                "review/manifest.json parameter value differs from parameters.yaml",
                parameter_id=parameter_id,
                manifest_value=record.get("value"),
                parameters_yaml_value=parameter_value(data),
            )
        if record.get("unit") is not None and parameter_unit(data) is not None and record.get("unit") != parameter_unit(data):
            add_issue(
                issues,
                severity,
                "manifest_parameter_unit_mismatch",
                "review/manifest.json parameter unit differs from parameters.yaml",
                parameter_id=parameter_id,
                manifest_unit=record.get("unit"),
                parameters_yaml_unit=parameter_unit(data),
            )
    if manifest_by_id:
        checks.append({"check": "manifest-parameters-present-in-parameters-yaml", "status": "pass", "count": len(manifest_by_id)})

    for parameter_id, data in parameters.items():
        preview = parameter_preview(data)
        ui = parameter_ui(data)
        effect = preview.get("effect")
        if effect and effect != "none" and ui.get("editable") is True and parameter_id not in manifest_by_id:
            add_issue(
                issues,
                "warning",
                "preview_bound_parameter_not_exposed",
                "parameters.yaml has an editable live-preview parameter that is not exposed in review/manifest.json",
                parameter_id=parameter_id,
                effect=effect,
            )


def compare_mesh_snapshot(
    project: Path,
    parameters: dict[str, Any],
    manifest: Any,
    issues: list[dict[str, Any]],
    checks: list[dict[str, Any]],
    *,
    phase: str,
    mode: str,
    override_allowed: bool,
) -> tuple[Path | None, dict[str, Any] | None]:
    preview = manifest_preview(manifest)
    mesh_path = resolve_from(project / "review", preview.get("mesh_json"))
    if mesh_path is None:
        add_issue(issues, "warning" if mode != "strict" else "error", "mesh_not_declared", "review/manifest.json preview.mesh_json is missing")
        return None, None
    errors: list[dict[str, Any]] = []
    mesh = load_json(mesh_path, errors, missing_severity=severity_for_current(phase, mode))
    issues.extend(errors)
    if not isinstance(mesh, dict):
        return mesh_path, None
    checks.append({"check": "preview-mesh-json", "status": "pass", "path": safe_relative(mesh_path, project)})

    source = mesh.get("source")
    if isinstance(source, str):
        if is_legacy_fusion_text(source) and not override_allowed:
            add_issue(issues, severity_for_current(phase, mode), "mesh_source_legacy_backend", "review/cache current mesh identifies a Fusion/legacy source without backend override", source=source)
    else:
        add_issue(issues, "warning", "mesh_source_missing", "review/cache current mesh does not record the source used to generate it")

    mesh_parameters = mesh.get("parameters")
    if isinstance(mesh_parameters, dict):
        source_symbol_to_id = {
            data.get("source_symbol"): parameter_id
            for parameter_id, data in parameters.items()
            if isinstance(data, dict) and isinstance(data.get("source_symbol"), str)
        }
        for key, value in mesh_parameters.items():
            parameter_id = key if key in parameters else source_symbol_to_id.get(key)
            if parameter_id is None:
                continue
            if not same_value(value, parameter_value(parameters[parameter_id])):
                add_issue(
                    issues,
                    severity_for_current(phase, mode),
                    "mesh_parameter_value_mismatch",
                    "review/cache current mesh parameter snapshot differs from parameters.yaml",
                    parameter_id=parameter_id,
                    mesh_value=value,
                    parameters_yaml_value=parameter_value(parameters[parameter_id]),
                )
    else:
        add_issue(
            issues,
            severity_for_snapshot(phase, mode),
            "mesh_parameter_snapshot_missing",
            "review/cache current mesh has no parameter snapshot; cannot prove it was generated from current parameters.yaml",
            mesh=safe_relative(mesh_path, project),
        )
    return mesh_path, mesh


def compare_report_snapshot(
    project: Path,
    spec: Any,
    parameters: dict[str, Any],
    report: Any,
    source_path: Path | None,
    mesh_path: Path | None,
    steps: list[Path],
    issues: list[dict[str, Any]],
    checks: list[dict[str, Any]],
    *,
    phase: str,
    phase_source: str,
    mode: str,
) -> None:
    if not isinstance(report, dict):
        return

    generated_at = generated_at_value(report)
    if generated_at is None:
        add_issue(issues, severity_for_snapshot(phase, mode), "validation_report_generated_at_missing", "validation/report.json does not record generated_at")
    elif not validate_generated_at(generated_at):
        add_issue(issues, severity_for_snapshot(phase, mode), "validation_report_generated_at_invalid", "validation/report.json generated_at is not an ISO-like timestamp", generated_at=generated_at)
    else:
        checks.append({"check": "validation-report-generated-at", "status": "pass", "generated_at": generated_at})

    recorded_phase = report_phase(report)
    if recorded_phase is None:
        add_issue(issues, severity_for_snapshot(phase, mode), "validation_report_phase_missing", "validation/report.json does not record the audited lifecycle phase")
    elif recorded_phase != phase:
        add_issue(
            issues,
            "error",
            "validation_report_phase_mismatch",
            "validation/report.json phase differs from spec/current.yaml lifecycle.phase",
            report_phase=recorded_phase,
            spec_phase=phase,
            phase_source=phase_source,
        )
    else:
        checks.append({"check": "validation-report-phase", "status": "pass", "phase": phase})

    hashes = collect_hashes(report)
    expected_hashes: list[tuple[str, list[str], Path | None]] = [
        ("source", ["source"], source_path),
        ("parameters", ["parameters", "parameter"], project / "parameters.yaml"),
        ("manifest", ["manifest"], project / "review" / "manifest.json"),
        ("step_manifest", ["step.manifest"], project / iteration_utils.STEP_MANIFEST_REL),
        ("mesh", ["mesh"], mesh_path),
    ]
    if steps:
        expected_hashes.append(("step", ["step"], steps[0]))

    for label, aliases, path in expected_hashes:
        if path is None or not path.is_file():
            continue
        expected = file_sha256(path)
        values = matching_hash_values(hashes, aliases)
        if not values:
            add_issue(
                issues,
                severity_for_snapshot(phase, mode),
                "validation_report_hash_missing",
                f"validation/report.json does not record a {label} hash or equivalent snapshot field",
                artifact=label,
                path=safe_relative(path, project),
            )
        elif expected and expected.lower() not in values:
            add_issue(
                issues,
                "error",
                "validation_report_hash_mismatch",
                f"validation/report.json {label} hash does not match the current artifact",
                artifact=label,
                path=safe_relative(path, project),
                expected_sha256=expected,
                report_hashes=values,
            )
        else:
            checks.append({"check": f"validation-report-hash:{label}", "status": "pass"})

    compare_report_parameter_values(parameters, report, issues, phase=phase, mode=mode)


def compare_report_parameter_values(parameters: dict[str, Any], report: Any, issues: list[dict[str, Any]], *, phase: str, mode: str) -> None:
    for path, value in iter_leaf_values(report):
        if isinstance(value, bool):
            continue
        number = numeric(value)
        if number is None:
            continue
        path_text = ".".join(path)
        lowered_path = path_text.lower()
        if "temporary" in lowered_path or "min" in lowered_path or "max" in lowered_path:
            continue
        for parameter_id, data in parameters.items():
            current_value = numeric(parameter_value(data))
            if current_value is None:
                continue
            tokens = parameter_alias_tokens(parameter_id, data)
            if not token_match(path_text, tokens):
                continue
            if not same_value(number, current_value):
                add_issue(
                    issues,
                    severity_for_current(phase, mode),
                    "validation_report_stale_parameter_value",
                    "validation/report.json records a current parameter value that differs from parameters.yaml",
                    parameter_id=parameter_id,
                    report_path=path_text,
                    report_value=value,
                    parameters_yaml_value=parameter_value(data),
                )


def brief_parameter_warnings(brief_text: str, parameters: dict[str, Any]) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    for line_number, line in enumerate(brief_text.splitlines(), start=1):
        line_numbers = []
        for match in NUMBER_RE.finditer(line):
            try:
                line_numbers.append(float(match.group(0)))
            except ValueError:
                continue
        if not line_numbers:
            continue
        for parameter_id, data in parameters.items():
            current = numeric(parameter_value(data))
            if current is None:
                continue
            tokens = parameter_alias_tokens(parameter_id, data)
            if not token_match(line, tokens):
                continue
            if not any(same_value(value, current) for value in line_numbers):
                warnings.append(
                    issue(
                        "warning",
                        "brief_stale_parameter_value",
                        "brief.md appears to mention an old parameter value",
                        parameter_id=parameter_id,
                        line=line_number,
                        brief_values=line_numbers,
                        parameters_yaml_value=parameter_value(data),
                        text=line.strip(),
                    )
                )
    return warnings


def audit_brief(
    project: Path,
    parameters: dict[str, Any],
    issues: list[dict[str, Any]],
    *,
    phase: str,
    mode: str,
    override_allowed: bool,
) -> None:
    path = project / "brief.md"
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        add_issue(issues, "error", "brief_missing", "brief.md is missing")
        return
    lower = text.lower()
    backend_severity = severity_for_current(phase, mode)
    stale_backend_phrases = [
        "current model is a fusion",
        "current fusion",
        "accepted baseline implementation",
        "current fusion implementation",
        "fusion implementation reference",
    ]
    if not override_allowed and (any(phrase in lower for phrase in stale_backend_phrases) or (FUSION_RE.search(text) and "current" in lower)):
        add_issue(
            issues,
            backend_severity,
            "brief_stale_backend_reference",
            "brief.md appears to describe Fusion/legacy backend state as current without a recorded backend override",
        )
    if phase == "draft_review" and any(phrase in lower for phrase in ["accepted baseline", "release-ready", "release ready", "handoff complete"]):
        add_issue(
            issues,
            "warning" if mode != "strict" else "error",
            "brief_lifecycle_language_mismatch",
            "brief.md uses accepted/release language while lifecycle.phase is draft_review or missing",
        )
    issues.extend(brief_parameter_warnings(text, parameters))


def audit(project: Path, *, mode: str = "auto") -> dict[str, Any]:
    if mode not in {"auto", "warn", "strict"}:
        raise RuntimeError("mode must be one of: auto, warn, strict")

    project = project.expanduser().resolve()
    issues: list[dict[str, Any]] = []
    checks: list[dict[str, Any]] = []

    spec_errors: list[dict[str, Any]] = []
    spec = load_yaml(project / "spec" / "current.yaml", spec_errors)
    issues.extend(spec_errors)
    phase, phase_source = phase_from_spec(spec)
    if phase is None:
        phase = "draft_review"
        phase_source = "default:draft_review"
        add_issue(
            issues,
            severity_for_missing_phase("strict" if mode == "strict" else "warn"),
            "phase_missing",
            "spec/current.yaml is missing lifecycle.phase; treating as draft_review, which is not a handoff/current state",
        )
        if isinstance(spec, dict) and isinstance(spec.get("status"), dict):
            add_issue(
                issues,
                "warning",
                "legacy_status_phase_substitute",
                "spec/current.yaml has legacy status fields; status.step_exported cannot substitute for lifecycle.phase",
            )
    elif phase not in PROJECT_PHASES:
        add_issue(issues, "error", "phase_unsupported", f"unsupported lifecycle.phase {phase!r}", expected=sorted(PROJECT_PHASES))
    else:
        checks.append({"check": "lifecycle-phase", "status": "pass", "phase": phase, "source": phase_source})

    effective_mode = "strict" if mode == "strict" else "warn"

    has_override, override_name, override_reason = backend_override(spec)
    override_allowed = phase == "backend_override" and bool(override_name and override_reason)
    if phase == "backend_override" and not override_allowed:
        add_issue(
            issues,
            "error",
            "backend_override_incomplete",
            "phase backend_override requires spec.backend.override with backend/name and reason",
            backend=override_name,
            reason=override_reason,
        )
    elif override_allowed:
        checks.append({"check": "backend-override-record", "status": "pass", "backend": override_name})
    elif has_override:
        add_issue(
            issues,
            "warning",
            "backend_override_outside_override_phase",
            f"spec.backend.override is recorded while lifecycle.phase is {phase}; confirm this exception is still intentional",
        )

    parameter_doc = load_yaml(project / "parameters.yaml", issues)
    parameters = parameter_doc.get("parameters") if isinstance(parameter_doc, dict) else None
    if not isinstance(parameters, dict):
        add_issue(issues, "error", "parameters_missing_mapping", "parameters.yaml must contain a parameters mapping")
        parameters = {}

    manifest = load_json(project / "review" / "manifest.json", issues)
    report_missing_severity = severity_for_current(phase, effective_mode) if phase in STEP_REQUIRED_PHASES or effective_mode == "strict" else "warning"
    report = load_json(project / "validation" / "report.json", issues, missing_severity=report_missing_severity)

    if isinstance(manifest, dict):
        compare_manifest_source(
            project,
            spec,
            manifest,
            issues,
            checks,
            phase=phase,
            mode=effective_mode,
            override_allowed=override_allowed,
        )
        compare_manifest_parameters(parameters, manifest, issues, checks, phase=phase, mode=effective_mode)
    steps = compare_step_state(project, spec, manifest, report, issues, checks, phase=phase, mode=effective_mode)
    mesh_path: Path | None = None
    if isinstance(manifest, dict):
        mesh_path, _ = compare_mesh_snapshot(
            project,
            parameters,
            manifest,
            issues,
            checks,
            phase=phase,
            mode=effective_mode,
            override_allowed=override_allowed,
        )
    source_path = current_source_from_spec(project, spec)
    compare_report_snapshot(
        project,
        spec,
        parameters,
        report,
        source_path,
        mesh_path,
        steps,
        issues,
        checks,
        phase=phase,
        phase_source=phase_source,
        mode=effective_mode,
    )
    audit_brief(project, parameters, issues, phase=phase, mode=effective_mode, override_allowed=override_allowed)

    errors = [item for item in issues if item["severity"] == "error"]
    warnings = [item for item in issues if item["severity"] == "warning"]
    status = "fail" if errors else ("warn" if warnings else "pass")
    summary = {
        "status_line": f"{status}: {len(errors)} error(s), {len(warnings)} warning(s)",
        "phase": phase,
        "strictness": effective_mode,
        "top_errors": [item["message"] for item in errors[:5]],
        "top_warnings": [item["message"] for item in warnings[:5]],
    }
    return {
        "schema": SCHEMA,
        "project": str(project),
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "phase": {"value": phase, "source": phase_source},
        "mode": mode,
        "strictness": effective_mode,
        "status": status,
        "checks": checks,
        "issues": issues,
        "errors": errors,
        "warnings": warnings,
        "summary": summary,
    }


def render_summary(report: dict[str, Any]) -> str:
    lines = [
        report["summary"]["status_line"],
        f"phase: {report['phase']['value']} ({report['phase']['source']}), strictness: {report['strictness']}",
    ]
    for label in ["errors", "warnings"]:
        items = report.get(label, [])
        if not items:
            continue
        lines.append(f"{label}:")
        for item in items[:10]:
            lines.append(f"- [{item.get('code')}] {item.get('message')}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_path", help="Model project root")
    parser.add_argument("--mode", choices=["auto", "warn", "strict"], default="auto", help="Audit strictness; auto is lightweight warn mode, strict is for export/package claims")
    parser.add_argument("--format", choices=["json", "summary", "both"], default="json", help="Output machine JSON, human summary, or both")
    args = parser.parse_args()

    try:
        report = audit(Path(args.project_path), mode=args.mode)
    except Exception as exc:
        report = {
            "schema": SCHEMA,
            "project": str(Path(args.project_path).expanduser().resolve()),
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "status": "fail",
            "errors": [issue("error", "unhandled_error", str(exc))],
            "warnings": [],
            "issues": [issue("error", "unhandled_error", str(exc))],
            "summary": {"status_line": f"fail: {exc}", "top_errors": [str(exc)], "top_warnings": []},
        }

    if args.format in {"summary", "both"}:
        print(render_summary(report), file=sys.stderr if args.format == "both" else sys.stdout)
    if args.format in {"json", "both"}:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report.get("status") in {"pass", "warn"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
