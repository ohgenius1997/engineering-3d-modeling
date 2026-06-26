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
- work-state checks that report whether STEP is present and fresh without forcing routine preview iteration through lifecycle promotion.
- export-level checks for fresh direct STEP output.
- strict handoff package checks that compare authoring truth, review artifacts, STEP outputs, validation reports, and package manifests.

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
- `checkpoints/`.

`spec/current.yaml` may include `lifecycle.phase` as a coarse work-state or legacy compatibility label. Missing phase is treated as `draft_review`.

## STEP Freshness Checks

Use these default STEP requirements:

- Ordinary work/review validation: STEP may be missing. Report warnings so agents do not describe the state as exported or handed off.
- Direct STEP export: `scripts/export_step.py` must produce STEP under `outputs/step/`, write `outputs/step/manifest.json` with `state: "exported"` and `stale: false`, and record source/spec/parameter/review-mesh/STEP hashes.
- Forced delivery check: `scripts/validate_model_project.py --require-step` must fail when STEP is missing or `outputs/step/manifest.json` is stale.
- Strict handoff package check: `scripts/create_handoff_package.py` must require a fresh deliverable STEP manifest (`exported` or a legacy promoted state), strict consistency, and no pending review data.
- `backend_override`: STEP may be deferred only as an explicit temporary backend state. The spec must record `backend.override` with backend/name and reason.

Draft STEP is allowed for review, but a manifest with `state: "draft"` or `stale: true` cannot satisfy a forced delivery check or handoff package. Continuing work after export does not require leaving a lifecycle state; mark the STEP manifest stale and rerun `scripts/export_step.py` when STEP is needed again.

Use `scripts/validate_model_project.py --require-step` when a delivery check must fail without STEP regardless of phase.

## Direct Export Gate

Use `scripts/export_step.py` when the user is satisfied with the preview and wants usable STEP. The export gate must:

- reject non-empty `review/annotations.json` and non-empty `review/parameter_patch.json`;
- run current `source/model.py` from the project root;
- require at least one STEP/STP file under `outputs/step/`;
- check STEP file existence, hash, readability, and any available BRep/bounding-box signature;
- write `outputs/step/manifest.json` with `state: "exported"`, source/spec/parameter/review-mesh hashes, STEP hashes, validation summary, and `stale: false`;
- write or refresh `validation/report.json` after export-level validation passes.

## Handoff Package Gate

Use `scripts/create_handoff_package.py` only when a delivery/release package is requested. The package gate must:

- reject pending review annotations and parameter patches;
- require fresh STEP from `scripts/export_step.py` or a compatible legacy promoted state;
- run strict consistency audit;
- create a zip under `outputs/handoff/`;
- include only deliverable and reproducible files such as STEP, README, handoff manifest, `spec/current.yaml`, `parameters.yaml`, `source/model.py`, `validation/report.json`, `review/index.html`, `review/manifest.json`, and `review/cache/current_mesh.json`;
- exclude `previous/`, `checkpoints/`, pending review data, private raw inputs unless explicitly allowed, temporary caches, test outputs, and research notes.

## Compatibility Lifecycle Promotion

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

For `accepted_current`, run validation with STEP required and write a fresh `validation/report.json` after the phase update passes. For `release_handoff`, first run strict consistency against the accepted current state, then write `release_handoff`, refresh `validation/report.json`, and run strict consistency again so the final report proves the legacy release snapshot. This is retained for compatibility; new daily export/handoff should use `export_step.py` and `create_handoff_package.py`.

## Handoff/Current Consistency Audit

Before creating a handoff package or making a release claim, run:

```bash
python3 engineering-3d-modeling/scripts/audit_project_consistency.py /path/to/model-project --mode strict
```

or include it in structural validation:

```bash
python3 engineering-3d-modeling/scripts/validate_model_project.py /path/to/model-project --strict-consistency
```

`validate_model_project.py` runs strict consistency only when explicitly requested with `--strict-consistency` / `--consistency-audit strict`; `create_handoff_package.py` runs strict consistency automatically.

The audit checks:

- `spec/current.yaml` records enough work-state/backend information for the audit; missing lifecycle phase is a warning, not a default daily blocker.
- `review/manifest.json` `versions.current.source` points to the current authoring source, usually `source/model.py`, not `inputs/legacy/` or a Fusion reference.
- `brief.md` does not describe old backend state, old core parameter values, or STEP/handoff status that conflicts with current files. Heuristic findings are warnings unless strict handoff rules make them blocking.
- `validation/report.json` records the current snapshot, including `generated_at`, phase, current artifact paths, and hashes or equivalent evidence for source, parameters, review manifest, mesh, STEP, and STEP manifest when present.
- `outputs/step/` has a fresh manifest when STEP is being delivered. Work/review states may miss STEP with a warning; strict handoff fails without STEP, without `outputs/step/manifest.json`, or with a draft/stale manifest.
- `parameters.yaml`, manifest-exposed parameters, `review/cache/current_mesh.json`, and validation report current fields do not disagree on parameter values or units.
- Fusion or other non-default current backend exceptions are allowed only when `spec/current.yaml` records `lifecycle.phase: backend_override` plus `backend.override.backend` or `backend.override.name` and `backend.override.reason`.

Use warning findings as handoff blockers when they mean the agent cannot prove current state. Do not silence them by editing reports alone; regenerate, resync, or re-export stale artifacts from authoring truth.

## Geometry Checks

For parts:

- build completes,
- STEP exports when the user requests delivery or handoff output,
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
- assembly STEP exports when the user requests delivery or handoff output.

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
  "phase": {"value": "draft_review", "source": "spec.lifecycle.phase"},
  "step_requirement": {"required": true, "reason": "--require-step"},
  "status": "pass",
  "checks": [],
  "warnings": [],
  "errors": [],
  "step_manifest": {
    "state": "exported",
    "generated_for_phase": "draft_review",
    "generated_by": "scripts/export_step.py",
    "stale": false
  },
  "outputs": {
    "assembly_step": "outputs/step/example.step",
    "part_steps": []
  },
  "snapshot": {
    "generated_at": "2026-06-19T00:00:00Z",
    "phase": {"value": "draft_review", "source": "spec.lifecycle.phase"},
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
