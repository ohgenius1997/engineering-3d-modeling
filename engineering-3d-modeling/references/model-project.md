# Model Project

## Purpose

A model project is the durable working area for one selected part or assembly direction. It should let a future agent understand the intent, regenerate the authoring truth, produce STEP when the phase requires it, inspect validation evidence, and continue iteration without relying on chat history.

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
```

## Artifact Roles

- `brief.md`: human-readable goal, constraints, assumptions, and selected direction.
- `AGENTS.md`: project-local routing instructions that tell future Codex sessions to use `$engineering-3d-modeling`, preserve the templated review HTML, check dependencies, and validate project structure.
- `spec/current.yaml`: structured root contract for the selected model or assembly. Complex assemblies may reference same-project sub-specs. It should include `lifecycle.phase`.
- `parameters.yaml`: adjustable dimensions, tolerances, formulas, bounds, and UI metadata.
- `inputs/`: drawings, photos, datasheets, legacy scripts, STEP references, and fixed-component files.
- `source/`: build123d implementation that generates CAD from the spec and parameters.
- `outputs/step/`: CAD exchange/delivery output plus `manifest.json`. Use STEP, not STL/3MF/G-code, as the model deliverable when the current result is accepted or handed off. STEP files may exist during draft work, but `manifest.json` records whether they are `draft`, `accepted_current`, or `release_handoff`.
- `validation/`: reports for build, export, dimensions, clearances, collisions, and review evidence.
- `review/`: HTML review surface, preview cache, structured annotations, and parameter patches. These are review artifacts, not CAD truth.
- `previous/`: one-step rollback snapshot of the immediately prior current state. It is not an accepted-only slot.

Authoring truth is the brief, spec, parameters, source or formula modules, and validation evidence. STEP is generated from that truth for CAD exchange/delivery. Review artifacts are derived feedback and preview data until an agent converts them into spec, parameter, or source changes.

## Lifecycle Phases

Record the project phase in `spec/current.yaml`:

```yaml
lifecycle:
  phase: draft_review
```

Use these V1 phases:

- `draft_review`: authoring truth and review artifacts are being developed. STEP may be missing, but the state is not complete or accepted.
- `accepted_current`: the current model result has been accepted for ongoing work. STEP should exist under `outputs/step/`.
- `release_handoff`: handoff/release validation. STEP must exist and validation should use strict checks.
- `backend_override`: a temporary non-default solid backend is being used. Record `backend.override` with backend/name and reason, for example when a Fusion 360 API script is used as a temporary backend. This is not the default truth shape.

## Lifecycle Promotion

Do not promote lifecycle state by editing `spec/current.yaml` directly. Use the bundled promotion gate:

```bash
python3 engineering-3d-modeling/scripts/promote_model_project.py /path/to/model-project accepted_current
python3 engineering-3d-modeling/scripts/promote_model_project.py /path/to/model-project release_handoff
```

Promotion is ordered: `draft_review -> accepted_current -> release_handoff`. A direct `draft_review -> release_handoff` attempt must fail unless `--allow-skip-accepted` is passed, and then the script must run both accepted and release gates. Missing or invalid phase values are treated as `draft_review` with a warning, not as accepted evidence.

The `accepted_current` gate requires no unconsumed `review/annotations.json`, no unapplied `review/parameter_patch.json`, current authoring source or existing output capable of providing STEP, and successful validation with STEP required. It updates `spec/current.yaml`, writes `outputs/step/manifest.json` with `state: "accepted_current"` and `promoted_by: "scripts/promote_model_project.py"`, and refreshes `validation/report.json` only after validation passes.

The `release_handoff` gate requires an already accepted current state with strict consistency evidence, STEP output, `outputs/step/manifest.json`, `validation/report.json` snapshot fields such as `generated_at`, phase, source/parameter/review-manifest/mesh/STEP/STEP-manifest hashes or equivalent evidence, and strict agreement among spec, report, manifest, mesh cache, and STEP paths. It then writes `release_handoff`, updates the STEP manifest to `state: "release_handoff"`, refreshes the validation report, and embeds the strict consistency audit.

If `lifecycle.phase: backend_override` or `spec.backend.override` is present, promotion must fail until the override is cleared or the command records an explicit accepted exception with `--accept-backend-override-reason`. Failed promotions restore the original phase, STEP manifest, and validation report; agents must report the JSON and human summary rather than claiming completion manually.

## Iteration, Current, And Previous

Keep revision management lightweight:

1. The root project state is always the current working state.
2. Before consuming saved `review/parameter_patch.json`, consuming `review/annotations.json`, or editing authoring truth/derived outputs, run `scripts/begin_model_iteration.py`.
3. Beginning an iteration copies the current brief, specs, parameters, source, outputs, validation, and review artifacts into `previous/`; writes `validation/iteration.json`; and marks any existing STEP manifest as draft/stale.
4. If the project was `accepted_current` or `release_handoff`, beginning an iteration changes `spec/current.yaml` back to `draft_review` before regeneration or source/spec edits.
5. Rollback means restoring `previous/` with `scripts/restore_previous.py --force`; the command defaults to dry-run.
6. Do not maintain rejected design branches in the model project by default.
7. Use outer Git or workspace history when heavier version management is needed.

The `previous/` copy should include the prior brief, specs, parameters, source, STEP outputs, validation, and review artifacts, including review cache files when they are part of the current preview/review state.

Use `scripts/begin_model_iteration.py --dry-run` before starting when unsure what will be replaced. It should not overwrite a populated `previous/` slot unless `--force` is passed explicitly. `scripts/roll_revision.py` remains a compatibility alias for direct snapshotting.

After a review cycle, prefer `scripts/regenerate_from_review.py --start-new-iteration` to apply parameter patches to `parameters.yaml`, regenerate CAD or review previews, sync review parameters, validate the draft, and clear consumed review state after success. Convert user annotations into the spec/source changes they request before passing `--clear-annotations`. Do not carry consumed annotations forward into the next current review.

## STEP Manifest

`outputs/step/manifest.json` records STEP state:

```json
{
  "schema": "engineering-3d-modeling.step_manifest.v1",
  "state": "draft",
  "generated_for_phase": "draft_review",
  "generated_at": "2026-06-20T00:00:00Z",
  "generated_by": "scripts/regenerate_from_review.py",
  "promoted_by": null,
  "stale": false,
  "source_hash": "...",
  "parameters_hash": "...",
  "step_files": [{"path": "outputs/step/example.step", "sha256": "..."}]
}
```

Allowed states are `draft`, `accepted_current`, and `release_handoff`. Draft STEP can support review, but it does not satisfy accepted/release validation. `accepted_current` and `release_handoff` manifest states are written by `scripts/promote_model_project.py` only.

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

A `draft_review` iteration may stop before STEP only when it has:

- updated authoring truth: brief, project-level `AGENTS.md`, spec, parameters, and source or formula modules;
- review artifacts or notes sufficient for the next feedback pass;
- validation evidence explaining that STEP is deferred because the phase is `draft_review`.

Do not call a `draft_review` state complete, accepted, release-ready, or handed off.

An `accepted_current` or `release_handoff` state is complete only when it has:

- updated authoring truth;
- generated STEP output plus promoted `outputs/step/manifest.json`, usually one assembly STEP for assemblies;
- per-part STEP only when requested or useful;
- validation evidence for build/export plus relevant dimensions and assembly relationships;
- an HTML review artifact or a lightweight snapshot/review note;
- a preserved one-step rollback snapshot when the accepted/release state was superseded by a new iteration.

The phase itself counts as accepted or handed off only after `scripts/promote_model_project.py` succeeds. A passing `validate_model_project.py` run is necessary evidence, but it is not by itself permission to skip the promotion gate.
