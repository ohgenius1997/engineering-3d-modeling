#!/usr/bin/env python3
"""Validate the structure of an engineering CAD model project."""

from __future__ import annotations

import argparse
from collections import Counter
import copy
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import review_validation
import audit_review_parameters
import audit_project_consistency
import iteration_utils


REQUIRED_FILES = [
    "AGENTS.md",
    "brief.md",
    "spec/current.yaml",
    "parameters.yaml",
    "source/model.py",
    "review/index.html",
    "review/manifest.json",
    "review/annotations.json",
    "review/parameter_patch.json",
]

REQUIRED_DIRS = [
    "spec",
    "inputs",
    "source",
    "outputs/step",
    "validation",
    "review",
    "previous",
]

FORBIDDEN_OUTPUT_SUFFIXES = {".stl", ".3mf", ".gcode", ".bgcode"}
PROJECT_PHASES = {"draft_review", "accepted_current", "release_handoff", "backend_override"}
STEP_REQUIRED_PHASES: set[str] = set()
STEP_MANIFEST_STATES = {"draft", "exported", "accepted_current", "release_handoff"}
STEP_PROMOTION_SCRIPT = "scripts/promote_model_project.py"


def load_json(path: Path, errors: list[str]) -> object | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        errors.append(f"missing JSON file: {path}")
    except json.JSONDecodeError as exc:
        errors.append(f"invalid JSON in {path}: {exc}")
    return None


def file_sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_relative(path: Path, project: Path) -> str:
    try:
        return str(path.resolve().relative_to(project.resolve()))
    except ValueError:
        return str(path)


def resolve_project_path(project: Path, value: object) -> Path | None:
    if not isinstance(value, str) or not value:
        return None
    path = Path(value)
    if path.is_absolute():
        return path.resolve()
    return (project / path).resolve()


def load_yaml_module():
    try:
        import yaml  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "PyYAML is required for geometry smoke validation. "
            "Run scripts/check_environment.py --install with this Python runtime."
        ) from exc
    return yaml


def load_parameters_yaml(path: Path) -> dict:
    yaml = load_yaml_module()
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"missing parameters.yaml: {path}") from exc
    if not isinstance(data, dict):
        raise RuntimeError("parameters.yaml must contain a YAML object")
    if not isinstance(data.get("parameters"), dict):
        raise RuntimeError("parameters.yaml must contain a 'parameters' mapping")
    return data


def load_spec_yaml(path: Path, errors: list[str]) -> dict[str, Any] | None:
    try:
        yaml = load_yaml_module()
    except RuntimeError as exc:
        errors.append(str(exc))
        return None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except Exception as exc:
        errors.append(f"invalid YAML in {path}: {exc}")
        return None
    if not isinstance(data, dict):
        errors.append("spec/current.yaml must contain a YAML object")
        return None
    return data


def phase_from_spec(spec: dict[str, Any] | None) -> tuple[str | None, str]:
    if not isinstance(spec, dict):
        return None, "missing"
    lifecycle = spec.get("lifecycle")
    if isinstance(lifecycle, dict) and isinstance(lifecycle.get("phase"), str):
        return lifecycle["phase"], "spec.lifecycle.phase"
    project = spec.get("project")
    if isinstance(project, dict):
        if isinstance(project.get("phase"), str):
            return project["phase"], "spec.project.phase"
        if isinstance(project.get("status"), str):
            return project["status"], "spec.project.status"
    status = spec.get("status")
    if isinstance(status, dict) and isinstance(status.get("phase"), str):
        return status["phase"], "spec.status.phase"
    if isinstance(status, str):
        return status, "spec.status"
    return None, "missing"


def resolve_project_phase(
    project: Path,
    *,
    phase_override: str | None = None,
    errors: list[str] | None = None,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    local_errors = errors if errors is not None else []
    local_warnings = warnings if warnings is not None else []
    spec = load_spec_yaml(project / "spec" / "current.yaml", local_errors)
    phase, source = phase_from_spec(spec)

    if phase_override:
        phase = phase_override
        source = "override"

    if phase is None:
        phase = "draft_review"
        source = "default:draft_review"
        local_warnings.append(
            "project phase is missing from spec/current.yaml; treating as draft_review, "
            "which may defer STEP but is not an accepted or release-ready state"
        )

    if phase not in PROJECT_PHASES:
        local_errors.append(
            "unsupported project phase "
            f"{phase!r}; expected one of {', '.join(sorted(PROJECT_PHASES))}"
        )

    return {"value": phase, "source": source, "spec": spec}


def step_requirement_for_phase(phase: str, require_step: bool | None) -> tuple[bool, str]:
    if require_step is True:
        return True, "--require-step"
    if require_step is False:
        return False, "explicit allow_missing_step"
    if phase in STEP_REQUIRED_PHASES:
        return True, f"phase:{phase}"
    return False, f"phase:{phase}"


def validate_step_manifest(
    project: Path,
    *,
    phase: str,
    step_required: bool,
    step_files: list[Path],
    errors: list[str],
    warnings: list[str],
    checks: list[dict[str, str]],
) -> dict[str, Any] | None:
    iteration_utils.refresh_step_freshness(project, updated_by="scripts/validate_model_project.py")
    path = project / iteration_utils.STEP_MANIFEST_REL
    manifest = load_json(path, errors) if path.is_file() else None
    phase_requires_promoted_step = phase in STEP_REQUIRED_PHASES

    if manifest is None:
        if step_files:
            message = (
                "outputs/step contains STEP/STP files but outputs/step/manifest.json is missing; "
                "draft STEP cannot be treated as accepted or release output without promotion"
            )
            if phase_requires_promoted_step:
                errors.append(message)
            else:
                warnings.append(message)
        return None

    if not isinstance(manifest, dict):
        errors.append("outputs/step/manifest.json must contain a JSON object")
        return None

    if manifest.get("schema") != iteration_utils.STEP_MANIFEST_SCHEMA:
        errors.append("outputs/step/manifest.json schema is missing or unexpected")

    state = manifest.get("state")
    if state not in STEP_MANIFEST_STATES:
        errors.append(
            "outputs/step/manifest.json state must be one of "
            + ", ".join(sorted(STEP_MANIFEST_STATES))
        )
    else:
        checks.append({"check": "step-manifest-state", "status": "pass", "state": str(state)})

    recorded_files = manifest.get("step_files")
    if not isinstance(recorded_files, list):
        errors.append("outputs/step/manifest.json step_files must be a list")
        recorded_files = []
    actual_by_rel = {safe_relative(path, project): path for path in step_files}
    recorded_paths = {
        item.get("path")
        for item in recorded_files
        if isinstance(item, dict) and isinstance(item.get("path"), str)
    }
    missing_from_manifest = sorted(set(actual_by_rel) - recorded_paths)
    if missing_from_manifest:
        message = (
            "outputs/step/manifest.json does not record current STEP file(s): "
            + ", ".join(missing_from_manifest)
        )
        if phase_requires_promoted_step:
            errors.append(message)
        else:
            warnings.append(message)
    for item in recorded_files:
        if not isinstance(item, dict):
            continue
        rel = item.get("path")
        if not isinstance(rel, str) or rel not in actual_by_rel:
            continue
        expected = file_sha256(actual_by_rel[rel])
        if expected and item.get("sha256") and str(item["sha256"]).lower() != expected.lower():
            message = f"outputs/step/manifest.json hash for {rel} does not match current file"
            if phase_requires_promoted_step:
                errors.append(message)
            else:
                warnings.append(message)

    if phase_requires_promoted_step:
        if state != phase:
            errors.append(
                f"phase {phase} requires outputs/step/manifest.json state {phase}; "
                f"current state is {state!r}"
            )
        if manifest.get("promoted_by") != STEP_PROMOTION_SCRIPT:
            errors.append(
                "accepted_current/release_handoff STEP manifest must be written by "
                f"{STEP_PROMOTION_SCRIPT}"
            )
        if manifest.get("stale") is True:
            errors.append("accepted_current/release_handoff STEP manifest must not be stale")
    elif state in STEP_REQUIRED_PHASES:
        errors.append(
            f"draft_review project still carries {state} STEP manifest semantics; "
            "start a new iteration with scripts/begin_model_iteration.py to mark STEP as draft/stale"
        )
    elif manifest.get("stale") is True and step_required:
        errors.append("STEP manifest is stale; rerun scripts/export_step.py before delivery")
    elif manifest.get("stale") is True:
        warnings.append("STEP manifest is stale; rerun scripts/export_step.py before using STEP as current output")

    return manifest


def review_audit_mode_for_phase(mode: str, phase: str) -> str:
    if mode != "auto":
        return mode
    return "basic"


def validate_backend_override_record(
    spec: dict[str, Any] | None,
    phase: str,
    errors: list[str],
    warnings: list[str],
    checks: list[dict[str, str]],
) -> None:
    if not isinstance(spec, dict):
        return
    backend = spec.get("backend") if isinstance(spec.get("backend"), dict) else {}
    override = backend.get("override") if isinstance(backend, dict) else None
    has_override = isinstance(override, dict) and bool(override)

    if phase == "backend_override":
        if not has_override:
            errors.append(
                "phase backend_override requires spec/current.yaml backend.override "
                "with at least backend/name and reason fields"
            )
            return
        backend_name = override.get("backend") or override.get("name")
        reason = override.get("reason")
        if not isinstance(backend_name, str) or not backend_name.strip():
            errors.append("backend.override must record the override backend/name")
        if not isinstance(reason, str) or not reason.strip():
            errors.append("backend.override must record the reason for the override")
        if backend_name and reason:
            checks.append({"check": "phase:backend_override-record", "status": "pass"})
        warnings.append(
            "phase backend_override is an explicit temporary backend state; "
            "do not treat it as accepted_current or release_handoff until STEP validation passes"
        )
    elif has_override:
        warnings.append(
            f"backend.override is recorded while phase is {phase}; confirm the override is still intentional"
        )


def numeric_value(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def parameter_value(data: object) -> float | None:
    if isinstance(data, dict):
        return numeric_value(data.get("value"))
    return numeric_value(data)


def parameter_ui(data: object) -> dict:
    if isinstance(data, dict) and isinstance(data.get("ui"), dict):
        return data["ui"]
    return {}


def parameter_validation(data: object) -> dict:
    if isinstance(data, dict) and isinstance(data.get("validation"), dict):
        return data["validation"]
    return {}


def geometry_smoke_candidates(parameters_doc: dict) -> list[dict[str, object]]:
    parameters = parameters_doc.get("parameters")
    if not isinstance(parameters, dict):
        return []

    candidates: list[dict[str, object]] = []
    for parameter_id, data in parameters.items():
        value = parameter_value(data)
        validation = parameter_validation(data)
        if value is None or validation.get("affects_geometry") is not True:
            continue
        candidates.append(
            {
                "id": str(parameter_id),
                "value": value,
                "data": data,
            }
        )
    return candidates


def number_from_meta(data: object, key: str) -> float | None:
    ui = parameter_ui(data)
    if key in ui:
        value = numeric_value(ui.get(key))
        if value is not None:
            return value
    if isinstance(data, dict):
        return numeric_value(data.get(key))
    return None


def perturbed_value(data: object, value: float) -> float:
    minimum = number_from_meta(data, "min")
    maximum = number_from_meta(data, "max")
    step = number_from_meta(data, "step")
    if step is None or step <= 0:
        span = (maximum - minimum) if minimum is not None and maximum is not None else abs(value)
        step = max(span * 0.1, 1.0)

    candidates = [value + step, value - step, value * 1.1 if value else value + step]
    for candidate in candidates:
        if minimum is not None and candidate < minimum:
            continue
        if maximum is not None and candidate > maximum:
            continue
        if abs(candidate - value) > 1e-9:
            return float(candidate)
    raise RuntimeError(f"cannot perturb value {value!r} within declared bounds")


def set_parameter_value(parameters_doc: dict, parameter_id: str, value: float) -> dict:
    updated = copy.deepcopy(parameters_doc)
    parameters = updated["parameters"]
    target = parameters[parameter_id]
    if isinstance(target, dict):
        target["value"] = value
    else:
        parameters[parameter_id] = value
    return updated


def write_temp_parameters(parameters_doc: dict) -> Path:
    yaml = load_yaml_module()
    tmp = tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8")
    with tmp:
        yaml.safe_dump(parameters_doc, tmp, sort_keys=False, allow_unicode=True)
    return Path(tmp.name)


def load_model_module(source_path: Path):
    module_name = f"engineering_3d_model_{abs(hash(source_path))}"
    spec = importlib.util.spec_from_file_location(module_name, source_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import model source: {source_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def vector_tuple(value: object) -> tuple[float, float, float]:
    try:
        return tuple(round(float(component), 6) for component in value)  # type: ignore[arg-type, return-value]
    except TypeError:
        return (
            round(float(getattr(value, "X")), 6),
            round(float(getattr(value, "Y")), 6),
            round(float(getattr(value, "Z")), 6),
        )


def scalar_metric(model: object, name: str) -> float | None:
    value = getattr(model, name, None)
    if callable(value):
        value = value()
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return round(float(value), 6)
    return None


def geometry_signature(model: object) -> tuple[object, ...]:
    bounding_box = getattr(model, "bounding_box", None)
    if not callable(bounding_box):
        raise RuntimeError("model returned by build_model() has no bounding_box() method")
    box = bounding_box()
    return (
        vector_tuple(box.min),
        vector_tuple(box.max),
        vector_tuple(box.size),
        scalar_metric(model, "volume"),
        scalar_metric(model, "area"),
    )


def build_signature_with_parameters(model_module: object, parameters_path: Path) -> tuple[object, ...]:
    load_parameters = getattr(model_module, "load_parameters", None)
    build_model = getattr(model_module, "build_model", None)
    if not callable(load_parameters):
        raise RuntimeError("source/model.py must define callable load_parameters(path)")
    if not callable(build_model):
        raise RuntimeError("source/model.py must define callable build_model(params)")
    params = load_parameters(parameters_path)
    model = build_model(params)
    return geometry_signature(model)


def validate_geometry_smoke(project: Path, errors: list[str], warnings: list[str], checks: list[dict[str, str]]) -> None:
    parameters_path = project / "parameters.yaml"
    parameters_doc = load_parameters_yaml(parameters_path)
    candidates = geometry_smoke_candidates(parameters_doc)
    if not candidates:
        warnings.append("no parameters declare validation.affects_geometry=true; geometry smoke skipped")
        return

    cache_dir = project / "review" / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("XDG_CACHE_HOME", str(cache_dir))

    model_module = load_model_module(project / "source" / "model.py")
    baseline = build_signature_with_parameters(model_module, parameters_path)

    for candidate in candidates:
        parameter_id = str(candidate["id"])
        value = float(candidate["value"])
        data = candidate["data"]
        changed_value = perturbed_value(data, value)
        changed_doc = set_parameter_value(parameters_doc, parameter_id, changed_value)
        temp_path = write_temp_parameters(changed_doc)
        try:
            changed = build_signature_with_parameters(model_module, temp_path)
        finally:
            try:
                temp_path.unlink()
            except FileNotFoundError:
                pass
        if changed == baseline:
            errors.append(
                f"geometry smoke parameter {parameter_id} did not change backend geometry "
                f"when value changed from {value} to {changed_value}"
            )
        else:
            checks.append({"check": f"geometry-smoke:{parameter_id}", "status": "pass"})


def face_indices(face: object) -> list[int]:
    if isinstance(face, list):
        return [int(value) for value in face if isinstance(value, int)]
    if isinstance(face, dict) and isinstance(face.get("indices"), list):
        return [int(value) for value in face["indices"] if isinstance(value, int)]
    return []


def face_part_id(face: object) -> str:
    if isinstance(face, dict):
        value = face.get("part_id") or face.get("part") or ""
        return value if isinstance(value, str) else ""
    return ""


def review_asset_path_from_manifest(project: Path, manifest: dict, key: str, errors: list[str]) -> Path | None:
    preview = manifest.get("preview")
    if not isinstance(preview, dict):
        return None
    value = preview.get(key)
    if not isinstance(value, str) or not value:
        return None
    path = (project / "review" / value).resolve()
    review_dir = (project / "review").resolve()
    if path != review_dir and review_dir not in path.parents:
        errors.append(f"preview {key} must stay under review/: {value}")
        return None
    return path


def mesh_path_from_manifest(project: Path, manifest: dict, errors: list[str]) -> Path | None:
    return review_asset_path_from_manifest(project, manifest, "mesh_json", errors)


def validate_preview_adapter(project: Path, manifest: dict, errors: list[str], checks: list[dict[str, str]]) -> None:
    parameters = manifest.get("parameters")
    adapter_parameter_ids = []
    if isinstance(parameters, list):
        for parameter in parameters:
            if not isinstance(parameter, dict):
                continue
            preview = parameter.get("preview")
            if isinstance(preview, dict) and preview.get("effect") == "adapter":
                adapter_parameter_ids.append(parameter.get("id"))
    path = review_asset_path_from_manifest(project, manifest, "adapter_js", errors)
    if adapter_parameter_ids and path is None:
        errors.append(
            "preview adapter parameters require preview.adapter_js: "
            + ", ".join(str(parameter_id) for parameter_id in adapter_parameter_ids)
        )
        return
    if path is None:
        return
    if path.suffix.lower() != ".js":
        errors.append("preview adapter_js must point to a JavaScript file")
        return
    if not path.is_file():
        errors.append(f"preview adapter_js does not exist: {path.relative_to(project)}")
        return
    checks.append({"check": "preview-adapter", "status": "pass"})


def vertex_key(vertex: object) -> tuple[float, float, float]:
    if not isinstance(vertex, list) or len(vertex) != 3:
        return (0.0, 0.0, 0.0)
    return tuple(round(float(value), 6) for value in vertex)  # type: ignore[return-value]


def validate_preview_mesh(project: Path, manifest: dict, errors: list[str], warnings: list[str], checks: list[dict[str, str]]) -> None:
    mesh_path = mesh_path_from_manifest(project, manifest, errors)
    if mesh_path is None:
        return
    mesh = load_json(mesh_path, errors)
    if not isinstance(mesh, dict):
        return

    vertices = mesh.get("vertices")
    faces = mesh.get("faces")
    if not isinstance(vertices, list) or not isinstance(faces, list):
        errors.append("preview mesh must contain vertices and faces lists")
        return
    if not vertices or not faces:
        errors.append("preview mesh vertices and faces must be non-empty")
        return

    invalid_vertices = [
        index
        for index, vertex in enumerate(vertices)
        if not (
            isinstance(vertex, list)
            and len(vertex) == 3
            and all(isinstance(value, (int, float)) for value in vertex)
        )
    ]
    if invalid_vertices:
        errors.append(f"preview mesh has invalid vertices: {invalid_vertices[:5]}")

    edge_counts: Counter[tuple[tuple[float, float, float], tuple[float, float, float]]] = Counter()
    part_ids: Counter[str] = Counter()
    for face_index, face in enumerate(faces):
        indices = face_indices(face)
        if len(indices) < 3:
            errors.append(f"preview mesh face {face_index} has fewer than 3 valid indices")
            continue
        invalid = [index for index in indices if index < 0 or index >= len(vertices)]
        if invalid:
            errors.append(f"preview mesh face {face_index} has out-of-range indices: {invalid[:5]}")
            continue
        part_id = face_part_id(face)
        if part_id:
            part_ids[part_id] += 1
        for i, a in enumerate(indices):
            b = indices[(i + 1) % len(indices)]
            edge = tuple(sorted((vertex_key(vertices[a]), vertex_key(vertices[b]))))
            edge_counts[edge] += 1

    project_info = manifest.get("project") if isinstance(manifest.get("project"), dict) else {}
    project_kind = project_info.get("kind")
    parts = manifest.get("parts", [])
    if project_kind == "part" and isinstance(parts, list) and len(parts) > 1:
        errors.append("part projects must not declare multiple manifest.parts; use one part plus feature_id groups")
    if project_kind == "part" and len(part_ids) > 1:
        errors.append("part preview mesh must not use multiple part_id values; use one part_id and feature_id for sub-features")

    preview = manifest.get("preview") if isinstance(manifest.get("preview"), dict) else {}
    mesh_closed = preview.get("mesh_closed", True)
    open_edges = [edge for edge, count in edge_counts.items() if count == 1]
    nonmanifold_edges = [edge for edge, count in edge_counts.items() if count > 2]
    if mesh_closed is not False and open_edges:
        errors.append(
            f"preview mesh has {len(open_edges)} open boundary edges; add missing caps/faces or set preview.mesh_closed=false"
        )
    if nonmanifold_edges:
        warnings.append(f"preview mesh has {len(nonmanifold_edges)} non-manifold edges")
    if not any(error.startswith("preview mesh") or "preview mesh" in error for error in errors):
        checks.append({"check": "preview-mesh", "status": "pass"})


def append_review_parameter_audit(
    project: Path,
    mode: str,
    errors: list[str],
    warnings: list[str],
    checks: list[dict[str, str]],
) -> dict | None:
    if mode == "off":
        return None
    try:
        report = audit_review_parameters.audit(project, mode=mode)
    except Exception as exc:
        errors.append(f"review parameter audit failed: {exc}")
        return None

    checks.append({"check": f"review-parameter-audit:{mode}", "status": report["status"]})
    for item in report.get("disabled_parameters", []):
        if not isinstance(item, dict):
            continue
        errors.append(
            "review parameter audit disabled "
            f"{item.get('id')}: {item.get('reason')}; suggested action: {item.get('suggested_action')}"
        )
    candidates = [
        item.get("id")
        for item in report.get("new_candidates", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    ]
    if candidates:
        warnings.append("review parameter audit found backend-only candidate parameters: " + ", ".join(candidates))
    for warning in report.get("warnings", []):
        warnings.append(f"review parameter audit: {warning}")
    return report


def source_path_from_spec(project: Path, spec: dict[str, Any] | None) -> Path | None:
    if isinstance(spec, dict):
        source = spec.get("source")
        if isinstance(source, dict):
            path = resolve_project_path(project, source.get("entrypoint"))
            if path is not None:
                return path
    path = project / "source" / "model.py"
    return path.resolve()


def mesh_path_for_snapshot(project: Path, manifest: object, errors: list[str]) -> Path | None:
    if not isinstance(manifest, dict):
        return None
    return mesh_path_from_manifest(project, manifest, errors)


def snapshot_file(project: Path, label: str, path: Path | None) -> dict[str, str] | None:
    if path is None:
        return None
    entry = {"path": safe_relative(path, project)}
    digest = file_sha256(path)
    if digest is not None:
        entry["sha256"] = digest
    return entry


def build_snapshot(
    project: Path,
    *,
    phase: str,
    phase_source: str,
    spec: dict[str, Any] | None,
    manifest: object,
    step_files: list[Path],
) -> dict[str, Any]:
    snapshot_errors: list[str] = []
    source_path = source_path_from_spec(project, spec)
    mesh_path = mesh_path_for_snapshot(project, manifest, snapshot_errors)
    files = {
        "spec": snapshot_file(project, "spec", project / "spec" / "current.yaml"),
        "parameters": snapshot_file(project, "parameters", project / "parameters.yaml"),
        "source": snapshot_file(project, "source", source_path),
        "manifest": snapshot_file(project, "manifest", project / "review" / "manifest.json"),
        "step_manifest": snapshot_file(project, "step_manifest", project / iteration_utils.STEP_MANIFEST_REL),
        "mesh": snapshot_file(project, "mesh", mesh_path),
    }
    files = {key: value for key, value in files.items() if value is not None}
    return {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "phase": {"value": phase, "source": phase_source},
        "files": files,
        "step_files": [
            {
                "path": safe_relative(path, project),
                "sha256": file_sha256(path),
            }
            for path in step_files
        ],
        "warnings": snapshot_errors,
    }


def consistency_mode_for_phase(mode: str, phase: str) -> str:
    if mode != "auto":
        return mode
    return "off"


def append_consistency_audit(
    project: Path,
    mode: str,
    errors: list[str],
    warnings: list[str],
    checks: list[dict[str, str]],
) -> dict[str, Any] | None:
    if mode == "off":
        return None
    try:
        report = audit_project_consistency.audit(project, mode=mode)
    except Exception as exc:
        errors.append(f"project consistency audit failed: {exc}")
        return None
    checks.append({"check": f"project-consistency-audit:{mode}", "status": report["status"]})
    for item in report.get("errors", []):
        if isinstance(item, dict):
            errors.append(f"project consistency audit {item.get('code')}: {item.get('message')}")
    for item in report.get("warnings", []):
        if isinstance(item, dict):
            warnings.append(f"project consistency audit {item.get('code')}: {item.get('message')}")
    return report


def validate(
    project: Path,
    require_step: bool | None = None,
    geometry_smoke: bool = False,
    review_parameter_audit: str = "auto",
    phase_override: str | None = None,
    consistency_audit: str = "auto",
) -> dict:
    project = project.expanduser().resolve()
    errors: list[str] = []
    warnings: list[str] = []
    checks: list[dict[str, str]] = []
    phase_info = resolve_project_phase(project, phase_override=phase_override, errors=errors, warnings=warnings)
    phase = str(phase_info["value"])
    spec = phase_info.get("spec") if isinstance(phase_info.get("spec"), dict) else None
    step_required, step_requirement_reason = step_requirement_for_phase(phase, require_step)
    audit_mode = review_audit_mode_for_phase(review_parameter_audit, phase)
    consistency_mode = consistency_mode_for_phase(consistency_audit, phase)

    for rel in REQUIRED_DIRS:
        path = project / rel
        if path.is_dir():
            checks.append({"check": f"dir:{rel}", "status": "pass"})
        else:
            errors.append(f"missing required directory: {rel}")

    for rel in REQUIRED_FILES:
        path = project / rel
        if path.is_file():
            checks.append({"check": f"file:{rel}", "status": "pass"})
        else:
            errors.append(f"missing required file: {rel}")

    validate_backend_override_record(spec, phase, errors, warnings, checks)

    manifest = load_json(project / "review" / "manifest.json", errors)
    annotations = load_json(project / "review" / "annotations.json", errors)
    parameter_patch = load_json(project / "review" / "parameter_patch.json", errors)

    if isinstance(manifest, dict):
        schema_errors = review_validation.validate_manifest_schema(manifest)
        if schema_errors:
            errors.extend(f"review/manifest.json schema: {error}" for error in schema_errors)
        else:
            checks.append({"check": "schema:review/manifest.json", "status": "pass"})
        if manifest.get("schema") != "engineering-3d-modeling.review_manifest.v1":
            warnings.append("review/manifest.json schema is missing or unexpected")
        if not isinstance(manifest.get("parameters", []), list):
            errors.append("review/manifest.json parameters must be a list")
        if not isinstance(manifest.get("refs", []), list):
            errors.append("review/manifest.json refs must be a list")
        validate_preview_adapter(project, manifest, errors, checks)
        validate_preview_mesh(project, manifest, errors, warnings, checks)

    if isinstance(annotations, dict):
        annotation_items = annotations.get("annotations")
        if not isinstance(annotation_items, list):
            errors.append("review/annotations.json annotations must be a list")
        else:
            for index, annotation in enumerate(annotation_items):
                if not isinstance(annotation, dict):
                    warnings.append(f"annotation {index} is not an object")
                    continue
                if annotation.get("status") and annotation.get("status") != "open":
                    warnings.append(f"annotation {annotation.get('id', index)} is not open; consumed annotations should be cleared")
                if not annotation.get("created_at"):
                    warnings.append(f"annotation {annotation.get('id', index)} has no created_at; annotations should be user-authored review records")
        schema_errors = review_validation.validate_annotations_schema(annotations)
        if schema_errors:
            errors.extend(f"review/annotations.json schema: {error}" for error in schema_errors)
        else:
            checks.append({"check": "schema:review/annotations.json", "status": "pass"})

    if isinstance(parameter_patch, dict):
        schema_errors = review_validation.validate_parameter_patch_schema(parameter_patch)
        if schema_errors:
            errors.extend(f"review/parameter_patch.json schema: {error}" for error in schema_errors)
        else:
            checks.append({"check": "schema:review/parameter_patch.json", "status": "pass"})
        patches = parameter_patch.get("patches")
        if not isinstance(patches, list):
            errors.append("review/parameter_patch.json patches must be a list")
        elif isinstance(manifest, dict):
            declared = {
                param.get("id")
                for param in manifest.get("parameters", [])
                if isinstance(param, dict) and isinstance(param.get("id"), str)
            }
            for patch in patches:
                if isinstance(patch, dict) and patch.get("parameter_id") not in declared:
                    errors.append(f"parameter patch references undeclared review parameter: {patch.get('parameter_id')}")
            try:
                domain_errors = review_validation.validate_patch_against_project(
                    project,
                    parameter_patch,
                    manifest=manifest,
                )
                if domain_errors:
                    errors.extend(f"review/parameter_patch.json: {error}" for error in domain_errors)
                else:
                    checks.append({"check": "domain:review/parameter_patch.json", "status": "pass"})
            except RuntimeError as exc:
                errors.append(f"review/parameter_patch.json: {exc}")

    step_files = sorted((project / "outputs" / "step").glob("*.step")) + sorted((project / "outputs" / "step").glob("*.stp"))
    if step_files:
        checks.append({"check": "step-output", "status": "pass"})
    elif step_required:
        errors.append(
            f"phase {phase} requires STEP/STP output in outputs/step "
            f"({step_requirement_reason}); none found"
        )
    else:
        warnings.append(
            f"phase {phase} allows missing STEP/STP during draft/review work "
            f"({step_requirement_reason}); do not call this state accepted, complete, or release-ready"
        )
    step_manifest = validate_step_manifest(
        project,
        phase=phase,
        step_required=step_required,
        step_files=step_files,
        errors=errors,
        warnings=warnings,
        checks=checks,
    )

    forbidden = []
    outputs = project / "outputs"
    if outputs.exists():
        for path in outputs.rglob("*"):
            if path.is_file() and path.suffix.lower() in FORBIDDEN_OUTPUT_SUFFIXES:
                forbidden.append(str(path.relative_to(project)))
    if forbidden:
        warnings.append("downstream or mesh output files found under outputs/: " + ", ".join(forbidden))

    if geometry_smoke:
        try:
            validate_geometry_smoke(project, errors, warnings, checks)
        except Exception as exc:
            errors.append(f"geometry smoke failed: {exc}")

    audit_report = append_review_parameter_audit(
        project,
        audit_mode,
        errors,
        warnings,
        checks,
    )

    consistency_report = append_consistency_audit(
        project,
        consistency_mode,
        errors,
        warnings,
        checks,
    )

    status = "pass" if not errors else "fail"
    snapshot = build_snapshot(
        project,
        phase=phase,
        phase_source=str(phase_info["source"]),
        spec=spec,
        manifest=manifest,
        step_files=step_files,
    )
    return {
        "schema": "engineering-3d-modeling.project_validation.v1",
        "project": str(project),
        "generated_at": snapshot["generated_at"],
        "phase": {"value": phase, "source": phase_info["source"]},
        "step_requirement": {"required": step_required, "reason": step_requirement_reason},
        "status": status,
        "checks": checks,
        "warnings": warnings,
        "errors": errors,
        "step_files": [str(path.relative_to(project)) for path in step_files],
        "snapshot": snapshot,
        "step_manifest": step_manifest,
        "review_parameter_audit_mode": audit_mode,
        "review_parameter_audit": audit_report,
        "consistency_audit_mode": consistency_mode,
        "consistency_audit": consistency_report,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_path", help="Model project root")
    parser.add_argument("--require-step", action="store_true", help="Fail if outputs/step has no STEP/STP")
    parser.add_argument(
        "--phase",
        choices=sorted(PROJECT_PHASES),
        help="Override spec/current.yaml lifecycle.phase for this validation run",
    )
    parser.add_argument(
        "--geometry-smoke",
        action="store_true",
        help="Build the model with perturbed validation.affects_geometry parameters and fail if geometry is unchanged",
    )
    parser.add_argument(
        "--review-parameter-audit",
        choices=["auto", "off", "basic", "strict"],
        default="auto",
        help="Audit review manifest parameters; auto uses basic review audit",
    )
    parser.add_argument(
        "--strict-consistency",
        action="store_true",
        help="Run handoff/current consistency audit against spec, manifest, brief, validation report, STEP, parameters, and review cache",
    )
    args = parser.parse_args()

    report = validate(
        Path(args.project_path),
        True if args.require_step else None,
        geometry_smoke=args.geometry_smoke,
        review_parameter_audit=args.review_parameter_audit,
        phase_override=args.phase,
        consistency_audit="strict" if args.strict_consistency else "auto",
    )
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
