#!/usr/bin/env python3
"""Sync preview-bound parameters from parameters.yaml into review/manifest.json."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_yaml():
    try:
        import yaml  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "PyYAML is required to sync review parameters. "
            "Run scripts/check_environment.py --install with the same Python runtime."
        ) from exc
    return yaml


def label_from_id(parameter_id: str) -> str:
    return parameter_id.replace("_", " ").strip().capitalize()


def numeric(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def preview_for_current_value(preview: dict, value: Any) -> dict:
    """Return manifest preview metadata for the current generated geometry."""

    entry = dict(preview)
    current = numeric(value)
    if current is not None:
        entry["baseline"] = current
    return entry


def parameter_entry(parameter_id: str, data: object, *, include_locked: bool) -> dict | None:
    if isinstance(data, dict):
        value = data.get("value")
        ui = data.get("ui") if isinstance(data.get("ui"), dict) else {}
        if ui.get("editable") is False and not include_locked:
            return None
        preview = data.get("preview")
        if not isinstance(preview, dict) or not preview.get("effect") or preview.get("effect") == "none":
            return None
        entry = {
            "id": parameter_id,
            "label": ui.get("label") or data.get("label") or label_from_id(parameter_id),
            "value": value,
            "preview": preview_for_current_value(preview, value),
        }
        for key in ["unit", "role"]:
            if data.get(key) is not None:
                entry[key] = data[key]
        for source_key, target_key in [("min", "min"), ("max", "max"), ("step", "step")]:
            if ui.get(source_key) is not None:
                entry[target_key] = ui[source_key]
            elif data.get(source_key) is not None:
                entry[target_key] = data[source_key]
        return entry
    return None


def sync(project: Path, *, include_locked: bool, audit_mode: str = "off") -> dict:
    if audit_mode not in {"off", "basic", "strict"}:
        raise RuntimeError("audit_mode must be one of: off, basic, strict")
    yaml = load_yaml()
    project = project.expanduser().resolve()
    parameters_path = project / "parameters.yaml"
    manifest_path = project / "review" / "manifest.json"

    parameters_doc = yaml.safe_load(parameters_path.read_text(encoding="utf-8"))
    if not isinstance(parameters_doc, dict) or not isinstance(parameters_doc.get("parameters"), dict):
        raise RuntimeError("parameters.yaml must contain a parameters mapping")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise RuntimeError("review/manifest.json must contain a JSON object")

    entries = []
    for parameter_id, data in parameters_doc["parameters"].items():
        entry = parameter_entry(str(parameter_id), data, include_locked=include_locked)
        if entry is not None:
            entries.append(entry)

    manifest["parameters"] = entries
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    result = {
        "schema": "engineering-3d-modeling.sync_review_parameters_result.v1",
        "status": "pass",
        "written": [str(manifest_path.relative_to(project))],
        "parameter_count": len(entries),
    }
    if audit_mode != "off":
        import audit_review_parameters

        audit_report = audit_review_parameters.audit(project, mode=audit_mode)
        result["review_parameter_audit"] = audit_report
        if audit_report["status"] == "fail":
            result["status"] = "fail"
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_path", help="Model project root")
    parser.add_argument("--include-locked", action="store_true", help="Include preview-bound parameters with ui.editable=false")
    parser.add_argument(
        "--audit",
        choices=["off", "basic", "strict"],
        default="basic",
        help="Audit review/manifest.json parameters after syncing",
    )
    args = parser.parse_args()

    try:
        report = sync(Path(args.project_path), include_locked=args.include_locked, audit_mode=args.audit)
    except Exception as exc:
        report = {
            "schema": "engineering-3d-modeling.sync_review_parameters_result.v1",
            "status": "fail",
            "written": [],
            "parameter_count": 0,
            "errors": [str(exc)],
        }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
