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
6. Validate generation with STEP export, geometry checks, dimensional checks, and review snapshots when practical.
7. Persist model-project artifacts such as brief, spec, parameters, source, STEP outputs, validation report, review notes, and change notes.
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
7. Export one assembly STEP by default and separate per-part STEP files only when useful.
8. Validate containment, collision/interference, clearances, access openings, and export success; create annotated or part-isolated review previews when practical.
9. Update model-project artifacts and project memory if durable workflow assumptions changed.

### HTML parameter adjustment
1. Load only parameters that include explicit live preview metadata plus UI metadata, bounds, units, and validation rules.
2. Render controls only for simple parameters whose preview effect is model-appropriate, such as wall thickness, fillets, clearances, lengths, holes, thread specs, chamfers, and shell thickness.
3. Do not infer live preview behavior from parameter names, labels, roles, or units.
4. Do not provide a natural-language input box in the HTML editor.
5. For assemblies, provide per-part show/hide controls rather than an exploded-view requirement.
6. Let users select or annotate parts, faces, edges, or features. Snap the selected point to a concrete entity when possible so the user gets selection confirmation.
7. Save selector refs, snapped positions, entity type, owning component, camera state, and text notes as structured review annotations.
8. Reject layout, exterior-form, structural, or feature-topology changes from the HTML editor and route them back to the coding agent's modeling workflow.
9. Save accepted HTML parameter changes as a parameter patch only after schema, manifest exposure, editability, type, unit, bounds, and step validation; direct `parameters.yaml` edits stay in the coding-agent workflow.
10. Record the change at the model-project level after regeneration succeeds.

### Model project iteration
1. Start from the latest model-project spec, parameter table, generated source, previews, exports, and validation report.
2. Before generating a new accepted result, copy the current source, parameters, STEP outputs, validation, and review artifacts to `previous/`; inspect with dry-run and require explicit force before overwriting a populated previous slot.
3. Convert the user's change request into explicit parameter, feature, geometry, or assembly changes.
4. Use visual review artifacts or interactive selection outputs when natural language is ambiguous.
5. Generate the next current revision and validate it.
6. Keep only the current and previous revision inside the model project by default; use outer project history for anything heavier.

### Completion standard
1. Deliver the committed STEP output requested by the user.
2. Preserve build123d source and parameters required to regenerate it.
3. Include a validation report covering build success, STEP export, key dimensions, clearances, and assembly relationships where relevant.
4. Include a review artifact: HTML review surface when available, otherwise snapshot or concise review note.
5. For assemblies, output one assembly STEP by default and per-part STEP files only when useful or requested.
6. Preserve the previous accepted state when one exists so one-step rollback and current-vs-previous review are possible.

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
