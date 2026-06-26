#!/usr/bin/env python3
"""Regenerate a model project from saved HTML review data.

This orchestrates the safe review loop:

1. apply review/parameter_patch.json into parameters.yaml,
2. execute source/model.py to rebuild backend CAD or review preview outputs,
3. sync preview-bound parameters into review/manifest.json,
4. validate structure, STEP output according to project phase, and optional parameter-to-geometry smoke,
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
import audit_project_consistency
import audit_review_parameters
import begin_model_iteration
import iteration_utils
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
    skip_review_parameter_audit: bool,
    review_parameter_audit_mode: str,
    skip_validation: bool,
    skip_geometry_smoke: bool,
    keep_patch: bool,
    allow_pending_annotations: bool,
    clear_annotations: bool,
    start_new_iteration: bool = False,
    force_iteration: bool = False,
    iteration_reason: str | None = None,
    phase_override: str | None = None,
) -> dict[str, Any]:
    project = project.expanduser().resolve()
    if phase_override in {"accepted_current", "release_handoff"}:
        return {
            "schema": "engineering-3d-modeling.regenerate_from_review_result.v1",
            "project": str(project),
            "phase": {"value": phase_override, "source": "override"},
            "step_requirement": {"required": True, "reason": f"phase:{phase_override}"},
            "status": "fail",
            "steps": [
                {
                    "step": "preflight-phase-override",
                    "status": "fail",
                    "message": "regenerate_from_review.py cannot declare accepted_current or release_handoff; run promote_model_project.py after draft regeneration validates",
                }
            ],
            "written": [],
        }

    phase_info = validate_model_project.resolve_project_phase(project, phase_override=phase_override)
    phase = str(phase_info["value"])
    step_required, step_requirement_reason = validate_model_project.step_requirement_for_phase(phase, None)
    audit_mode = validate_model_project.review_audit_mode_for_phase(review_parameter_audit_mode, phase)
    report: dict[str, Any] = {
        "schema": "engineering-3d-modeling.regenerate_from_review_result.v1",
        "project": str(project),
        "phase": {"value": phase, "source": phase_info["source"]},
        "step_requirement": {"required": step_required, "reason": step_requirement_reason},
        "status": "fail",
        "steps": [],
        "written": [],
    }

    annotation_count = pending_annotation_count(project)
    patch_count = iteration_utils.pending_patch_count(project)
    active_iteration = iteration_utils.active_iteration(project)
    if start_new_iteration and active_iteration is None:
        begin_result = begin_model_iteration.begin_iteration(
            project,
            force=force_iteration,
            reason=iteration_reason or "regenerate_from_review.py consuming saved review data",
            started_by="scripts/regenerate_from_review.py --start-new-iteration",
        )
        report["steps"].append(
            {
                "step": "begin-iteration",
                "status": begin_result["status"],
                "result": begin_result,
            }
        )
        report["written"].extend(begin_result.get("written", []))
        if begin_result["status"] != "pass":
            report["status"] = "fail"
            return report
        phase_info = validate_model_project.resolve_project_phase(project, phase_override=phase_override)
        phase = str(phase_info["value"])
        step_required, step_requirement_reason = validate_model_project.step_requirement_for_phase(phase, None)
        audit_mode = validate_model_project.review_audit_mode_for_phase(review_parameter_audit_mode, phase)
        report["phase"] = {"value": phase, "source": phase_info["source"]}
        report["step_requirement"] = {"required": step_required, "reason": step_requirement_reason}
        active_iteration = iteration_utils.active_iteration(project)
    else:
        report["steps"].append(
            {
                "step": "preflight-iteration",
                "status": "pass",
                "parameter_patch_count": patch_count,
                "annotation_count": annotation_count,
                "active_iteration": active_iteration is not None,
                "message": "preview revision checkpoint is the default one-step rollback; previous/ iteration snapshots are optional compatibility safety points",
            }
        )

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

    checkpoint = iteration_utils.checkpoint_preview_revision(
        project,
        reason=iteration_reason or "regenerate_from_review.py before changing the visible preview model",
        created_by="scripts/regenerate_from_review.py",
        force=True,
    )
    report["written"].extend([iteration_utils.PREVIEW_REVISION_REL, iteration_utils.PREVIEW_CHECKPOINT_REL])
    report["steps"].append(
        {
            "step": "checkpoint-preview-revision",
            "status": "pass",
            "checkpoint": checkpoint.get("checkpoint"),
            "hashes_before": checkpoint.get("hashes_before"),
        }
    )
    stale_manifest = iteration_utils.mark_step_manifest_stale(
        project,
        reason="review regeneration is changing authoring truth or visible preview; rerun scripts/export_step.py for a fresh STEP",
        updated_by="scripts/regenerate_from_review.py",
    )
    if stale_manifest is not None:
        report["written"].append(iteration_utils.STEP_MANIFEST_REL)
        report["steps"].append(
            {
                "step": "mark-step-stale",
                "status": "pass",
                "state": stale_manifest.get("state"),
                "stale": stale_manifest.get("stale"),
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
    if iteration_utils.step_files(project):
        step_manifest = iteration_utils.load_step_manifest(project)
        if step_manifest is None:
            step_manifest = iteration_utils.mark_draft_step(
                project,
                generated_by="scripts/regenerate_from_review.py",
                stale=True,
                reason="review regeneration touched the preview; export_step.py has not confirmed STEP freshness",
            )
            report["written"].append(iteration_utils.STEP_MANIFEST_REL)
        report["steps"].append(
            {
                "step": "step-output-stale-until-export",
                "status": "pass",
                "step_file_count": len(iteration_utils.step_files(project)),
                "manifest_state": step_manifest.get("state") if isinstance(step_manifest, dict) else None,
                "stale": step_manifest.get("stale") if isinstance(step_manifest, dict) else None,
            }
        )

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

    if not skip_review_parameter_audit:
        audit_report = audit_review_parameters.audit(project, mode=audit_mode)
        report["steps"].append(
            {
                "step": "review-parameter-audit",
                "status": audit_report["status"],
                "mode": audit_mode,
                "valid_preview_parameters": audit_report.get("valid_preview_parameters", []),
                "disabled_count": len(audit_report.get("disabled_parameters", [])),
                "candidate_count": len(audit_report.get("new_candidates", [])),
                "result": audit_report,
            }
        )
        if audit_report["status"] == "fail":
            report["status"] = "fail"
            return report

    if not skip_validation:
        validation_report = validate_model_project.validate(
            project,
            require_step=None,
            geometry_smoke=not skip_geometry_smoke,
            review_parameter_audit="auto",
            phase_override=phase_override,
            consistency_audit="off",
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

        consistency_mode = validate_model_project.consistency_mode_for_phase("auto", phase)
        if consistency_mode != "off":
            consistency_report = audit_project_consistency.audit(project, mode=consistency_mode)
            validation_report["consistency_audit_mode"] = consistency_mode
            validation_report["consistency_audit"] = consistency_report
            if consistency_report["status"] == "fail":
                validation_report["status"] = "fail"
                validation_report.setdefault("errors", []).extend(
                    f"project consistency audit {item.get('code')}: {item.get('message')}"
                    for item in consistency_report.get("errors", [])
                    if isinstance(item, dict)
                )
            validation_path.write_text(json.dumps(validation_report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            report["steps"].append(
                {
                    "step": "project-consistency-audit",
                    "status": consistency_report["status"],
                    "mode": consistency_mode,
                    "error_count": len(consistency_report.get("errors", [])),
                    "warning_count": len(consistency_report.get("warnings", [])),
                }
            )
            if consistency_report["status"] == "fail":
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

    if active_iteration is not None:
        completed = iteration_utils.complete_iteration(
            project,
            completed_by="scripts/regenerate_from_review.py",
            status="completed",
        )
        report["written"].append(iteration_utils.ITERATION_METADATA_REL)
        report["steps"].append(
            {
                "step": "complete-iteration",
                "status": "pass",
                "metadata": completed,
            }
        )

    report["status"] = "pass"
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_path", help="Model project root")
    parser.add_argument("--python", default=sys.executable, help="Python executable used for dependency check and source/model.py")
    parser.add_argument("--skip-environment-check", action="store_true", help="Do not run check_environment.py --json first")
    parser.add_argument("--skip-sync-review-parameters", action="store_true", help="Do not refresh review/manifest.json parameters")
    parser.add_argument(
        "--phase",
        choices=sorted(validate_model_project.PROJECT_PHASES),
        help="Override spec/current.yaml lifecycle.phase for this regeneration run",
    )
    parser.add_argument(
        "--skip-review-parameter-audit",
        action="store_true",
        help="Do not audit review/manifest.json parameters after syncing",
    )
    parser.add_argument(
        "--review-parameter-audit",
        choices=["auto", "basic", "strict"],
        default="auto",
        help="Audit strength used after syncing review parameters; auto uses basic review audit",
    )
    parser.add_argument("--skip-validation", action="store_true", help="Do not run validate_model_project.py after rebuilding")
    parser.add_argument("--skip-geometry-smoke", action="store_true", help="Do not run parameter-to-geometry smoke validation")
    parser.add_argument("--keep-patch", action="store_true", help="Keep review/parameter_patch.json after a successful regeneration")
    parser.add_argument(
        "--start-new-iteration",
        action="store_true",
        help="Also run begin_model_iteration.py to create a coarse previous/ snapshot before regeneration",
    )
    parser.add_argument(
        "--force-iteration",
        action="store_true",
        help="Allow --start-new-iteration to overwrite populated previous/ or active iteration metadata",
    )
    parser.add_argument("--iteration-reason", help="Short reason recorded in validation/iteration.json")
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
            skip_review_parameter_audit=args.skip_review_parameter_audit,
            review_parameter_audit_mode=args.review_parameter_audit,
            skip_validation=args.skip_validation,
            skip_geometry_smoke=args.skip_geometry_smoke,
            keep_patch=args.keep_patch,
            allow_pending_annotations=args.allow_pending_annotations,
            clear_annotations=args.clear_annotations,
            start_new_iteration=args.start_new_iteration,
            force_iteration=args.force_iteration,
            iteration_reason=args.iteration_reason,
            phase_override=args.phase,
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
