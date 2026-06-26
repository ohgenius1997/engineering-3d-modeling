#!/usr/bin/env python3
"""Restore the previous visible preview revision.

Default mode is a dry-run. Pass --force to copy files back from
checkpoints/preview_previous/.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import iteration_utils


SCHEMA = "engineering-3d-modeling.restore_preview_revision_result.v1"


def safe_restore_path(project: Path, rel: str) -> Path:
    destination = (project / rel).resolve()
    project_root = project.resolve()
    if destination != project_root and project_root not in destination.parents:
        raise RuntimeError(f"unsafe restore path: {rel}")
    return destination


def copy_back(checkpoint: Path, project: Path, rel: str) -> bool:
    source = checkpoint / rel
    if not source.exists():
        return False
    destination = safe_restore_path(project, rel)
    if destination.exists():
        if destination.is_dir():
            shutil.rmtree(destination)
        else:
            destination.unlink()
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        shutil.copytree(source, destination, ignore=shutil.ignore_patterns("__pycache__", ".DS_Store"))
    else:
        shutil.copy2(source, destination)
    return True


def restore_preview_revision(project: Path, *, force: bool = False) -> dict[str, Any]:
    project = project.expanduser().resolve()
    checkpoint = iteration_utils.ensure_safe_preview_checkpoint(project)
    metadata_path = project / iteration_utils.PREVIEW_REVISION_REL
    metadata = iteration_utils.load_json_doc(metadata_path, {}) if metadata_path.is_file() else {}
    planned = [
        rel
        for rel in iteration_utils.PREVIEW_CHECKPOINT_PATHS
        if (checkpoint / rel).exists()
    ]
    result: dict[str, Any] = {
        "schema": SCHEMA,
        "project": str(project),
        "status": "dry-run" if not force else "fail",
        "dry_run": not force,
        "checkpoint": iteration_utils.PREVIEW_CHECKPOINT_REL,
        "metadata": metadata,
        "would_restore": planned,
        "restored": [],
        "missing": [rel for rel in iteration_utils.PREVIEW_CHECKPOINT_PATHS if not (checkpoint / rel).exists()],
    }
    if not checkpoint.is_dir():
        result["status"] = "fail"
        result["error"] = f"missing preview checkpoint: {iteration_utils.PREVIEW_CHECKPOINT_REL}"
        return result
    if not force:
        return result

    restored = []
    for rel in planned:
        if copy_back(checkpoint, project, rel):
            restored.append(rel)
    result["restored"] = restored
    result["status"] = "pass"
    result["dry_run"] = False
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_path", help="Model project root")
    parser.add_argument("--force", action="store_true", help="Actually restore files; without this the command is dry-run")
    args = parser.parse_args()

    try:
        result = restore_preview_revision(Path(args.project_path), force=args.force)
    except Exception as exc:
        result = {
            "schema": SCHEMA,
            "project": str(Path(args.project_path).expanduser().resolve()),
            "status": "fail",
            "dry_run": not args.force,
            "error": str(exc),
        }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["status"] in {"pass", "dry-run"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
