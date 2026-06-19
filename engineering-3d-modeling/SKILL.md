---
name: engineering-3d-modeling
description: Use when creating, initializing, modifying, reviewing, validating, or exporting engineering-style 3D CAD model projects from natural language, dimensioned CAD drawings, qualitative photo references, existing CAD/modeling scripts, STEP/STP files, or fixed-component assembly requests. Guides build123d-first workflows that preserve editable specs, parameters, source, validation, STEP output, templated HTML review UI, local review-server saves, dependency checks, and structured annotations. Not for slicers, STL/3MF/G-code, print settings, simulation, animation, rendering, mesh art, or industrial-design sculpting.
---

# Engineering 3D Modeling

## Core Contract

This skill turns an engineering CAD request into a maintainable model project, not a one-shot model file. The durable truth is the project brief, `spec/current.yaml`, `parameters.yaml`, build123d source, validation evidence, review data, and committed STEP output.

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
5. Before replacing an accepted current result, preserve the previous state with the two-slot `current`/`previous` scheme.
6. When continuing from HTML review, prefer `scripts/regenerate_from_review.py` to apply `review/parameter_patch.json`, rebuild backend CAD, sync review parameters, clear consumed review state, and validate. Treat `review/annotations.json` as user-authored requests only; convert consumed annotations into spec/parameter/source changes before passing `--clear-annotations`. If running steps manually, apply parameter patches before regeneration and clear current review state only after validation passes.
7. Generate or modify build123d source from the spec and parameters.
8. Export STEP as the committed model output. For assemblies, export one assembly STEP by default; export per-part STEP only when requested or useful for inspection/handoff.
9. Validate build success, STEP export, key dimensions, clearances, assembly relationships, review mesh sanity, and part-vs-feature grouping where relevant.
10. Update review artifacts: HTML review surface when available, otherwise a snapshot or review note. Sync only explicit live-preview-bound parameters from `parameters.yaml` into `review/manifest.json` with `scripts/sync_review_parameters.py`. Save parameter patches and annotation records as structured review data.

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

## HTML Review Boundary

V1 HTML review may support:

- STEP or derived preview display.
- Parameter controls only for simple, safe parameters with explicit live preview bindings, such as wall thickness, fillets, clearances, lengths, hole diameters, thread specs, chamfers, shell thickness, and rib counts when the preview effect is known to be model-appropriate. Numeric review parameters must render as sliders. Do not infer preview behavior from parameter names, labels, or roles.
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
- `references/validation.md`: V1 validation gates and report expectations.

## Bundled Scripts

- `scripts/check_environment.py`: check build123d and PyYAML availability; with `--install`, install missing packages into the active Python environment. Run it with the same Python runtime that will execute the model source.
- `scripts/apply_parameter_patch.py`: validate and merge saved HTML parameter patches into `parameters.yaml` before backend regeneration. Patches must reference parameters exposed in `review/manifest.json`, remain editable in `parameters.yaml`, and pass type, unit, bounds, and step checks.
- `scripts/init_model_project.py`: scaffold a lightweight model project.
- `scripts/regenerate_from_review.py`: apply saved review parameter patches, rebuild `source/model.py`, sync review sliders, validate STEP and parameter-to-geometry smoke, then clear consumed review state after success.
- `scripts/reset_review_state.py`: clear current annotations and parameter patches after the agent consumes them into the next model revision.
- `scripts/roll_revision.py`: copy the accepted current state into `previous/` before regeneration; use `--dry-run` to inspect, and `--force` is required before overwriting a populated `previous/`.
- `scripts/sync_review_parameters.py`: sync only explicit live-preview-bound `parameters.yaml` entries into `review/manifest.json` for HTML sliders.
- `scripts/validate_model_project.py`: check required files, bundled JSON schemas, review data, patch domain rules, STEP presence, parameter-to-geometry smoke when requested, and forbidden downstream outputs.
- `scripts/serve_review.py`: serve a model project's review UI and safely write `review/annotations.json` plus `review/parameter_patch.json` only after schema and parameter-domain validation passes.

Run scripts from the skill directory or pass absolute paths. They use only the Python standard library.

## Non-Goals

Do not use this skill for STL/3MF/G-code/Bambu/slicer workflows, printer/material settings, simulation, animation, photoreal rendering, freeform mesh sculpting, or industrial-design-grade surfacing. Do not treat mesh reverse engineering as solved in V1.
