#!/usr/bin/env python3
"""Export a fresh STEP file directly from the current authoring truth."""

from __future__ import annotations

import argparse
import inspect
import json
from pathlib import Path
import sys
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import audit_project_consistency
import audit_spec_coverage
import iteration_utils
import summarize_model_project
import validate_model_project


SCHEMA = "engineering-3d-modeling.export_step_result.v1"


def step_readability(project: Path) -> list[dict[str, Any]]:
    records = []
    for path in iteration_utils.step_files(project):
        text = path.read_text(encoding="utf-8", errors="ignore")[:256]
        records.append(
            {
                "path": iteration_utils.safe_relative(path, project),
                "sha256": iteration_utils.file_sha256(path),
                "bytes": path.stat().st_size,
                "readable": path.stat().st_size > 0,
                "looks_like_step": "ISO-10303-21" in text or "HEADER" in text,
            }
        )
    return records


def geometry_summary(project: Path) -> dict[str, Any]:
    source = project / "source" / "model.py"
    parameters = project / "parameters.yaml"
    try:
        module = validate_model_project.load_model_module(source)
        signature = validate_model_project.build_signature_with_parameters(module, parameters)
    except Exception as exc:
        return {"status": "warn", "message": f"basic BRep/bbox check unavailable: {exc}"}
    return {
        "status": "pass",
        "signature": signature,
        "bbox_min": signature[0],
        "bbox_max": signature[1],
        "bbox_size": signature[2],
        "volume": signature[3],
        "area": signature[4],
    }


def assembly_step_path(project: Path, spec: dict[str, Any] | None) -> Path:
    if isinstance(spec, dict):
        outputs = spec.get("outputs")
        if isinstance(outputs, dict):
            value = outputs.get("assembly_step")
            if isinstance(value, str) and value.strip():
                path = Path(value)
                return path if path.is_absolute() else project / path
    return project / "outputs" / "step" / f"{project.name}.step"


def export_model_step(model: object, path: Path, model_module: object) -> None:
    write_step = getattr(model_module, "write_step", None)
    if callable(write_step):
        signature = inspect.signature(write_step)
        if len(signature.parameters) >= 2:
            write_step(model, path)
        else:
            write_step(model)
        return

    try:
        from build123d import export_step as build123d_export_step
    except ImportError as exc:
        raise RuntimeError(
            "build123d is required to export STEP when source/model.py does not define write_step(model, path)"
        ) from exc
    path.parent.mkdir(parents=True, exist_ok=True)
    build123d_export_step(model, str(path))


def build_and_export_step(project: Path, source_path: Path, output_path: Path) -> dict[str, Any]:
    model_module = validate_model_project.load_model_module(source_path)
    load_parameters = getattr(model_module, "load_parameters", None)
    build_model = getattr(model_module, "build_model", None)
    if not callable(load_parameters):
        raise RuntimeError("source/model.py must define callable load_parameters(path)")
    if not callable(build_model):
        raise RuntimeError("source/model.py must define callable build_model(params)")
    params = load_parameters(project / "parameters.yaml")
    model = build_model(params)
    export_model_step(model, output_path, model_module)
    return {
        "source": iteration_utils.safe_relative(source_path, project),
        "output": iteration_utils.safe_relative(output_path, project),
        "model_type": type(model).__name__,
    }


def pending_review(project: Path) -> dict[str, int]:
    return {
        "parameter_patch_count": iteration_utils.pending_patch_count(project),
        "annotation_count": iteration_utils.pending_annotation_count(project),
    }


def write_manifest(project: Path, *, generated_by: str, validation_summary: dict[str, Any]) -> dict[str, Any]:
    phase, _, _ = iteration_utils.current_phase(project)
    manifest = iteration_utils.write_step_manifest(
        project,
        state="exported",
        generated_for_phase=phase,
        generated_by=generated_by,
        promoted_by=None,
        stale=False,
        stale_reason="",
    )
    manifest["export_kind"] = "direct_step"
    manifest["script_version"] = "export_step.v1"
    manifest["validation_summary"] = validation_summary
    iteration_utils.write_json_doc(project / iteration_utils.STEP_MANIFEST_REL, manifest)
    return manifest


def export_step(
    project: Path,
    *,
    python_executable: str = sys.executable,
    skip_validation: bool = False,
    geometry_smoke: bool = False,
) -> dict[str, Any]:
    project = project.expanduser().resolve()
    report: dict[str, Any] = {
        "schema": SCHEMA,
        "project": str(project),
        "status": "fail",
        "steps": [],
        "warnings": [],
        "errors": [],
        "written": [],
    }

    pending = pending_review(project)
    report["steps"].append({"step": "pending-review", "status": "pass" if not any(pending.values()) else "fail", **pending})
    if pending["parameter_patch_count"] or pending["annotation_count"]:
        report["errors"].append(
            "cannot export STEP while review/parameter_patch.json or review/annotations.json contains unconsumed review data; consume it with regenerate_from_review.py or clear it after converting it into authoring truth"
        )
        return report

    spec = iteration_utils.load_yaml_doc(project / "spec" / "current.yaml")
    coverage = audit_spec_coverage.audit(project, write=True)
    report["steps"].append(
        {
            "step": "spec-coverage-audit",
            "status": coverage["status"],
            "feature_gap_count": len(coverage.get("feature_gaps", [])),
            "unused_geometry_parameter_count": len(coverage.get("unused_geometry_parameters", [])),
        }
    )
    report["written"].append("validation/spec_coverage.json")
    if coverage["status"] == "fail":
        report["errors"].extend(f"spec coverage: {item}" for item in coverage.get("errors", []))
        return report
    if coverage["status"] == "warn":
        report["warnings"].extend(f"spec coverage: {item}" for item in coverage.get("warnings", []))

    source_path = validate_model_project.source_path_from_spec(project, spec)
    if source_path is None or not source_path.is_file():
        report["errors"].append("source/model.py is missing; cannot regenerate STEP")
        report["steps"].append({"step": "source", "status": "fail", "source": str(source_path) if source_path else None})
        return report

    output_path = assembly_step_path(project, spec)
    if python_executable != sys.executable:
        report["warnings"].append(
            "--python is retained for compatibility; export_step.py now imports source/model.py in the current interpreter. "
            "Run this script with the desired Python executable instead."
        )
    try:
        build_export = build_and_export_step(project, source_path, output_path)
    except Exception as exc:
        report["errors"].append(f"current authoring source could not export STEP: {exc}")
        report["steps"].append(
            {
                "step": "build-and-export-step",
                "status": "fail",
                "source": iteration_utils.safe_relative(source_path, project),
                "output": iteration_utils.safe_relative(output_path, project),
                "message": str(exc),
            }
        )
        return report

    step_files = iteration_utils.step_files(project)
    build_status = "pass" if step_files else "fail"
    report["steps"].append(
        {
            "step": "build-and-export-step",
            "status": build_status,
            "source": build_export["source"],
            "output": build_export["output"],
            "model_type": build_export["model_type"],
            "step_files": [iteration_utils.safe_relative(path, project) for path in step_files],
        }
    )
    if build_status != "pass":
        report["errors"].append("current authoring source did not produce STEP/STP under outputs/step")
        return report
    if iteration_utils.update_review_manifest_current(project, source_path=source_path, step_path=output_path):
        report["written"].append("review/manifest.json")
        report["steps"].append(
            {
                "step": "update-review-manifest-step",
                "status": "pass",
                "step_path": iteration_utils.review_relative_path(project, output_path),
            }
        )

    readability = step_readability(project)
    unreadable = [item["path"] for item in readability if not item["readable"]]
    if unreadable:
        report["errors"].append("STEP file(s) are empty or unreadable: " + ", ".join(unreadable))
        return report
    geometry = geometry_summary(project)
    validation_summary = {
        "step_files": readability,
        "geometry": geometry,
    }
    manifest = write_manifest(project, generated_by="scripts/export_step.py", validation_summary=validation_summary)
    report["written"].append(iteration_utils.STEP_MANIFEST_REL)
    report["steps"].append({"step": "write-step-manifest", "status": "pass", "manifest": manifest})

    if not skip_validation:
        validation = validate_model_project.validate(
            project,
            require_step=True,
            geometry_smoke=geometry_smoke,
            review_parameter_audit="auto",
            consistency_audit="off",
        )
        report["steps"].append(
            {
                "step": "validate-export",
                "status": validation["status"],
                "error_count": len(validation.get("errors", [])),
                "warning_count": len(validation.get("warnings", [])),
            }
        )
        report["warnings"].extend(f"validation: {item}" for item in validation.get("warnings", []))
        if validation["status"] != "pass":
            report["errors"].extend(f"validation: {item}" for item in validation.get("errors", []))
            return report
        report_path = project / "validation" / "report.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(validation, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        report["written"].append("validation/report.json")

    audit = audit_project_consistency.audit(project, mode="warn")
    report["steps"].append(
        {
            "step": "export-consistency-audit",
            "status": audit["status"],
            "error_count": len(audit.get("errors", [])),
            "warning_count": len(audit.get("warnings", [])),
        }
    )
    if audit["status"] == "fail":
        report["errors"].extend(
            f"export audit {item.get('code')}: {item.get('message')}"
            for item in audit.get("errors", [])
            if isinstance(item, dict)
        )
        return report

    try:
        current_context = summarize_model_project.write_current_context(project)
        report["written"].append("validation/current_context.json")
        report["steps"].append(
            {
                "step": "write-current-context",
                "status": "pass",
                "step_state": current_context.get("step", {}).get("state"),
                "step_stale": current_context.get("step", {}).get("stale"),
            }
        )
    except Exception as exc:
        report["warnings"].append(f"could not refresh validation/current_context.json: {exc}")
        report["steps"].append({"step": "write-current-context", "status": "warn", "message": str(exc)})

    report["status"] = "pass"
    report["manifest"] = manifest
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_path", help="Model project root")
    parser.add_argument(
        "--python",
        default=sys.executable,
        help="Compatibility option; run this script with the desired Python because export imports source/model.py in-process",
    )
    parser.add_argument("--skip-validation", action="store_true", help="Skip validate_model_project.py after export")
    parser.add_argument("--geometry-smoke", action="store_true", help="Run geometry smoke validation after export")
    args = parser.parse_args()

    try:
        result = export_step(
            Path(args.project_path),
            python_executable=args.python,
            skip_validation=args.skip_validation,
            geometry_smoke=args.geometry_smoke,
        )
    except Exception as exc:
        result = {
            "schema": SCHEMA,
            "project": str(Path(args.project_path).expanduser().resolve()),
            "status": "fail",
            "steps": [{"step": "unhandled-error", "status": "fail", "message": str(exc)}],
            "warnings": [],
            "errors": [str(exc)],
            "written": [],
        }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
