# Model Project

## Purpose

A model project is the durable working area for one selected part or assembly direction. It should let a future agent understand the intent, regenerate the STEP output, inspect validation evidence, and continue iteration without relying on chat history.

## Default Layout

```text
<model-project>/
  brief.md
  AGENTS.md
  spec/
    current.yaml
  parameters.yaml
  inputs/
  source/
    model.py
  outputs/
    step/
  validation/
  review/
    index.html
    manifest.json
    annotations.json
    parameter_patch.json
    cache/
  previous/
```

## Artifact Roles

- `brief.md`: human-readable goal, constraints, assumptions, and selected direction.
- `AGENTS.md`: project-local routing instructions that tell future Codex sessions to use `$engineering-3d-modeling`, preserve the templated review HTML, check dependencies, and validate project structure.
- `spec/current.yaml`: structured root contract for the selected model or assembly. Complex assemblies may reference same-project sub-specs.
- `parameters.yaml`: adjustable dimensions, tolerances, formulas, bounds, and UI metadata.
- `inputs/`: drawings, photos, datasheets, legacy scripts, STEP references, and fixed-component files.
- `source/`: build123d implementation that generates CAD from the spec and parameters.
- `outputs/step/`: committed CAD output. Use STEP, not STL/3MF/G-code, as the model deliverable.
- `validation/`: reports for build, export, dimensions, clearances, collisions, and review evidence.
- `review/`: HTML review surface, preview cache, structured annotations, and parameter patches.
- `previous/`: one prior accepted state for rollback and current-vs-previous comparison.

## Current And Previous

Keep revision management lightweight:

1. The root project state is always the current working state.
2. Before replacing an accepted current result, copy the current artifacts to `previous/`.
3. Rollback means restoring `previous/` manually or with project-specific tooling.
4. Do not maintain rejected design branches in the model project by default.
5. Use outer Git or workspace history when heavier version management is needed.

The `previous/` copy should include the prior brief, specs, parameters, source, STEP outputs, validation, and review artifacts. It should not include derived caches unless they are useful for comparison and small enough to keep.

Use `scripts/roll_revision.py --dry-run` before rolling when unsure what will be replaced. The script should not overwrite a populated `previous/` slot unless `--force` is passed explicitly.

After a review cycle, prefer `scripts/regenerate_from_review.py` to apply parameter patches to `parameters.yaml`, regenerate CAD, sync review parameters, validate, and clear consumed review state after success. Convert user annotations into the spec/source changes they request before passing `--clear-annotations`. Do not carry consumed annotations forward into the next current review.

## Spec Granularity

Use one `spec/current.yaml` for simple models. Split into same-project sub-specs only when the model has independent reviewable domains, such as:

- fixed components and envelopes,
- layout and constraints,
- generated shell/enclosure parts,
- ducting or airflow geometry,
- simple mechanisms or gear trains,
- electronics mounting,
- validation targets.

`spec/current.yaml` remains the root contract and should list every referenced sub-spec.

## Completion Standard

A V1 iteration is complete only when it has:

- an updated brief, project-level `AGENTS.md`, spec, parameters, and build123d source;
- generated STEP output, usually one assembly STEP for assemblies;
- per-part STEP only when requested or useful;
- validation evidence for build/export plus relevant dimensions and assembly relationships;
- an HTML review artifact or a lightweight snapshot/review note;
- a preserved previous accepted state when replacing prior accepted output.
