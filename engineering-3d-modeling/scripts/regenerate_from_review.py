#!/usr/bin/env python3
"""Regenerate a model project from saved HTML review data.

This orchestrates the safe review loop:

1. apply review/parameter_patch.json into parameters.yaml,
2. execute source/model.py to rebuild STEP output,
3. sync preview-bound parameters into review/manifest.json,
4. validate structure, STEP output, and optional parameter-to-geometry smoke,
5. clear consumed review state only after the regenerated project validates.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import apply_parameter_patch
import reset_review_state
import sync_review_parameters
import validate_model_project


def load_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default
    if not isinstance(data, dict):
        raise RuntimeError(f"{path} must contain a JSON object")
    return data


def pending_annotation_count(project: Path) -> int:
    data = load_json(project / "review" / "annotations.json", {"annotations": []})
    annotations = data.get("annotations")
    if not isinstance(annotations, list):
        raise RuntimeError("review/annotations.json annotations must be a list")
    return len(annotations)


def command_step(command: list[str], *, cwd: Path | None = None) -> dict[str, Any]:
    result = subprocess.run(command, cwd=str(cwd) if cwd else None, capture_output=True, text=True)
    step: dict[str, Any] = {
        "status": "pass" if result.returncode == 0 else "fail",
        "command": command,
        "returncode": result.returncode,
    }
    if result.stdout:
        step["stdout"] = result.stdout
    if result.stderr:
        step["stderr"] = result.stderr
    return step


def environment_step(python_executable: str) -> dict[str, Any]:
    command = [python_executable, str(SCRIPT_DIR / "check_environment.py"), "--json"]
    step = command_step(command)
    if step["status"] == "pass":
        try:
            step["report"] = json.loads(step.get("stdout", "{}"))
        except json.JSONDecodeError as exc:
            step["status"] = "fail"
            step["error"] = f"environment check did not return JSON: {exc}"
    return step


def source_build_step(project: Path, python_executable: str) -> dict[str, Any]:
    return command_step([python_executable, str(project / "source" / "model.py")], cwd=project)


def fail(report: dict[str, Any], step_name: str, message: str, **extra: Any) -> dict[str, Any]:
    report["status"] = "fail"
    step = {"step": step_name, "status": "fail", "message": message}
    step.update(extra)
    report["steps"].append(step)
    return report


def regenerate(
    project: Path,
    *,
    python_executable: str,
    skip_environment_check: bool,
    skip_sync_review_parameters: bool,
    skip_validation: bool,
    skip_geometry_smoke: bool,
    keep_patch: bool,
    allow_pending_annotations: bool,
    clear_annotations: bool,
) -> dict[str, Any]:
    project = project.expanduser().resolve()
    report: dict[str, Any] = {
        "schema": "engineering-3d-modeling.regenerate_from_review_result.v1",
        "project": str(project),
        "status": "fail",
        "steps": [],
        "written": [],
    }

    annotation_count = pending_annotation_count(project)
    if annotation_count and not (allow_pending_annotations or clear_annotations):
        return fail(
            report,
            "preflight-annotations",
            (
                f"review/annotations.json contains {annotation_count} annotation(s). "
                "Convert them into spec/source changes first, then pass --clear-annotations; "
                "or pass --allow-pending-annotations to regenerate parameters while leaving them open."
            ),
            annotation_count=annotation_count,
        )
    report["steps"].append(
        {
            "step": "preflight-annotations",
            "status": "pass",
            "annotation_count": annotation_count,
            "will_clear_annotations": bool(clear_annotations or annotation_count == 0),
        }
    )

    if not skip_environment_check:
        step = environment_step(python_executable)
        step["step"] = "environment"
        report["steps"].append(step)
        env_report = step.get("report") if isinstance(step.get("report"), dict) else {}
        if step["status"] != "pass" or env_report.get("status") == "fail":
            report["status"] = "fail"
            return report

    apply_result = apply_parameter_patch.apply_patch(project, clear_patch=False, dry_run=False)
    report["steps"].append(
        {
            "step": "apply-parameter-patch",
            "status": apply_result["status"],
            "applied_count": len(apply_result.get("applied", [])),
            "result": apply_result,
        }
    )
    report["written"].extend(apply_result.get("written", []))
    if apply_result["status"] == "fail":
        report["status"] = "fail"
        return report

    step = source_build_step(project, python_executable)
    step["step"] = "build-source"
    report["steps"].append(step)
    if step["status"] != "pass":
        report["status"] = "fail"
        return report

    if not skip_sync_review_parameters:
        sync_result = sync_review_parameters.sync(project, include_locked=False)
        report["steps"].append(
            {
                "step": "sync-review-parameters",
                "status": sync_result["status"],
                "parameter_count": sync_result.get("parameter_count", 0),
                "result": sync_result,
            }
        )
        report["written"].extend(sync_result.get("written", []))
        if sync_result["status"] != "pass":
            report["status"] = "fail"
            return report

    if not skip_validation:
        validation_report = validate_model_project.validate(
            project,
            require_step=True,
            geometry_smoke=not skip_geometry_smoke,
        )
        validation_path = project / "validation" / "report.json"
        validation_path.parent.mkdir(parents=True, exist_ok=True)
        validation_path.write_text(json.dumps(validation_report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        report["written"].append(str(validation_path.relative_to(project)))
        report["steps"].append(
            {
                "step": "validate",
                "status": validation_report["status"],
                "report": str(validation_path.relative_to(project)),
                "error_count": len(validation_report.get("errors", [])),
                "warning_count": len(validation_report.get("warnings", [])),
            }
        )
        if validation_report["status"] != "pass":
            report["status"] = "fail"
            return report

    should_clear_annotations = clear_annotations or annotation_count == 0
    should_clear_patch = not keep_patch
    if should_clear_annotations or should_clear_patch:
        reset_result = reset_review_state.reset(
            project,
            annotations=should_clear_annotations,
            parameter_patch=should_clear_patch,
        )
        report["steps"].append(
            {
                "step": "reset-review-state",
                "status": reset_result["status"],
                "result": reset_result,
            }
        )
        report["written"].extend(reset_result.get("written", []))

    report["status"] = "pass"
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_path", help="Model project root")
    parser.add_argument("--python", default=sys.executable, help="Python executable used for dependency check and source/model.py")
    parser.add_argument("--skip-environment-check", action="store_true", help="Do not run check_environment.py --json first")
    parser.add_argument("--skip-sync-review-parameters", action="store_true", help="Do not refresh review/manifest.json parameters")
    parser.add_argument("--skip-validation", action="store_true", help="Do not run validate_model_project.py after rebuilding")
    parser.add_argument("--skip-geometry-smoke", action="store_true", help="Do not run parameter-to-geometry smoke validation")
    parser.add_argument("--keep-patch", action="store_true", help="Keep review/parameter_patch.json after a successful regeneration")
    parser.add_argument(
        "--allow-pending-annotations",
        action="store_true",
        help="Regenerate while leaving non-empty review/annotations.json untouched",
    )
    parser.add_argument(
        "--clear-annotations",
        action="store_true",
        help="Clear review/annotations.json after successful regeneration; use only after annotations were consumed",
    )
    args = parser.parse_args()

    if args.allow_pending_annotations and args.clear_annotations:
        print(
            json.dumps(
                {
                    "schema": "engineering-3d-modeling.regenerate_from_review_result.v1",
                    "status": "fail",
                    "errors": ["--allow-pending-annotations and --clear-annotations are mutually exclusive"],
                },
                indent=2,
            )
        )
        return 2

    try:
        report = regenerate(
            Path(args.project_path),
            python_executable=args.python,
            skip_environment_check=args.skip_environment_check,
            skip_sync_review_parameters=args.skip_sync_review_parameters,
            skip_validation=args.skip_validation,
            skip_geometry_smoke=args.skip_geometry_smoke,
            keep_patch=args.keep_patch,
            allow_pending_annotations=args.allow_pending_annotations,
            clear_annotations=args.clear_annotations,
        )
    except Exception as exc:
        report = {
            "schema": "engineering-3d-modeling.regenerate_from_review_result.v1",
            "project": str(Path(args.project_path).expanduser().resolve()),
            "status": "fail",
            "steps": [{"step": "unhandled-error", "status": "fail", "message": str(exc)}],
            "written": [],
        }

    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
