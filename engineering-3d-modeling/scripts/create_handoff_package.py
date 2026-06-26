#!/usr/bin/env python3
"""Create an optional reproducible handoff package zip for a model project."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
from typing import Any
import zipfile


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import audit_project_consistency
import iteration_utils


SCHEMA = "engineering-3d-modeling.handoff_package_result.v1"
HANDOFF_MANIFEST_SCHEMA = "engineering-3d-modeling.handoff_manifest.v1"


BASE_INCLUDE = [
    "spec/current.yaml",
    "parameters.yaml",
    "source/model.py",
    "validation/report.json",
    "review/index.html",
    "review/manifest.json",
    "review/cache/current_mesh.json",
]


def slugify(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-").lower()
    return slug or "model"


def project_name(project: Path) -> str:
    try:
        spec = iteration_utils.load_yaml_doc(project / "spec" / "current.yaml")
    except Exception:
        return project.name
    info = spec.get("project")
    if isinstance(info, dict) and isinstance(info.get("name"), str):
        return info["name"]
    return project.name


def pending_review(project: Path) -> dict[str, int]:
    return {
        "parameter_patch_count": iteration_utils.pending_patch_count(project),
        "annotation_count": iteration_utils.pending_annotation_count(project),
    }


def file_record(project: Path, rel: str) -> dict[str, Any]:
    path = project / rel
    return {
        "path": rel,
        "sha256": iteration_utils.file_sha256(path),
        "bytes": path.stat().st_size if path.is_file() else None,
    }


def collect_files(project: Path) -> tuple[list[str], list[str]]:
    include = [rel for rel in BASE_INCLUDE if (project / rel).is_file()]
    missing = [rel for rel in BASE_INCLUDE if not (project / rel).is_file()]
    for step in iteration_utils.step_files(project):
        rel = iteration_utils.safe_relative(step, project)
        if rel not in include:
            include.append(rel)
    if (project / iteration_utils.STEP_MANIFEST_REL).is_file():
        include.append(iteration_utils.STEP_MANIFEST_REL)
    screenshots = sorted((project / "review").glob("*.png")) + sorted((project / "review" / "cache").glob("*screenshot*.png"))
    for screenshot in screenshots:
        rel = iteration_utils.safe_relative(screenshot, project)
        if rel not in include:
            include.append(rel)
    return include, missing


def step_ready(project: Path) -> tuple[bool, str, dict[str, Any] | None]:
    manifest = iteration_utils.refresh_step_freshness(project, updated_by="scripts/create_handoff_package.py")
    if manifest is None:
        return False, "outputs/step/manifest.json is missing; run scripts/export_step.py first", None
    if manifest.get("stale") is True:
        return False, "STEP manifest is stale; rerun scripts/export_step.py first", manifest
    if manifest.get("state") not in {"exported", "accepted_current", "release_handoff"}:
        return False, f"STEP manifest state {manifest.get('state')!r} is not a deliverable state", manifest
    if not iteration_utils.step_files(project):
        return False, "outputs/step contains no STEP/STP file", manifest
    return True, "STEP output is fresh", manifest


def build_handoff_manifest(
    project: Path,
    *,
    generated_at: str,
    zip_path: Path,
    files: list[str],
    step_manifest: dict[str, Any],
    audit: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema": HANDOFF_MANIFEST_SCHEMA,
        "generated_at": generated_at,
        "generated_by": "scripts/create_handoff_package.py",
        "skill_version": "engineering-3d-modeling.v1",
        "source_project": str(project),
        "package": iteration_utils.safe_relative(zip_path, project),
        "step_state": {
            "state": step_manifest.get("state"),
            "stale": step_manifest.get("stale"),
            "generated_at": step_manifest.get("generated_at"),
            "step_files": step_manifest.get("step_files", []),
        },
        "validation_status": "pass" if not audit.get("errors") else "fail",
        "warning_summary": [
            f"{item.get('code')}: {item.get('message')}"
            for item in audit.get("warnings", [])
            if isinstance(item, dict)
        ],
        "files": [file_record(project, rel) for rel in files],
    }


def readme_text(name: str, generated_at: str) -> str:
    return f"""# {name} Handoff Package

Generated at: {generated_at}

This package is a reproducible snapshot of the current engineering CAD model
project. The editable authoring truth is `spec/current.yaml`, `parameters.yaml`,
and `source/model.py`. STEP files under `outputs/step/` are the CAD exchange
deliverables for this snapshot.
"""


def create_package(project: Path, *, output_dir: Path | None = None) -> dict[str, Any]:
    project = project.expanduser().resolve()
    result: dict[str, Any] = {
        "schema": SCHEMA,
        "project": str(project),
        "status": "fail",
        "steps": [],
        "warnings": [],
        "errors": [],
        "written": [],
    }
    pending = pending_review(project)
    result["steps"].append({"step": "pending-review", "status": "pass" if not any(pending.values()) else "fail", **pending})
    if pending["parameter_patch_count"] or pending["annotation_count"]:
        result["errors"].append("cannot create handoff package with unconsumed review annotations or parameter patches")
        return result

    ready, message, step_manifest = step_ready(project)
    result["steps"].append({"step": "step-freshness", "status": "pass" if ready else "fail", "message": message})
    if not ready or step_manifest is None:
        result["errors"].append(message)
        return result

    audit = audit_project_consistency.audit(project, mode="strict")
    result["steps"].append(
        {
            "step": "strict-consistency-audit",
            "status": audit["status"],
            "error_count": len(audit.get("errors", [])),
            "warning_count": len(audit.get("warnings", [])),
        }
    )
    result["warnings"].extend(
        f"{item.get('code')}: {item.get('message')}"
        for item in audit.get("warnings", [])
        if isinstance(item, dict)
    )
    if audit["status"] == "fail":
        result["errors"].extend(
            f"{item.get('code')}: {item.get('message')}"
            for item in audit.get("errors", [])
            if isinstance(item, dict)
        )
        return result

    generated_at = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    name = project_name(project)
    out_dir = output_dir.expanduser().resolve() if output_dir is not None else project / "outputs" / "handoff"
    out_dir.mkdir(parents=True, exist_ok=True)
    zip_path = out_dir / f"{slugify(name)}-{generated_at}.zip"
    files, missing = collect_files(project)
    handoff_manifest = build_handoff_manifest(
        project,
        generated_at=generated_at,
        zip_path=zip_path,
        files=files,
        step_manifest=step_manifest,
        audit=audit,
    )
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as package:
        package.writestr("README.md", readme_text(name, generated_at))
        package.writestr("handoff_manifest.json", json.dumps(handoff_manifest, indent=2, ensure_ascii=False) + "\n")
        for rel in files:
            package.write(project / rel, rel)

    manifest_path = out_dir / f"{zip_path.stem}-manifest.json"
    manifest_path.write_text(json.dumps(handoff_manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    result["status"] = "pass"
    result["package"] = str(zip_path)
    result["manifest"] = str(manifest_path)
    result["missing_optional"] = missing
    result["written"] = [
        iteration_utils.safe_relative(zip_path, project),
        iteration_utils.safe_relative(manifest_path, project),
    ]
    result["steps"].append({"step": "write-package", "status": "pass", "file_count": len(files) + 2})
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_path", help="Model project root")
    parser.add_argument("--output-dir", help="Directory for the handoff zip; defaults to outputs/handoff")
    args = parser.parse_args()

    try:
        result = create_package(
            Path(args.project_path),
            output_dir=Path(args.output_dir) if args.output_dir else None,
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
