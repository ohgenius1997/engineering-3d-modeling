#!/usr/bin/env python3
"""Restore the current model-project state from previous/."""

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
import validate_model_project


SCHEMA = "engineering-3d-modeling.restore_previous_result.v1"


def restore_entries(previous: Path) -> list[str]:
    entries = []
    if not previous.is_dir():
        return entries
    for path in sorted(previous.iterdir()):
        if path.name in {".gitkeep", "REVISION_INFO.json"}:
            continue
        entries.append(path.name)
    return entries


def copy_previous_item(previous: Path, project: Path, name: str) -> None:
    source = previous / name
    destination = project / name
    if source.is_dir():
        shutil.copytree(
            source,
            destination,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns("__pycache__", ".DS_Store"),
        )
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def restore_previous(
    project: Path,
    *,
    force: bool = False,
    skip_validation: bool = False,
) -> dict[str, Any]:
    project = project.expanduser().resolve()
    previous = iteration_utils.ensure_safe_previous(project)
    entries = restore_entries(previous)
    result: dict[str, Any] = {
        "schema": SCHEMA,
        "project": str(project),
        "status": "dry-run" if not force else "fail",
        "previous": iteration_utils.safe_relative(previous, project),
        "would_restore": entries,
        "would_remove_current": [rel for rel in iteration_utils.SNAPSHOT_PATHS if (project / rel).exists()],
        "written": [],
    }
    if not entries:
        result["status"] = "fail"
        result["errors"] = ["previous/ does not contain a restorable snapshot"]
        return result
    if not force:
        result["message"] = "dry-run only; pass --force to restore previous/ into the current project"
        return result

    for rel in iteration_utils.SNAPSHOT_PATHS:
        path = project / rel
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()

    for name in entries:
        copy_previous_item(previous, project, name)
        result["written"].append(name)

    if not skip_validation:
        validation = validate_model_project.validate(
            project,
            require_step=None,
            geometry_smoke=False,
            review_parameter_audit="auto",
            consistency_audit="off",
        )
        result["validation"] = {
            "status": validation["status"],
            "phase": validation["phase"],
            "error_count": len(validation.get("errors", [])),
            "warning_count": len(validation.get("warnings", [])),
        }
    else:
        result["validation"] = {"status": "skipped"}

    result["status"] = "pass"
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_path", help="Model project root")
    parser.add_argument("--force", action="store_true", help="Restore previous/ into the current project")
    parser.add_argument("--skip-validation", action="store_true", help="Do not run basic validation after restore")
    args = parser.parse_args()

    try:
        result = restore_previous(Path(args.project_path), force=args.force, skip_validation=args.skip_validation)
    except Exception as exc:
        result = {
            "schema": SCHEMA,
            "project": str(Path(args.project_path).expanduser().resolve()),
            "status": "fail",
            "errors": [str(exc)],
            "written": [],
        }

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("status") in {"pass", "dry-run"} else 1


if __name__ == "__main__":
    raise SystemExit(main())

