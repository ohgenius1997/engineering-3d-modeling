#!/usr/bin/env python3
"""Apply review parameter patches to parameters.yaml."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import review_validation


PATCH_EMPTY = {"schema": "engineering-3d-modeling.parameter_patch.v1", "patches": []}


def load_yaml():
    try:
        import yaml  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "PyYAML is required to apply parameter patches. "
            "Run scripts/check_environment.py --install with the same Python runtime."
        ) from exc
    return yaml


def load_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return PATCH_EMPTY.copy()
    if not isinstance(data, dict):
        raise RuntimeError(f"{path} must contain a JSON object")
    return data


def apply_patch(project: Path, *, clear_patch: bool, dry_run: bool) -> dict:
    yaml = load_yaml()
    project = project.expanduser().resolve()
    parameters_path = project / "parameters.yaml"
    patch_path = project / "review" / "parameter_patch.json"

    patch_doc = load_json(patch_path)
    schema_errors = review_validation.validate_parameter_patch_schema(patch_doc)
    if schema_errors:
        return {
            "schema": "engineering-3d-modeling.apply_parameter_patch_result.v1",
            "status": "fail",
            "applied": [],
            "errors": schema_errors,
            "written": [],
        }
    patches = patch_doc.get("patches", [])

    if not patches:
        return {
            "schema": "engineering-3d-modeling.apply_parameter_patch_result.v1",
            "status": "noop",
            "applied": [],
            "errors": [],
            "written": [],
        }

    try:
        parameters_doc = yaml.safe_load(parameters_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"missing parameters.yaml: {parameters_path}") from exc

    if not isinstance(parameters_doc, dict):
        raise RuntimeError("parameters.yaml must contain a YAML object")
    parameters = parameters_doc.get("parameters")
    if not isinstance(parameters, dict):
        raise RuntimeError("parameters.yaml must contain a 'parameters' mapping")

    validation_errors = review_validation.validate_patch_against_project(
        project,
        patch_doc,
        parameters_doc=parameters_doc,
    )
    if validation_errors:
        return {
            "schema": "engineering-3d-modeling.apply_parameter_patch_result.v1",
            "status": "fail",
            "applied": [],
            "errors": validation_errors,
            "written": [],
        }

    errors: list[str] = []
    applied: list[dict[str, object]] = []
    for patch in patches:
        if not isinstance(patch, dict):
            errors.append("patch entry must be an object")
            continue
        parameter_id = patch.get("parameter_id")
        if not isinstance(parameter_id, str) or not parameter_id:
            errors.append("patch entry missing parameter_id")
            continue
        if parameter_id not in parameters:
            errors.append(f"patch references unknown parameter: {parameter_id}")
            continue
        if "value" not in patch:
            errors.append(f"patch for {parameter_id} missing value")
            continue

        target = parameters[parameter_id]
        old_value = target.get("value") if isinstance(target, dict) else target
        if not dry_run:
            if isinstance(target, dict):
                target["value"] = patch["value"]
                if patch.get("unit") and not target.get("unit"):
                    target["unit"] = patch["unit"]
            else:
                parameters[parameter_id] = patch["value"]
        applied.append({"parameter_id": parameter_id, "old_value": old_value, "new_value": patch["value"]})

    if errors:
        return {
            "schema": "engineering-3d-modeling.apply_parameter_patch_result.v1",
            "status": "fail",
            "applied": applied,
            "errors": errors,
            "written": [],
        }

    written: list[str] = []
    if not dry_run:
        parameters_path.write_text(
            yaml.safe_dump(parameters_doc, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
        written.append(str(parameters_path.relative_to(project)))
        if clear_patch:
            patch_path.parent.mkdir(parents=True, exist_ok=True)
            patch_path.write_text(json.dumps(PATCH_EMPTY, indent=2) + "\n", encoding="utf-8")
            written.append(str(patch_path.relative_to(project)))

    return {
        "schema": "engineering-3d-modeling.apply_parameter_patch_result.v1",
        "status": "pass",
        "applied": applied,
        "errors": [],
        "written": written,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_path", help="Model project root")
    parser.add_argument("--keep-patch", action="store_true", help="Do not clear review/parameter_patch.json after applying")
    parser.add_argument("--dry-run", action="store_true", help="Report what would change without writing files")
    args = parser.parse_args()

    try:
        report = apply_patch(Path(args.project_path), clear_patch=not args.keep_patch, dry_run=args.dry_run)
    except RuntimeError as exc:
        report = {
            "schema": "engineering-3d-modeling.apply_parameter_patch_result.v1",
            "status": "fail",
            "applied": [],
            "errors": [str(exc)],
            "written": [],
        }

    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["status"] in {"pass", "noop"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
