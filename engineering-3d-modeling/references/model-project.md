# Model Project

## Purpose

A model project is the durable working area for one selected part or assembly direction. It should let a future agent understand the intent, regenerate the authoring truth, iterate through visible preview revisions, export fresh STEP on demand, inspect validation evidence, and continue without relying on chat history.

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
      manifest.json
  validation/
  review/
    index.html
    manifest.json
    annotations.json
    parameter_patch.json
    cache/
  previous/
  checkpoints/
    preview_previous/
```

## Artifact Roles

- `brief.md`: human-readable goal, constraints, assumptions, and selected direction.
- `AGENTS.md`: project-local routing instructions that tell future Codex sessions to use `$engineering-3d-modeling`, preserve the templated review HTML, check dependencies, and validate project structure.
- `spec/current.yaml`: structured root contract for the selected model or assembly. Complex assemblies may reference same-project sub-specs. It should include `lifecycle.phase`.
- `parameters.yaml`: adjustable dimensions, tolerances, formulas, bounds, and UI metadata.
- `inputs/`: drawings, photos, datasheets, legacy scripts, STEP references, and fixed-component files.
- `source/`: build123d implementation that generates CAD from the spec and parameters.
- `outputs/step/`: CAD exchange/delivery output plus `manifest.json`. Use STEP, not STL/3MF/G-code, as the model deliverable. `scripts/export_step.py` writes fresh direct exports with `state: "exported"` and `stale: false`.
- `outputs/handoff/`: optional handoff package zips and their manifests.
- `validation/`: reports for build, export, dimensions, clearances, collisions, and review evidence.
- `review/`: HTML review surface, preview cache, structured annotations, and parameter patches. These are review artifacts, not CAD truth.
- `checkpoints/preview_previous/`: lightweight checkpoint of the previous visible preview revision. This is the default target for "go back one version."
- `previous/`: coarse whole-attempt rollback snapshot. It remains for compatibility and larger iteration safety, not for default one-preview-step rollback.

Authoring truth is the brief, spec, parameters, source or formula modules, and validation evidence. STEP is generated from that truth for CAD exchange/delivery. Review artifacts are derived feedback and preview data until an agent converts them into spec, parameter, or source changes.

## Work State And Legacy Lifecycle

New projects may still record a coarse work state in `spec/current.yaml`:

```yaml
lifecycle:
  phase: draft_review
```

Use these values as compatibility/work-state labels:

- `draft_review`: authoring truth and review artifacts are being developed. STEP may be missing, but the state is not complete or accepted.
- `accepted_current`: legacy accepted-baseline marker. Do not require it before direct STEP export.
- `release_handoff`: legacy release marker. New handoffs are package snapshots created by `scripts/create_handoff_package.py`.
- `backend_override`: a temporary non-default solid backend is being used. Record `backend.override` with backend/name and reason, for example when a Fusion 360 API script is used as a temporary backend. This is not the default truth shape.

## Direct STEP Export

When the user is satisfied with the current preview, export STEP directly:

```bash
python3 engineering-3d-modeling/scripts/export_step.py /path/to/model-project
```

The export command fails when `review/parameter_patch.json` or `review/annotations.json` contains unconsumed review data. It then runs the current authoring source, verifies STEP output, writes `outputs/step/manifest.json`, and refreshes validation evidence.

## Optional Handoff Package

Handoff is a packaging action, not a required day-to-day state transition:

```bash
python3 engineering-3d-modeling/scripts/create_handoff_package.py /path/to/model-project
```

The command performs strict consistency checks and creates `outputs/handoff/<model-name>-<timestamp>.zip`. The zip includes only deliverable, reproducible, readable artifacts such as STEP, handoff manifest, README, specs, parameters, source, validation report, review HTML, review manifest, and current preview mesh. It must not include `previous/`, `checkpoints/`, pending review data, private raw inputs unless explicitly allowed, temporary caches, tests, or research notes.

## Compatibility Promotion

`scripts/promote_model_project.py` remains for older projects that explicitly use `accepted_current` and `release_handoff`. It is transactional and should still be used instead of editing lifecycle phase by hand when maintaining that old flow. New daily modeling should not require accept/handoff promotion before exporting STEP.

## Iteration, Current, And Previous

Keep revision management lightweight:

1. The root project state is always the current working state.
2. Before any operation that will change the HTML-visible preview model, save a preview checkpoint with `scripts/checkpoint_preview_revision.py --reason "..."`. `scripts/regenerate_from_review.py` does this automatically.
3. "Go back one version" means dry-run then restore the preview checkpoint with `scripts/restore_preview_revision.py` and `scripts/restore_preview_revision.py --force`.
4. "Undo the whole modeling attempt" means restore `previous/` with `scripts/restore_previous.py --force`; that command defaults to dry-run.
5. `scripts/begin_model_iteration.py` remains available for coarse safety. It copies the current brief, specs, parameters, source, outputs, validation, and review artifacts into `previous/`; writes `validation/iteration.json`; and marks any existing STEP manifest stale.
6. Do not maintain rejected design branches in the model project by default.
7. Use outer Git or workspace history when heavier version management is needed.

The `previous/` copy should include the prior brief, specs, parameters, source, STEP outputs, validation, and review artifacts, including review cache files when they are part of the current preview/review state.

Use `scripts/begin_model_iteration.py --dry-run` before starting when unsure what will be replaced. It should not overwrite a populated `previous/` slot unless `--force` is passed explicitly. `scripts/roll_revision.py` remains a compatibility alias for direct snapshotting.

After a review cycle, prefer `scripts/regenerate_from_review.py` to apply parameter patches to `parameters.yaml`, checkpoint the previous preview, regenerate CAD or review previews, sync review parameters, validate the work/review state, mark existing STEP stale, and clear consumed review state after success. Convert user annotations into the spec/source changes they request before passing `--clear-annotations`. Do not carry consumed annotations forward into the next current review. Pass `--start-new-iteration` only when you also want the coarse `previous/` snapshot.

## STEP Manifest

`outputs/step/manifest.json` records STEP state:

```json
{
  "schema": "engineering-3d-modeling.step_manifest.v1",
  "state": "exported",
  "generated_for_phase": "draft_review",
  "generated_at": "2026-06-20T00:00:00Z",
  "generated_by": "scripts/regenerate_from_review.py",
  "promoted_by": null,
  "stale": false,
  "source_hash": "...",
  "parameters_hash": "...",
  "spec_hash": "...",
  "review_mesh_hash": "...",
  "step_files": [{"path": "outputs/step/example.step", "sha256": "..."}]
}
```

Allowed states are `draft`, `exported`, `accepted_current`, and `release_handoff`. `exported` is the recommended direct daily STEP output. `accepted_current` and `release_handoff` are legacy promoted states written by `scripts/promote_model_project.py`. Any later authoring-truth or visible-preview change should mark the manifest `stale: true`.

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

## Phase Completion Standards

A work/review iteration may stop before STEP only when it has:

- updated authoring truth: brief, project-level `AGENTS.md`, spec, parameters, and source or formula modules;
- review artifacts or notes sufficient for the next feedback pass;
- validation evidence explaining that STEP is deferred because the phase is `draft_review`.

Do not call a work/review state release-ready or handed off.

A directly exported current STEP state is usable only when it has:

- updated authoring truth;
- generated STEP output plus fresh `outputs/step/manifest.json` with `state: "exported"` and `stale: false`, usually one assembly STEP for assemblies;
- per-part STEP only when requested or useful;
- validation evidence for build/export plus relevant dimensions and assembly relationships;
- an HTML review artifact or a lightweight snapshot/review note;
- a preview checkpoint when the visible preview changed during the iteration.

An optional handoff is complete only after `scripts/create_handoff_package.py` succeeds and produces a zip plus handoff manifest. A passing `validate_model_project.py` run is useful evidence, but it is not by itself a handoff package.
