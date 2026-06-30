---
name: engineering-3d-modeling
description: Use when creating, initializing, modifying, reviewing, validating, or exporting engineering-style 3D CAD model projects from natural language, dimensioned CAD drawings, qualitative photo references, existing CAD/modeling scripts, STEP/STP files, or fixed-component assembly requests. Guides build123d-first workflows that preserve editable specs, parameters, source, validation, STEP output, templated HTML review UI, local review-server saves, dependency checks, and structured annotations. Not for slicers, STL/3MF/G-code, print settings, simulation, animation, rendering, mesh art, or industrial-design sculpting.
---

# Engineering 3D Modeling

## Core Contract

This skill turns an engineering CAD request into a maintainable model project, not a one-shot model file. Keep three artifact layers separate:

- Authoring truth: the project brief, `spec/current.yaml`, `parameters.yaml`, build123d source or formula modules, and validation evidence.
- CAD exchange/delivery output: STEP under `outputs/step/` plus `outputs/step/manifest.json` after explicit export. A fresh direct export has manifest `state: "exported"` and `stale: false`; later authoring-truth or preview changes mark it stale until `scripts/export_step.py` is rerun.
- Review artifacts: `review/index.html`, `review/manifest.json`, `review/cache/`, `review/annotations.json`, and `review/parameter_patch.json`. These are review data, not CAD truth.

Use build123d as the default local CAD backend. Other backends are allowed only when the user explicitly asks for them or an existing project already depends on them.

Daily CAD modeling is a continuous loop: adjust, preview, then adjust again. Before any operation that will change the visible HTML preview model, save a lightweight preview revision checkpoint. "Go back one version" means restoring that preview checkpoint. `previous/` remains a coarse compatibility snapshot for undoing a whole modeling attempt.

Use `references/context-routing.md` for detailed task tags, minimum reads, artifact boundaries, controlled modeling intent templates, and the review annotation clarity gate. Keep `SKILL.md` as the concise workflow router.

## First Moves

1. Classify the request:
   - Natural language: extract object, purpose, units, constraints, and assumptions.
   - Dimensioned CAD drawing: treat dimensions, callouts, and structure as precise requirements.
   - Photo: treat as qualitative form or structural reference unless independent dimensions are supplied.
   - Existing source: preserve it under project inputs, then extract durable intent into specs and parameters.
   - STEP/STP: use as CAD reference or fixed component; do not claim it preserves parametric history.
   - STL/OBJ/mesh: reference-only in V1.
2. Create or continue exactly one active model or assembly direction. Alternative concepts may be discussed before selection, but only the selected direction becomes the active model project.
3. For new projects, run `scripts/init_model_project.py`; do not hand-roll the scaffold or review HTML. The script creates `review/index.html` from the bundled template and a project-level `AGENTS.md` to keep future sessions on this skill. New projects start as `draft_review`: build source and review/preview artifacts first, and do not export STEP until the user confirms the preview or explicitly asks for STEP.
4. For existing projects, start from project `AGENTS.md`, then `validation/current_context.json` or `scripts/summarize_model_project.py`. Use `references/context-routing.md` task tags to choose the exact next reads instead of loading history by default.
5. Before build123d generation or validation, run `scripts/check_environment.py --json` with the same Python runtime that will execute `source/model.py`. If build123d or PyYAML is missing, immediately rerun with `--install`; request permission if pip, network, or environment writes are blocked. Do not continue CAD generation while required dependencies are missing.
6. Before any preview-changing edit, run `scripts/checkpoint_preview_revision.py --reason "..."` or use a workflow script that does it automatically. This saves `checkpoints/preview_previous/` and `validation/preview_revision.json`.
7. When continuing from HTML review, prefer `scripts/regenerate_from_review.py`. It checkpoints the current visible preview, applies `review/parameter_patch.json`, rebuilds from `source/model.py`, syncs/audits preview sliders, validates the work/review state, marks existing STEP stale, clears consumed review state after success, and refreshes current context where possible. Treat `review/annotations.json` as user-authored requests only; if target, operation, reference, direction, dimensions, scope, preserve rules, or validation are unclear, use the clarity gate in `references/context-routing.md` before modeling.
8. Generate or modify build123d source from the spec and parameters. Running `source/model.py` directly is a build or preview-regeneration smoke path, not the STEP export path.
9. When the user is satisfied with the preview, export usable STEP directly with `scripts/export_step.py`. This fails if current review patches or annotations are unconsumed, regenerates STEP from current `spec/current.yaml`, `parameters.yaml`, and `source/model.py`, validates the export, and writes a fresh `outputs/step/manifest.json`.
10. Create a delivery/release bundle only when requested with `scripts/create_handoff_package.py`. Handoff is an optional package action, not a required day-to-day state promotion.
11. Validate source interface, spec-to-code coverage, build success, fresh STEP when requested, key dimensions, clearances, assembly relationships, review mesh sanity/provenance, part-vs-feature grouping, and strict package consistency where relevant. Use `scripts/validate_model_project.py --require-step` for forced delivery checks and `scripts/audit_project_consistency.py --mode strict` before package creation or release claims.
12. Update review artifacts: HTML review surface when available, otherwise a snapshot or review note. Sync only explicit live-preview-bound parameters from `parameters.yaml` into `review/manifest.json` with `scripts/sync_review_parameters.py`, then audit exposed parameters with `scripts/audit_review_parameters.py` when geometry or preview behavior changed. Save parameter patches and annotation records as structured review data.

## Project Shape

Use this default model-project layout unless an existing project already has a compatible structure:

```text
brief.md
AGENTS.md
spec/current.yaml
parameters.yaml
inputs/
source/model.py
outputs/step/
validation/
review/
previous/
checkpoints/
```

Complex assemblies may keep `spec/current.yaml` as a root manifest and reference same-project sub-specs by reviewable domain, such as fixed components, layout, shell, mechanism, electronics mounting, and validation. Do not introduce cross-project reuse in V1.

`spec/current.yaml` may record `lifecycle.phase` for compatibility and coarse work state:

- `draft_review`: authoring truth plus review artifacts may exist without STEP; this is not complete.
- `accepted_current`: legacy accepted-baseline marker; no longer required before STEP export.
- `release_handoff`: legacy release marker; handoff packages are now created by `scripts/create_handoff_package.py`.
- `backend_override`: temporary non-default backend state, such as Fusion 360 API. Record `backend.override` with backend/name and reason; do not treat this as the default authoring truth shape.

Do not force routine modeling through `accepted_current` or `release_handoff`. Treat them as legacy compatibility labels for old projects. The recommended path is preview checkpointing, regeneration, direct STEP export after preview confirmation, and optional handoff package creation.

## HTML Review Boundary

V1 HTML review may support:

- STEP or derived preview display.
- Parameter controls only for simple, safe parameters with explicit live preview bindings, such as global dimensions, uniform offsets, and formula-backed values when the preview effect is known to be model-appropriate. Numeric review parameters must render as sliders. Do not infer preview behavior from parameter names, labels, or roles.
- Do not bind localized engineering features such as chamfers, fillets, holes, mounts, connector cutouts, PCB or battery clearances, base positions, ribs, slots, threads, or layout positions to `preview.effect: "generic_morph"`. Use `preview.effect: "adapter"` with a model-specific preview adapter, or keep the parameter backend-only until regeneration. Any intentional `generic_morph` must declare `preview.scope`, `preview.feature_refs`, or `preview.rationale` so audit can distinguish it from a placeholder.
- Equation-driven projects may opt into a model-specific `preview.adapter_js` formula preview adapter. Use this when real-time review must regenerate a derived preview mesh from the same model formulas, such as guide-vane count, airfoil thickness, or camber angle. Adapter-backed parameters use `preview.effect: "adapter"` and still save patches for backend regeneration; the adapter is preview-only and must not replace build123d validation or direct STEP export.
- Canvas-attached assembly part show/hide and isolate controls.
- Annotation records with editable text and optional precise snapped refs for parts, faces, CAD edges, vertices, and named features; review HTML should display clean CAD-style edges by default without exposing mesh wireframe/debug modes.
- One save action that writes review data through the local review server when direct local-file persistence is needed.
- Optional current-vs-previous comparison.

V1 HTML review must not provide a natural-language modeling input box, direct topology editing, lasso/freehand markup, exploded-view requirements, slicer controls, or print settings. Saved HTML changes are review data or parameter patches; the backend must regenerate and validate CAD before they become model truth.

For single-part projects, use one manifest part at most; group subregions with `feature_id`, not multiple `part_id` values. Use multiple manifest parts only for assemblies or genuinely separate generated parts.

## Resource Routing

Read only the references needed for the task:

- `references/context-routing.md`: global context routing, composable task tags, artifact boundaries, controlled intent templates, and review annotation clarity gate.
- `references/model-project.md`: project structure, artifact roles, current/previous revision handling, completion standard.
- `references/inputs.md`: precision rules for natural language, drawings, photos, STEP/STP, meshes, and existing scripts.
- `references/build123d-patterns.md`: source structure and STEP export conventions.
- `references/assemblies-and-layout.md`: fixed components, layout specs, generated parts, gear trains, and assembly validation.
- `references/formulas.md`: equation-driven curves, profiles, and formula validation.
- `references/review-html.md`: review manifest, parameter patches, selector refs, and annotation data.
- `references/validation.md`: V1 validation gates, current/handoff consistency audit, and report expectations.

## Bundled Scripts

- `scripts/check_environment.py`: check build123d and PyYAML availability; with `--install`, install missing packages into the active Python environment. Run it with the same Python runtime that will execute the model source.
- `scripts/apply_parameter_patch.py`: validate and merge saved HTML parameter patches into `parameters.yaml` before backend regeneration. Patches must reference parameters exposed in `review/manifest.json`, remain editable in `parameters.yaml`, and pass type, unit, bounds, and step checks.
- `scripts/audit_review_parameters.py`: audit `parameters.yaml`, `review/manifest.json`, `source/model.py`, preview mesh cache, and optional preview adapter so stale or non-reactive review parameters are hidden or fail validation.
- `scripts/audit_project_consistency.py`: audit `spec/current.yaml`, `brief.md`, `parameters.yaml`, `review/manifest.json`, `review/cache/current_mesh.json`, STEP files, `outputs/step/manifest.json`, and `validation/report.json` for current/handoff drift before accepting or handing off a model project.
- `scripts/checkpoint_preview_revision.py`: save `checkpoints/preview_previous/` plus `validation/preview_revision.json` before a visible preview model change.
- `scripts/audit_spec_coverage.py`: audit declared spec features, placements, constraints, validation targets, and geometry-impacting parameters against source/registry/layout evidence; write `validation/spec_coverage.json` with `--write`.
- `scripts/init_model_project.py`: scaffold a lightweight model project.
- `scripts/begin_model_iteration.py`: optional coarse compatibility safety point that snapshots the whole project under `previous/`, records active iteration metadata, and marks existing STEP stale before a larger modeling attempt.
- `scripts/export_step.py`: explicit STEP export from current authoring truth after preview confirmation or a user export request. It blocks pending review data, imports `source/model.py`, calls `load_parameters()` and `build_model()`, writes STEP under `outputs/step/`, writes `outputs/step/manifest.json` with `state: "exported"` and freshness hashes, and writes validation evidence.
- `scripts/create_handoff_package.py`: optional strict handoff package generator that creates a zip under `outputs/handoff/` from a whitelist of deliverable/reproducible files.
- `scripts/promote_model_project.py`: compatibility lifecycle promotion gate for old `accepted_current` / `release_handoff` projects. Do not use it as the default daily modeling flow.
- `scripts/regenerate_from_review.py`: apply saved review parameter patches, checkpoint the previous visible preview, rebuild `source/model.py`, sync and audit review sliders, validate work/review state, mark existing STEP stale, and clear consumed review state after success. `--start-new-iteration` remains available when a coarse `previous/` snapshot is desired.
- `scripts/restore_preview_revision.py`: restore the previous visible preview revision; default output is dry-run and `--force` is required to write.
- `scripts/restore_previous.py`: restore the whole current model-project snapshot from `previous/`; use for undoing a whole attempt, not the default "go back one version" action. Default output is dry-run and `--force` is required to write.
- `scripts/reset_review_state.py`: clear current annotations and parameter patches after the agent consumes them into the next model revision.
- `scripts/roll_revision.py`: compatibility alias for copying the current state into `previous/`; prefer `begin_model_iteration.py` for new iteration work.
- `scripts/summarize_model_project.py`: produce a compact continuation summary and optionally write `validation/current_context.json`.
- `scripts/sync_review_parameters.py`: sync only explicit live-preview-bound `parameters.yaml` entries into `review/manifest.json` for HTML sliders; command-line use audits synced parameters by default.
- `scripts/validate_model_project.py`: check required files, bundled JSON schemas, review data, patch domain rules, STEP freshness when STEP is required, review parameter audit, explicit consistency audit when requested, parameter-to-geometry smoke when requested, and forbidden downstream outputs. `--require-step` forces a delivery check.
- `scripts/serve_review.py`: serve one model project's review UI and safely write `review/annotations.json` plus `review/parameter_patch.json` only after schema and parameter-domain validation passes. Use `--port 0` when multiple review projects may run at once; the script prints the actual assigned URL.

Run scripts from the skill directory or pass absolute paths. They use only the Python standard library.

## Non-Goals

Do not use this skill for STL/3MF/G-code/Bambu/slicer workflows, printer/material settings, simulation, animation, photoreal rendering, freeform mesh sculpting, or industrial-design-grade surfacing. Do not treat mesh reverse engineering as solved in V1.
