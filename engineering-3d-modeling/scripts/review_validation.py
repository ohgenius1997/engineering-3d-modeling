#!/usr/bin/env python3
"""Shared validation helpers for review JSON and parameter patches."""

from __future__ import annotations

import json
import math
from pathlib import Path
import re
from typing import Any


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = SKILL_ROOT / "assets" / "review-template"

SCHEMA_FILES = {
    "manifest": "manifest.schema.json",
    "annotations": "annotations.schema.json",
    "parameter_patch": "parameter_patch.schema.json",
}

CLARITY_FIELDS = ["target", "operation", "reference", "direction", "dimensions", "scope", "preserve", "validation"]
OPERATION_RE = re.compile(r"\b(add|remove|move|resize|cut|fillet|chamfer|align|offset|avoid|preserve|keep|change|adjust|increase|decrease|widen|narrow|raise|lower)\b", re.IGNORECASE)
DIRECTION_RE = re.compile(r"\b(x|y|z|normal|radial|axial|inward|outward|left|right|up|down|toward|away|clockwise|counterclockwise)\b", re.IGNORECASE)
DIMENSION_RE = re.compile(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)\s*(?:mm|cm|m|in|inch|deg|degree|degrees)?", re.IGNORECASE)
SCOPE_RE = re.compile(r"\b(selected|this|that|all|each|every|part|whole|global|same|both)\b", re.IGNORECASE)
PRESERVE_RE = re.compile(r"\b(preserve|keep|do not|don't|without changing|leave|maintain)\b", re.IGNORECASE)
VALIDATION_RE = re.compile(r"\b(validate|check|fit|clearance|collision|align|measure|verify|test)\b", re.IGNORECASE)
REFERENCE_RE = re.compile(r"\b(edge|face|axis|ref|reference|from|to|against|with|hole|slot|mount|component|part)\b", re.IGNORECASE)
HIGH_RISK_TERMS = {
    "axis",
    "battery",
    "bearing",
    "boss",
    "chamfer",
    "clearance",
    "collision",
    "connector",
    "coordinate",
    "cutout",
    "direction",
    "fillet",
    "fit",
    "gap",
    "gear",
    "hole",
    "impeller",
    "interference",
    "mount",
    "opening",
    "origin",
    "pcb",
    "placement",
    "port",
    "rib",
    "screw",
    "slot",
    "standoff",
    "thread",
    "wall",
    "wallthickness",
}
HIGH_RISK_PREFIXES = ("align", "manufactur")
HIGH_RISK_CN_TERMS = [
    "孔",
    "螺纹",
    "螺丝",
    "螺钉",
    "螺栓",
    "电池",
    "间隙",
    "缝隙",
    "配合",
    "卡扣",
    "槽",
    "开孔",
    "切口",
    "安装",
    "固定",
    "对齐",
    "轴",
    "坐标",
    "方向",
    "碰撞",
    "干涉",
    "装配",
    "连接器",
    "电机",
    "轴承",
    "齿轮",
    "风扇",
    "叶轮",
    "壁厚",
    "筋",
    "倒角",
    "圆角",
]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_schema(name: str) -> dict[str, Any]:
    try:
        filename = SCHEMA_FILES[name]
    except KeyError as exc:
        raise RuntimeError(f"unknown schema: {name}") from exc
    data = load_json(SCHEMA_DIR / filename)
    if not isinstance(data, dict):
        raise RuntimeError(f"schema {name} must be a JSON object")
    return data


def json_type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def matches_type(value: Any, expected: str) -> bool:
    if expected == "null":
        return value is None
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))
    if expected == "string":
        return isinstance(value, str)
    if expected == "array":
        return isinstance(value, list)
    if expected == "object":
        return isinstance(value, dict)
    return True


def resolve_ref(schema: dict[str, Any], ref: str) -> dict[str, Any]:
    prefix = "#/$defs/"
    if not ref.startswith(prefix):
        raise RuntimeError(f"unsupported schema ref: {ref}")
    name = ref[len(prefix) :]
    defs = schema.get("$defs")
    if not isinstance(defs, dict) or not isinstance(defs.get(name), dict):
        raise RuntimeError(f"schema ref not found: {ref}")
    return defs[name]


def validate_json_schema(data: Any, schema: dict[str, Any], *, root_schema: dict[str, Any] | None = None, path: str = "$") -> list[str]:
    """Validate the schema keywords used by the bundled review schemas."""

    root = root_schema or schema
    if "$ref" in schema:
        return validate_json_schema(data, resolve_ref(root, str(schema["$ref"])), root_schema=root, path=path)

    if "oneOf" in schema:
        variants = schema["oneOf"]
        if not isinstance(variants, list):
            return [f"{path}: oneOf must be a list in schema"]
        matching = [variant for variant in variants if not validate_json_schema(data, variant, root_schema=root, path=path)]
        if len(matching) != 1:
            return [f"{path}: expected exactly one matching schema, found {len(matching)}"]
        return []

    errors: list[str] = []
    expected_type = schema.get("type")
    if expected_type is not None:
        expected = expected_type if isinstance(expected_type, list) else [expected_type]
        if not any(isinstance(item, str) and matches_type(data, item) for item in expected):
            errors.append(f"{path}: expected type {'/'.join(map(str, expected))}, got {json_type_name(data)}")
            return errors

    if "const" in schema and data != schema["const"]:
        errors.append(f"{path}: expected const {schema['const']!r}, got {data!r}")
    if "enum" in schema and data not in schema["enum"]:
        errors.append(f"{path}: expected one of {schema['enum']!r}, got {data!r}")

    if isinstance(data, dict):
        required = schema.get("required", [])
        if isinstance(required, list):
            for key in required:
                if isinstance(key, str) and key not in data:
                    errors.append(f"{path}: missing required property {key!r}")
        properties = schema.get("properties", {})
        if isinstance(properties, dict):
            for key, property_schema in properties.items():
                if key in data and isinstance(property_schema, dict):
                    errors.extend(validate_json_schema(data[key], property_schema, root_schema=root, path=f"{path}.{key}"))

    if isinstance(data, list):
        min_items = schema.get("minItems")
        max_items = schema.get("maxItems")
        if isinstance(min_items, int) and len(data) < min_items:
            errors.append(f"{path}: expected at least {min_items} items, got {len(data)}")
        if isinstance(max_items, int) and len(data) > max_items:
            errors.append(f"{path}: expected at most {max_items} items, got {len(data)}")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(data):
                errors.extend(validate_json_schema(item, item_schema, root_schema=root, path=f"{path}[{index}]"))

    return errors


def validate_manifest_schema(data: Any) -> list[str]:
    return validate_json_schema(data, load_schema("manifest"))


def validate_annotations_schema(data: Any) -> list[str]:
    return validate_json_schema(data, load_schema("annotations"))


def validate_parameter_patch_schema(data: Any) -> list[str]:
    return validate_json_schema(data, load_schema("parameter_patch"))


def identifier_tokens(value: str) -> list[str]:
    normalized = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", value)
    normalized = re.sub(r"[^0-9A-Za-z]+", " ", normalized)
    return [item.lower() for item in normalized.split() if item]


def high_risk_terms(value: str) -> list[str]:
    terms = set()
    for token in identifier_tokens(value):
        compact = token.replace("_", "")
        if token in HIGH_RISK_TERMS or compact in HIGH_RISK_TERMS:
            terms.add(token)
        elif any(token.startswith(prefix) for prefix in HIGH_RISK_PREFIXES):
            terms.add(token)
    for term in HIGH_RISK_CN_TERMS:
        if term in value:
            terms.add(term)
    return sorted(terms)


def is_high_risk_text(value: str) -> bool:
    return bool(high_risk_terms(value))


def annotation_text(annotation: dict[str, Any]) -> str:
    value = annotation.get("text")
    return value if isinstance(value, str) else ""


def annotation_missing_clarity(annotation: dict[str, Any]) -> list[str]:
    text = annotation_text(annotation)
    target = annotation.get("target")
    missing = []
    if not isinstance(target, dict):
        missing.append("target")
    if not OPERATION_RE.search(text):
        missing.append("operation")
    if not (isinstance(target, dict) and target.get("ref")) and not REFERENCE_RE.search(text):
        missing.append("reference")
    if not (isinstance(target, dict) and target.get("normal")) and not DIRECTION_RE.search(text):
        missing.append("direction")
    if not DIMENSION_RE.search(text):
        missing.append("dimensions")
    if not SCOPE_RE.search(text):
        missing.append("scope")
    if not PRESERVE_RE.search(text):
        missing.append("preserve")
    if not VALIDATION_RE.search(text):
        missing.append("validation")
    return missing


def audit_annotation_clarity(annotations_doc: dict[str, Any]) -> dict[str, Any]:
    report: dict[str, Any] = {
        "schema": "engineering-3d-modeling.annotation_clarity_audit.v1",
        "status": "pass",
        "items": [],
        "warnings": [],
        "errors": [],
    }
    annotations = annotations_doc.get("annotations")
    if not isinstance(annotations, list):
        report["status"] = "fail"
        report["errors"].append("review/annotations.json annotations must be a list")
        return report
    for index, annotation in enumerate(annotations):
        if not isinstance(annotation, dict):
            continue
        if annotation.get("status") and annotation.get("status") != "open":
            continue
        missing = annotation_missing_clarity(annotation)
        text = annotation_text(annotation)
        risk_terms = high_risk_terms(text)
        high_risk = bool(risk_terms)
        item = {
            "id": annotation.get("id", index),
            "status": "fail" if high_risk and missing else ("warn" if missing else "pass"),
            "high_risk": high_risk,
            "risk_terms": risk_terms,
            "missing": missing,
        }
        report["items"].append(item)
        if item["status"] == "fail":
            report["errors"].append(
                f"annotation {item['id']} is high-risk and unclear: missing {', '.join(missing)}"
            )
        elif item["status"] == "warn":
            report["warnings"].append(f"annotation {item['id']} has low-risk clarity gaps: {', '.join(missing)}")
    if report["errors"]:
        report["status"] = "fail"
    elif report["warnings"]:
        report["status"] = "warn"
    return report


def load_yaml():
    try:
        import yaml  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "PyYAML is required for parameter validation. "
            "Run scripts/check_environment.py --install with the same Python runtime."
        ) from exc
    return yaml


def load_parameters_doc(project: Path) -> dict[str, Any]:
    yaml = load_yaml()
    path = project / "parameters.yaml"
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"missing parameters.yaml: {path}") from exc
    if not isinstance(data, dict):
        raise RuntimeError("parameters.yaml must contain a YAML object")
    if not isinstance(data.get("parameters"), dict):
        raise RuntimeError("parameters.yaml must contain a 'parameters' mapping")
    return data


def load_manifest_doc(project: Path) -> dict[str, Any]:
    path = project / "review" / "manifest.json"
    try:
        data = load_json(path)
    except FileNotFoundError as exc:
        raise RuntimeError(f"missing review/manifest.json: {path}") from exc
    if not isinstance(data, dict):
        raise RuntimeError("review/manifest.json must contain a JSON object")
    return data


def numeric(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return float(value)
    return None


def parameter_value(data: Any) -> Any:
    if isinstance(data, dict):
        return data.get("value")
    return data


def parameter_ui(data: Any) -> dict[str, Any]:
    if isinstance(data, dict) and isinstance(data.get("ui"), dict):
        return data["ui"]
    return {}


def parameter_meta_number(data: Any, key: str) -> float | None:
    ui = parameter_ui(data)
    if key in ui:
        value = numeric(ui.get(key))
        if value is not None:
            return value
    if isinstance(data, dict):
        return numeric(data.get(key))
    return None


def value_type_label(value: Any) -> str:
    if isinstance(value, bool):
        return "boolean"
    if numeric(value) is not None:
        return "number"
    if isinstance(value, str):
        return "string"
    return "unsupported"


def validate_value_type(parameter_id: str, old_value: Any, new_value: Any) -> list[str]:
    old_type = value_type_label(old_value)
    new_type = value_type_label(new_value)
    if old_type == "unsupported":
        return [f"parameter {parameter_id} has unsupported current value type: {type(old_value).__name__}"]
    if old_type != new_type:
        return [f"patch for {parameter_id} value type {new_type} does not match parameter type {old_type}"]
    return []


def validate_step(parameter_id: str, value: float, target: Any) -> list[str]:
    step = parameter_meta_number(target, "step")
    if step is None or step <= 0:
        return []
    anchor = parameter_meta_number(target, "min")
    if anchor is None:
        current = numeric(parameter_value(target))
        anchor = current if current is not None else 0.0
    ratio = (value - anchor) / step
    if abs(ratio - round(ratio)) > 1e-6:
        return [f"patch for {parameter_id} value {value} does not align to step {step} from anchor {anchor}"]
    return []


def validate_patch_against_project(
    project: Path,
    patch_doc: dict[str, Any],
    *,
    parameters_doc: dict[str, Any] | None = None,
    manifest: dict[str, Any] | None = None,
    require_manifest_parameter: bool = True,
) -> list[str]:
    errors = validate_parameter_patch_schema(patch_doc)
    if errors:
        return errors

    project = project.expanduser().resolve()
    parameters_doc = parameters_doc or load_parameters_doc(project)
    manifest = manifest or load_manifest_doc(project)

    parameters = parameters_doc.get("parameters")
    if not isinstance(parameters, dict):
        return ["parameters.yaml must contain a 'parameters' mapping"]
    manifest_parameters = manifest.get("parameters")
    if not isinstance(manifest_parameters, list):
        return ["review/manifest.json parameters must be a list"]
    declared = {
        param.get("id"): param
        for param in manifest_parameters
        if isinstance(param, dict) and isinstance(param.get("id"), str)
    }

    patches = patch_doc.get("patches")
    if not isinstance(patches, list):
        return ["review/parameter_patch.json patches must be a list"]

    for index, patch in enumerate(patches):
        if not isinstance(patch, dict):
            errors.append(f"patch {index} must be an object")
            continue
        parameter_id = patch.get("parameter_id")
        if not isinstance(parameter_id, str) or not parameter_id:
            errors.append(f"patch {index} missing parameter_id")
            continue
        if parameter_id not in parameters:
            errors.append(f"patch references unknown parameter: {parameter_id}")
            continue
        if require_manifest_parameter and parameter_id not in declared:
            errors.append(f"patch references parameter not exposed in review manifest: {parameter_id}")
            continue
        target = parameters[parameter_id]
        ui = parameter_ui(target)
        if ui.get("editable") is False:
            errors.append(f"patch references non-editable parameter: {parameter_id}")
        if "value" not in patch:
            errors.append(f"patch for {parameter_id} missing value")
            continue

        old_value = parameter_value(target)
        new_value = patch["value"]
        errors.extend(validate_value_type(parameter_id, old_value, new_value))
        new_number = numeric(new_value)
        if new_number is not None:
            minimum = parameter_meta_number(target, "min")
            maximum = parameter_meta_number(target, "max")
            if minimum is not None and new_number < minimum:
                errors.append(f"patch for {parameter_id} value {new_number} is below min {minimum}")
            if maximum is not None and new_number > maximum:
                errors.append(f"patch for {parameter_id} value {new_number} is above max {maximum}")
            errors.extend(validate_step(parameter_id, new_number, target))

        if isinstance(target, dict) and target.get("unit") is not None and patch.get("unit") is not None:
            if patch.get("unit") != target.get("unit"):
                errors.append(f"patch for {parameter_id} unit {patch.get('unit')!r} does not match {target.get('unit')!r}")

    return errors
