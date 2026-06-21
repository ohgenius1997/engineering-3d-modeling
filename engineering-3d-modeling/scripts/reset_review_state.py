#!/usr/bin/env python3
"""Clear current review annotations and parameter patches after they are consumed."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


EMPTY_ANNOTATIONS = {"schema": "engineering-3d-modeling.annotations.v1", "annotations": []}
EMPTY_PATCH = {"schema": "engineering-3d-modeling.parameter_patch.v1", "patches": []}


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def reset(project: Path, *, annotations: bool, parameter_patch: bool) -> dict:
    project = project.expanduser().resolve()
    written: list[str] = []
    if annotations:
        path = project / "review" / "annotations.json"
        write_json(path, EMPTY_ANNOTATIONS)
        written.append(str(path.relative_to(project)))
    if parameter_patch:
        path = project / "review" / "parameter_patch.json"
        write_json(path, EMPTY_PATCH)
        written.append(str(path.relative_to(project)))
    return {
        "schema": "engineering-3d-modeling.reset_review_state_result.v1",
        "status": "pass",
        "written": written,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_path", help="Model project root")
    parser.add_argument("--annotations-only", action="store_true", help="Clear only review/annotations.json")
    parser.add_argument("--patch-only", action="store_true", help="Clear only review/parameter_patch.json")
    args = parser.parse_args()

    annotations = not args.patch_only
    parameter_patch = not args.annotations_only
    report = reset(Path(args.project_path), annotations=annotations, parameter_patch=parameter_patch)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
