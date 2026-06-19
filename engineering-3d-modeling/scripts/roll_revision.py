#!/usr/bin/env python3
"""Copy the accepted current model-project state into previous/."""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


COPY_PATHS = [
    "brief.md",
    "parameters.yaml",
    "spec",
    "source",
    "outputs/step",
    "validation",
    "review/manifest.json",
    "review/annotations.json",
    "review/parameter_patch.json",
    "review/index.html",
]


def ensure_safe_previous(project: Path) -> Path:
    previous = (project / "previous").resolve()
    project_resolved = project.resolve()
    if previous.name != "previous" or previous.parent != project_resolved:
        raise RuntimeError(f"Unsafe previous path: {previous}")
    return previous


def previous_entries(previous: Path) -> list[str]:
    if not previous.exists():
        return []
    entries = []
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
        shutil.copytree(source, destination, dirs_exist_ok=True, ignore=shutil.ignore_patterns("cache", "__pycache__"))
    else:
        shutil.copy2(source, destination)
    return True


def planned_copy_paths(project: Path) -> tuple[list[str], list[str]]:
    copied = []
    missing = []
    for rel in COPY_PATHS:
        if (project / rel).exists():
            copied.append(rel)
        else:
            missing.append(rel)
    return copied, missing


def roll(project: Path, *, force: bool = False, dry_run: bool = False) -> dict:
    project = project.expanduser().resolve()
    previous = ensure_safe_previous(project)
    existing = previous_entries(previous)
    if dry_run:
        copied, missing = planned_copy_paths(project)
        return {
            "schema": "engineering-3d-modeling.previous_revision_plan.v1",
            "status": "dry-run",
            "previous": str(previous.relative_to(project)),
            "would_overwrite": existing,
            "would_copy": copied,
            "missing": missing,
        }
    if existing and not force:
        raise RuntimeError(
            "previous/ already contains a revision; rerun with --dry-run to inspect or --force to overwrite"
        )

    if previous.exists():
        shutil.rmtree(previous)
    previous.mkdir(parents=True)

    copied = []
    missing = []
    for rel in COPY_PATHS:
        if copy_item(project, previous, rel):
            copied.append(rel)
        else:
            missing.append(rel)

    info = {
        "schema": "engineering-3d-modeling.previous_revision.v1",
        "status": "pass",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "copied": copied,
        "missing": missing,
    }
    (previous / "REVISION_INFO.json").write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
    return info


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_path", help="Model project root")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be copied without writing previous/")
    parser.add_argument("--force", action="store_true", help="Overwrite a populated previous/ revision slot")
    args = parser.parse_args()

    try:
        info = roll(Path(args.project_path), force=args.force, dry_run=args.dry_run)
    except RuntimeError as exc:
        info = {
            "schema": "engineering-3d-modeling.previous_revision_result.v1",
            "status": "fail",
            "errors": [str(exc)],
        }
        print(json.dumps(info, indent=2))
        return 1
    print(json.dumps(info, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
