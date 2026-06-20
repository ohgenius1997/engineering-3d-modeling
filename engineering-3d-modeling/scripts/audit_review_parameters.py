#!/usr/bin/env python3
"""Audit review-exposed parameters against current model and preview behavior."""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import review_validation


SCHEMA = "engineering-3d-modeling.review_parameter_audit.v1"
PREVIEW_EFFECTS = {
    "scale_axis",
    "scale_radial",
    "scale_uniform",
    "offset_axis",
    "offset_radial",
    "twist_z",
    "ripple_radial",
    "generic_morph",
    "adapter",
}
AXIS_INDEX = {"x": 0, "y": 1, "z": 2}
DISABLE_ACTION = "set preview.effect to none and remove from review manifest"


def load_yaml_module():
    try:
        import yaml  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "PyYAML is required to audit review parameters. "
            "Run scripts/check_environment.py --install with this Python runtime."
        ) from exc
    return yaml


def load_json_if_present(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None


def manifest_parameters(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    parameters = manifest.get("parameters")
    if not isinstance(parameters, list):
        return []
    return [parameter for parameter in parameters if isinstance(parameter, dict)]


def manifest_parameter_map(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for parameter in manifest_parameters(manifest):
        parameter_id = parameter.get("id")
        if isinstance(parameter_id, str):
            out[parameter_id] = parameter
    return out


def parameter_value(data: Any) -> Any:
    return review_validation.parameter_value(data)


def parameter_ui(data: Any) -> dict[str, Any]:
    return review_validation.parameter_ui(data)


def parameter_validation(data: Any) -> dict[str, Any]:
    if isinstance(data, dict) and isinstance(data.get("validation"), dict):
        return data["validation"]
    return {}


def numeric(value: Any) -> float | None:
    return review_validation.numeric(value)


def parameter_meta_number(data: Any, key: str) -> float | None:
    return review_validation.parameter_meta_number(data, key)


def preview_metadata(parameter: dict[str, Any], yaml_data: Any) -> dict[str, Any] | None:
    preview = parameter.get("preview")
    if isinstance(preview, dict):
        return preview
    return None


def preview_effect(preview: dict[str, Any] | None) -> str | None:
    if not isinstance(preview, dict):
        return None
    effect = preview.get("effect")
    return effect if isinstance(effect, str) else None


def disabled(parameter_id: str, reason: str) -> dict[str, str]:
    return {
        "id": parameter_id,
        "reason": reason,
        "suggested_action": DISABLE_ACTION,
    }


def candidate(parameter_id: str, reason: str) -> dict[str, str]:
    return {
        "id": parameter_id,
        "reason": reason,
        "suggested_action": "keep in backend workflow until a preview binding is defined",
    }


def review_asset_path(project: Path, manifest: dict[str, Any], key: str) -> Path | None:
    preview = manifest.get("preview")
    if not isinstance(preview, dict):
        return None
    value = preview.get(key)
    if not isinstance(value, str) or not value:
        return None
    path = (project / "review" / value).resolve()
    review_dir = (project / "review").resolve()
    if path != review_dir and review_dir not in path.parents:
        raise RuntimeError(f"preview {key} must stay under review/: {value}")
    return path


def adapter_path(project: Path, manifest: dict[str, Any]) -> Path | None:
    return review_asset_path(project, manifest, "adapter_js")


def mesh_path(project: Path, manifest: dict[str, Any]) -> Path | None:
    return review_asset_path(project, manifest, "mesh_json")


def number_from_meta(data: Any, key: str) -> float | None:
    value = parameter_meta_number(data, key)
    if value is not None:
        return value
    return None


def perturbed_value(data: Any, value: Any) -> Any:
    number = numeric(value)
    if number is None:
        return None

    minimum = number_from_meta(data, "min")
    maximum = number_from_meta(data, "max")
    step = number_from_meta(data, "step")
    if step is None or step <= 0:
        span = (maximum - minimum) if minimum is not None and maximum is not None else abs(number)
        step = max(span * 0.1, 1.0)

    candidates = [number + step, number - step, number * 1.1 if number else number + step]
    for changed in candidates:
        if minimum is not None and changed < minimum:
            continue
        if maximum is not None and changed > maximum:
            continue
        if abs(changed - number) <= 1e-9:
            continue
        if isinstance(value, int) and not isinstance(value, bool) and abs(changed - round(changed)) <= 1e-9:
            return int(round(changed))
        return float(changed)
    return None


def set_parameter_value(parameters_doc: dict[str, Any], parameter_id: str, value: Any) -> dict[str, Any]:
    updated = copy.deepcopy(parameters_doc)
    parameters = updated["parameters"]
    target = parameters[parameter_id]
    if isinstance(target, dict):
        target["value"] = value
    else:
        parameters[parameter_id] = value
    return updated


def write_temp_parameters(parameters_doc: dict[str, Any]) -> Path:
    yaml = load_yaml_module()
    tmp = tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8")
    with tmp:
        yaml.safe_dump(parameters_doc, tmp, sort_keys=False, allow_unicode=True)
    return Path(tmp.name)


def load_model_module(source_path: Path):
    module_name = f"engineering_3d_audit_model_{abs(hash(source_path))}"
    spec = importlib.util.spec_from_file_location(module_name, source_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import model source: {source_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def vector_tuple(value: Any) -> tuple[float, float, float]:
    if isinstance(value, (list, tuple)) and len(value) >= 3:
        return tuple(round(float(component), 6) for component in value[:3])  # type: ignore[return-value]
    try:
        return tuple(round(float(component), 6) for component in value)  # type: ignore[arg-type, return-value]
    except TypeError:
        return (
            round(float(getattr(value, "X")), 6),
            round(float(getattr(value, "Y")), 6),
            round(float(getattr(value, "Z")), 6),
        )


def scalar_metric(model: Any, name: str) -> float | None:
    value = getattr(model, name, None)
    if callable(value):
        value = value()
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return round(float(value), 6)
    return None


def geometry_signature(model: Any) -> tuple[Any, ...]:
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


class BackendGeometryProbe:
    def __init__(self, project: Path, parameters_doc: dict[str, Any]) -> None:
        self.project = project
        self.parameters_doc = parameters_doc
        self._loaded = False
        self._baseline: tuple[Any, ...] | None = None
        self._module: Any = None
        self._load_error: str | None = None

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        try:
            cache_dir = self.project / "review" / "cache"
            cache_dir.mkdir(parents=True, exist_ok=True)
            os.environ.setdefault("XDG_CACHE_HOME", str(cache_dir))
            self._module = load_model_module(self.project / "source" / "model.py")
            self._baseline = self._build_signature(self.project / "parameters.yaml")
        except Exception as exc:
            self._load_error = str(exc)

    def _build_signature(self, parameters_path: Path) -> tuple[Any, ...]:
        load_parameters = getattr(self._module, "load_parameters", None)
        build_model = getattr(self._module, "build_model", None)
        if not callable(load_parameters):
            raise RuntimeError("source/model.py must define callable load_parameters(path)")
        if not callable(build_model):
            raise RuntimeError("source/model.py must define callable build_model(params)")
        params = load_parameters(parameters_path)
        model = build_model(params)
        return geometry_signature(model)

    def changed(self, parameter_id: str, data: Any) -> tuple[bool | None, Any | None, str | None]:
        self._ensure_loaded()
        if self._load_error is not None:
            return (None, None, self._load_error)
        if self._baseline is None:
            return (None, None, "backend geometry baseline was not produced")
        value = parameter_value(data)
        changed_value = perturbed_value(data, value)
        if changed_value is None:
            return (None, None, "parameter value is not numeric or cannot be perturbed within bounds")
        changed_doc = set_parameter_value(self.parameters_doc, parameter_id, changed_value)
        temp_path = write_temp_parameters(changed_doc)
        try:
            changed_signature = self._build_signature(temp_path)
        except Exception as exc:
            return (None, changed_value, str(exc))
        finally:
            try:
                temp_path.unlink()
            except FileNotFoundError:
                pass
        return (changed_signature != self._baseline, changed_value, None)


def rounded_vertices(vertices: list[Any]) -> list[list[float]]:
    out: list[list[float]] = []
    for vertex in vertices:
        if isinstance(vertex, list) and len(vertex) >= 3:
            out.append([round(float(vertex[0]), 6), round(float(vertex[1]), 6), round(float(vertex[2]), 6)])
    return out


def face_indices(face: Any) -> list[int]:
    if isinstance(face, list):
        return [int(value) for value in face if isinstance(value, int)]
    if isinstance(face, dict) and isinstance(face.get("indices"), list):
        return [int(value) for value in face["indices"] if isinstance(value, int)]
    return []


def normalize_mesh(mesh: Any) -> dict[str, Any] | None:
    if not isinstance(mesh, dict):
        return None
    if isinstance(mesh.get("vertices"), list) and isinstance(mesh.get("faces"), list):
        return {"vertices": mesh["vertices"], "faces": mesh["faces"]}
    faces = mesh.get("faces")
    if not isinstance(faces, list):
        return None
    vertices: list[list[float]] = []
    vertex_to_index: dict[tuple[float, float, float], int] = {}
    normalized_faces: list[dict[str, Any]] = []
    for face in faces:
        if not isinstance(face, dict) or not isinstance(face.get("pts"), list):
            return None
        indices = []
        for point in face["pts"]:
            if not isinstance(point, list) or len(point) < 3:
                return None
            key = tuple(round(float(point[index]), 12) for index in range(3))
            if key not in vertex_to_index:
                vertex_to_index[key] = len(vertices)
                vertices.append([float(key[0]), float(key[1]), float(key[2])])
            indices.append(vertex_to_index[key])
        normalized_faces.append({"indices": indices})
    return {"vertices": vertices, "faces": normalized_faces}


def mesh_signature(mesh: Any) -> tuple[Any, ...] | None:
    normalized = normalize_mesh(mesh)
    if normalized is None:
        return None
    vertices = rounded_vertices(normalized["vertices"])
    faces = [face_indices(face) for face in normalized["faces"]]
    if not vertices:
        return (0, len(faces), None)
    mins = [min(vertex[index] for vertex in vertices) for index in range(3)]
    maxes = [max(vertex[index] for vertex in vertices) for index in range(3)]
    digest = hashlib.sha256(
        json.dumps({"vertices": vertices, "faces": faces}, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return (len(vertices), len(faces), tuple(mins), tuple(maxes), digest)


def compute_bounds(vertices: list[list[float]]) -> dict[str, Any]:
    if not vertices:
        return {"center": [0.0, 0.0, 0.0], "radius": 20.0}
    mins = list(vertices[0])
    maxes = list(vertices[0])
    for vertex in vertices:
        for index in range(3):
            mins[index] = min(mins[index], vertex[index])
            maxes[index] = max(maxes[index], vertex[index])
    center = [(mins[index] + maxes[index]) / 2.0 for index in range(3)]
    radius = max(abs(maxes[index] - mins[index]) for index in range(3)) or 1.0
    return {"center": center, "radius": radius}


def effect_axes(effect: dict[str, Any]) -> list[int]:
    axes = effect.get("axes")
    if isinstance(axes, list):
        return [AXIS_INDEX[axis] for axis in axes if isinstance(axis, str) and axis in AXIS_INDEX]
    name = effect.get("effect")
    if name == "scale_uniform":
        return [0, 1, 2]
    if name in {"scale_radial", "offset_radial", "ripple_radial"}:
        axial = AXIS_INDEX.get(str(effect.get("axis") or "x"), 0)
        return [index for index in [0, 1, 2] if index != axial]
    axis = AXIS_INDEX.get(str(effect.get("axis") or "x"))
    return [] if axis is None else [axis]


def effect_origin(effect: dict[str, Any], bounds: dict[str, Any]) -> list[float]:
    origin = effect.get("origin")
    if isinstance(origin, list) and len(origin) == 3:
        return [float(origin[0]), float(origin[1]), float(origin[2])]
    if effect.get("anchor") == "origin":
        return [0.0, 0.0, 0.0]
    center = bounds.get("center")
    return [float(center[0]), float(center[1]), float(center[2])] if isinstance(center, list) else [0.0, 0.0, 0.0]


def normalized_delta(value: float, baseline: float) -> float:
    denominator = max(abs(baseline), 1.0)
    return max(-1.5, min(1.5, (value - baseline) / denominator))


def apply_preview_effect(point: list[float], effect: dict[str, Any], bounds: dict[str, Any], value: float) -> list[float]:
    out = list(point)
    baseline = numeric(effect.get("baseline"))
    if baseline is None:
        baseline = value
    axes = effect_axes(effect)
    origin = effect_origin(effect, bounds)
    factor = numeric(effect.get("factor"))
    factor = 1.0 if factor is None else factor
    name = effect.get("effect")

    if name == "offset_axis":
        for axis in axes:
            out[axis] += (value - baseline) * factor
    elif name == "offset_radial":
        delta = (value - baseline) * factor
        vec = [out[axis] - origin[axis] for axis in axes]
        length = math.hypot(*vec)
        if length > 1e-9:
            for offset, axis in enumerate(axes):
                out[axis] += (vec[offset] / length) * delta
    elif name == "twist_z":
        angle = (value - baseline) * math.pi / 180.0 * factor
        x = out[0] - origin[0]
        y = out[1] - origin[1]
        cos = math.cos(angle)
        sin = math.sin(angle)
        out[0] = origin[0] + x * cos - y * sin
        out[1] = origin[1] + x * sin + y * cos
    elif name == "ripple_radial":
        delta = normalized_delta(value, baseline) * float(bounds.get("radius") or 1.0) * 0.12 * factor
        vec = [out[axis] - origin[axis] for axis in axes]
        length = math.hypot(*vec)
        phase = math.atan2(out[1] - origin[1], out[0] - origin[0]) * 3.0 + (out[2] - origin[2]) / (
            float(bounds.get("radius") or 1.0) * 0.35
        )
        ripple = math.sin(phase) * delta
        if length > 1e-9:
            for offset, axis in enumerate(axes):
                out[axis] += (vec[offset] / length) * ripple
    elif name == "generic_morph":
        delta = normalized_delta(value, baseline) * float(bounds.get("radius") or 1.0) * 0.08 * factor
        out[0] += math.sin((out[2] - origin[2]) / (float(bounds.get("radius") or 1.0) * 0.5) + 1.7) * delta
        out[1] += math.cos((out[0] - origin[0]) / (float(bounds.get("radius") or 1.0) * 0.5) + 0.9) * delta
        out[2] += math.sin((out[1] - origin[1]) / (float(bounds.get("radius") or 1.0) * 0.5) + 2.1) * delta * 0.5
    else:
        if abs(baseline) < 1e-9:
            return out
        ratio = value / baseline
        for axis in axes:
            out[axis] = origin[axis] + (out[axis] - origin[axis]) * ratio
    return out


class PreviewMeshProbe:
    def __init__(self, project: Path, manifest: dict[str, Any]) -> None:
        self.project = project
        self.manifest = manifest
        self._mesh: dict[str, Any] | None | bool = False
        self._error: str | None = None

    def _ensure_loaded(self) -> None:
        if self._mesh is not False:
            return
        try:
            path = mesh_path(self.project, self.manifest)
            if path is None:
                self._mesh = None
                return
            raw = load_json_if_present(path)
            mesh = normalize_mesh(raw)
            if mesh is None:
                self._error = f"preview mesh is missing or invalid: {path.relative_to(self.project)}"
                self._mesh = None
                return
            self._mesh = mesh
        except Exception as exc:
            self._error = str(exc)
            self._mesh = None

    def changed(self, parameter: dict[str, Any], yaml_data: Any) -> tuple[bool | None, Any | None, str | None]:
        self._ensure_loaded()
        if self._error:
            return (None, None, self._error)
        if not isinstance(self._mesh, dict):
            return (None, None, "review preview mesh is not declared")
        preview = preview_metadata(parameter, yaml_data)
        if not isinstance(preview, dict):
            return (None, None, "parameter has no preview metadata")
        value = parameter.get("value", parameter_value(yaml_data))
        changed_value = perturbed_value(yaml_data, value)
        if changed_value is None:
            return (None, None, "parameter value is not numeric or cannot be perturbed within bounds")
        number = numeric(changed_value)
        if number is None:
            return (None, changed_value, "changed value is not numeric")
        vertices = rounded_vertices(self._mesh["vertices"])
        bounds = compute_bounds(vertices)
        changed_mesh = {
            "vertices": [apply_preview_effect(vertex, preview, bounds, number) for vertex in vertices],
            "faces": self._mesh["faces"],
        }
        return (mesh_signature(changed_mesh) != mesh_signature(self._mesh), changed_value, None)


ADAPTER_NODE_SCRIPT = r"""
const fs = require("fs");
const vm = require("vm");
const crypto = require("crypto");
const input = JSON.parse(fs.readFileSync(0, "utf8"));
const sandbox = {window: {}, console};
sandbox.globalThis = sandbox;
sandbox.window.window = sandbox.window;
vm.createContext(sandbox);
vm.runInContext(input.adapterCode, sandbox, {filename: input.adapterPath});
const adapter = sandbox.window.Engineering3DPreviewAdapter || sandbox.window.engineering3DPreviewAdapter || sandbox.Engineering3DPreviewAdapter;
if (!adapter || typeof adapter.generateMesh !== "function") {
  throw new Error("adapter must assign window.Engineering3DPreviewAdapter.generateMesh");
}
function normalizeMesh(data) {
  if (!data || typeof data !== "object") return null;
  if (Array.isArray(data.vertices) && Array.isArray(data.faces)) return data;
  if (Array.isArray(data.faces) && data.faces.every(face => Array.isArray(face && face.pts))) {
    const vertices = [];
    const faces = [];
    const map = new Map();
    function vertexIndex(point) {
      const key = point.map(value => Number(value).toPrecision(12)).join(",");
      if (!map.has(key)) {
        map.set(key, vertices.length);
        vertices.push(point.map(Number));
      }
      return map.get(key);
    }
    for (const face of data.faces) {
      faces.push({indices: face.pts.map(vertexIndex)});
    }
    return {vertices, faces};
  }
  return null;
}
function signature(data) {
  const mesh = normalizeMesh(data);
  if (!mesh) throw new Error("adapter returned invalid mesh");
  const vertices = mesh.vertices.map(vertex => vertex.slice(0, 3).map(value => Number(value).toFixed(6)));
  const faces = mesh.faces.map(face => Array.isArray(face) ? face : face.indices || []);
  const digest = crypto.createHash("sha256").update(JSON.stringify({vertices, faces})).digest("hex");
  return {vertexCount: vertices.length, faceCount: faces.length, digest};
}
function valuesFor(override) {
  const values = {};
  for (const record of input.manifest.parameters || []) {
    if (!record || !record.id) continue;
    values[record.id] = override && override.id === record.id ? override.value : record.value;
  }
  return values;
}
function recordsFor(override) {
  return (input.manifest.parameters || []).map(record => {
    if (!record || override === null || record.id !== override.id) return record;
    return Object.assign({}, record, {value: override.value});
  });
}
function generate(override) {
  const result = adapter.generateMesh({
    parameters: valuesFor(override),
    parameterRecords: recordsFor(override),
    manifest: input.manifest,
    adapterConfig: (input.manifest.preview && input.manifest.preview.adapter_config) || {},
    baseMesh: input.baseMesh,
    units: input.manifest.project && input.manifest.project.units,
  });
  if (result && typeof result.then === "function") {
    throw new Error("async preview adapters are not supported by the audit script");
  }
  return signature(result);
}
const baseline = generate(null);
const changed = generate({id: input.parameterId, value: input.changedValue});
process.stdout.write(JSON.stringify({changed: JSON.stringify(baseline) !== JSON.stringify(changed), baseline, changed}));
"""


class AdapterPreviewProbe:
    def __init__(self, project: Path, manifest: dict[str, Any]) -> None:
        self.project = project
        self.manifest = manifest
        self._node = shutil.which("node")
        self._adapter_path: Path | None | bool = False
        self._base_mesh: Any | None | bool = False
        self._error: str | None = None

    def _ensure_loaded(self) -> None:
        if self._adapter_path is not False:
            return
        try:
            self._adapter_path = adapter_path(self.project, self.manifest)
            if self._adapter_path is None:
                return
            if not self._adapter_path.is_file():
                self._error = f"preview adapter_js does not exist: {self._adapter_path.relative_to(self.project)}"
                return
            base_path = mesh_path(self.project, self.manifest)
            self._base_mesh = load_json_if_present(base_path) if base_path is not None else None
        except Exception as exc:
            self._error = str(exc)

    def changed(self, parameter: dict[str, Any], yaml_data: Any) -> tuple[bool | None, Any | None, str | None]:
        self._ensure_loaded()
        if self._error:
            return (None, None, self._error)
        if self._adapter_path is None or self._adapter_path is False:
            return (None, None, "manifest.preview.adapter_js is not declared")
        if self._node is None:
            return (None, None, "node is required to execute preview_adapter.js during audit")
        parameter_id = parameter.get("id")
        if not isinstance(parameter_id, str):
            return (None, None, "manifest parameter id is missing")
        value = parameter.get("value", parameter_value(yaml_data))
        changed_value = perturbed_value(yaml_data, value)
        if changed_value is None:
            return (None, None, "parameter value is not numeric or cannot be perturbed within bounds")
        payload = {
            "adapterCode": self._adapter_path.read_text(encoding="utf-8"),
            "adapterPath": str(self._adapter_path),
            "baseMesh": None if self._base_mesh is False else self._base_mesh,
            "manifest": self.manifest,
            "parameterId": parameter_id,
            "changedValue": changed_value,
        }
        result = subprocess.run(
            [self._node, "-e", ADAPTER_NODE_SCRIPT],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or f"node exited with {result.returncode}"
            return (None, changed_value, detail)
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            return (None, changed_value, f"adapter audit returned invalid JSON: {exc}")
        return (bool(data.get("changed")), changed_value, None)


def has_live_preview_binding(data: Any) -> bool:
    if not isinstance(data, dict):
        return False
    preview = data.get("preview")
    if not isinstance(preview, dict):
        return False
    effect = preview_effect(preview)
    return effect in PREVIEW_EFFECTS and effect != "none"


def report_status(disabled_parameters: list[dict[str, str]], new_candidates: list[dict[str, str]], warnings: list[str]) -> str:
    if disabled_parameters:
        return "fail"
    if new_candidates or warnings:
        return "warn"
    return "pass"


def audit(project: Path, *, mode: str = "basic") -> dict[str, Any]:
    if mode not in {"basic", "strict"}:
        raise RuntimeError("audit mode must be 'basic' or 'strict'")

    project = project.expanduser().resolve()
    parameters_doc = review_validation.load_parameters_doc(project)
    manifest = review_validation.load_manifest_doc(project)
    parameters = parameters_doc.get("parameters")
    if not isinstance(parameters, dict):
        raise RuntimeError("parameters.yaml must contain a parameters mapping")

    disabled_parameters: list[dict[str, str]] = []
    valid_preview_parameters: list[str] = []
    new_candidates: list[dict[str, str]] = []
    warnings: list[str] = []
    checks: list[dict[str, str]] = []

    backend_probe = BackendGeometryProbe(project, parameters_doc)
    preview_probe = PreviewMeshProbe(project, manifest)
    adapter_probe = AdapterPreviewProbe(project, manifest)
    manifest_by_id = manifest_parameter_map(manifest)

    for parameter in manifest_parameters(manifest):
        parameter_id = parameter.get("id")
        if not isinstance(parameter_id, str) or not parameter_id:
            disabled_parameters.append(disabled("<missing>", "manifest parameter is missing a string id"))
            continue
        if parameter_id not in parameters:
            disabled_parameters.append(disabled(parameter_id, "manifest preview parameter no longer exists in parameters.yaml"))
            continue

        data = parameters[parameter_id]
        ui = parameter_ui(data)
        if ui.get("editable") is not True:
            disabled_parameters.append(disabled(parameter_id, "parameter is not explicitly ui.editable: true"))
            continue

        preview = preview_metadata(parameter, data)
        effect = preview_effect(preview)
        if effect not in PREVIEW_EFFECTS:
            disabled_parameters.append(disabled(parameter_id, f"parameter preview.effect is missing or unsupported: {effect!r}"))
            continue
        if effect == "none":
            disabled_parameters.append(disabled(parameter_id, "preview.effect none is not eligible for review manifest exposure"))
            continue
        if numeric(preview.get("factor")) == 0 if isinstance(preview, dict) else False:
            disabled_parameters.append(disabled(parameter_id, "preview metadata uses placeholder factor: 0"))
            continue

        if effect == "adapter":
            try:
                path = adapter_path(project, manifest)
            except RuntimeError as exc:
                disabled_parameters.append(disabled(parameter_id, str(exc)))
                continue
            if path is None:
                disabled_parameters.append(disabled(parameter_id, "preview.effect adapter requires manifest.preview.adapter_js"))
                continue
            if path.suffix.lower() != ".js":
                disabled_parameters.append(disabled(parameter_id, "manifest.preview.adapter_js must point to a JavaScript file"))
                continue

        if mode == "strict":
            validation = parameter_validation(data)
            if validation.get("affects_geometry") is True:
                changed, changed_value, error = backend_probe.changed(parameter_id, data)
                if changed is False:
                    disabled_parameters.append(
                        disabled(
                            parameter_id,
                            (
                                "parameter declares validation.affects_geometry=true but changing "
                                f"from {parameter_value(data)!r} to {changed_value!r} did not change backend geometry"
                            ),
                        )
                    )
                    continue
                if changed is None:
                    disabled_parameters.append(
                        disabled(parameter_id, f"could not verify backend geometry effect: {error}")
                    )
                    continue
                checks.append({"check": f"backend-geometry:{parameter_id}", "status": "pass"})
            elif effect == "adapter":
                changed, changed_value, error = adapter_probe.changed(parameter, data)
                if changed is False:
                    disabled_parameters.append(
                        disabled(
                            parameter_id,
                            (
                                "parameter preview.effect adapter did not change adapter preview mesh "
                                f"when value changed from {parameter.get('value')!r} to {changed_value!r}"
                            ),
                        )
                    )
                    continue
                if changed is None:
                    disabled_parameters.append(disabled(parameter_id, f"could not verify adapter preview effect: {error}"))
                    continue
                checks.append({"check": f"adapter-preview:{parameter_id}", "status": "pass"})
            else:
                changed, changed_value, error = preview_probe.changed(parameter, data)
                if changed is False:
                    disabled_parameters.append(
                        disabled(
                            parameter_id,
                            (
                                "parameter preview metadata did not change review preview mesh "
                                f"when value changed from {parameter.get('value')!r} to {changed_value!r}"
                            ),
                        )
                    )
                    continue
                if changed is None:
                    warnings.append(f"could not verify generic preview mesh effect for {parameter_id}: {error}")
                else:
                    checks.append({"check": f"preview-mesh:{parameter_id}", "status": "pass"})

        valid_preview_parameters.append(parameter_id)

    if mode == "strict":
        for parameter_id, data in parameters.items():
            parameter_id = str(parameter_id)
            if parameter_id in valid_preview_parameters or parameter_id in manifest_by_id:
                continue
            validation = parameter_validation(data)
            if validation.get("affects_geometry") is not True:
                continue
            changed, _changed_value, error = backend_probe.changed(parameter_id, data)
            if changed is True and not has_live_preview_binding(data):
                new_candidates.append(
                    candidate(parameter_id, "affects backend geometry but has no safe preview binding yet")
                )
            elif changed is None and error:
                warnings.append(f"could not evaluate candidate parameter {parameter_id}: {error}")

    status = report_status(disabled_parameters, new_candidates, warnings)
    return {
        "schema": SCHEMA,
        "project": str(project),
        "mode": mode,
        "status": status,
        "valid_preview_parameters": valid_preview_parameters,
        "disabled_parameters": disabled_parameters,
        "new_candidates": new_candidates,
        "warnings": warnings,
        "checks": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_path", help="Model project root")
    parser.add_argument("--mode", choices=["basic", "strict"], default="basic", help="Audit strength")
    args = parser.parse_args()

    try:
        report = audit(Path(args.project_path), mode=args.mode)
    except Exception as exc:
        report = {
            "schema": SCHEMA,
            "project": str(Path(args.project_path).expanduser().resolve()),
            "mode": args.mode,
            "status": "fail",
            "valid_preview_parameters": [],
            "disabled_parameters": [
                {
                    "id": "<audit>",
                    "reason": str(exc),
                    "suggested_action": "fix the model project or rerun with required dependencies available",
                }
            ],
            "new_candidates": [],
            "warnings": [],
            "checks": [],
        }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["status"] in {"pass", "warn"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
