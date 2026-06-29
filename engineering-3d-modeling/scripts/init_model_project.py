#!/usr/bin/env python3
"""Scaffold a lightweight engineering CAD model project."""

from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path
import sys


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import iteration_utils


def slugify(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-").lower()
    return slug or "model"


def write_text(path: Path, text: str, force: bool) -> None:
    if path.exists() and not force:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, data: object, force: bool) -> None:
    write_text(path, json.dumps(data, indent=2) + "\n", force)


def copy_template_index(project: Path, force: bool) -> None:
    destination = project / "review" / "index.html"
    if destination.exists() and not force:
        return

    skill_root = Path(__file__).resolve().parents[1]
    template = skill_root / "assets" / "review-template" / "index.html"
    destination.parent.mkdir(parents=True, exist_ok=True)
    if template.exists():
        shutil.copyfile(template, destination)
    else:
        destination.write_text("<!doctype html><title>CAD Review</title>\n", encoding="utf-8")


def brief_text(name: str, kind: str) -> str:
    return f"""# {name}

## Purpose

Maintain an engineering CAD {kind} project with editable authoring truth, reviewable preview artifacts, and direct STEP export when the visible result is satisfactory.

## Current Direction

This scaffold represents one active model direction. Record confirmed design intent here in short human prose, and keep exact dimensions, placements, constraints, and validation targets in `spec/current.yaml` and `parameters.yaml`.

## Pointers

- Structured truth: `spec/current.yaml`, `parameters.yaml`
- CAD source: `source/model.py`
- Review surface: `review/index.html`, `review/manifest.json`
- Continuation summary: `validation/current_context.json`
"""


def agents_text(name: str, kind: str) -> str:
    return f"""# AGENTS.md

<INSTRUCTIONS>
This is an engineering CAD model project. Wake and use `$engineering-3d-modeling` for model creation, continuation, CAD edits, review annotations, parameter patches, preview regeneration, preview rollback, STEP export, handoff packaging, review server work, validation, and diagnostics in this directory.

Start with `validation/current_context.json` when present, or run the installed skill's `scripts/summarize_model_project.py` before broad file reads. Do not default to full history, `previous/`, or handoff package reads.

Project facts:
- Active model: {name}
- Kind: {kind}
- Default backend: build123d
- Short human summary: `brief.md`
- Structured authoring truth: `spec/current.yaml`, `parameters.yaml`, `source/model.py`, and validation evidence
- Review artifacts: `review/index.html`, `review/manifest.json`, `review/annotations.json`, `review/parameter_patch.json`, `review/cache/`
- Direct STEP output: `outputs/step/` plus `outputs/step/manifest.json`
- Default one-step rollback: `checkpoints/preview_previous/` plus `validation/preview_revision.json`

Rules:
- Read the installed skill's `references/context-routing.md` for task tags, minimum reads, artifact boundaries, controlled modeling intent templates, and review annotation clarity gate. Do not copy that routing table into this project.
- Keep `brief.md` short. Do not put open questions, long requirements, parameter tables, bbox data, validation evidence, history, or agent diagnostics there.
- Treat `review/annotations.json` and `review/parameter_patch.json` as review input, not CAD truth. Do not store agent diagnostics or consumed notes in annotations.
- If a review annotation is unclear about target, operation, reference, direction, dimensions, scope, preserve rules, or validation, ask or record an explicit low-risk assumption before modeling.
- Do not hand-roll a replacement review HTML. Restore it from the installed skill template or rerun `scripts/init_model_project.py`.
- Before build123d generation, run the installed skill's `scripts/check_environment.py --json` with the same Python that will execute `source/model.py`.
- Before changing the visible HTML preview model, save a preview checkpoint. "Go back one version" means `scripts/restore_preview_revision.py`, not `previous/`.
- Prefer `scripts/regenerate_from_review.py` for saved review patches. It checkpoints the preview, applies patches, rebuilds, syncs/audits review parameters, validates, marks STEP stale, clears consumed review state after success, and refreshes current context.
- Expose only parameters with explicit trustworthy live-preview bindings. Use preview adapters for localized or topology-changing features; do not use generic morph as a fallback.
- Export usable STEP directly with `scripts/export_step.py` when the preview is satisfactory. It must block pending review input and write a fresh non-stale `outputs/step/manifest.json`.
- Create a handoff zip only when requested with `scripts/create_handoff_package.py`.
- Keep V1 scope to lightweight engineering STEP CAD. Do not add STL, 3MF, G-code, slicer, simulation, animation, or rendering deliverables unless explicitly requested.
</INSTRUCTIONS>
"""


def spec_text(name: str, slug: str, kind: str, per_part_step: bool) -> str:
    per_part = "true" if per_part_step else "false"
    return f"""schema: engineering-3d-modeling.spec.v1
project:
  name: {name!r}
  kind: {kind}
  units: mm
model:
  selected_direction: current
  precision: engineering
coordinate_system:
  origin:
    description: model origin, replace with project-specific convention
    point_mm: [0, 0, 0]
  axes:
    x:
      vector: [1, 0, 0]
      positive_direction: define_for_project
    y:
      vector: [0, 1, 0]
      positive_direction: define_for_project
    z:
      vector: [0, 0, 1]
      positive_direction: define_for_project
lifecycle:
  phase: draft_review
  status: in_progress
  note: STEP may be deferred while this project is in draft/review; export fresh STEP with scripts/export_step.py when the preview is satisfactory.
inputs: []
placements: {{}}
features: []
constraints:
  formal: []
  narrative: []
decisions: []
validation_targets:
  dimensions: {{}}
  clearances: {{}}
  features: {{}}
backend:
  default: build123d
  override: null
source:
  entrypoint: source/model.py
outputs:
  assembly_step: outputs/step/{slug}.step
  per_part_step: {per_part}
review:
  manifest: review/manifest.json
  annotations: review/annotations.json
  parameter_patch: review/parameter_patch.json
validation:
  report: validation/report.json
  current_context: validation/current_context.json
  feature_registry: validation/feature_registry.json
  layout_report: validation/layout_report.json
"""


def current_context(name: str, kind: str) -> dict:
    return {
        "schema": "engineering-3d-modeling.current_context.v1",
        "project": {"name": name, "kind": kind, "units": "mm"},
        "status": "scaffolded",
        "source": {"entrypoint": "source/model.py"},
        "pending_review": {"annotations": 0, "parameter_patches": 0},
        "review": {"mesh": None},
        "step": {"state": "draft", "stale": False, "files": []},
        "preview_checkpoint": {"available": False, "path": "checkpoints/preview_previous"},
        "validation": {"status": "not_run", "errors": [], "warnings": []},
        "key_parameters": [],
        "layout_facts": {},
        "unresolved": {"blockers": [], "questions": []},
        "recommended_next_reads": ["spec/current.yaml", "parameters.yaml", "source/model.py"],
    }


def parameters_text() -> str:
    return """schema: engineering-3d-modeling.parameters.v1
units: mm
parameters:
  body_length:
    value: 40.0
    unit: mm
    role: envelope_length
    preview:
      effect: scale_axis
      axis: x
      baseline: 40.0
      anchor: center
    ui:
      editable: true
      control: slider
      min: 10.0
      max: 120.0
      step: 1.0
    validation:
      affects_geometry: true
  body_width:
    value: 24.0
    unit: mm
    role: envelope_width
    preview:
      effect: scale_axis
      axis: y
      baseline: 24.0
      anchor: center
    ui:
      editable: true
      control: slider
      min: 8.0
      max: 80.0
      step: 1.0
    validation:
      affects_geometry: true
  body_height:
    value: 8.0
    unit: mm
    role: envelope_height
    preview:
      effect: scale_axis
      axis: z
      baseline: 8.0
      anchor: center
    ui:
      editable: true
      control: slider
      min: 2.0
      max: 40.0
      step: 0.5
    validation:
      affects_geometry: true
"""


def model_source_text(slug: str) -> str:
    return f'''#!/usr/bin/env python3
"""build123d source for this model project.

Replace the starter geometry with model-specific construction. Keep the project
spec and parameters as the authoring contract, and export STEP for accepted or
handoff states.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STEP_OUTPUT = PROJECT_ROOT / "outputs" / "step" / "{slug}.step"
os.environ.setdefault("XDG_CACHE_HOME", str(PROJECT_ROOT / "review" / "cache"))


def load_parameters(path: Path) -> dict:
    """Load the project parameter document from YAML."""

    try:
        import yaml  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "PyYAML is required to read parameters.yaml. "
            "Run scripts/check_environment.py --install with this Python runtime."
        ) from exc

    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"missing parameters file: {{path}}") from exc

    if not isinstance(data, dict):
        raise RuntimeError("parameters.yaml must contain a YAML mapping")
    if not isinstance(data.get("parameters"), dict):
        raise RuntimeError("parameters.yaml must contain a 'parameters' mapping")
    return data


def parameter_value(params: dict, parameter_id: str, default: float) -> float:
    """Return a positive numeric parameter value from the project document."""

    parameters = params.get("parameters", {{}})
    entry: Any = parameters.get(parameter_id, default) if isinstance(parameters, dict) else default
    value = entry.get("value", default) if isinstance(entry, dict) else entry
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RuntimeError(f"parameter {{parameter_id}} must be numeric")
    value = float(value)
    if value <= 0:
        raise RuntimeError(f"parameter {{parameter_id}} must be positive")
    return value


def build_model(params: dict):
    """Build and return a build123d Part or Assembly.

    Implement model-specific geometry here. Keep major features in named helper
    functions so review refs and validation checks remain traceable.
    """

    try:
        from build123d import Box, BuildPart
    except ImportError as exc:
        raise RuntimeError("build123d is required to generate CAD output") from exc

    body_length = parameter_value(params, "body_length", 40.0)
    body_width = parameter_value(params, "body_width", 24.0)
    body_height = parameter_value(params, "body_height", 8.0)

    with BuildPart() as starter:
        Box(body_length, body_width, body_height)

    return starter.part


def write_step(model, path: Path) -> None:
    from build123d import export_step as build123d_export_step

    path.parent.mkdir(parents=True, exist_ok=True)
    build123d_export_step(model, str(path))


def main() -> None:
    params = load_parameters(PROJECT_ROOT / "parameters.yaml")
    model = build_model(params)
    write_step(model, STEP_OUTPUT)
    print(f"wrote {{STEP_OUTPUT}}")


if __name__ == "__main__":
    main()
'''


def manifest(name: str, slug: str, kind: str) -> dict:
    return {
        "schema": "engineering-3d-modeling.review_manifest.v1",
        "project": {"name": name, "kind": kind, "units": "mm"},
        "versions": {
            "current": {"step": f"../outputs/step/{slug}.step"},
            "previous": None,
        },
        "preview": {"mesh_json": None, "mesh_closed": True},
        "parts": [],
        "parameters": [],
        "refs": [],
    }


def scaffold(project: Path, name: str, kind: str, per_part_step: bool, force: bool) -> None:
    slug = slugify(name)
    directories = [
        "spec",
        "inputs",
        "source",
        "outputs/step",
        "outputs/handoff",
        "validation",
        "review/cache",
        "previous",
        "checkpoints/preview_previous",
    ]
    for directory in directories:
        (project / directory).mkdir(parents=True, exist_ok=True)

    for keep in [
        "inputs/.gitkeep",
        "outputs/step/.gitkeep",
        "outputs/handoff/.gitkeep",
        "validation/.gitkeep",
        "review/cache/.gitkeep",
        "previous/.gitkeep",
        "checkpoints/preview_previous/.gitkeep",
    ]:
        write_text(project / keep, "", force)

    write_text(project / "brief.md", brief_text(name, kind), force)
    write_text(project / "AGENTS.md", agents_text(name, kind), force)
    write_text(project / "spec" / "current.yaml", spec_text(name, slug, kind, per_part_step), force)
    write_text(project / "parameters.yaml", parameters_text(), force)
    write_text(project / "source" / "model.py", model_source_text(slug), force)
    if force or not (project / iteration_utils.STEP_MANIFEST_REL).exists():
        iteration_utils.write_step_manifest(
            project,
            state="draft",
            generated_for_phase="draft_review",
            generated_by="scripts/init_model_project.py",
            promoted_by=None,
            stale=False,
            generated_at=None,
        )
    write_json(project / "review" / "manifest.json", manifest(name, slug, kind), force)
    write_json(
        project / "review" / "annotations.json",
        {"schema": "engineering-3d-modeling.annotations.v1", "annotations": []},
        force,
    )
    write_json(
        project / "review" / "parameter_patch.json",
        {"schema": "engineering-3d-modeling.parameter_patch.v1", "patches": []},
        force,
    )
    write_json(project / "validation" / "current_context.json", current_context(name, kind), force)
    copy_template_index(project, force)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_path", help="Directory to create or update")
    parser.add_argument("--name", help="Human-readable model name")
    parser.add_argument("--kind", choices=["part", "assembly"], default="part")
    parser.add_argument("--per-part-step", action="store_true", help="Mark per-part STEP export as enabled")
    parser.add_argument("--force", action="store_true", help="Overwrite existing scaffold files")
    args = parser.parse_args()

    project = Path(args.project_path).expanduser().resolve()
    name = args.name or project.name
    scaffold(project, name, args.kind, args.per_part_step, args.force)
    print(project)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
