#!/usr/bin/env python3
"""Copy the current model-project state into previous/ as a one-step rollback snapshot."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import iteration_utils


def roll(project: Path, *, force: bool = False, dry_run: bool = False) -> dict:
    phase = "unknown"
    try:
        phase, _, _ = iteration_utils.current_phase(project.expanduser().resolve())
    except Exception:
        pass
    return iteration_utils.snapshot_current_to_previous(
        project,
        force=force,
        dry_run=dry_run,
        started_from_phase=phase,
        started_by="scripts/roll_revision.py",
    )


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
