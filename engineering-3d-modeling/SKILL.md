---
name: engineering-3d-modeling
description: Use when creating, initializing, modifying, reviewing, validating, or exporting engineering-style 3D CAD model projects from natural language, dimensioned CAD drawings, qualitative photo references, existing CAD/modeling scripts, STEP/STP files, or fixed-component assembly requests. Guides build123d-first workflows that preserve editable specs, parameters, source, validation, STEP output, templated HTML review UI, local review-server saves, dependency checks, and structured annotations. Not for slicers, STL/3MF/G-code, print settings, simulation, animation, rendering, mesh art, or industrial-design sculpting.
---

# Engineering 3D Modeling

## Core Contract

This skill turns an engineering CAD request into a maintainable model project, not a one-shot model file. Keep three artifact layers separate:

- Authoring truth: the project brief, `spec/current.yaml`, `parameters.yaml`, build123d source or formula modules, and validation evidence.
- CAD exchange/delivery output: STEP under `outputs/step/` plus `outputs/step/manifest.json`. STEP files may exist in draft, but accepted/release STEP semantics require promotion-gate manifest state.
- Review artifacts: `review/index.html`, `review/manifest.json`, `review/cache/`, `review/annotations.json`, and `review/parameter_patch.json`. These are review data, not CAD truth.

Use build123d as the default local CAD backend. Other backends are allowed only when the user explicitly asks for them or an existing project already depends on them.

## First Moves

1. Classify the request:
   - Natural language: extract object, purpose, units, constraints, and assumptions.
   - Dimensioned CAD drawing: treat dimensions, callouts, and structure as precise requirements.
   - Photo: treat as qualitative form or structural reference unless independent dimensions are supplied.
   - Existing source: preserve it under project inputs, then extract durable intent into specs and parameters.
   - STEP/STP: use as CAD reference or fixed component; do not claim it preserves parametric history.
   - STL/OBJ/mesh: reference-only in V1.
2. Create or continue exactly one active model or assembly direction. Alternative concepts may be discussed before selection, but only the selected direction becomes the active model project.
3. For new projects, run `scripts/init_model_project.py`; do not hand-roll the scaffold or review HTML. The script creates `review/index.html` from the bundled template and a project-level `AGENTS.md` to keep future sessions on this skill.
4. Before build123d generation or validation, run `scripts/check_environment.py --json` with the same Python runtime that will execute `source/model.py`. If build123d or PyYAML is missing, immediately rerun with `--install`; request permission if pip, network, or environment writes are blocked. Do not continue CAD generation while required dependencies are missing.
5. Before any real iteration that will consume saved review data or modify authoring truth/derived outputs, run `scripts/begin_model_iteration.py`. It copies the current authoring truth and outputs into `previous/`, records `validation/iteration.json`, and changes `accepted_current` or `release_handoff` projects back to `draft_review`.
6. When continuing from HTML review, prefer `scripts/regenerate_from_review.py --start-new-iteration` if `review/parameter_patch.json` or `review/annotations.json` is non-empty and no active iteration exists. Treat `review/annotations.json` as user-authored requests only; convert consumed annotations into spec/parameter/source changes before passing `--clear-annotations`. If running steps manually, begin the iteration first, apply parameter patches before regeneration, and clear current review state only after validation passes.
7. Generate or modify build123d source from the spec and parameters.
8. Draft iterations may generate STEP, but only as draft STEP. Ordinary regeneration must not declare accepted/release output and must not leave a promoted STEP manifest attached to a draft project.
9. Do not manually edit `lifecycle.phase` to claim completion. Promote lifecycle state with `scripts/promote_model_project.py`, which blocks unconsumed review annotations, unapplied parameter patches, missing or draft STEP manifest state, direct draft-to-release skips unless explicitly allowed, and unaccepted backend overrides.
10. Validate build success, phase-appropriate STEP manifest state, key dimensions, clearances, assembly relationships, review mesh sanity, part-vs-feature grouping, and handoff/current consistency where relevant. Use `scripts/validate_model_project.py --require-step` for forced delivery checks regardless of phase, and `--strict-consistency` before accepted/release handoff when `validation/report.json` should prove the current snapshot.
11. Update review artifacts: HTML review surface when available, otherwise a snapshot or review note. Sync only explicit live-preview-bound parameters from `parameters.yaml` into `review/manifest.json` with `scripts/sync_review_parameters.py`, then audit exposed parameters with `scripts/audit_review_parameters.py` when geometry or preview behavior changed. Save parameter patches and annotation records as structured review data.

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
```

Complex assemblies may keep `spec/current.yaml` as a root manifest and reference same-project sub-specs by reviewable domain, such as fixed components, layout, shell, mechanism, electronics mounting, and validation. Do not introduce cross-project reuse in V1.

`spec/current.yaml` should record `lifecycle.phase`:

- `draft_review`: authoring truth plus review artifacts may exist without STEP; this is not complete.
- `accepted_current`: current result is accepted and should have STEP.
- `release_handoff`: handoff/release check; STEP is required and validation should be strict.
- `backend_override`: temporary non-default backend state, such as Fusion 360 API. Record `backend.override` with backend/name and reason; do not treat this as the default authoring truth shape.

Move from `draft_review` to `accepted_current`, and from `accepted_current` to `release_handoff`, only through `scripts/promote_model_project.py`. If a phase is missing or invalid, the promotion script treats it as `draft_review` with a warning; failed promotions restore the original phase and validation report.

## HTML Review Boundary

V1 HTML review may support:

- STEP or derived preview display.
- Parameter controls only for simple, safe parameters with explicit live preview bindings, such as global dimensions, uniform offsets, and formula-backed values when the preview effect is known to be model-appropriate. Numeric review parameters must render as sliders. Do not infer preview behavior from parameter names, labels, or roles.
- Do not bind localized engineering features such as chamfers, fillets, holes, mounts, connector cutouts, PCB or battery clearances, base positions, ribs, slots, threads, or layout positions to `preview.effect: "generic_morph"`. Use `preview.effect: "adapter"` with a model-specific preview adapter, or keep the parameter backend-only until regeneration. Any intentional `generic_morph` must declare `preview.scope`, `preview.feature_refs`, or `preview.rationale` so audit can distinguish it from a placeholder.
- Equation-driven projects may opt into a model-specific `preview.adapter_js` formula preview adapter. Use this when real-time review must regenerate a derived preview mesh from the same model formulas, such as guide-vane count, airfoil thickness, or camber angle. Adapter-backed parameters use `preview.effect: "adapter"` and still save patches for backend regeneration; the adapter is preview-only and must not replace build123d validation or accepted/release STEP output.
- Canvas-attached assembly part show/hide and isolate controls.
- Annotation records with editable text and optional snapped refs for parts, faces, edges, vertices, and named features.
- One save action that writes review data through the local review server when direct local-file persistence is needed.
- Optional current-vs-previous comparison.

V1 HTML review must not provide a natural-language modeling input box, direct topology editing, lasso/freehand markup, exploded-view requirements, slicer controls, or print settings. Saved HTML changes are review data or parameter patches; the backend must regenerate and validate CAD before they become model truth.

For single-part projects, use one manifest part at most; group subregions with `feature_id`, not multiple `part_id` values. Use multiple manifest parts only for assemblies or genuinely separate generated parts.

## Resource Routing

Read only the references needed for the task:

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
- `scripts/init_model_project.py`: scaffold a lightweight model project.
- `scripts/begin_model_iteration.py`: create the one-step rollback snapshot under `previous/`, return accepted/release projects to `draft_review`, record active iteration metadata, and mark existing STEP as draft/stale before authoring truth changes.
- `scripts/promote_model_project.py`: transactional lifecycle promotion gate. It promotes only `draft_review -> accepted_current -> release_handoff`, writes accepted/release STEP manifest state, refreshes `validation/report.json`, and emits human plus JSON output.
- `scripts/regenerate_from_review.py`: apply saved review parameter patches, rebuild `source/model.py`, sync and audit review sliders, validate draft/current state, mark generated STEP as draft, and clear consumed review state after success. It fails on pending review data or accepted/release phases unless an iteration has already begun or `--start-new-iteration` is passed.
- `scripts/restore_previous.py`: restore the whole current model-project snapshot from `previous/`; default output is dry-run and `--force` is required to write.
- `scripts/reset_review_state.py`: clear current annotations and parameter patches after the agent consumes them into the next model revision.
- `scripts/roll_revision.py`: compatibility alias for copying the current state into `previous/`; prefer `begin_model_iteration.py` for new iteration work.
- `scripts/sync_review_parameters.py`: sync only explicit live-preview-bound `parameters.yaml` entries into `review/manifest.json` for HTML sliders; command-line use audits synced parameters by default.
- `scripts/validate_model_project.py`: check required files, bundled JSON schemas, review data, patch domain rules, phase-aware STEP presence, review parameter audit, handoff/current consistency audit for `release_handoff` or `--strict-consistency`, parameter-to-geometry smoke when requested, and forbidden downstream outputs. `--require-step` forces a delivery check.
- `scripts/serve_review.py`: serve one model project's review UI and safely write `review/annotations.json` plus `review/parameter_patch.json` only after schema and parameter-domain validation passes. Use `--port 0` when multiple review projects may run at once; the script prints the actual assigned URL.

Run scripts from the skill directory or pass absolute paths. They use only the Python standard library.

## Non-Goals

Do not use this skill for STL/3MF/G-code/Bambu/slicer workflows, printer/material settings, simulation, animation, photoreal rendering, freeform mesh sculpting, or industrial-design-grade surfacing. Do not treat mesh reverse engineering as solved in V1.
