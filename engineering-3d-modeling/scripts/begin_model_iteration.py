#!/usr/bin/env python3
"""Begin a new model-project iteration with a one-step rollback snapshot."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import iteration_utils


SCHEMA = "engineering-3d-modeling.begin_iteration_result.v1"


def begin_iteration(
    project: Path,
    *,
    force: bool = False,
    dry_run: bool = False,
    reason: str | None = None,
    started_by: str = "scripts/begin_model_iteration.py",
) -> dict[str, Any]:
    project = project.expanduser().resolve()
    phase, phase_source, spec = iteration_utils.current_phase(project)
    pending_review = {
        "parameter_patch_count": iteration_utils.pending_patch_count(project),
        "annotation_count": iteration_utils.pending_annotation_count(project),
    }
    existing_active = iteration_utils.active_iteration(project)
    result: dict[str, Any] = {
        "schema": SCHEMA,
        "project": str(project),
        "status": "fail",
        "dry_run": dry_run,
        "started_from_phase": {"value": phase, "source": phase_source},
        "final_phase": {"value": "draft_review", "source": "spec.lifecycle.phase"},
        "pending_review": pending_review,
        "steps": [],
        "written": [],
    }

    if existing_active is not None and not force:
        result["steps"].append(
            {
                "step": "preflight-active-iteration",
                "status": "fail",
                "message": "validation/iteration.json already records an active iteration; pass --force only if you intentionally want to replace the rollback point",
            }
        )
        return result
    result["steps"].append({"step": "preflight-active-iteration", "status": "pass"})

    snapshot = iteration_utils.snapshot_current_to_previous(
        project,
        force=force,
        dry_run=dry_run,
        reason=reason,
        started_from_phase=phase,
        started_by=started_by,
    )
    result["steps"].append({"step": "snapshot-previous", "status": snapshot["status"], "result": snapshot})
    if dry_run:
        result["status"] = "dry-run"
        return result

    started_at = iteration_utils.utc_now()
    if phase != "draft_review":
        iteration_utils.set_phase_to_draft(project, spec, started_at=started_at, reason=reason)
        result["written"].append("spec/current.yaml")
        result["steps"].append(
            {
                "step": "set-phase-draft-review",
                "status": "pass",
                "from_phase": phase,
                "to_phase": "draft_review",
            }
        )
    else:
        result["steps"].append({"step": "set-phase-draft-review", "status": "pass", "from_phase": phase})

    step_manifest = iteration_utils.mark_draft_step(
        project,
        generated_by=started_by,
        stale=bool(iteration_utils.step_files(project)),
        reason=f"new iteration started from {phase}",
    )
    result["written"].append(iteration_utils.STEP_MANIFEST_REL)
    result["steps"].append(
        {
            "step": "mark-step-draft",
            "status": "pass",
            "state": step_manifest["state"],
            "stale": step_manifest["stale"],
            "step_file_count": len(step_manifest.get("step_files", [])),
        }
    )

    metadata = iteration_utils.write_iteration_metadata(
        project,
        started_at=started_at,
        started_from_phase=phase,
        started_by=started_by,
        reason=reason,
        previous_snapshot_hash=str(snapshot.get("previous_snapshot_hash", "")),
        pending_review=pending_review,
    )
    result["written"].append(iteration_utils.ITERATION_METADATA_REL)
    result["steps"].append({"step": "write-iteration-metadata", "status": "pass", "metadata": metadata})
    result["status"] = "pass"
    result["previous_snapshot_hash"] = snapshot.get("previous_snapshot_hash")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_path", help="Model project root")
    parser.add_argument("--force", action="store_true", help="Overwrite a populated previous/ snapshot or active iteration metadata")
    parser.add_argument("--dry-run", action="store_true", help="Show the rollback snapshot plan without changing files")
    parser.add_argument("--reason", help="Short reason for starting this iteration")
    args = parser.parse_args()

    try:
        result = begin_iteration(
            Path(args.project_path),
            force=args.force,
            dry_run=args.dry_run,
            reason=args.reason,
        )
    except Exception as exc:
        result = {
            "schema": SCHEMA,
            "project": str(Path(args.project_path).expanduser().resolve()),
            "status": "fail",
            "steps": [{"step": "unhandled-error", "status": "fail", "message": str(exc)}],
            "written": [],
        }

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("status") in {"pass", "dry-run"} else 1


if __name__ == "__main__":
    raise SystemExit(main())

