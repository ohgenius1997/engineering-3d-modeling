#!/usr/bin/env python3
"""Save the current visible preview revision before changing preview geometry."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import iteration_utils


SCHEMA = "engineering-3d-modeling.checkpoint_preview_revision_result.v1"


def checkpoint(
    project: Path,
    *,
    reason: str,
    force: bool = True,
    dry_run: bool = False,
    created_by: str = "scripts/checkpoint_preview_revision.py",
) -> dict:
    try:
        metadata = iteration_utils.checkpoint_preview_revision(
            project,
            reason=reason,
            created_by=created_by,
            force=force,
            dry_run=dry_run,
        )
        return {
            "schema": SCHEMA,
            "project": str(project.expanduser().resolve()),
            "status": metadata["status"] if dry_run else "pass",
            "dry_run": dry_run,
            "checkpoint": iteration_utils.PREVIEW_CHECKPOINT_REL,
            "metadata": metadata,
            "written": [] if dry_run else [iteration_utils.PREVIEW_REVISION_REL, iteration_utils.PREVIEW_CHECKPOINT_REL],
        }
    except Exception as exc:
        return {
            "schema": SCHEMA,
            "project": str(project.expanduser().resolve()),
            "status": "fail",
            "dry_run": dry_run,
            "error": str(exc),
            "written": [],
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_path", help="Model project root")
    parser.add_argument("--reason", required=True, help="Why the visible preview is about to change")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be saved")
    parser.add_argument("--no-force", action="store_true", help="Fail instead of replacing the previous preview checkpoint")
    args = parser.parse_args()

    result = checkpoint(
        Path(args.project_path),
        reason=args.reason,
        force=not args.no_force,
        dry_run=args.dry_run,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["status"] in {"pass", "dry-run"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
