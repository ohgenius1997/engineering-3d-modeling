#!/usr/bin/env python3
"""Audit lightweight spec-to-source coverage for a model project."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import iteration_utils


SCHEMA = "engineering-3d-modeling.spec_coverage.v1"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except json.JSONDecodeError:
        return None


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def contains_value(data: Any, value: str) -> bool:
    if isinstance(data, str):
        return data == value or value in data
    if isinstance(data, dict):
        return any(contains_value(item, value) for item in data.values())
    if isinstance(data, list):
        return any(contains_value(item, value) for item in data)
    return False


def source_contains(source_text: str, item_id: str) -> bool:
    needles = [
        item_id,
        item_id.replace("-", "_"),
        item_id.replace("_", "-"),
    ]
    return any(needle and needle in source_text for needle in needles)


def declared_items(data: Any, *, kind: str) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, dict):
                item_id = value.get("id") if isinstance(value.get("id"), str) else key
            else:
                item_id = key
            if isinstance(item_id, str) and item_id:
                items.append({"kind": kind, "id": item_id})
    elif isinstance(data, list):
        for index, value in enumerate(data):
            item_id: str | None = None
            if isinstance(value, dict):
                for key in ["id", "feature_id", "placement_id", "constraint_id", "name"]:
                    if isinstance(value.get(key), str) and value[key]:
                        item_id = value[key]
                        break
            elif isinstance(value, str):
                item_id = value
            if item_id:
                items.append({"kind": kind, "id": item_id})
            elif isinstance(value, dict) and value:
                items.append({"kind": kind, "id": f"{kind}_{index}"})
    return items


def spec_declarations(spec: dict[str, Any]) -> list[dict[str, str]]:
    declarations: list[dict[str, str]] = []
    declarations.extend(declared_items(spec.get("features"), kind="feature"))
    declarations.extend(declared_items(spec.get("placements"), kind="placement"))

    constraints = spec.get("constraints")
    if isinstance(constraints, dict):
        for section in ["formal", "narrative"]:
            declarations.extend(declared_items(constraints.get(section), kind="constraint"))
    else:
        declarations.extend(declared_items(constraints, kind="constraint"))

    targets = spec.get("validation_targets")
    if isinstance(targets, dict):
        for section, value in targets.items():
            declarations.extend(declared_items(value, kind=f"validation_target:{section}"))
    else:
        declarations.extend(declared_items(targets, kind="validation_target"))
    return declarations


def parameter_map(parameters_doc: dict[str, Any]) -> dict[str, Any]:
    parameters = parameters_doc.get("parameters")
    return parameters if isinstance(parameters, dict) else {}


def affects_geometry(data: Any) -> bool:
    if not isinstance(data, dict):
        return False
    validation = data.get("validation")
    return isinstance(validation, dict) and validation.get("affects_geometry") is True


def unused_reason(data: Any) -> str | None:
    if not isinstance(data, dict):
        return None
    validation = data.get("validation")
    if isinstance(validation, dict) and isinstance(validation.get("unused_reason"), str):
        return validation["unused_reason"]
    return None


def expected_source_refs(data: Any) -> list[str]:
    if not isinstance(data, dict):
        return []
    validation = data.get("validation")
    if not isinstance(validation, dict):
        return []
    refs = validation.get("expected_source_refs")
    if isinstance(refs, list):
        return [item for item in refs if isinstance(item, str) and item]
    if isinstance(refs, str) and refs:
        return [refs]
    return []


def parameter_consumed(source_text: str, parameter_id: str, data: Any) -> bool:
    refs = expected_source_refs(data)
    if refs:
        return all(ref in source_text for ref in refs)
    return source_contains(source_text, parameter_id)


def audit(project: Path, *, write: bool = False) -> dict[str, Any]:
    project = project.expanduser().resolve()
    report: dict[str, Any] = {
        "schema": SCHEMA,
        "project": str(project),
        "generated_at": utc_now(),
        "status": "pass",
        "checks": [],
        "warnings": [],
        "errors": [],
        "feature_gaps": [],
        "placement_gaps": [],
        "constraint_gaps": [],
        "validation_target_gaps": [],
        "unused_geometry_parameters": [],
        "waived_unused_geometry_parameters": [],
    }
    try:
        spec = iteration_utils.load_yaml_doc(project / "spec" / "current.yaml")
        parameters_doc = iteration_utils.load_yaml_doc(project / "parameters.yaml")
    except Exception as exc:
        report["status"] = "fail"
        report["errors"].append(str(exc))
        if write:
            iteration_utils.write_json_doc(project / "validation" / "spec_coverage.json", report)
        return report

    source_text = read_text(project / "source" / "model.py")
    if not source_text:
        report["status"] = "fail"
        report["errors"].append("missing source/model.py")
        if write:
            iteration_utils.write_json_doc(project / "validation" / "spec_coverage.json", report)
        return report

    registry = read_json(project / "validation" / "feature_registry.json")
    layout = read_json(project / "validation" / "layout_report.json")

    for item in spec_declarations(spec):
        item_id = item["id"]
        covered = (
            source_contains(source_text, item_id)
            or contains_value(registry, item_id)
            or contains_value(layout, item_id)
        )
        check = {"check": f"{item['kind']}:{item_id}", "status": "pass" if covered else "warn"}
        report["checks"].append(check)
        if covered:
            continue
        gap = {"kind": item["kind"], "id": item_id}
        if item["kind"] == "feature":
            report["feature_gaps"].append(gap)
        elif item["kind"] == "placement":
            report["placement_gaps"].append(gap)
        elif item["kind"] == "constraint":
            report["constraint_gaps"].append(gap)
        elif item["kind"].startswith("validation_target"):
            report["validation_target_gaps"].append(gap)

    for parameter_id, data in parameter_map(parameters_doc).items():
        if not isinstance(parameter_id, str) or not affects_geometry(data):
            continue
        reason = unused_reason(data)
        if reason:
            report["waived_unused_geometry_parameters"].append({"id": parameter_id, "reason": reason})
            continue
        if parameter_consumed(source_text, parameter_id, data):
            report["checks"].append({"check": f"parameter:{parameter_id}", "status": "pass"})
        else:
            report["unused_geometry_parameters"].append({"id": parameter_id})
            report["checks"].append({"check": f"parameter:{parameter_id}", "status": "warn"})

    warning_count = sum(
        len(report[key])
        for key in [
            "feature_gaps",
            "placement_gaps",
            "constraint_gaps",
            "validation_target_gaps",
            "unused_geometry_parameters",
        ]
    )
    if warning_count:
        report["status"] = "warn"
        report["warnings"].append(f"spec coverage audit found {warning_count} gap(s)")

    if write:
        iteration_utils.write_json_doc(project / "validation" / "spec_coverage.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_path", help="Model project root")
    parser.add_argument("--json", action="store_true", help="Print JSON output (default)")
    parser.add_argument("--write", action="store_true", help="Write validation/spec_coverage.json")
    args = parser.parse_args()

    report = audit(Path(args.project_path), write=args.write)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["status"] != "fail" else 1


if __name__ == "__main__":
    raise SystemExit(main())
