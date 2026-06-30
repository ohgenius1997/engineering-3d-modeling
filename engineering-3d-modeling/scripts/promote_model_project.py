#!/usr/bin/env python3
"""Promote an engineering model project through lifecycle phases.

This is the explicit lifecycle gate for moving a project from draft review to
accepted current, and from accepted current to release handoff. It writes
`spec/current.yaml` and `validation/report.json` only after phase-appropriate
validation passes; failed promotions restore the original phase/report state.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import audit_project_consistency
import export_step as export_step_script
import iteration_utils
import validate_model_project


SCHEMA = "engineering-3d-modeling.lifecycle_promotion_result.v1"
TARGET_PHASES = {"accepted_current", "release_handoff"}
PROMOTABLE_PHASES = {"draft_review", "accepted_current", "release_handoff", "backend_override"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def step_files(project: Path) -> list[Path]:
    root = project / "outputs" / "step"
    return sorted(root.glob("*.step")) + sorted(root.glob("*.stp"))


def safe_relative(path: Path, project: Path) -> str:
    try:
        return str(path.resolve().relative_to(project.resolve()))
    except ValueError:
        return str(path)


def load_yaml_doc(path: Path) -> dict[str, Any]:
    yaml = validate_model_project.load_yaml_module()
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"missing YAML file: {path}") from exc
    if not isinstance(data, dict):
        raise RuntimeError(f"{path} must contain a YAML object")
    return data


def write_yaml_doc(path: Path, data: dict[str, Any]) -> None:
    yaml = validate_model_project.load_yaml_module()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")


def load_json_doc(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"missing JSON file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise RuntimeError(f"{path} must contain a JSON object")
    return data


def phase_from_spec_for_promotion(spec: dict[str, Any]) -> tuple[str, str, list[str]]:
    warnings: list[str] = []
    raw_phase, source = validate_model_project.phase_from_spec(spec)
    if raw_phase is None:
        warnings.append(
            "project phase is missing from spec/current.yaml; treating as draft_review, "
            "which must not be considered accepted or release-ready"
        )
        return "draft_review", "default:draft_review", warnings
    if raw_phase not in PROMOTABLE_PHASES:
        warnings.append(
            f"project phase {raw_phase!r} is not a valid lifecycle phase; treating as draft_review"
        )
        return "draft_review", "default:draft_review", warnings
    return raw_phase, source, warnings


def backend_override_record(spec: dict[str, Any]) -> dict[str, Any] | None:
    backend = spec.get("backend")
    if not isinstance(backend, dict):
        return None
    override = backend.get("override")
    if isinstance(override, dict) and override:
        return override
    return None


def override_acceptance_recorded(override: dict[str, Any] | None) -> bool:
    if not isinstance(override, dict):
        return False
    accepted = override.get("accepted_for_promotion")
    if isinstance(accepted, dict) and isinstance(accepted.get("reason"), str) and accepted["reason"].strip():
        return True
    return isinstance(override.get("accepted_reason"), str) and bool(str(override["accepted_reason"]).strip())


def record_override_acceptance(spec: dict[str, Any], *, target_phase: str, reason: str, accepted_at: str) -> None:
    override = backend_override_record(spec)
    if override is None:
        return
    override["accepted_for_promotion"] = {
        "target_phase": target_phase,
        "reason": reason.strip(),
        "accepted_at": accepted_at,
        "script": "scripts/promote_model_project.py",
    }


def pending_annotation_count(project: Path) -> int:
    data = load_json_doc(project / "review" / "annotations.json")
    annotations = data.get("annotations")
    if not isinstance(annotations, list):
        raise RuntimeError("review/annotations.json annotations must be a list")
    return len(annotations)


def pending_patch_count(project: Path) -> int:
    data = load_json_doc(project / "review" / "parameter_patch.json")
    patches = data.get("patches")
    if not isinstance(patches, list):
        raise RuntimeError("review/parameter_patch.json patches must be a list")
    return len(patches)


def promotion_sequence(current_phase: str, target_phase: str, *, allow_skip_accepted: bool) -> list[str]:
    current_for_order = "draft_review" if current_phase == "backend_override" else current_phase
    if current_for_order == target_phase:
        raise RuntimeError(f"project is already at lifecycle.phase {target_phase}")
    if current_for_order == "release_handoff":
        raise RuntimeError("release_handoff is terminal for this promotion flow")

    if target_phase == "accepted_current":
        if current_for_order != "draft_review":
            raise RuntimeError(
                "accepted_current promotion is only allowed from draft_review "
                f"(current phase: {current_phase})"
            )
        return ["accepted_current"]

    if target_phase == "release_handoff":
        if current_for_order == "accepted_current":
            return ["release_handoff"]
        if current_for_order == "draft_review":
            if not allow_skip_accepted:
                raise RuntimeError(
                    "cannot promote directly from draft_review to release_handoff; "
                    "run accepted_current first or pass --allow-skip-accepted"
                )
            return ["accepted_current", "release_handoff"]

    raise RuntimeError(f"unsupported promotion {current_phase} -> {target_phase}")


def base_report(project: Path, target_phase: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "project": str(project),
        "generated_at": utc_now(),
        "target_phase": target_phase,
        "status": "fail",
        "initial_phase": None,
        "final_phase": None,
        "dry_run": False,
        "steps": [],
        "warnings": [],
        "errors": [],
        "written": [],
    }


def add_step(report: dict[str, Any], name: str, status: str, **extra: Any) -> None:
    step = {"step": name, "status": status}
    step.update(extra)
    report["steps"].append(step)


def fail(report: dict[str, Any], step_name: str, message: str, **extra: Any) -> dict[str, Any]:
    report["status"] = "fail"
    report["errors"].append(message)
    add_step(report, step_name, "fail", message=message, **extra)
    return report


def restore_file(path: Path, original: str | None) -> None:
    if original is None:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(original, encoding="utf-8")


def read_optional_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None


def ensure_step_available(
    project: Path,
    spec: dict[str, Any],
    report: dict[str, Any],
    *,
    python_executable: str,
    rebuild_step: bool,
) -> bool:
    existing = step_files(project)
    if existing and not rebuild_step:
        source_path = validate_model_project.source_path_from_spec(project, spec)
        expected_step = export_step_script.assembly_step_path(project, spec)
        current_step = expected_step if expected_step.is_file() else existing[0]
        if source_path is not None:
            iteration_utils.update_review_manifest_current(project, source_path=source_path, step_path=current_step)
        add_step(
            report,
            "step-output",
            "pass",
            mode="existing",
            step_files=[safe_relative(path, project) for path in existing],
            review_manifest_step=iteration_utils.review_relative_path(project, current_step),
        )
        return True

    source_path = validate_model_project.source_path_from_spec(project, spec)
    if source_path is None or not source_path.is_file():
        fail(
            report,
            "build-source",
            "current authoring source is missing; cannot generate STEP",
            source=safe_relative(source_path, project) if source_path is not None else None,
        )
        return False

    output_path = export_step_script.assembly_step_path(project, spec)
    if python_executable != sys.executable:
        report["warnings"].append(
            "--python is retained for compatibility; promote_model_project.py now imports source/model.py in the current interpreter. "
            "Run this script with the desired Python executable instead."
        )
    try:
        build_export = export_step_script.build_and_export_step(project, source_path, output_path)
    except Exception as exc:
        add_step(
            report,
            "build-and-export-step",
            "fail",
            source=safe_relative(source_path, project),
            output=safe_relative(output_path, project),
            message=str(exc),
        )
        report["errors"].append(f"current authoring source failed while exporting STEP: {exc}")
        return False

    produced = step_files(project)
    status = "pass" if produced else "fail"
    add_step(
        report,
        "build-and-export-step",
        status,
        source=build_export["source"],
        output=build_export["output"],
        model_type=build_export["model_type"],
        step_files=[safe_relative(path, project) for path in produced],
    )
    if not produced:
        report["errors"].append("current authoring source exported no STEP/STP under outputs/step")
        return False
    if iteration_utils.update_review_manifest_current(project, source_path=source_path, step_path=output_path):
        add_step(
            report,
            "update-review-manifest-step",
            "pass",
            step_path=iteration_utils.review_relative_path(project, output_path),
        )
    return True


def update_phase_spec(
    project: Path,
    spec: dict[str, Any],
    *,
    phase: str,
    previous_phase: str,
    override_reason: str | None,
    promoted_at: str,
) -> dict[str, Any]:
    lifecycle = spec.setdefault("lifecycle", {})
    if not isinstance(lifecycle, dict):
        lifecycle = {}
        spec["lifecycle"] = lifecycle
    lifecycle["phase"] = phase
    lifecycle["promoted_at"] = promoted_at
    lifecycle["promoted_from"] = previous_phase
    lifecycle["promoted_by"] = "scripts/promote_model_project.py"
    if override_reason:
        record_override_acceptance(spec, target_phase=phase, reason=override_reason, accepted_at=promoted_at)
    write_yaml_doc(project / "spec" / "current.yaml", spec)
    return spec


def write_validation_report(project: Path, validation_report: dict[str, Any]) -> None:
    path = project / "validation" / "report.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(validation_report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def run_accepted_validation(project: Path, report: dict[str, Any], *, geometry_smoke: bool) -> bool:
    validation = validate_model_project.validate(
        project,
        require_step=True,
        geometry_smoke=geometry_smoke,
        review_parameter_audit="auto",
        consistency_audit="off",
    )
    add_step(
        report,
        "accepted-validation",
        validation["status"],
        report_path="validation/report.json",
        error_count=len(validation.get("errors", [])),
        warning_count=len(validation.get("warnings", [])),
    )
    report["warnings"].extend(f"accepted validation: {item}" for item in validation.get("warnings", []))
    if validation["status"] != "pass":
        report["errors"].extend(f"accepted validation: {item}" for item in validation.get("errors", []))
        return False
    write_validation_report(project, validation)
    return True


def run_accepted_strict_consistency(project: Path, report: dict[str, Any]) -> bool:
    audit = audit_project_consistency.audit(project, mode="strict")
    add_step(
        report,
        "accepted-current-consistency",
        audit["status"],
        mode="strict",
        error_count=len(audit.get("errors", [])),
        warning_count=len(audit.get("warnings", [])),
    )
    report["warnings"].extend(
        f"accepted consistency {item.get('code')}: {item.get('message')}"
        for item in audit.get("warnings", [])
        if isinstance(item, dict)
    )
    if audit["status"] == "fail":
        report["errors"].extend(
            f"accepted consistency {item.get('code')}: {item.get('message')}"
            for item in audit.get("errors", [])
            if isinstance(item, dict)
        )
        return False
    return True


def run_release_validation(project: Path, report: dict[str, Any], *, geometry_smoke: bool) -> bool:
    validation = validate_model_project.validate(
        project,
        require_step=True,
        geometry_smoke=geometry_smoke,
        review_parameter_audit="strict",
        consistency_audit="off",
    )
    add_step(
        report,
        "release-validation",
        validation["status"],
        report_path="validation/report.json",
        error_count=len(validation.get("errors", [])),
        warning_count=len(validation.get("warnings", [])),
    )
    report["warnings"].extend(f"release validation: {item}" for item in validation.get("warnings", []))
    if validation["status"] != "pass":
        report["errors"].extend(f"release validation: {item}" for item in validation.get("errors", []))
        return False

    write_validation_report(project, validation)
    audit = audit_project_consistency.audit(project, mode="strict")
    validation["consistency_audit_mode"] = "strict"
    validation["consistency_audit"] = audit
    add_step(
        report,
        "release-consistency",
        audit["status"],
        mode="strict",
        error_count=len(audit.get("errors", [])),
        warning_count=len(audit.get("warnings", [])),
    )
    report["warnings"].extend(
        f"release consistency {item.get('code')}: {item.get('message')}"
        for item in audit.get("warnings", [])
        if isinstance(item, dict)
    )
    if audit["status"] == "fail":
        report["errors"].extend(
            f"release consistency {item.get('code')}: {item.get('message')}"
            for item in audit.get("errors", [])
            if isinstance(item, dict)
        )
        return False

    write_validation_report(project, validation)
    return True


def promote_mutable(
    project: Path,
    *,
    target_phase: str,
    allow_skip_accepted: bool,
    accept_backend_override_reason: str | None,
    python_executable: str,
    rebuild_step: bool,
    geometry_smoke: bool,
) -> dict[str, Any]:
    project = project.expanduser().resolve()
    report = base_report(project, target_phase)
    report["warnings"].append(
        "compatibility flow: promote_model_project.py is retained for legacy accepted/release projects; "
        "routine modeling should use preview checkpoints, scripts/export_step.py, and scripts/create_handoff_package.py"
    )
    spec_path = project / "spec" / "current.yaml"
    report_path = project / "validation" / "report.json"

    try:
        spec = load_yaml_doc(spec_path)
        current_phase, phase_source, phase_warnings = phase_from_spec_for_promotion(spec)
    except Exception as exc:
        return fail(report, "load-spec", str(exc))

    report["initial_phase"] = {"value": current_phase, "source": phase_source}
    report["warnings"].extend(phase_warnings)

    if target_phase not in TARGET_PHASES:
        return fail(report, "target-phase", f"unsupported target phase {target_phase!r}")

    try:
        annotation_count = pending_annotation_count(project)
        patch_count = pending_patch_count(project)
    except Exception as exc:
        return fail(report, "preflight-review-state", str(exc))

    review_ok = annotation_count == 0 and patch_count == 0
    add_step(
        report,
        "preflight-review-state",
        "pass" if review_ok else "fail",
        annotation_count=annotation_count,
        parameter_patch_count=patch_count,
    )
    if annotation_count:
        report["errors"].append(
            f"review/annotations.json contains {annotation_count} unconsumed annotation(s); "
            "convert them into spec/parameter/source changes and clear review state before promotion"
        )
    if patch_count:
        report["errors"].append(
            f"review/parameter_patch.json contains {patch_count} unapplied patch(es); "
            "run scripts/regenerate_from_review.py before promotion"
        )
    if not review_ok:
        report["status"] = "fail"
        return report

    override = backend_override_record(spec)
    override_needs_acceptance = current_phase == "backend_override" or override is not None
    if override_needs_acceptance and not (
        accept_backend_override_reason and accept_backend_override_reason.strip()
    ) and not override_acceptance_recorded(override):
        return fail(
            report,
            "preflight-backend-override",
            "backend_override or spec.backend.override cannot be promoted directly; "
            "clear backend.override or pass --accept-backend-override-reason with the accepted exception rationale",
        )
    add_step(
        report,
        "preflight-backend-override",
        "pass",
        has_backend_override=override is not None,
        current_phase=current_phase,
        accepted_reason_recorded=bool(
            accept_backend_override_reason and accept_backend_override_reason.strip()
        )
        or override_acceptance_recorded(override),
    )

    try:
        sequence = promotion_sequence(current_phase, target_phase, allow_skip_accepted=allow_skip_accepted)
    except Exception as exc:
        return fail(report, "promotion-sequence", str(exc))
    add_step(report, "promotion-sequence", "pass", phases=sequence)

    original_spec_text = read_optional_text(spec_path)
    original_report_text = read_optional_text(report_path)
    original_step_manifest_text = read_optional_text(project / iteration_utils.STEP_MANIFEST_REL)
    original_review_manifest_text = read_optional_text(project / "review" / "manifest.json")
    previous_phase = current_phase
    written: set[str] = set()

    try:
        for phase in sequence:
            if not ensure_step_available(
                project,
                spec,
                report,
                python_executable=python_executable,
                rebuild_step=rebuild_step,
            ):
                raise RuntimeError("STEP preflight failed")
            if read_optional_text(project / "review" / "manifest.json") != original_review_manifest_text:
                written.add("review/manifest.json")

            if phase == "release_handoff":
                if not run_accepted_strict_consistency(project, report):
                    raise RuntimeError("accepted_current consistency audit failed")

            spec = update_phase_spec(
                project,
                spec,
                phase=phase,
                previous_phase=previous_phase,
                override_reason=accept_backend_override_reason,
                promoted_at=utc_now(),
            )
            written.add("spec/current.yaml")
            add_step(report, f"write-phase:{phase}", "pass", path="spec/current.yaml")
            step_manifest = iteration_utils.write_step_manifest(
                project,
                state=phase,
                generated_for_phase=phase,
                generated_by="scripts/promote_model_project.py",
                promoted_by="scripts/promote_model_project.py",
                stale=False,
            )
            written.add(iteration_utils.STEP_MANIFEST_REL)
            add_step(
                report,
                f"write-step-manifest:{phase}",
                "pass",
                path=iteration_utils.STEP_MANIFEST_REL,
                step_file_count=len(step_manifest.get("step_files", [])),
            )

            if phase == "accepted_current":
                if not run_accepted_validation(project, report, geometry_smoke=geometry_smoke):
                    raise RuntimeError("accepted_current validation failed")
                written.add("validation/report.json")
                previous_phase = "accepted_current"
                continue

            if phase == "release_handoff":
                if not run_release_validation(project, report, geometry_smoke=geometry_smoke):
                    raise RuntimeError("release_handoff validation failed")
                written.add("validation/report.json")
                previous_phase = "release_handoff"
                continue

            raise RuntimeError(f"unexpected promotion phase: {phase}")
    except Exception as exc:
        restore_file(spec_path, original_spec_text)
        restore_file(report_path, original_report_text)
        restore_file(project / iteration_utils.STEP_MANIFEST_REL, original_step_manifest_text)
        restore_file(project / "review" / "manifest.json", original_review_manifest_text)
        report["status"] = "fail"
        report["final_phase"] = report["initial_phase"]
        report["written"] = []
        add_step(
            report,
            "rollback",
            "pass",
            reason=str(exc),
            restored=[
                "spec/current.yaml",
                "validation/report.json",
                iteration_utils.STEP_MANIFEST_REL,
                "review/manifest.json",
            ],
        )
        return report

    report["status"] = "pass"
    report["final_phase"] = {"value": target_phase, "source": "spec.lifecycle.phase"}
    report["written"] = sorted(written)
    return report


def promote(
    project: Path,
    *,
    target_phase: str,
    allow_skip_accepted: bool = False,
    accept_backend_override_reason: str | None = None,
    python_executable: str = sys.executable,
    rebuild_step: bool = False,
    geometry_smoke: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    project = project.expanduser().resolve()
    if not dry_run:
        return promote_mutable(
            project,
            target_phase=target_phase,
            allow_skip_accepted=allow_skip_accepted,
            accept_backend_override_reason=accept_backend_override_reason,
            python_executable=python_executable,
            rebuild_step=rebuild_step,
            geometry_smoke=geometry_smoke,
        )

    with tempfile.TemporaryDirectory(prefix="e3dm-promote-", dir="/private/tmp") as tmp:
        temp_project = Path(tmp) / project.name
        ignore = shutil.ignore_patterns(".git", "__pycache__")
        shutil.copytree(project, temp_project, ignore=ignore)
        report = promote_mutable(
            temp_project,
            target_phase=target_phase,
            allow_skip_accepted=allow_skip_accepted,
            accept_backend_override_reason=accept_backend_override_reason,
            python_executable=python_executable,
            rebuild_step=rebuild_step,
            geometry_smoke=geometry_smoke,
        )
    report["project"] = str(project)
    report["dry_run"] = True
    report["written"] = []
    return report


def render_summary(report: dict[str, Any]) -> str:
    initial = report.get("initial_phase") or {}
    initial_value = initial.get("value", "unknown") if isinstance(initial, dict) else "unknown"
    final = report.get("final_phase") or {}
    final_value = final.get("value", initial_value) if isinstance(final, dict) else initial_value
    lines = [
        f"{report.get('status', 'fail')}: {initial_value} -> {report.get('target_phase')} (final: {final_value})",
        f"project: {report.get('project')}",
    ]
    if report.get("dry_run"):
        lines.append("dry_run: true")
    for label in ["errors", "warnings"]:
        items = report.get(label, [])
        if not items:
            continue
        lines.append(f"{label}:")
        for item in items[:10]:
            lines.append(f"- {item}")
    steps = report.get("steps", [])
    if steps:
        lines.append("steps:")
        for step in steps:
            detail = step.get("message") or step.get("reason") or ""
            suffix = f" - {detail}" if detail else ""
            lines.append(f"- {step.get('step')}: {step.get('status')}{suffix}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_path", help="Model project root")
    parser.add_argument("target_phase", choices=sorted(TARGET_PHASES), help="Lifecycle phase to promote to")
    parser.add_argument(
        "--allow-skip-accepted",
        action="store_true",
        help="Allow draft_review -> release_handoff by running accepted and release validation gates in order",
    )
    parser.add_argument(
        "--accept-backend-override-reason",
        help="Record why a backend_override/spec.backend.override exception is accepted for this promotion",
    )
    parser.add_argument("--python", default=sys.executable, help="Python executable used if source/model.py must generate STEP")
    parser.add_argument("--rebuild-step", action="store_true", help="Run current authoring source even when STEP already exists")
    parser.add_argument("--geometry-smoke", action="store_true", help="Run parameter-to-geometry smoke validation")
    parser.add_argument("--dry-run", action="store_true", help="Run the promotion gates on a temporary project copy")
    parser.add_argument(
        "--format",
        choices=["json", "summary", "both"],
        default="both",
        help="Output machine JSON, human summary, or both",
    )
    args = parser.parse_args()

    try:
        report = promote(
            Path(args.project_path),
            target_phase=args.target_phase,
            allow_skip_accepted=args.allow_skip_accepted,
            accept_backend_override_reason=args.accept_backend_override_reason,
            python_executable=args.python,
            rebuild_step=args.rebuild_step,
            geometry_smoke=args.geometry_smoke,
            dry_run=args.dry_run,
        )
    except Exception as exc:
        project = Path(args.project_path).expanduser().resolve()
        report = fail(base_report(project, args.target_phase), "unhandled-error", str(exc))

    if args.format in {"summary", "both"}:
        print(render_summary(report), file=sys.stderr if args.format == "both" else sys.stdout)
    if args.format in {"json", "both"}:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report.get("status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
