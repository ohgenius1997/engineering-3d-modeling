#!/usr/bin/env python3
"""Shared iteration and STEP-manifest helpers for model-project scripts."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
from typing import Any


ITERATION_SCHEMA = "engineering-3d-modeling.iteration.v1"
STEP_MANIFEST_SCHEMA = "engineering-3d-modeling.step_manifest.v1"
ITERATION_METADATA_REL = "validation/iteration.json"
STEP_MANIFEST_REL = "outputs/step/manifest.json"

SNAPSHOT_PATHS = [
    "brief.md",
    "AGENTS.md",
    "parameters.yaml",
    "spec",
    "source",
    "outputs",
    "validation",
    "review",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_yaml_module():
    try:
        import yaml  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "PyYAML is required for model iteration scripts. "
            "Run scripts/check_environment.py --install with this Python runtime."
        ) from exc
    return yaml


def load_yaml_doc(path: Path) -> dict[str, Any]:
    yaml = load_yaml_module()
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"missing YAML file: {path}") from exc
    if not isinstance(data, dict):
        raise RuntimeError(f"{path} must contain a YAML object")
    return data


def write_yaml_doc(path: Path, data: dict[str, Any]) -> None:
    yaml = load_yaml_module()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")


def load_json_doc(path: Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return dict(default or {})
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise RuntimeError(f"{path} must contain a JSON object")
    return data


def write_json_doc(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def safe_relative(path: Path, project: Path) -> str:
    try:
        return str(path.resolve().relative_to(project.resolve()))
    except ValueError:
        return str(path)


def file_sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tree_hash(root: Path, *, ignore_names: set[str] | None = None) -> str:
    ignore = ignore_names or set()
    digest = hashlib.sha256()
    if not root.exists():
        return digest.hexdigest()
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name in ignore or "__pycache__" in path.parts:
            continue
        rel = str(path.relative_to(root)).replace("\\", "/")
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        digest.update(b"\0")
    return digest.hexdigest()


def project_phase_from_spec(spec: dict[str, Any] | None) -> tuple[str, str]:
    if isinstance(spec, dict):
        lifecycle = spec.get("lifecycle")
        if isinstance(lifecycle, dict) and isinstance(lifecycle.get("phase"), str):
            return lifecycle["phase"], "spec.lifecycle.phase"
    return "draft_review", "default:draft_review"


def current_phase(project: Path) -> tuple[str, str, dict[str, Any]]:
    spec = load_yaml_doc(project / "spec" / "current.yaml")
    phase, source = project_phase_from_spec(spec)
    return phase, source, spec


def set_phase_to_draft(project: Path, spec: dict[str, Any], *, started_at: str, reason: str | None) -> None:
    lifecycle = spec.setdefault("lifecycle", {})
    if not isinstance(lifecycle, dict):
        lifecycle = {}
        spec["lifecycle"] = lifecycle
    previous_phase = lifecycle.get("phase")
    lifecycle["phase"] = "draft_review"
    lifecycle["status"] = "in_progress"
    lifecycle["iteration_started_at"] = started_at
    lifecycle["iteration_started_from"] = previous_phase or "draft_review"
    lifecycle["iteration_started_by"] = "scripts/begin_model_iteration.py"
    if reason:
        lifecycle["iteration_reason"] = reason
    for key in ["promoted_at", "promoted_from", "promoted_by"]:
        lifecycle.pop(key, None)
    write_yaml_doc(project / "spec" / "current.yaml", spec)


def ensure_safe_previous(project: Path) -> Path:
    previous = (project / "previous").resolve()
    project_resolved = project.resolve()
    if previous.name != "previous" or previous.parent != project_resolved:
        raise RuntimeError(f"unsafe previous path: {previous}")
    return previous


def previous_entries(previous: Path) -> list[str]:
    if not previous.exists():
        return []
    entries: list[str] = []
    for path in previous.rglob("*"):
        rel = str(path.relative_to(previous))
        if rel == ".gitkeep":
            continue
        entries.append(rel)
    return sorted(entries)


def copy_item(project: Path, previous: Path, rel: str) -> bool:
    source = project / rel
    if not source.exists():
        return False
    destination = previous / rel
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        shutil.copytree(
            source,
            destination,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns("__pycache__", ".DS_Store"),
        )
    else:
        shutil.copy2(source, destination)
    return True


def planned_snapshot_paths(project: Path) -> tuple[list[str], list[str]]:
    copied = []
    missing = []
    for rel in SNAPSHOT_PATHS:
        if (project / rel).exists():
            copied.append(rel)
        else:
            missing.append(rel)
    return copied, missing


def snapshot_current_to_previous(
    project: Path,
    *,
    force: bool = False,
    dry_run: bool = False,
    reason: str | None = None,
    started_from_phase: str | None = None,
    started_by: str = "scripts/begin_model_iteration.py",
) -> dict[str, Any]:
    project = project.expanduser().resolve()
    previous = ensure_safe_previous(project)
    existing = previous_entries(previous)
    if dry_run:
        copied, missing = planned_snapshot_paths(project)
        return {
            "schema": "engineering-3d-modeling.previous_snapshot_plan.v1",
            "status": "dry-run",
            "previous": safe_relative(previous, project),
            "would_overwrite": existing,
            "would_copy": copied,
            "missing": missing,
        }

    if existing and not force:
        raise RuntimeError(
            "previous/ already contains a snapshot; rerun with --dry-run to inspect or --force to overwrite"
        )

    if previous.exists():
        shutil.rmtree(previous)
    previous.mkdir(parents=True)

    copied = []
    missing = []
    for rel in SNAPSHOT_PATHS:
        if copy_item(project, previous, rel):
            copied.append(rel)
        else:
            missing.append(rel)

    snapshot_hash = tree_hash(previous, ignore_names={"REVISION_INFO.json", ".gitkeep"})
    info = {
        "schema": "engineering-3d-modeling.previous_snapshot.v1",
        "status": "pass",
        "created_at": utc_now(),
        "created_by": started_by,
        "reason": reason or "",
        "started_from_phase": started_from_phase or "unknown",
        "previous_snapshot_hash": snapshot_hash,
        "copied": copied,
        "missing": missing,
    }
    write_json_doc(previous / "REVISION_INFO.json", info)
    return info


def step_files(project: Path) -> list[Path]:
    root = project / "outputs" / "step"
    return sorted(root.glob("*.step")) + sorted(root.glob("*.stp"))


def step_manifest_path(project: Path) -> Path:
    return project / STEP_MANIFEST_REL


def load_step_manifest(project: Path) -> dict[str, Any] | None:
    path = step_manifest_path(project)
    if not path.is_file():
        return None
    return load_json_doc(path)


def step_file_records(project: Path) -> list[dict[str, Any]]:
    records = []
    for path in step_files(project):
        records.append(
            {
                "path": safe_relative(path, project),
                "sha256": file_sha256(path),
            }
        )
    return records


def write_step_manifest(
    project: Path,
    *,
    state: str,
    generated_for_phase: str,
    generated_by: str,
    promoted_by: str | None = None,
    stale: bool = False,
    stale_reason: str | None = None,
    previous_state: str | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    project = project.expanduser().resolve()
    now = utc_now()
    existing = load_step_manifest(project)
    existing_generated_at = existing.get("generated_at") if isinstance(existing, dict) else None
    if generated_at is not None:
        resolved_generated_at = generated_at
    elif stale and existing_generated_at:
        resolved_generated_at = existing_generated_at
    else:
        resolved_generated_at = now
    manifest = {
        "schema": STEP_MANIFEST_SCHEMA,
        "state": state,
        "generated_for_phase": generated_for_phase,
        "generated_at": resolved_generated_at,
        "updated_at": now,
        "generated_by": generated_by,
        "promoted_by": promoted_by,
        "stale": bool(stale),
        "stale_reason": stale_reason or "",
        "previous_state": previous_state or (existing.get("state") if isinstance(existing, dict) else None),
        "source_hash": file_sha256(project / "source" / "model.py"),
        "parameters_hash": file_sha256(project / "parameters.yaml"),
        "step_files": step_file_records(project),
    }
    write_json_doc(step_manifest_path(project), manifest)
    return manifest


def mark_draft_step(project: Path, *, generated_by: str, stale: bool, reason: str) -> dict[str, Any]:
    return write_step_manifest(
        project,
        state="draft",
        generated_for_phase="draft_review",
        generated_by=generated_by,
        promoted_by=None,
        stale=stale,
        stale_reason=reason,
    )


def pending_patch_count(project: Path) -> int:
    data = load_json_doc(project / "review" / "parameter_patch.json", {"patches": []})
    patches = data.get("patches")
    if not isinstance(patches, list):
        raise RuntimeError("review/parameter_patch.json patches must be a list")
    return len(patches)


def pending_annotation_count(project: Path) -> int:
    data = load_json_doc(project / "review" / "annotations.json", {"annotations": []})
    annotations = data.get("annotations")
    if not isinstance(annotations, list):
        raise RuntimeError("review/annotations.json annotations must be a list")
    return len(annotations)


def active_iteration(project: Path) -> dict[str, Any] | None:
    path = project / ITERATION_METADATA_REL
    if not path.is_file():
        return None
    data = load_json_doc(path)
    if data.get("schema") != ITERATION_SCHEMA:
        return None
    if data.get("status") == "active" and not data.get("completed_at"):
        return data
    return None


def write_iteration_metadata(
    project: Path,
    *,
    started_at: str,
    started_from_phase: str,
    started_by: str,
    reason: str | None,
    previous_snapshot_hash: str,
    pending_review: dict[str, int],
) -> dict[str, Any]:
    metadata = {
        "schema": ITERATION_SCHEMA,
        "status": "active",
        "started_at": started_at,
        "started_from_phase": started_from_phase,
        "current_phase": "draft_review",
        "started_by": started_by,
        "reason": reason or "",
        "previous": "previous",
        "previous_snapshot_hash": previous_snapshot_hash,
        "pending_review": pending_review,
        "step_manifest": STEP_MANIFEST_REL,
    }
    write_json_doc(project / ITERATION_METADATA_REL, metadata)
    return metadata


def complete_iteration(project: Path, *, completed_by: str, status: str = "completed") -> dict[str, Any] | None:
    path = project / ITERATION_METADATA_REL
    if not path.is_file():
        return None
    data = load_json_doc(path)
    data["status"] = status
    data["completed_at"] = utc_now()
    data["completed_by"] = completed_by
    write_json_doc(path, data)
    return data
