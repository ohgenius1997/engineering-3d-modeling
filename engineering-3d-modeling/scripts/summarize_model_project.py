#!/usr/bin/env python3
"""Summarize an engineering 3D model project for continuation.

The default output is a short human summary. Use --json for machine-readable
output or --write-current-context to refresh validation/current_context.json.
This script intentionally uses only the Python standard library.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any


SCHEMA = "engineering-3d-modeling.current_context.v1"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def load_json(path: Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return dict(default or {})
    except json.JSONDecodeError as exc:
        return {"_error": f"invalid JSON: {exc}"}
    return data if isinstance(data, dict) else {"_error": "expected JSON object"}


def sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rel(path: Path, project: Path) -> str:
    try:
        return str(path.resolve().relative_to(project.resolve()))
    except ValueError:
        return str(path)


def parse_scalar(value: str) -> Any:
    value = value.strip()
    if value in {"", "null", "~"}:
        return None
    if value in {"true", "false"}:
        return value == "true"
    if (value.startswith("'") and value.endswith("'")) or (value.startswith('"') and value.endswith('"')):
        return value[1:-1]
    try:
        if re.fullmatch(r"[-+]?\d+", value):
            return int(value)
        if re.fullmatch(r"[-+]?\d+\.\d+", value):
            return float(value)
    except ValueError:
        pass
    return value


def yaml_scalar(text: str, path: list[str]) -> Any:
    stack: list[tuple[int, str]] = []
    for raw_line in text.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        match = re.match(r"^(\s*)([A-Za-z0-9_-]+):(?:\s*(.*))?$", raw_line)
        if not match:
            continue
        indent = len(match.group(1))
        key = match.group(2)
        value = match.group(3) or ""
        while stack and stack[-1][0] >= indent:
            stack.pop()
        current = [item[1] for item in stack] + [key]
        if current == path:
            return parse_scalar(value)
        stack.append((indent, key))
    return None


def parameter_summaries(text: str, limit: int = 8) -> list[dict[str, Any]]:
    lines = text.splitlines()
    parameters_indent: int | None = None
    entries: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    current_indent: int | None = None

    for line in lines:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        match = re.match(r"^(\s*)([A-Za-z0-9_.-]+):(?:\s*(.*))?$", line)
        if not match:
            continue
        indent = len(match.group(1))
        key = match.group(2)
        value = match.group(3) or ""
        if parameters_indent is None:
            if indent == 0 and key == "parameters":
                parameters_indent = indent
            continue
        if indent <= parameters_indent and key != "parameters":
            break
        if indent == parameters_indent + 2:
            if current:
                entries.append(current)
            current = {"id": key}
            current_indent = indent
            if value:
                current["value"] = parse_scalar(value)
        elif current is not None and current_indent is not None and indent == current_indent + 2:
            if key in {"value", "unit", "role"}:
                current[key] = parse_scalar(value)
    if current:
        entries.append(current)
    return entries[:limit]


def pending_count(project: Path, rel_path: str, key: str) -> int:
    data = load_json(project / rel_path, {key: []})
    values = data.get(key)
    return len(values) if isinstance(values, list) else 0


def review_mesh_summary(project: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    preview = manifest.get("preview") if isinstance(manifest.get("preview"), dict) else {}
    mesh_value = preview.get("mesh_json") if isinstance(preview, dict) else None
    if not isinstance(mesh_value, str) or not mesh_value:
        return {"path": None, "exists": False}
    path = (project / "review" / mesh_value).resolve()
    review_root = (project / "review").resolve()
    if path != review_root and review_root not in path.parents:
        return {"path": mesh_value, "exists": False, "error": "mesh path escapes review/"}
    summary: dict[str, Any] = {"path": rel(path, project), "exists": path.is_file()}
    if path.is_file():
        summary["sha256"] = sha256(path)
        summary["modified_at"] = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat().replace("+00:00", "Z")
    return summary


def step_summary(project: Path, mesh_hash: str | None) -> dict[str, Any]:
    manifest_path = project / "outputs" / "step" / "manifest.json"
    manifest = load_json(manifest_path, {})
    step_files = sorted((project / "outputs" / "step").glob("*.step")) + sorted((project / "outputs" / "step").glob("*.stp"))
    summary: dict[str, Any] = {
        "manifest": "outputs/step/manifest.json" if manifest_path.is_file() else None,
        "state": manifest.get("state") if isinstance(manifest.get("state"), str) else None,
        "stale": bool(manifest.get("stale")) if manifest else None,
        "stale_reason": manifest.get("stale_reason", "") if manifest else "",
        "files": [{"path": rel(path, project), "sha256": sha256(path)} for path in step_files],
    }
    mismatches = []
    comparisons = {
        "source_hash": sha256(project / "source" / "model.py"),
        "parameters_hash": sha256(project / "parameters.yaml"),
        "spec_hash": sha256(project / "spec" / "current.yaml"),
        "review_mesh_hash": mesh_hash,
    }
    for key, current in comparisons.items():
        recorded = manifest.get(key) if isinstance(manifest, dict) else None
        if recorded and current and str(recorded).lower() != str(current).lower():
            mismatches.append(key)
    if mismatches:
        summary["stale"] = True
        summary["stale_reason"] = "hash mismatch: " + ", ".join(mismatches)
        summary["freshness_mismatches"] = mismatches
    if summary["state"] is None and step_files:
        summary["state"] = "files_without_manifest"
        summary["stale"] = True
    return summary


def preview_checkpoint_summary(project: Path) -> dict[str, Any]:
    revision = load_json(project / "validation" / "preview_revision.json", {})
    checkpoint = project / "checkpoints" / "preview_previous"
    available = checkpoint.is_dir() and any(path.name != ".gitkeep" for path in checkpoint.rglob("*"))
    return {
        "available": available,
        "path": "checkpoints/preview_previous",
        "created_at": revision.get("created_at"),
        "reason": revision.get("reason"),
    }


def validation_summary(project: Path) -> dict[str, Any]:
    report = load_json(project / "validation" / "report.json", {})
    return {
        "status": report.get("status", "not_run"),
        "errors": report.get("errors", []) if isinstance(report.get("errors", []), list) else [],
        "warnings": report.get("warnings", []) if isinstance(report.get("warnings", []), list) else [],
    }


def layout_facts(project: Path) -> dict[str, Any]:
    data = load_json(project / "validation" / "layout_report.json", {})
    if not data:
        return {}
    facts: dict[str, Any] = {}
    for key in ["bbox", "bounding_box", "clearances", "placements", "alignments", "features"]:
        if key in data:
            facts[key] = data[key]
    return facts or {"available_keys": sorted(k for k in data.keys() if not k.startswith("_"))}


def existing_unresolved(project: Path) -> dict[str, list[Any]]:
    current = load_json(project / "validation" / "current_context.json", {})
    unresolved = current.get("unresolved") if isinstance(current.get("unresolved"), dict) else {}
    blockers = unresolved.get("blockers") if isinstance(unresolved.get("blockers"), list) else []
    questions = unresolved.get("questions") if isinstance(unresolved.get("questions"), list) else []
    return {"blockers": blockers, "questions": questions}


def recommended_reads(context: dict[str, Any]) -> list[str]:
    reads = ["validation/current_context.json"]
    pending = context["pending_review"]
    if pending["annotations"]:
        reads.extend(["review/annotations.json", "review/manifest.json", "spec/current.yaml", "source/model.py"])
    if pending["parameter_patches"]:
        reads.extend(["review/parameter_patch.json", "parameters.yaml", "review/manifest.json"])
    if context["validation"]["status"] == "fail":
        reads.extend(["validation/report.json", "spec/current.yaml", "parameters.yaml", "source/model.py"])
    if context["step"].get("stale"):
        reads.extend(["outputs/step/manifest.json", "spec/current.yaml", "parameters.yaml", "source/model.py"])
    if not pending["annotations"] and not pending["parameter_patches"] and context["validation"]["status"] != "fail":
        reads.extend(["spec/current.yaml", "parameters.yaml", "source/model.py"])
    return list(dict.fromkeys(reads))


def summarize(project: Path) -> dict[str, Any]:
    project = project.expanduser().resolve()
    spec_text = read_text(project / "spec" / "current.yaml")
    params_text = read_text(project / "parameters.yaml")
    manifest = load_json(project / "review" / "manifest.json", {})
    project_info = manifest.get("project") if isinstance(manifest.get("project"), dict) else {}
    name = yaml_scalar(spec_text, ["project", "name"]) or project_info.get("name") or project.name
    kind = yaml_scalar(spec_text, ["project", "kind"]) or project_info.get("kind")
    units = yaml_scalar(spec_text, ["project", "units"]) or project_info.get("units")
    source_entrypoint = yaml_scalar(spec_text, ["source", "entrypoint"]) or "source/model.py"
    review_mesh = review_mesh_summary(project, manifest)
    context = {
        "schema": SCHEMA,
        "generated_at": utc_now(),
        "project": {"name": name, "kind": kind, "units": units},
        "source": {"entrypoint": source_entrypoint},
        "pending_review": {
            "annotations": pending_count(project, "review/annotations.json", "annotations"),
            "parameter_patches": pending_count(project, "review/parameter_patch.json", "patches"),
        },
        "review": {"mesh": review_mesh},
        "step": step_summary(project, review_mesh.get("sha256") if isinstance(review_mesh.get("sha256"), str) else None),
        "preview_checkpoint": preview_checkpoint_summary(project),
        "validation": validation_summary(project),
        "key_parameters": parameter_summaries(params_text),
        "layout_facts": layout_facts(project),
        "unresolved": existing_unresolved(project),
    }
    context["recommended_next_reads"] = recommended_reads(context)
    return context


def write_current_context(project: Path) -> dict[str, Any]:
    context = summarize(project)
    path = project.expanduser().resolve() / "validation" / "current_context.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(context, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return context


def human_summary(context: dict[str, Any]) -> str:
    project = context["project"]
    pending = context["pending_review"]
    step = context["step"]
    validation = context["validation"]
    mesh = context["review"]["mesh"]
    lines = [
        f"Project: {project.get('name')} ({project.get('kind')}, {project.get('units')})",
        f"Source: {context['source'].get('entrypoint')}",
        f"Pending review: {pending.get('annotations', 0)} annotation(s), {pending.get('parameter_patches', 0)} parameter patch(es)",
        f"Review mesh: {mesh.get('path') or 'none'}",
        f"STEP: state={step.get('state') or 'none'}, stale={step.get('stale')}, files={len(step.get('files', []))}",
        f"Preview checkpoint: {'available' if context['preview_checkpoint'].get('available') else 'missing'}",
        f"Validation: {validation.get('status')} ({len(validation.get('errors', []))} error(s), {len(validation.get('warnings', []))} warning(s))",
    ]
    if context.get("key_parameters"):
        params = ", ".join(
            f"{item.get('id')}={item.get('value')}{(' ' + item.get('unit')) if item.get('unit') else ''}"
            for item in context["key_parameters"]
        )
        lines.append(f"Key parameters: {params}")
    unresolved = context.get("unresolved", {})
    blockers = unresolved.get("blockers", [])
    questions = unresolved.get("questions", [])
    if blockers or questions:
        lines.append(f"Unresolved: {len(blockers)} blocker(s), {len(questions)} question(s)")
    lines.append("Recommended next reads: " + ", ".join(context.get("recommended_next_reads", [])))
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_path", help="Model project root")
    parser.add_argument("--json", action="store_true", help="Print machine-readable current-context JSON")
    parser.add_argument(
        "--write-current-context",
        action="store_true",
        help="Write validation/current_context.json in addition to printing output",
    )
    args = parser.parse_args()

    project = Path(args.project_path)
    context = write_current_context(project) if args.write_current_context else summarize(project)
    if args.json:
        print(json.dumps(context, indent=2, ensure_ascii=False))
    else:
        print(human_summary(context))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
