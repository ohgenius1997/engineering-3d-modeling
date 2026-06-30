#!/usr/bin/env python3
"""Summarize an engineering 3D model project for continuation.

The default output is a short human summary. Use --json for machine-readable
output or --write-current-context to refresh validation/current_context.json.
This script intentionally uses only the Python standard library.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any


SCHEMA = "engineering-3d-modeling.current_context.v1"
HIGH_RISK_RE = re.compile(
    r"\b("
    r"hole|holes|slot|slots|cutout|cutouts|port|ports|opening|openings|"
    r"mount|mounts|boss|bosses|standoff|standoffs|thread|threads|"
    r"clearance|clearances|gap|gaps|fit|collision|interference|"
    r"axis|axes|align|alignment|placement|origin|coordinate|direction|"
    r"pcb|battery|connector|motor|bearing|gear|fan|impeller|"
    r"wall[_ -]?thickness|rib|ribs|chamfer|chamfers|fillet|fillets"
    r")\b",
    re.IGNORECASE,
)

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

try:
    import review_validation
except Exception:  # pragma: no cover - summary should degrade if imported standalone
    review_validation = None  # type: ignore[assignment]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def load_json(path: Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return dict(default or {})
    except json.JSONDecodeError as exc:
        return {"_error": f"invalid JSON: {exc}"}
    return data if isinstance(data, dict) else {"_error": "expected JSON object"}


def sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rel(path: Path, project: Path) -> str:
    try:
        return str(path.resolve().relative_to(project.resolve()))
    except ValueError:
        return str(path)


def parse_scalar(value: str) -> Any:
    value = value.strip()
    if value in {"", "null", "~"}:
        return None
    if value in {"true", "false"}:
        return value == "true"
    if (value.startswith("'") and value.endswith("'")) or (value.startswith('"') and value.endswith('"')):
        return value[1:-1]
    try:
        if re.fullmatch(r"[-+]?\d+", value):
            return int(value)
        if re.fullmatch(r"[-+]?\d+\.\d+", value):
            return float(value)
    except ValueError:
        pass
    return value


def yaml_scalar(text: str, path: list[str]) -> Any:
    stack: list[tuple[int, str]] = []
    for raw_line in text.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        match = re.match(r"^(\s*)([A-Za-z0-9_-]+):(?:\s*(.*))?$", raw_line)
        if not match:
            continue
        indent = len(match.group(1))
        key = match.group(2)
        value = match.group(3) or ""
        while stack and stack[-1][0] >= indent:
            stack.pop()
        current = [item[1] for item in stack] + [key]
        if current == path:
            return parse_scalar(value)
        stack.append((indent, key))
    return None


def parameter_summaries(text: str, limit: int = 8) -> list[dict[str, Any]]:
    lines = text.splitlines()
    parameters_indent: int | None = None
    entries: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    current_indent: int | None = None

    for line in lines:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        match = re.match(r"^(\s*)([A-Za-z0-9_.-]+):(?:\s*(.*))?$", line)
        if not match:
            continue
        indent = len(match.group(1))
        key = match.group(2)
        value = match.group(3) or ""
        if parameters_indent is None:
            if indent == 0 and key == "parameters":
                parameters_indent = indent
            continue
        if indent <= parameters_indent and key != "parameters":
            break
        if indent == parameters_indent + 2:
            if current:
                entries.append(current)
            current = {"id": key}
            current_indent = indent
            if value:
                current["value"] = parse_scalar(value)
        elif current is not None and current_indent is not None and indent == current_indent + 2:
            if key in {"value", "unit", "role"}:
                current[key] = parse_scalar(value)
    if current:
        entries.append(current)
    return entries[:limit]


def parameter_details(text: str) -> list[dict[str, Any]]:
    lines = text.splitlines()
    parameters_indent: int | None = None
    entries: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    current_indent: int | None = None
    section: str | None = None

    def finish() -> None:
        if current:
            entries.append(current)

    for line in lines:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        match = re.match(r"^(\s*)([A-Za-z0-9_.-]+):(?:\s*(.*))?$", line)
        if not match:
            continue
        indent = len(match.group(1))
        key = match.group(2)
        value = match.group(3) or ""
        if parameters_indent is None:
            if indent == 0 and key == "parameters":
                parameters_indent = indent
            continue
        if indent <= parameters_indent and key != "parameters":
            break
        if indent == parameters_indent + 2:
            finish()
            current = {"id": key}
            current_indent = indent
            section = None
            if value:
                current["value"] = parse_scalar(value)
        elif current is not None and current_indent is not None and indent == current_indent + 2:
            if key in {"value", "unit", "role"}:
                current[key] = parse_scalar(value)
                section = None
            elif key in {"ui", "validation", "preview"}:
                current[key] = {}
                section = key
            else:
                section = None
        elif (
            current is not None
            and current_indent is not None
            and section is not None
            and indent == current_indent + 4
            and isinstance(current.get(section), dict)
        ):
            current[section][key] = parse_scalar(value)
    finish()
    return entries


def pending_count(project: Path, rel_path: str, key: str) -> int:
    data = load_json(project / rel_path, {key: []})
    values = data.get(key)
    return len(values) if isinstance(values, list) else 0


def review_mesh_summary(project: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    preview = manifest.get("preview") if isinstance(manifest.get("preview"), dict) else {}
    mesh_value = preview.get("mesh_json") if isinstance(preview, dict) else None
    if not isinstance(mesh_value, str) or not mesh_value:
        return {"path": None, "exists": False}
    path = (project / "review" / mesh_value).resolve()
    review_root = (project / "review").resolve()
    if path != review_root and review_root not in path.parents:
        return {"path": mesh_value, "exists": False, "error": "mesh path escapes review/"}
    summary: dict[str, Any] = {"path": rel(path, project), "exists": path.is_file()}
    if path.is_file():
        summary["sha256"] = sha256(path)
        summary["modified_at"] = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat().replace("+00:00", "Z")
        mesh = load_json(path, {})
        provenance = mesh.get("provenance") if isinstance(mesh.get("provenance"), dict) else {}
        if provenance:
            summary["provenance"] = provenance
    return summary


def preview_status(project: Path, review_mesh: dict[str, Any]) -> dict[str, Any]:
    if not review_mesh.get("path"):
        return {"status": "missing", "stale_reasons": []}
    if not review_mesh.get("exists"):
        return {"status": "missing", "stale_reasons": ["declared mesh is missing"]}
    provenance = review_mesh.get("provenance")
    if not isinstance(provenance, dict) or not provenance:
        return {"status": "unknown", "stale_reasons": ["preview mesh provenance missing"]}
    comparisons = {
        "spec_hash": sha256(project / "spec" / "current.yaml"),
        "parameters_hash": sha256(project / "parameters.yaml"),
        "source_hash": sha256(project / "source" / "model.py"),
        "manifest_hash": sha256(project / "review" / "manifest.json"),
    }
    adapter = provenance.get("adapter_path")
    if isinstance(adapter, str) and adapter:
        comparisons["adapter_hash"] = sha256(project / "review" / adapter)
    stale = []
    metadata = []
    for key, current in comparisons.items():
        recorded = provenance.get(key)
        if recorded and current and str(recorded).lower() != str(current).lower():
            if key in {"source_hash", "parameters_hash", "adapter_hash"}:
                stale.append(key)
            else:
                metadata.append(key)
    status = "stale" if stale else "current"
    return {"status": status, "stale_reasons": stale, "metadata_drift": metadata, "provenance": provenance}


def step_summary(project: Path, mesh_hash: str | None) -> dict[str, Any]:
    manifest_path = project / "outputs" / "step" / "manifest.json"
    manifest = load_json(manifest_path, {})
    step_files = sorted((project / "outputs" / "step").glob("*.step")) + sorted((project / "outputs" / "step").glob("*.stp"))
    summary: dict[str, Any] = {
        "manifest": "outputs/step/manifest.json" if manifest_path.is_file() else None,
        "state": manifest.get("state") if isinstance(manifest.get("state"), str) else None,
        "stale": bool(manifest.get("stale")) if manifest else None,
        "stale_reason": manifest.get("stale_reason", "") if manifest else "",
        "files": [{"path": rel(path, project), "sha256": sha256(path)} for path in step_files],
    }
    mismatches = []
    comparisons = {
        "source_hash": sha256(project / "source" / "model.py"),
        "parameters_hash": sha256(project / "parameters.yaml"),
        "spec_hash": sha256(project / "spec" / "current.yaml"),
        "review_mesh_hash": mesh_hash,
    }
    for key, current in comparisons.items():
        recorded = manifest.get(key) if isinstance(manifest, dict) else None
        if recorded and current and str(recorded).lower() != str(current).lower():
            mismatches.append(key)
    if mismatches:
        summary["stale"] = True
        summary["stale_reason"] = "hash mismatch: " + ", ".join(mismatches)
        summary["freshness_mismatches"] = mismatches
    if summary["state"] is None and step_files:
        summary["state"] = "files_without_manifest"
        summary["stale"] = True
    elif summary["state"] is None:
        summary["state"] = "not_exported"
    return summary


def preview_checkpoint_summary(project: Path) -> dict[str, Any]:
    revision = load_json(project / "validation" / "preview_revision.json", {})
    checkpoint = project / "checkpoints" / "preview_previous"
    available = checkpoint.is_dir() and any(path.name != ".gitkeep" for path in checkpoint.rglob("*"))
    return {
        "available": available,
        "path": "checkpoints/preview_previous",
        "created_at": revision.get("created_at"),
        "reason": revision.get("reason"),
    }


def validation_summary(project: Path) -> dict[str, Any]:
    report = load_json(project / "validation" / "report.json", {})
    return {
        "status": report.get("status", "not_run"),
        "errors": report.get("errors", []) if isinstance(report.get("errors", []), list) else [],
        "warnings": report.get("warnings", []) if isinstance(report.get("warnings", []), list) else [],
    }


def coverage_summary(project: Path) -> dict[str, Any]:
    data = load_json(project / "validation" / "spec_coverage.json", {})
    if not data:
        return {"status": "not_run", "feature_gaps": [], "unused_geometry_parameters": []}
    if data.get("_error"):
        return {"status": "unknown", "feature_gaps": [], "unused_geometry_parameters": [], "error": data.get("_error")}
    return {
        "status": data.get("status", "unknown"),
        "feature_gaps": data.get("feature_gaps", []) if isinstance(data.get("feature_gaps", []), list) else [],
        "unused_geometry_parameters": data.get("unused_geometry_parameters", [])
        if isinstance(data.get("unused_geometry_parameters", []), list)
        else [],
        "placement_gaps": data.get("placement_gaps", []) if isinstance(data.get("placement_gaps", []), list) else [],
        "constraint_gaps": data.get("constraint_gaps", []) if isinstance(data.get("constraint_gaps", []), list) else [],
        "validation_target_gaps": data.get("validation_target_gaps", [])
        if isinstance(data.get("validation_target_gaps", []), list)
        else [],
    }


def open_annotations(project: Path) -> list[dict[str, Any]]:
    data = load_json(project / "review" / "annotations.json", {"annotations": []})
    annotations = data.get("annotations")
    if not isinstance(annotations, list):
        return []
    return [
        item
        for item in annotations
        if isinstance(item, dict) and (not item.get("status") or item.get("status") == "open")
    ]


def annotation_clarity_summary(project: Path) -> dict[str, Any]:
    annotations_doc = load_json(project / "review" / "annotations.json", {"annotations": []})
    annotations = annotations_doc.get("annotations")
    if not isinstance(annotations, list) or not annotations:
        return {"status": "clear", "blocking_count": 0, "assumption_count": 0, "high_risk_count": 0, "items": []}
    if review_validation is None:
        return {
            "status": "unknown",
            "blocking_count": 0,
            "assumption_count": 0,
            "high_risk_count": 0,
            "items": [],
            "error": "review_validation unavailable",
        }
    report = review_validation.audit_annotation_clarity(annotations_doc)
    items = report.get("items") if isinstance(report.get("items"), list) else []
    blocking = [item for item in items if isinstance(item, dict) and item.get("status") == "fail"]
    assumptions = [item for item in items if isinstance(item, dict) and item.get("status") == "warn"]
    high_risk = [item for item in items if isinstance(item, dict) and item.get("high_risk")]
    status = "clear"
    if report.get("status") == "fail":
        status = "fail"
    elif report.get("status") == "warn":
        status = "needs_assumption"
    return {
        "status": status,
        "blocking_count": len(blocking),
        "assumption_count": len(assumptions),
        "high_risk_count": len(high_risk),
        "items": items,
    }


def manifest_parameter_map(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    values = manifest.get("parameters")
    if not isinstance(values, list):
        return {}
    return {
        item["id"]: item
        for item in values
        if isinstance(item, dict) and isinstance(item.get("id"), str) and item["id"]
    }


def patch_value_map(project: Path) -> dict[str, Any]:
    data = load_json(project / "review" / "parameter_patch.json", {"patches": []})
    patches = data.get("patches")
    if not isinstance(patches, list):
        return {}
    values: dict[str, Any] = {}
    for item in patches:
        if isinstance(item, dict) and isinstance(item.get("parameter_id"), str):
            values[item["parameter_id"]] = item.get("value")
    return values


def preview_parameter_map(project: Path, review_mesh: dict[str, Any]) -> dict[str, Any]:
    path_value = review_mesh.get("path")
    if not isinstance(path_value, str) or not path_value:
        return {}
    data = load_json(project / path_value, {})
    values = data.get("parameters")
    return values if isinstance(values, dict) else {}


def parameter_state(
    project: Path,
    params_text: str,
    manifest: dict[str, Any],
    review_mesh: dict[str, Any],
    preview: dict[str, Any],
    coverage: dict[str, Any],
) -> list[dict[str, Any]]:
    manifest_params = manifest_parameter_map(manifest)
    patch_values = patch_value_map(project)
    preview_values = preview_parameter_map(project, review_mesh)
    unused = {
        item.get("id")
        for item in coverage.get("unused_geometry_parameters", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    out: list[dict[str, Any]] = []
    for item in parameter_details(params_text):
        parameter_id = item["id"]
        manifest_item = manifest_params.get(parameter_id, {})
        validation = item.get("validation") if isinstance(item.get("validation"), dict) else {}
        ui = item.get("ui") if isinstance(item.get("ui"), dict) else {}
        preview_meta = item.get("preview") if isinstance(item.get("preview"), dict) else {}
        truth_value = item.get("value")
        review_value = manifest_item.get("value") if manifest_item else None
        pending_patch_value = patch_values.get(parameter_id)
        preview_snapshot_value = preview_values.get(parameter_id)
        review_exposed = bool(manifest_item)
        preview_bound = bool(preview_meta) or bool(manifest_item.get("preview") if isinstance(manifest_item, dict) else None)
        affects_geometry = validation.get("affects_geometry") is True
        source_consumed = not (affects_geometry and parameter_id in unused)
        status = "current"
        if parameter_id in patch_values:
            status = "patch_pending"
        elif review_exposed and review_value != truth_value:
            status = "manifest_mismatch"
        elif preview_snapshot_value is not None and preview_snapshot_value != truth_value:
            status = "preview_stale"
        elif preview.get("status") == "stale" and review_exposed:
            status = "preview_stale"
        elif not source_consumed:
            status = "source_unconsumed"
        elif not review_exposed:
            status = "backend_only"
        out.append(
            {
                "id": parameter_id,
                "truth_value": truth_value,
                "review_value": review_value,
                "pending_patch_value": pending_patch_value,
                "preview_snapshot_value": preview_snapshot_value,
                "unit": item.get("unit") or manifest_item.get("unit"),
                "affects_geometry": affects_geometry,
                "source_consumed": source_consumed,
                "review_exposed": review_exposed,
                "preview_bound": preview_bound,
                "editable": ui.get("editable"),
                "status": status,
            }
        )
    return out


def review_state(
    project: Path,
    context: dict[str, Any],
    manifest: dict[str, Any],
    review_mesh: dict[str, Any],
    parameters_state: list[dict[str, Any]],
) -> dict[str, Any]:
    manifest_params = manifest_parameter_map(manifest)
    refs = manifest.get("refs")
    refs_count = len(refs) if isinstance(refs, list) else 0
    stale_panel = [
        item
        for item in parameters_state
        if item.get("review_exposed") and item.get("status") not in {"current", "patch_pending"}
    ]
    preview = context["preview"]
    return {
        "pending_input": {
            "parameter_patches": context["pending_review"]["parameter_patches"],
            "annotations": context["pending_review"]["annotations"],
        },
        "annotation_clarity": annotation_clarity_summary(project),
        "preview": {
            "status": preview.get("status"),
            "provenance": "present" if review_mesh.get("provenance") else "missing",
            "mesh": review_mesh.get("path"),
        },
        "parameter_panel": {
            "status": "current" if not stale_panel else "stale",
            "exposed_count": len(manifest_params),
            "stale_count": len(stale_panel),
        },
        "refs": {"status": "available" if refs_count else "missing", "count": refs_count},
    }


def layout_facts(project: Path) -> dict[str, Any]:
    data = load_json(project / "validation" / "layout_report.json", {})
    if not data:
        return {}
    facts: dict[str, Any] = {}
    for key in ["bbox", "bounding_box", "clearances", "placements", "alignments", "features"]:
        if key in data:
            facts[key] = data[key]
    return facts or {"available_keys": sorted(k for k in data.keys() if not k.startswith("_"))}


def existing_unresolved(project: Path) -> dict[str, list[Any]]:
    current = load_json(project / "validation" / "current_context.json", {})
    unresolved = current.get("unresolved") if isinstance(current.get("unresolved"), dict) else {}
    blockers = unresolved.get("blockers") if isinstance(unresolved.get("blockers"), list) else []
    questions = unresolved.get("questions") if isinstance(unresolved.get("questions"), list) else []
    return {"blockers": blockers, "questions": questions}


def high_risk_terms(values: list[str]) -> list[str]:
    terms: list[str] = []
    for value in values:
        if review_validation is not None and hasattr(review_validation, "high_risk_terms"):
            terms.extend(review_validation.high_risk_terms(value))
            continue
        for match in HIGH_RISK_RE.finditer(value.replace("_", " ")):
            terms.append(match.group(0).lower())
    return sorted(set(terms))


def risk_escalation(project: Path, context: dict[str, Any], parameters_state: list[dict[str, Any]]) -> list[str]:
    reasons: list[str] = []
    annotation_texts = [annotation.get("text", "") for annotation in open_annotations(project)]
    annotation_terms = high_risk_terms([item for item in annotation_texts if isinstance(item, str)])
    if annotation_terms:
        reasons.append("high-risk annotation term(s): " + ", ".join(annotation_terms))
    pending_parameter_ids = [
        str(item.get("id"))
        for item in parameters_state
        if item.get("status") == "patch_pending"
    ]
    parameter_terms = high_risk_terms(pending_parameter_ids)
    if parameter_terms:
        reasons.append("high-risk parameter patch term(s): " + ", ".join(parameter_terms))
    coverage = context.get("coverage", {})
    gap_count = sum(
        len(coverage.get(key, [])) if isinstance(coverage.get(key), list) else 0
        for key in ["feature_gaps", "placement_gaps", "constraint_gaps", "validation_target_gaps"]
    )
    if gap_count:
        reasons.append(f"coverage gap(s): {gap_count}")
    if context.get("preview", {}).get("status") == "stale":
        reasons.append("preview provenance is stale")
    if context.get("validation", {}).get("status") == "fail":
        reasons.append("validation report is failing")
    return reasons


def context_cost_for(next_action: str, context: dict[str, Any], escalation_reasons: list[str]) -> str:
    clarity = context.get("review_state", {}).get("annotation_clarity", {})
    if clarity.get("status") == "fail":
        return "large"
    if any("high-risk annotation" in reason for reason in escalation_reasons):
        return "large"
    if next_action == "inspect" and not escalation_reasons:
        return "tiny"
    if next_action == "apply_parameter_patch" and not escalation_reasons:
        return "small"
    if any("coverage gap" in reason or "validation report" in reason for reason in escalation_reasons):
        return "medium"
    if any("high-risk parameter" in reason for reason in escalation_reasons):
        return "medium"
    return "medium"


def minimum_reads_for(
    next_action: str,
    context: dict[str, Any],
    parameters_state: list[dict[str, Any]] | None = None,
) -> list[str]:
    reads = ["validation/current_context.json"]
    if next_action == "apply_parameter_patch":
        reads.extend(["review/parameter_patch.json", "parameters.yaml", "review/manifest.json"])
    elif next_action in {"clarify_review_annotation", "consume_annotation"}:
        reads.extend(["review/annotations.json", "review/manifest.json"])
        if next_action == "consume_annotation":
            reads.extend(["spec/current.yaml", "parameters.yaml", "source/model.py"])
    elif next_action == "update_review_preview":
        reads.extend(["review/manifest.json", "parameters.yaml", "source/model.py"])
    elif next_action == "fix_validation":
        reads.extend(["validation/report.json", "spec/current.yaml", "parameters.yaml", "source/model.py"])
    elif next_action == "fix_coverage":
        reads.extend(["validation/spec_coverage.json", "spec/current.yaml", "parameters.yaml", "source/model.py"])
    elif next_action == "inspect":
        reads = ["validation/current_context.json"]
    pending = context.get("pending_review", {})
    if pending.get("parameter_patches") and "review/parameter_patch.json" not in reads:
        reads.extend(["review/parameter_patch.json", "parameters.yaml"])
    if next_action == "apply_parameter_patch" and parameters_state:
        pending_parameter_ids = [
            str(item.get("id"))
            for item in parameters_state
            if item.get("status") == "patch_pending"
        ]
        if high_risk_terms(pending_parameter_ids):
            reads.extend(["spec/current.yaml", "source/model.py", "validation/spec_coverage.json"])
    if context.get("step", {}).get("stale") and next_action not in {"inspect", "apply_parameter_patch", "clarify_review_annotation"}:
        reads.append("outputs/step/manifest.json")
    return list(dict.fromkeys(reads))


def gate_plan_for(next_action: str, context: dict[str, Any], escalation_reasons: list[str] | None = None) -> dict[str, Any]:
    required_by_action = {
        "inspect": ["update_current_context"],
        "apply_parameter_patch": [
            "apply_parameter_patch",
            "source_build_smoke",
            "review_parameter_audit",
            "update_current_context",
        ],
        "clarify_review_annotation": ["review_clarity"],
        "consume_annotation": ["review_clarity", "source_build_smoke", "coverage_audit", "update_current_context"],
        "update_review_preview": [
            "preview_checkpoint",
            "source_build_smoke",
            "sync_review_parameters",
            "review_parameter_audit",
            "update_current_context",
        ],
        "fix_validation": ["rerun_failing_validation", "update_current_context"],
        "fix_coverage": ["coverage_audit", "update_current_context"],
    }
    required = list(required_by_action.get(next_action, ["update_current_context"]))
    optional: list[str] = []
    skipped = [
        {
            "gate": "step_export",
            "reason": "draft review iteration; user did not request STEP",
        },
        {
            "gate": "handoff_package",
            "reason": "handoff package was not requested",
        },
    ]
    if context.get("coverage", {}).get("status") == "not_run" and "coverage_audit" not in required:
        optional.append("coverage_audit")
    if escalation_reasons and any("high-risk parameter" in reason for reason in escalation_reasons):
        if "coverage_audit" not in required:
            required.append("coverage_audit")
    if context.get("step", {}).get("state") == "not_exported":
        optional.append("export_step_after_preview_confirmation")
    return {"for_next_action": next_action, "required": required, "optional": optional, "skipped": skipped}


def routing_summary(project: Path, context: dict[str, Any], parameters_state: list[dict[str, Any]]) -> dict[str, Any]:
    tags = ["continue_existing_project"]
    pending = context["pending_review"]
    clarity = context.get("review_state", {}).get("annotation_clarity", {})
    next_action = "inspect"
    if pending["annotations"]:
        tags.append("consume_review_feedback")
        next_action = "clarify_review_annotation" if clarity.get("status") == "fail" else "consume_annotation"
    elif pending["parameter_patches"]:
        tags.append("consume_review_feedback")
        next_action = "apply_parameter_patch"
    elif context["validation"].get("status") == "fail":
        next_action = "fix_validation"
    elif context["coverage"].get("status") == "fail":
        next_action = "fix_coverage"
    elif context["coverage"].get("status") == "warn":
        next_action = "fix_coverage"
    elif context["preview"].get("status") in {"stale", "missing", "unknown"}:
        next_action = "update_review_preview"
    if context["coverage"].get("status") in {"warn", "fail", "not_run"}:
        tags.append("spec_coverage_audit")
    if context["preview"].get("status") in {"stale", "missing", "unknown"}:
        tags.append("update_review_preview")
    if context["validation"].get("status") == "fail":
        tags.append("validation_failure")
    if next_action in {"consume_annotation", "fix_coverage"}:
        tags.append("geometry_feature_change")
    escalation_reasons = risk_escalation(project, context, parameters_state)
    context_cost = context_cost_for(next_action, context, escalation_reasons)
    minimum_reads = minimum_reads_for(next_action, context, parameters_state)
    forbidden_actions = []
    if pending["annotations"] or pending["parameter_patches"]:
        forbidden_actions.extend(["export_step", "handoff_package"])
    else:
        forbidden_actions.append("handoff_package")
    return {
        "next_action": next_action,
        "intent": "continue_existing_project",
        "context_cost": context_cost,
        "recommended_tags": list(dict.fromkeys(tags)),
        "minimum_reads": minimum_reads,
        "minimum_next_reads": minimum_reads,
        "optional_reads": [],
        "required_gates": gate_plan_for(next_action, context, escalation_reasons)["required"],
        "forbidden_actions": forbidden_actions,
        "escalation_reasons": escalation_reasons,
    }


def blockers(context: dict[str, Any]) -> list[str]:
    out: list[str] = []
    pending = context["pending_review"]
    if pending["annotations"]:
        out.append("review/annotations.json contains pending annotations")
    if pending["parameter_patches"]:
        out.append("review/parameter_patch.json contains pending parameter patches")
    if context["validation"].get("status") == "fail":
        out.append("validation/report.json status is fail")
    if context["coverage"].get("status") == "fail":
        out.append("validation/spec_coverage.json status is fail")
    clarity = context.get("review_state", {}).get("annotation_clarity", {})
    if clarity.get("status") == "fail":
        out.append("high-risk review annotations need clarification before modeling")
    return out


def trust_summary(context: dict[str, Any], parameters_state: list[dict[str, Any]]) -> dict[str, str]:
    parameter_statuses = {str(item.get("status")) for item in parameters_state}
    if "patch_pending" in parameter_statuses:
        parameters = "patch_pending"
    elif parameter_statuses & {"manifest_mismatch", "preview_stale", "source_unconsumed"}:
        parameters = "stale_or_unverified"
    else:
        parameters = "current"
    step = context["step"].get("state") or "not_exported"
    if context["step"].get("stale"):
        step = "stale"
    return {
        "authoring_truth": "current" if context["validation"].get("status") != "fail" else "needs_repair",
        "review_preview": str(context["preview"].get("status", "unknown")),
        "parameters": parameters,
        "step": str(step),
        "handoff": "not_requested",
    }


def ready_states(project: Path, context: dict[str, Any], phase: str, manifest: dict[str, Any]) -> dict[str, bool]:
    has_authoring = bool((project / "spec" / "current.yaml").is_file()) and bool((project / "parameters.yaml").is_file())
    has_source = bool((project / "source" / "model.py").is_file())
    has_review = not manifest.get("_error") and bool((project / "review" / "manifest.json").is_file())
    authoring_ready = (
        phase == "draft_review"
        and has_authoring
        and has_source
        and has_review
        and context["validation"].get("status") != "fail"
    )
    review_preview_ready = context["preview"].get("status") == "current"
    draft_review_ready = authoring_ready and review_preview_ready
    export_ready = context["step"].get("state") == "exported" and context["step"].get("stale") is False
    return {
        "authoring_ready": bool(authoring_ready),
        "review_preview_ready": bool(review_preview_ready),
        "draft_review_ready": bool(draft_review_ready),
        "export_ready": bool(export_ready),
        "handoff_ready": False,
    }


def summarize(project: Path) -> dict[str, Any]:
    project = project.expanduser().resolve()
    spec_text = read_text(project / "spec" / "current.yaml")
    params_text = read_text(project / "parameters.yaml")
    manifest = load_json(project / "review" / "manifest.json", {})
    project_info = manifest.get("project") if isinstance(manifest.get("project"), dict) else {}
    name = yaml_scalar(spec_text, ["project", "name"]) or project_info.get("name") or project.name
    kind = yaml_scalar(spec_text, ["project", "kind"]) or project_info.get("kind")
    units = yaml_scalar(spec_text, ["project", "units"]) or project_info.get("units")
    phase = yaml_scalar(spec_text, ["lifecycle", "phase"]) or "draft_review"
    source_entrypoint = yaml_scalar(spec_text, ["source", "entrypoint"]) or "source/model.py"
    review_mesh = review_mesh_summary(project, manifest)
    preview = preview_status(project, review_mesh)
    coverage = coverage_summary(project)
    context = {
        "schema": SCHEMA,
        "generated_at": utc_now(),
        "project": {"name": name, "kind": kind, "units": units},
        "work_state": {"phase": phase},
        "source": {"entrypoint": source_entrypoint},
        "pending_review": {
            "annotations": pending_count(project, "review/annotations.json", "annotations"),
            "parameter_patches": pending_count(project, "review/parameter_patch.json", "patches"),
        },
        "review": {"mesh": review_mesh},
        "step": step_summary(project, review_mesh.get("sha256") if isinstance(review_mesh.get("sha256"), str) else None),
        "preview": preview,
        "preview_checkpoint": preview_checkpoint_summary(project),
        "validation": validation_summary(project),
        "coverage": coverage,
        "key_parameters": parameter_summaries(params_text),
        "layout_facts": layout_facts(project),
        "unresolved": existing_unresolved(project),
    }
    context["step"]["export_allowed"] = not (
        context["pending_review"]["annotations"] or context["pending_review"]["parameter_patches"]
    )
    context["parameter_state"] = parameter_state(project, params_text, manifest, review_mesh, preview, coverage)
    context["review_state"] = review_state(project, context, manifest, review_mesh, context["parameter_state"])
    context["trust"] = trust_summary(context, context["parameter_state"])
    context["ready_states"] = ready_states(project, context, str(phase), manifest)
    context["routing"] = routing_summary(project, context, context["parameter_state"])
    context["gate_plan"] = gate_plan_for(
        context["routing"]["next_action"],
        context,
        context["routing"].get("escalation_reasons", []),
    )
    context["routing"]["required_gates"] = context["gate_plan"]["required"]
    context["blockers"] = blockers(context)
    previous = load_json(project / "validation" / "current_context.json", {})
    context["assumptions"] = previous.get("assumptions", []) if isinstance(previous.get("assumptions", []), list) else []
    context["input_precision"] = previous.get("input_precision", {}) if isinstance(previous.get("input_precision"), dict) else {}
    context["recommended_next_reads"] = context["routing"]["minimum_reads"]
    return context


def write_current_context(project: Path) -> dict[str, Any]:
    context = summarize(project)
    path = project.expanduser().resolve() / "validation" / "current_context.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(context, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return context


def human_summary(context: dict[str, Any]) -> str:
    project = context["project"]
    pending = context["pending_review"]
    step = context["step"]
    validation = context["validation"]
    mesh = context["review"]["mesh"]
    lines = [
        f"Project: {project.get('name')} ({project.get('kind')}, {project.get('units')})",
        f"Source: {context['source'].get('entrypoint')}",
        f"Pending review: {pending.get('annotations', 0)} annotation(s), {pending.get('parameter_patches', 0)} parameter patch(es)",
        f"Review mesh: {mesh.get('path') or 'none'}",
        f"Preview: status={context.get('preview', {}).get('status')}",
        f"STEP: state={step.get('state') or 'none'}, stale={step.get('stale')}, files={len(step.get('files', []))}",
        f"Coverage: {context.get('coverage', {}).get('status')}",
        f"Preview checkpoint: {'available' if context['preview_checkpoint'].get('available') else 'missing'}",
        f"Validation: {validation.get('status')} ({len(validation.get('errors', []))} error(s), {len(validation.get('warnings', []))} warning(s))",
    ]
    if context.get("key_parameters"):
        params = ", ".join(
            f"{item.get('id')}={item.get('value')}{(' ' + item.get('unit')) if item.get('unit') else ''}"
            for item in context["key_parameters"]
        )
        lines.append(f"Key parameters: {params}")
    unresolved = context.get("unresolved", {})
    blockers = unresolved.get("blockers", [])
    questions = unresolved.get("questions", [])
    if blockers or questions:
        lines.append(f"Unresolved: {len(blockers)} blocker(s), {len(questions)} question(s)")
    routing = context.get("routing", {})
    if isinstance(routing, dict) and routing.get("recommended_tags"):
        lines.append("Recommended tags: " + ", ".join(routing.get("recommended_tags", [])))
    lines.append("Recommended next reads: " + ", ".join(context.get("recommended_next_reads", [])))
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_path", help="Model project root")
    parser.add_argument("--json", action="store_true", help="Print machine-readable current-context JSON")
    parser.add_argument(
        "--write-current-context",
        action="store_true",
        help="Write validation/current_context.json in addition to printing output",
    )
    args = parser.parse_args()

    project = Path(args.project_path)
    context = write_current_context(project) if args.write_current_context else summarize(project)
    if args.json:
        print(json.dumps(context, indent=2, ensure_ascii=False))
    else:
        print(human_summary(context))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
