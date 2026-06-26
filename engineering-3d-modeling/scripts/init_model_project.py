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

## Goal

Create a maintainable engineering CAD {kind} project that preserves editable authoring truth, supports continuous preview iteration, and exports STEP directly when the visible result is satisfactory.

## Selected Direction

Current direction is the active model. Rejected alternatives should not be developed in this project unless the user explicitly pivots.

## Inputs

Record drawings, photos, STEP references, datasheets, and legacy source under `inputs/`.

## Assumptions

- Units default to mm until changed.
- build123d is the default backend.
- This scaffold starts in `draft_review`; STEP can be exported directly with `scripts/export_step.py` when the preview is satisfactory.
- HTML review comments are structured review data until converted into spec, parameter, or source changes.

## Open Questions

- Replace this section with model-specific unknowns.
"""


def agents_text(name: str, kind: str) -> str:
    return f"""# AGENTS.md

<INSTRUCTIONS>
This is an engineering CAD model project created for the `engineering-3d-modeling` skill.

Use `$engineering-3d-modeling` for model creation, review, parameter changes, annotations, validation, and STEP export work in this directory.

Project facts:
- Active model: {name}
- Kind: {kind}
- Default backend: build123d
- Authoring truth: `brief.md`, `spec/current.yaml`, `parameters.yaml`, `source/model.py`, and validation evidence
- CAD exchange/delivery output: STEP under `outputs/step/`, exported directly with `scripts/export_step.py`
- STEP state: `outputs/step/manifest.json`, where `exported` means fresh direct STEP and `stale: true` means authoring truth or preview changed after export
- Review artifacts: `review/manifest.json`, `review/annotations.json`, `review/parameter_patch.json`, `review/index.html`, and `review/cache/`
- Preview rollback: `checkpoints/preview_previous/` plus `validation/preview_revision.json`

Rules:
- Do not hand-roll a replacement review HTML. Use the installed skill's `assets/review-template/index.html` or rerun the installed skill's `scripts/init_model_project.py` to restore it.
- Before running build123d generation, check dependencies with the installed skill's `scripts/check_environment.py --json` using the same Python that will execute `source/model.py`; if required packages are missing, rerun it with `--install` before continuing and request permission if pip, network, or environment writes are blocked.
- Before any operation that will change the visible HTML preview model, save the current visible revision with `scripts/checkpoint_preview_revision.py --reason "...";` this is the default "go back one version" checkpoint.
- Use `scripts/restore_preview_revision.py` to inspect that rollback and `scripts/restore_preview_revision.py --force` to restore it. Use `scripts/restore_previous.py --force` only to undo a whole coarse iteration from `previous/`.
- Before regenerating from HTML review, prefer the installed skill's `scripts/regenerate_from_review.py` to apply `review/parameter_patch.json`, rebuild backend CAD, checkpoint the previous preview, sync and audit review parameters, clear consumed review state, and validate. If running the steps manually, checkpoint the preview first, apply the parameter patch, then convert user annotations into spec/source changes before clearing them.
- `previous/` and `scripts/begin_model_iteration.py` remain optional coarse compatibility safety points for a whole modeling attempt, not the default meaning of "return to the previous version."
- After editing `parameters.yaml`, sync only parameters with explicit live preview metadata into the HTML manifest with the installed skill's `scripts/sync_review_parameters.py`; then audit exposed parameters with `scripts/audit_review_parameters.py --mode strict` after geometry or preview behavior changes. Parameters without correct live preview bindings should stay in the agent-led regeneration workflow.
- `review/annotations.json` is for user-authored review requests only. Do not store agent diagnostics, baseline analysis, or consumed notes there; use `validation/` or `brief.md` instead.
- After consuming review annotations into a new model revision, clear current review state with the installed skill's `scripts/reset_review_state.py` so the next review starts empty.
- For a single `part` project, keep `manifest.parts` to zero or one real part and use mesh `feature_id` for shroud, hub, vanes, holes, and other subregions. Multiple `part_id` groups are for assemblies.
- Keep `review/index.html` present. Serve it through the installed skill's `scripts/serve_review.py --port 0` when the page needs to save annotations or parameter patches back to local files; report the printed URL because the operating system assigns the actual port.
- Validate the model project with the installed skill's `scripts/validate_model_project.py` after structural or review-workflow changes. Use `--require-step` for forced delivery checks.
- When the user is satisfied with the preview, export usable STEP directly with `scripts/export_step.py`. It fails while `review/parameter_patch.json` or `review/annotations.json` contains unconsumed review data.
- If authoring truth or the visible preview changes after STEP export, treat `outputs/step/manifest.json` as stale and rerun `scripts/export_step.py` before using STEP as current output.
- Generate a delivery/release zip only when requested with `scripts/create_handoff_package.py`; handoff is a package action, not a required daily lifecycle promotion.
- `scripts/promote_model_project.py` remains a compatibility entry for old accepted/release workflows, but do not force routine modeling through accept/handoff promotion.
- Do not add STL, 3MF, G-code, slicer, simulation, animation, or rendering deliverables unless the user explicitly leaves this skill's V1 scope.
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
lifecycle:
  phase: draft_review
  status: in_progress
  note: STEP may be deferred while this project is in draft/review; export fresh STEP with scripts/export_step.py when the preview is satisfactory.
inputs: []
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
"""


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
