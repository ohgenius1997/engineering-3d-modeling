# Validation

## Validation Layers

V1 validation should distinguish:

- project-structure checks,
- parameter/schema checks,
- bundled review JSON schema checks for manifest, annotations, and parameter patches,
- source execution,
- STEP export,
- solid/BRep validity when the backend can report it,
- parameter-to-backend-geometry smoke checks for parameters that declare `validation.affects_geometry: true`,
- dimensional checks,
- assembly containment and clearance checks,
- collision/interference checks,
- review data checks,
- current-vs-previous regression checks when relevant.
- lifecycle phase checks that decide whether STEP and promoted STEP manifest state are required.
- handoff/current consistency checks that compare authoring truth, review artifacts, STEP outputs, and validation reports.

## Minimum Project Checks

Check that these exist:

- `brief.md`,
- `AGENTS.md`,
- `spec/current.yaml`,
- `parameters.yaml`,
- `source/model.py`,
- `outputs/step/`,
- `validation/`,
- `review/index.html`,
- `review/manifest.json`,
- `review/annotations.json`,
- `review/parameter_patch.json`,
- `previous/`.

`spec/current.yaml` should include `lifecycle.phase`. If it is missing, validators treat the project as `draft_review` and warn that the state is not accepted or release-ready.

## Phase-Aware STEP Checks

Use these default STEP requirements:

- `draft_review`: STEP may be missing. Report the phase and warn that the state is not complete, accepted, or release-ready.
- `accepted_current`: STEP should be present under `outputs/step/`, and `outputs/step/manifest.json` must have `state: "accepted_current"` and `promoted_by: "scripts/promote_model_project.py"`.
- `release_handoff`: STEP must be present, `outputs/step/manifest.json` must have `state: "release_handoff"` and `promoted_by: "scripts/promote_model_project.py"`, and validation should use strict review-parameter audit.
- `backend_override`: STEP may be deferred only as an explicit temporary backend state. The spec must record `backend.override` with backend/name and reason.

Draft STEP is allowed for review, but a manifest with `state: "draft"` cannot satisfy `accepted_current` or `release_handoff`. A project in `draft_review` must not carry accepted/release STEP manifest semantics; run `scripts/begin_model_iteration.py` when continuing from a promoted project.

Use `scripts/validate_model_project.py --require-step` when a delivery check must fail without STEP regardless of phase.

## Lifecycle Promotion Gates

Use `scripts/promote_model_project.py` when changing `spec/current.yaml` `lifecycle.phase` to `accepted_current` or `release_handoff`. The validator proves a state; the promotion script owns the phase transition and report refresh.

The promotion gate must:

- treat a missing or unsupported phase as `draft_review` with a warning;
- reject unordered transitions except `draft_review -> accepted_current -> release_handoff`;
- reject direct `draft_review -> release_handoff` unless `--allow-skip-accepted` is explicit, then run accepted and release gates in order;
- reject non-empty `review/annotations.json` and non-empty `review/parameter_patch.json` before accepting a draft;
- require STEP for every accepted or release promotion, using existing STEP or the current authoring source to generate it;
- write or refresh `outputs/step/manifest.json` as `accepted_current` or `release_handoff` only after the promotion gate owns the phase transition;
- reject `backend_override` or lingering `spec.backend.override` unless the override is cleared or `--accept-backend-override-reason` records why the exception is accepted;
- restore the original phase, STEP manifest, and `validation/report.json` on failure.

For `accepted_current`, run validation with STEP required and write a fresh `validation/report.json` after the phase update passes. For `release_handoff`, first run strict consistency against the accepted current state, then write `release_handoff`, refresh `validation/report.json`, and run strict consistency again so the final report proves the release snapshot.

## Handoff/Current Consistency Audit

Before calling a model current, accepted, handed off, or release-ready, run:

```bash
python3 engineering-3d-modeling/scripts/audit_project_consistency.py /path/to/model-project --mode strict
```

or include it in structural validation:

```bash
python3 engineering-3d-modeling/scripts/validate_model_project.py /path/to/model-project --strict-consistency
```

`validate_model_project.py` also runs strict consistency automatically for `release_handoff`.

The audit checks:

- `spec/current.yaml` records `lifecycle.phase`; missing phase is a warning for draft review and a failure in strict handoff audit.
- `review/manifest.json` `versions.current.source` points to the current authoring source, usually `source/model.py`, not `inputs/legacy/` or a Fusion reference.
- `brief.md` does not describe old backend state, old core parameter values, or accepted/release STEP status that conflicts with the lifecycle phase. Heuristic findings are warnings unless strict/current handoff rules make them blocking.
- `validation/report.json` records the current snapshot, including `generated_at`, phase, current artifact paths, and hashes or equivalent evidence for source, parameters, review manifest, mesh, STEP, and STEP manifest when present.
- `outputs/step/` matches the phase. `draft_review` may miss STEP with a warning; `accepted_current` and `release_handoff` fail without STEP, without `outputs/step/manifest.json`, or with a draft/stale/unpromoted manifest.
- `parameters.yaml`, manifest-exposed parameters, `review/cache/current_mesh.json`, and validation report current fields do not disagree on parameter values or units.
- Fusion or other non-default current backend exceptions are allowed only when `spec/current.yaml` records `lifecycle.phase: backend_override` plus `backend.override.backend` or `backend.override.name` and `backend.override.reason`.

Use warning findings as handoff blockers when they mean the agent cannot prove current state. Do not silence them by editing reports alone; regenerate or resync the stale artifact from authoring truth.

## Geometry Checks

For parts:

- build completes,
- STEP exports when the phase requires accepted or handoff output,
- model is non-empty,
- explicitly geometry-affecting parameters change the backend model signature when perturbed within declared bounds,
- key dimensions match parameters,
- wall thickness, fillets, holes, threads, ribs, and chamfers are within allowed bounds.

For assemblies:

- fixed components import or envelopes generate,
- generated parts are positioned,
- components are contained where required,
- collisions are absent or explicitly intentional,
- clearances meet rules,
- access openings align with components,
- assembly STEP exports when the phase requires accepted or handoff output.

## Review Checks

Check that:

- review manifest parses as JSON,
- review manifest, annotations, and parameter patch files pass their bundled schemas,
- parts and refs use stable ids,
- part projects use at most one real manifest part and distinguish subregions with `feature_id`,
- preview mesh face groups match part-vs-feature semantics,
- preview mesh is closed when the source solid is closed, including caps on revolved cones, ducts, hubs, and other surfaces,
- annotations parse and have target refs when provided,
- current annotations are user-authored open review records, not agent diagnostics or already-consumed notes,
- parameter patches refer to declared manifest parameters that remain editable in `parameters.yaml`,
- parameter patch values pass type, unit, min, max, and step checks before they are applied,
- saved parameter changes are applied to `parameters.yaml`, regenerated, and revalidated before becoming current model truth.

## Out Of Scope Checks

Do not make V1 validation depend on slicer output, printer profiles, material selection, G-code, 3MF packaging, simulation, animation, or photoreal rendering.

## Report Shape

Prefer a machine-readable report plus a short human summary:

```json
{
  "schema": "engineering-3d-modeling.validation_report.v1",
  "phase": {"value": "accepted_current", "source": "spec.lifecycle.phase"},
  "step_requirement": {"required": true, "reason": "phase:accepted_current"},
  "status": "pass",
  "checks": [],
  "warnings": [],
  "errors": [],
  "step_manifest": {
    "state": "accepted_current",
    "generated_for_phase": "accepted_current",
    "promoted_by": "scripts/promote_model_project.py"
  },
  "outputs": {
    "assembly_step": "outputs/step/example.step",
    "part_steps": []
  },
  "snapshot": {
    "generated_at": "2026-06-19T00:00:00Z",
    "phase": {"value": "accepted_current", "source": "spec.lifecycle.phase"},
    "files": {
      "parameters": {"path": "parameters.yaml", "sha256": "..."},
      "source": {"path": "source/model.py", "sha256": "..."},
      "manifest": {"path": "review/manifest.json", "sha256": "..."},
      "step_manifest": {"path": "outputs/step/manifest.json", "sha256": "..."},
      "mesh": {"path": "review/cache/current_mesh.json", "sha256": "..."}
    },
    "step_files": [{"path": "outputs/step/example.step", "sha256": "..."}]
  }
}
```
