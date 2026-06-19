#!/usr/bin/env python3
"""Validate the structure of an engineering CAD model project."""

from __future__ import annotations

import argparse
from collections import Counter
import copy
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


def load_json(path: Path, errors: list[str]) -> object | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        errors.append(f"missing JSON file: {path}")
    except json.JSONDecodeError as exc:
        errors.append(f"invalid JSON in {path}: {exc}")
    return None


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


def mesh_path_from_manifest(project: Path, manifest: dict, errors: list[str]) -> Path | None:
    preview = manifest.get("preview")
    if not isinstance(preview, dict):
        return None
    mesh_json = preview.get("mesh_json")
    if not isinstance(mesh_json, str) or not mesh_json:
        return None
    path = (project / "review" / mesh_json).resolve()
    review_dir = (project / "review").resolve()
    if path != review_dir and review_dir not in path.parents:
        errors.append(f"preview mesh_json must stay under review/: {mesh_json}")
        return None
    return path


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


def validate(project: Path, require_step: bool, geometry_smoke: bool = False) -> dict:
    project = project.expanduser().resolve()
    errors: list[str] = []
    warnings: list[str] = []
    checks: list[dict[str, str]] = []

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
    elif require_step:
        errors.append("no STEP/STP files found in outputs/step")
    else:
        warnings.append("no STEP/STP files found in outputs/step")

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

    status = "pass" if not errors else "fail"
    return {
        "schema": "engineering-3d-modeling.project_validation.v1",
        "project": str(project),
        "status": status,
        "checks": checks,
        "warnings": warnings,
        "errors": errors,
        "step_files": [str(path.relative_to(project)) for path in step_files],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_path", help="Model project root")
    parser.add_argument("--require-step", action="store_true", help="Fail if outputs/step has no STEP/STP")
    parser.add_argument(
        "--geometry-smoke",
        action="store_true",
        help="Build the model with perturbed validation.affects_geometry parameters and fail if geometry is unchanged",
    )
    args = parser.parse_args()

    report = validate(Path(args.project_path), args.require_step, geometry_smoke=args.geometry_smoke)
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
