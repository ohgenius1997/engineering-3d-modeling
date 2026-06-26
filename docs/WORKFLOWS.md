# Workflows

## Memory Metadata
- owner: repeatable-agent-workflows
- read_when: executing or modifying repeatable project workflows
- update_when: workflow steps, safety checks, validation, or handoff behavior changes
- max_lines: 260
- stale_if: implemented workflow differs from documented workflow

## Maintenance Rules
- Use this file for repeatable agent workflows that the project must preserve.
- Update when the sequence of work, safety checks, or handoff behavior changes.
- Keep examples concise and realistic.
- Do not duplicate current roadmap details from `PLAN.md`.

## Workflow Index
- Natural-language engineering model request
- Existing model/script continuation
- Assembly/enclosure request
- HTML parameter adjustment
- Model project iteration
- Preview revision rollback
- Direct STEP export
- Optional handoff package
- Compatibility lifecycle promotion
- Strict consistency audit
- Backend bake-off
- Project-memory checkpoint

## Standard Workflow Template
1. Read required context.
2. Confirm current state.
3. Perform the task.
4. Validate outputs.
5. Update project memory.

## Project Workflows
### Natural-language engineering model request
1. Read `AGENTS.md`, `PROJECT_STATUS.md`, `docs/SKILL_SPEC.md`, and `docs/DOMAIN.md`.
2. Extract requested object, purpose, units, constraints, input modality, precision expectation, and STEP output needs.
3. Ask only for missing information that blocks safe model generation.
4. Convert the request into a structured spec with explicit assumptions.
5. Generate or adapt build123d modeling code from the spec.
6. Validate generation with work/review checks, geometry checks, dimensional checks, and review snapshots when practical.
7. Persist model-project artifacts such as brief, spec, parameters, source, review preview, validation report, and STEP output when exported.
8. Update project memory if scope, decisions, blockers, or risks changed.

### Existing model/script continuation
1. Read project context and inspect the existing CAD/modeling script.
2. Identify backend, parameters, assumptions, exports, and validation gaps.
3. Store legacy source under model-project inputs, then extract durable intent into `spec/current.yaml` and `parameters.yaml`.
4. Treat STEP/STP files as CAD references or imported components, and mesh files as reference-only unless a future adapter says otherwise.
5. Modify the model through structured specs and parameterized source where practical.
6. Validate the updated model and record the change at the model-project level.

### Assembly/enclosure request
1. Read project context and collect fixed/imported component inputs such as CAD files, drawings, datasheets, or user dimensions.
2. Build a component registry with envelopes, interfaces, keepouts, provenance, and required clearances.
3. Separate hard constraints from soft goals such as compactness, ergonomics, or appearance.
4. For complex projects, make `spec/current.yaml` the root manifest and split bulky local details into same-project sub-specs only when independent reviewable domains exist.
5. When layout freedom is high, propose one to three layout options with assumptions and tradeoffs, then ask the user to select one active direction. Do not persist rejected options by default.
6. Freeze only the selected layout into the model-project spec, then generate individual parts such as shells, lids, cradles, mounts, bosses, cutouts, and ribs.
7. Export one assembly STEP by default with `scripts/export_step.py` when the preview is satisfactory; add separate per-part STEP files only when useful.
8. Validate containment, collision/interference, clearances, access openings, and export success; create annotated or part-isolated review previews when practical.
9. Update model-project artifacts and project memory if durable workflow assumptions changed.

### HTML parameter adjustment
1. Load only parameters that include explicit live preview metadata plus UI metadata, bounds, units, and validation rules.
2. Render controls only for simple parameters whose preview effect is model-appropriate, such as wall thickness, fillets, clearances, lengths, holes, thread specs, chamfers, and shell thickness.
3. Do not infer live preview behavior from parameter names, labels, roles, or units.
4. For equation-driven geometry, use `manifest.preview.adapter_js` plus `preview.effect: "adapter"` only when a model-specific formula preview can regenerate the derived mesh and stay aligned with backend source.
5. Do not provide a natural-language input box in the HTML editor.
6. For assemblies, provide per-part show/hide controls rather than an exploded-view requirement.
7. Let users select or annotate parts, faces, edges, or features. Snap the selected point to a concrete entity when possible so the user gets selection confirmation.
8. Save selector refs, snapped positions, entity type, owning component, camera state, and text notes as structured review annotations.
9. Reject layout, exterior-form, structural, or feature-topology changes from the HTML editor unless they are explicitly handled by a model-specific preview adapter; even then, save only a parameter patch and route authoritative geometry through backend regeneration.
10. Save accepted HTML parameter changes as a parameter patch only after schema, manifest exposure, editability, type, unit, bounds, and step validation; direct `parameters.yaml` edits stay in the coding-agent workflow.
11. After backend geometry, formula, or preview-adapter changes, run review-parameter audit before accepting the regenerated review manifest. Remove or fail stale parameters whose perturbation no longer changes backend geometry or adapter/preview signature.
12. Record the change at the model-project level after regeneration succeeds. Existing STEP manifests should become stale until `scripts/export_step.py` is rerun.

### Model project iteration
1. Start from the latest model-project spec, parameter table, generated source, previews, exports, and validation report.
2. Before changing the visible HTML preview model, run `scripts/checkpoint_preview_revision.py --reason "..."`; `scripts/regenerate_from_review.py` does this automatically.
3. Treat `checkpoints/preview_previous/` as the default one-preview-step rollback target.
4. Treat `previous/` as an optional coarse whole-attempt snapshot. Use `scripts/begin_model_iteration.py` only when that larger rollback point is useful.
5. Convert the user's change request into explicit parameter, feature, geometry, or assembly changes.
6. Use visual review artifacts or interactive selection outputs when natural language is ambiguous.
7. Generate the next current revision, sync preview-bound parameters, and audit `review/manifest.json` so historical parameters are not carried forward just because they existed in the previous panel.
8. Validate the revision as a work/review state; existing STEP may be stale and should not be used as current output until re-exported.
9. When the user is satisfied, export STEP directly with `scripts/export_step.py`.
10. Keep only the current preview checkpoint and optional coarse previous snapshot inside the model project by default; use outer project history for anything heavier.

### Preview revision rollback
1. "Return to the previous version" means restore the previous visible preview revision, not the beginning of a whole modeling attempt.
2. Save the checkpoint with `scripts/checkpoint_preview_revision.py /path/to/model-project --reason "..."` before preview-changing work.
3. Inspect restore with `scripts/restore_preview_revision.py /path/to/model-project`.
4. Restore with `scripts/restore_preview_revision.py /path/to/model-project --force`.
5. Use `scripts/restore_previous.py --force` only when the whole coarse attempt in `previous/` should be undone.
6. Use Git or future multi-checkpoint history for anything more complex than one preview step plus one coarse attempt.

### Direct STEP export
1. Run `scripts/export_step.py /path/to/model-project` when the user is satisfied with the preview and wants usable STEP.
2. Fail export when `review/annotations.json` or `review/parameter_patch.json` contains unconsumed review data.
3. Regenerate from `source/model.py` using current `spec/current.yaml` and `parameters.yaml`.
4. Verify STEP file existence, hash, readability, and available BRep/bounding-box evidence.
5. Write `outputs/step/manifest.json` with `state: "exported"`, freshness hashes, validation summary, and `stale: false`.
6. Write or refresh `validation/report.json`.
7. If later authoring truth or the preview mesh changes, mark the STEP manifest stale and rerun export before using STEP as current output.

### Optional handoff package
1. Run `scripts/create_handoff_package.py /path/to/model-project` only when the user asks for a delivery/release bundle.
2. Fail packaging when pending review annotations or parameter patches exist.
3. Require fresh STEP from `scripts/export_step.py` or a compatible legacy promoted state.
4. Run strict consistency audit before writing the zip.
5. Include only deliverable/reproducible files: STEP, handoff manifest, README, spec, parameters, source, validation report, review HTML, review manifest, current preview mesh, and optional screenshot if already present.
6. Exclude `previous/`, `checkpoints/`, pending review JSON, private raw inputs unless explicitly allowed, temporary caches, tests, and research notes.
7. Treat old handoff zips as immutable historical snapshots; continuing model work only makes current STEP/package status stale, not the old zip.

### Compatibility lifecycle promotion
1. `scripts/promote_model_project.py` remains for old projects that explicitly use `accepted_current` and `release_handoff`; do not use it as the default daily modeling path.
2. Treat missing or invalid phase as `draft_review` with a warning. Do not let legacy status fields substitute for `lifecycle.phase`.
3. Fail promotion when `review/annotations.json` contains unconsumed annotations or `review/parameter_patch.json` contains unapplied patches. Consume annotations into spec/parameter/source changes and run `scripts/regenerate_from_review.py` for parameter patches first.
4. Require STEP for accepted and release promotion. Existing STEP may be used, but the script must write the accepted/release `outputs/step/manifest.json` state; draft or stale STEP manifest state fails validation.
5. Block `backend_override` or lingering `spec.backend.override` unless the override is cleared or `--accept-backend-override-reason` records why the exception is accepted.
6. Promote only in order: `draft_review -> accepted_current -> release_handoff`. Direct `draft_review -> release_handoff` fails unless `--allow-skip-accepted` is explicit, and then the script runs accepted and release gates in order.
7. For `release_handoff`, require strict consistency of the accepted current state before writing the release phase, then refresh `validation/report.json` and run strict consistency again.
8. On failure, preserve the original phase, STEP manifest, and validation report. Use the script's human summary and JSON output in the handoff note.

### Strict consistency audit
1. Use ordinary validation during each review iteration; use strict consistency for STEP delivery claims and handoff package creation.
2. Confirm `review/manifest.json` `versions.current.source` points to the current authoring source, usually `source/model.py`. A legacy/Fusion source is current only when `lifecycle.phase: backend_override` and `backend.override` records backend/name plus reason.
3. Scan `brief.md` for stale backend claims, old core parameter values, and STEP/handoff language that conflicts with current files. Treat uncertain findings as warnings and resolve them before handoff.
4. Confirm `outputs/step/` and `outputs/step/manifest.json` are fresh when STEP is being delivered: failure if missing, draft, stale, or hash-mismatched.
5. Confirm `validation/report.json` records the current snapshot with `generated_at`, phase, current artifact paths, and source/parameter/review-manifest/mesh/STEP/STEP-manifest hashes or equivalent evidence.
6. Compare `parameters.yaml`, manifest-exposed parameters, review mesh parameter snapshots, and validation report current fields. Any current value/unit disagreement is a failure for handoff.
7. Use the audit's JSON output for agent automation and its summary for handoff notes.

### Completion standard
1. For work/review, preserve authoring truth plus review artifacts and validation evidence; do not call it handed off.
2. For direct STEP export, deliver STEP output requested by the user plus fresh `outputs/step/manifest.json` with `state: "exported"` and `stale: false`.
3. Preserve build123d source and parameters required to regenerate it.
4. Include a validation report covering build success, STEP export when requested, key dimensions, clearances, and assembly relationships where relevant.
5. For handoff packages, include a strict consistency audit result showing authoring truth, review artifacts, STEP, and validation report are synchronized.
6. Include a review artifact: HTML review surface when available, otherwise snapshot or concise review note.
7. For assemblies, output one assembly STEP by default and per-part STEP files only when useful or requested.
8. Preserve the previous visible preview before preview-changing operations so one-step rollback and current-vs-previous review are possible.

### Backend bake-off
1. Read `docs/BACKEND_BAKEOFF_PLAN.md` before running backend candidate tests.
2. Use shared backend-neutral fixture specs and acceptance criteria across candidates.
3. Test hard gates before investing in full implementation.
4. Keep candidate outputs isolated under `experiments/backend-bakeoff/<candidate>/`.
5. Score each candidate with the same weighted scorecard.
6. Record a default backend decision only after comparison evidence exists.

### Project-memory checkpoint
1. Update `PROJECT_STATUS.md` after stable progress changes.
2. Add `docs/DECISIONS.md` entries only for durable choices.
3. Keep process traces and ordinary attempts out of project-memory docs.
