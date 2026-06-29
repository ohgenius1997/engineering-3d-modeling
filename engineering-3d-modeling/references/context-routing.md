# Context Routing

## Global Flow

For an existing model project, read in this order:

```text
project AGENTS.md
  -> $engineering-3d-modeling SKILL.md
  -> validation/current_context.json or scripts/summarize_model_project.py
  -> this reference's task tags
  -> exact authoring, review, validation, or output files for those tags
```

Do not default to full reads of long history, `previous/`, handoff packages, or project status logs. `brief.md` is a short human entry point; it is not required for every implementation task.

When multiple tags apply, merge their minimum reads. Prefer structured truth and generated evidence over narrative Markdown.

## Composable Task Tags

### `new_model_project`

- Minimum reads: user request, relevant input files, `references/inputs.md`, `references/model-project.md`.
- Optional reads: `references/assemblies-and-layout.md`, `references/formulas.md`, `references/review-html.md`.
- Writes: new model-project scaffold from `scripts/init_model_project.py`; then `spec/current.yaml`, `parameters.yaml`, `source/model.py`, `review/manifest.json`, validation artifacts.
- Forbidden writes: no hand-written replacement `review/index.html`; no `outputs/handoff/` package unless explicitly requested.
- Validation expectations: run environment check before CAD generation; validate project structure and review JSON before presenting the project.

### `continue_existing_project`

- Minimum reads: project `AGENTS.md`, `validation/current_context.json` if present, otherwise `scripts/summarize_model_project.py` output.
- Optional reads: `brief.md` for human orientation, `spec/current.yaml`, `parameters.yaml`, `validation/report.json`, `review/manifest.json`.
- Writes: `validation/current_context.json` after stable state changes.
- Forbidden writes: do not rewrite `brief.md` with history or open questions; do not migrate old project structure unless requested.
- Validation expectations: confirm pending review state, STEP freshness, latest validation status, and recommended next reads before editing.

### `consume_review_feedback`

- Minimum reads: `review/annotations.json`, `review/parameter_patch.json`, `review/manifest.json`, `validation/current_context.json` or summary output, `references/review-html.md`.
- Optional reads: `spec/current.yaml`, `parameters.yaml`, `source/model.py`, `validation/feature_registry.json`, `validation/layout_report.json`.
- Writes: consumed changes into `spec/current.yaml`, `parameters.yaml`, `source/model.py`, and validation evidence; clear consumed review state after success.
- Forbidden writes: no agent diagnostics or consumed notes in `review/annotations.json`; no handoff package in ordinary review iteration.
- Validation expectations: apply the review annotation clarity gate before modeling; regenerate, sync/audit review parameters, validate, and update current context.

### `update_review_preview`

- Minimum reads: `review/manifest.json`, `parameters.yaml`, `source/model.py`, `validation/current_context.json` or summary output.
- Optional reads: `review/cache/current_mesh.json`, `validation/layout_report.json`, `validation/feature_registry.json`.
- Writes: `review/manifest.json`, `review/cache/*`, `validation/report.json`, `validation/current_context.json`; mark STEP stale when the visible preview or authoring truth changes.
- Forbidden writes: no STEP freshness claim unless `scripts/export_step.py` reruns; no direct CAD truth in review cache.
- Validation expectations: checkpoint the previous visible preview first, then sync and audit review parameters.

### `parameter_preview_or_adapter`

- Minimum reads: `parameters.yaml`, `review/manifest.json`, `references/review-html.md`.
- Optional reads: `review/cache/preview_adapter.js`, `source/model.py`, `validation/feature_registry.json`.
- Writes: parameter metadata, manifest preview bindings, optional model-specific preview adapter, validation report.
- Forbidden writes: do not expose localized features through `preview.effect: "generic_morph"`; do not make review patches edit hidden parameters.
- Validation expectations: run `scripts/audit_review_parameters.py`; strict mode after geometry or preview behavior changes.

### `geometry_feature_change`

- Minimum reads: `spec/current.yaml`, `parameters.yaml`, `source/model.py`, `validation/current_context.json` or summary output.
- Optional reads: `validation/feature_registry.json`, `validation/layout_report.json`, `review/annotations.json`, `review/manifest.json`.
- Writes: feature intent in `spec/current.yaml`, parameters when adjustable, source implementation, feature registry entries when useful, validation report.
- Forbidden writes: do not bury feature intent only in source code; do not invent missing dimensions when the clarity gate fails.
- Validation expectations: validate feature dimensions, named refs, part-vs-feature grouping, and any affected review selectors.

### `assembly_alignment`

- Minimum reads: `spec/current.yaml`, `parameters.yaml`, `source/model.py`, `validation/layout_report.json` when present.
- Optional reads: fixed component inputs, `references/assemblies-and-layout.md`, `validation/feature_registry.json`, `review/manifest.json`.
- Writes: explicit placement rules in `spec/current.yaml`, layout report, source transforms, validation evidence.
- Forbidden writes: do not encode critical alignment only as prose; do not move fixed components without preserving recorded constraints.
- Validation expectations: check transformed bboxes, clearances, collisions, access openings, and rule satisfaction.

### `step_export`

- Minimum reads: `spec/current.yaml`, `parameters.yaml`, `source/model.py`, `review/annotations.json`, `review/parameter_patch.json`, `outputs/step/manifest.json` if present.
- Optional reads: `validation/report.json`, `review/manifest.json`, `review/cache/current_mesh.json`.
- Writes: STEP files under `outputs/step/`, `outputs/step/manifest.json`, `validation/report.json`, `validation/current_context.json`.
- Forbidden writes: no export while review annotations or parameter patches are pending; no handoff zip.
- Validation expectations: use `scripts/export_step.py`; fresh direct STEP has `state: "exported"` and `stale: false`.

### `handoff_package`

- Minimum reads: `spec/current.yaml`, `parameters.yaml`, `source/model.py`, `outputs/step/manifest.json`, `validation/report.json`, `review/manifest.json`.
- Optional reads: `brief.md`, `review/cache/current_mesh.json`, package manifest.
- Writes: whitelisted package artifacts under `outputs/handoff/`, `validation/current_context.json`.
- Forbidden writes: no pending review data in package; exclude `previous/`, `checkpoints/`, temporary caches, tests, and private raw inputs unless explicitly allowed.
- Validation expectations: require fresh STEP, no pending review data, and strict consistency via `scripts/create_handoff_package.py`.

### `preview_rollback`

- Minimum reads: `validation/preview_revision.json`, `checkpoints/preview_previous/`.
- Optional reads: current `parameters.yaml`, `review/manifest.json`, `review/cache/`, `outputs/step/manifest.json`.
- Writes: restored preview checkpoint after dry-run and explicit force; `validation/current_context.json`.
- Forbidden writes: do not use `previous/` for normal "go back one version"; do not delete history.
- Validation expectations: dry-run first, then force only when requested or clearly intended; mark STEP stale if restored authoring/preview differs from exported STEP.

### `preview_vs_cad_mismatch`

- Minimum reads: `review/manifest.json`, `review/cache/current_mesh.json`, `parameters.yaml`, `source/model.py`, `validation/report.json`.
- Optional reads: `outputs/step/manifest.json`, `validation/layout_report.json`, `validation/feature_registry.json`.
- Writes: corrected preview cache/adapter/manifest or corrected source/spec, validation report, current context.
- Forbidden writes: do not hide mismatches by editing reports only; do not leave misleading sliders exposed.
- Validation expectations: rerun source generation or preview sync, audit review parameters, and document residual mismatch as a blocker if unresolved.

### `validation_failure`

- Minimum reads: failing command output, `validation/report.json`, `spec/current.yaml`, `parameters.yaml`, `source/model.py`.
- Optional reads: `review/manifest.json`, `review/parameter_patch.json`, `outputs/step/manifest.json`, `validation/layout_report.json`, `validation/feature_registry.json`.
- Writes: fixed authoring truth or derived artifacts, refreshed validation report, current context.
- Forbidden writes: do not mark success by editing validation JSON alone.
- Validation expectations: rerun the failing validation plus any directly affected gates.

## Artifact Directory

- `brief.md`: short human summary of purpose, current direction, key confirmed intent, and pointers. No open questions, long requirements, parameter tables, bbox details, validation evidence, history, or diagnostics.
- `spec/current.yaml`: structured authoring contract for project identity, units, coordinate system, inputs, placements, features, formal constraints, decisions, validation targets, source/output/review pointers, and lifecycle state.
- `parameters.yaml`: parameter values, units, bounds, steps, geometry impact, review exposure metadata, and preview binding metadata.
- `source/model.py`: executable build123d construction and deterministic output generation from specs and parameters.
- `validation/current_context.json`: compact first-read digest for continuing the project, usually generated by `scripts/summarize_model_project.py`.
- `validation/feature_registry.json`: optional feature index mapping feature ids to parts, source anchors, parameters, review refs, bbox/points, validation targets, adapter involvement, and warnings. It is an index, not a second CAD implementation.
- `validation/layout_report.json`: generated layout facts such as placements, transformed bboxes, clearances, alignments, generated feature bboxes, and computed dimensions.
- `validation/report.json`: validation status, checks, errors, warnings, freshness evidence, and current snapshot hashes.
- `review/index.html`: bundled review UI template.
- `review/manifest.json`: preview model, parts, refs, exposed live-preview parameters, and optional adapter configuration.
- `review/annotations.json`: user-authored review requests only.
- `review/parameter_patch.json`: saved review slider changes waiting for backend regeneration.
- `review/cache/*`: derived preview mesh and optional adapter assets; never CAD truth.
- `outputs/step/*`: CAD exchange output plus `outputs/step/manifest.json` freshness state.
- `outputs/handoff/*`: optional whitelisted release package artifacts.
- `checkpoints/preview_previous/`: previous visible preview revision for default one-step rollback.
- `previous/`: coarse whole-attempt compatibility snapshot.

## Controlled Modeling Intent Templates

### New Model

```text
Purpose:
Units and coordinate system:
Fixed components and sources:
Generated parts:
Interfaces, openings, contact faces, mounting features:
Layout constraints and clearances:
Adjustable parameters:
Validation targets:
Manufacturing or handoff assumptions, if geometry-relevant:
```

### Geometry Feature

```text
Feature:
Target:
Purpose:
Reference:
Operation:
Shape:
Dimensions:
Placement:
Direction:
Scope:
Preserve:
Adjustable:
Validation:
```

### Constraint

```text
Constraint:
Subject:
Reference:
Relation:
Value:
Priority:
Validation:
```

### Assembly Alignment

```text
Placement:
Source component:
Reference feature:
Target feature:
Rotation:
Alignment rules:
Validation:
```

### Parameterization

```text
Parameter:
Feature:
Unit:
Current value:
Allowed range:
Step:
Review exposure:
Preview behavior:
Reason:
Validation:
```

## Review Annotation Clarity Gate

Before consuming `review/annotations.json`, check whether every actionable annotation is clear on these dimensions:

- target: part, face, edge, hole, feature, component, or global region;
- operation: add, remove, move, resize, cut, fillet, chamfer, align, offset, avoid, preserve, or parameterize;
- reference: selected ref, drawing dimension, STEP feature, existing edge/face/axis, or named component;
- direction: X/Y/Z, normal, radial, axial, inward/outward, or toward/away from a reference;
- dimensions: numeric values, units, ranges, tolerance, or named parameter;
- scope: one selected feature, all same-type features, one part, or whole model;
- preserve: constraints, placements, features, or outputs that must not change;
- validation: how correctness will be checked.

If any of these are unclear and multiple interpretations are reasonable, ask a clarifying question before modeling. If there is one low-risk interpretation, proceed only after recording the assumption in `spec/current.yaml` decisions/constraints or `validation/current_context.json`, and report it. Assembly fit, holes, clearances, coordinate directions, collision risk, and manufacturability are not low-risk by default.
