# Skill Spec

## Memory Metadata
- owner: skill-product-spec
- read_when: developing, changing, validating, or packaging a Codex skill/plugin/agent capability
- update_when: trigger rules, workflow, bundled resources, validation, or installation behavior changes
- max_lines: 220
- stale_if: skill scope, resources, or trigger behavior changes

## Maintenance Rules
- Use this file for Codex skill product shape, trigger behavior, workflows, bundled resources, and validation expectations.
- Update when skill scope, resources, scripts, templates, or invocation semantics change.
- Do not use this file for generic project planning; use `PLAN.md`.

## Skill Identity
- Name: engineering-3d-modeling
- Purpose: Guide Codex sessions through lightweight engineering CAD model projects, from natural-language intent, drawings, references, or existing model files to editable build123d source, reviewable drafts, and validated STEP output for accepted or handoff states.
- Primary users: Codex sessions and developers

## Known Facts
- The skill is intended for engineering-style parametric models, not freeform art modeling.
- The skill should preserve a clean boundary between user intent, structured specifications, geometry generation, and validation.
- The skill is a CAD model-project workflow, not a one-shot CAD generator. It should preserve enough artifacts for repeated debugging, review, and refinement.
- The starting historical example was a guide-vane CAD model with equation-driven geometry.
- Natural-language model creation is a required scenario.
- Existing modeling scripts may need to be adopted and modified, including prior Fusion 360 scripts and scripts originally created through this skill.
- Standard CAD drawing inputs should be supported; hand-drawn sketch interpretation is out of scope for now.
- Dimensioned CAD drawings require accurate dimensional, shape, and structural modeling. Photos are useful only as qualitative references for exterior form or structural ideas unless scale and dimensions are independently supplied.
- Existing STEP/STP files may be imported as CAD references or fixed components. Mesh files such as STL/OBJ are reference-only for V1; parameterized reverse engineering from meshes is out of scope.
- Assemblies are expected later, so early templates should not block part-to-assembly growth.
- Each modeling task should be treated as a versioned, ongoing model project with persistent artifacts.
- V1 is focused on editable engineering CAD model projects with STEP as the CAD exchange/delivery output for accepted or handoff states, not downstream printing, slicing, simulation, animation, or rendering workflows.
- Models may require analytical definitions such as fifth-degree polynomial curves, NACA airfoil profiles, splines, guide-vane laws, or other equation-driven geometry.
- Unstructured assembly prompts must be normalized into fixed/imported components, component envelopes, keepouts, interfaces, layout constraints, generated parts, and validation targets before detailed part geometry is created.
- A model project owns one selected model or assembly. Alternative directions may be proposed before selection, but active modeling continues on only one chosen direction.
- Interactive HTML adjustment is limited to simple parameters that have explicit live preview bindings, such as wall thickness, fillets, clearances, lengths, holes, thread specs, chamfers, and shell thickness when the preview effect is model-appropriate. The page must not accept natural-language modeling input; layout, exterior-form, and structural changes go back through the coding agent's modeling workflow.
- V1 review HTML should support preview, explicit preview-bound parameter controls, assembly part show/hide, snapped selector refs, editable annotation records, optional current-vs-previous comparison, and English/Chinese UI switching. The left review workbench should group high-frequency tasks into parameter and annotation tabs; assembly part visibility belongs in a canvas-attached floating rail with part thumbnails, show/hide controls, isolate controls, and arrow scrolling. Direct local save should go through a local review server that validates bundled schemas and parameter patch domain rules before overwriting `review/annotations.json` and `review/parameter_patch.json`. It should not support lasso/freehand markup, explosion view, or direct geometry editing in V1.
- Complex projects may use `spec/current.yaml` as a root manifest that references same-project sub-specs; this is internal decomposition, not cross-project reuse or parallel variant management. Complex assemblies are the main V1 trigger.
- V1 default backend is build123d for local Python BRep generation. CadQuery, Zoo/KCL, Fusion, and other routes may remain optional adapters or research paths when a specific workflow justifies them.
- V1 priority model families are parameterized parts, engineering enclosures/shells, simple fixed-component assemblies, simple 1-3 stage gear transmission structures, and math-defined geometry such as ducts, guide vanes, NACA profiles, and simple analytic exterior forms.
- V1 does not target industrial-design-grade sculpted surfaces; supported exterior form is simple and mathematically parameterized.
- A V1 skill package exists under `engineering-3d-modeling/` with the skill entrypoint, focused references, project scaffold scripts, revision rolling, structure validation, and a review HTML/schema template.
- New model projects should include a generated project-level `AGENTS.md` so later sessions are guided back to `$engineering-3d-modeling` even when the user does not explicitly invoke the skill.
- The skill should actively check for build123d and PyYAML before generation or validation. If either is missing, the workflow should rerun the dependency helper with `--install` using the same Python runtime that will execute model source, requesting permission if pip, network, or environment writes are blocked.
- Review annotations are user-authored input only; agent diagnostics and consumed notes must not be stored in current `review/annotations.json`.
- Saved HTML parameter patches must be validated against `review/manifest.json` and `parameters.yaml`, applied to `parameters.yaml` before regeneration, then cleared after they are consumed.
- Model-project truth is layered: authoring truth is brief/spec/parameters/source or formula modules plus validation evidence; STEP is CAD exchange/delivery output required for `accepted_current` and `release_handoff`; review HTML, preview caches, annotations, and parameter patches are review artifacts only.
- Model projects should record `spec/current.yaml` `lifecycle.phase`: `draft_review` may lack STEP and must not be called complete, `accepted_current` should include STEP, `release_handoff` must include STEP and strict validation, and `backend_override` must explicitly record non-default backend use such as Fusion 360 API.
- Handoff/current audits must detect drift between authoring truth, review artifacts, STEP output, and validation reports. The audit should check lifecycle phase, manifest current source, stale brief language, validation report snapshot fields, STEP/report agreement, parameter consistency across `parameters.yaml`, manifest, mesh cache, and report, and explicit backend override records for Fusion/legacy current exceptions.
- Lifecycle promotion must be script-owned. Agents should use `scripts/promote_model_project.py` to move `draft_review -> accepted_current -> release_handoff`, so phase changes cannot be based on oral judgment or direct YAML edits without validation evidence.
- Every true modeling iteration must start with `scripts/begin_model_iteration.py` or an equivalent automatic call from `scripts/regenerate_from_review.py --start-new-iteration`. This writes `previous/` as a one-step rollback snapshot, records active iteration metadata in `validation/iteration.json`, and returns accepted/release projects to `draft_review`.
- `previous/` is the immediately prior rollback snapshot, not an accepted-only slot.
- STEP state is explicit in `outputs/step/manifest.json`. Draft STEP may exist, but `accepted_current` and `release_handoff` require manifest state matching the phase and written by `scripts/promote_model_project.py`.
- Single joined part projects should not be represented as multiple manifest parts. Use one part plus mesh `feature_id` groups for features such as shrouds, hubs, vanes, ribs, bosses, holes, and faces.
- Preview meshes should match the CAD model closely enough for review. Closed solids need cap faces in the mesh; validation should catch open preview boundaries unless explicitly marked open.
- HTML parameter controls should render only explicit live-preview-bound numeric review parameters as sliders and trigger an immediate visible preview update for those parameters. The V1 template must not infer geometry effects from parameter ids, labels, roles, or units.
- Equation-driven projects may declare a same-project `review/cache/preview_adapter.js` through `manifest.preview.adapter_js`. Adapter-backed parameters use `preview.effect: "adapter"` and let the standard template regenerate a derived preview mesh from model-specific formulas while preserving the standard annotation, selector, save, and parameter-patch workflow.
- Review-exposed parameters must be audited after model or preview changes. Manifest parameters must still exist in `parameters.yaml`, be explicitly editable, avoid placeholder preview metadata, and prove their declared backend geometry or adapter/preview effect in strict mode. Stale parameters should fail validation or be removed from `review/manifest.json`; backend-only geometry parameters should be reported as candidates until a safe preview binding exists.

## Decisions
- Use structured specs before geometry generation.
- Prefer deterministic generator workflows over one-shot CAD API generation.
- Treat `spec/current.yaml` and `parameters.yaml` as the durable model-project truth; generated backend scripts are implementation artifacts.
- Keep the default `source/` template limited to the active backend. Add Fusion 360 adapters or shared code only when a specific model project needs them.
- Clarify that specs/parameters are authoring truth. Release-grade engineering definition may require CAD geometry, PMI/GD&T, drawings, validation evidence, exchange files, and release metadata.
- Prioritize editable authoring truth and phase-appropriate STEP CAD output over full MBD/PMI release artifacts, slicer settings, material selection, G-code, simulation, animation, rendering, or print operations in V1.
- Treat engineering formulas and named profiles as first-class authoring inputs: specs reference them, parameters bind them, and source/formula modules implement and validate them.
- For assembly modeling, use a component registry and layout/constraint layer before generating individual parts. High-freedom prompts should produce explicit layout proposals and assumptions before detailed geometry is finalized.
- Keep parallel design variants out of the default project structure. Do not persist rejected candidate options by default; retain only a concise selection rationale when it will help future iteration.
- HTML review surfaces are parameter editors and preview tools, not CAD truth or natural-language modeling agents. Saving from HTML must produce a parameter update that is regenerated and validated by the backend.
- Model-specific formula preview adapters are allowed only as preview accelerators. They may change preview topology, such as guide-vane count, but they do not replace backend build123d regeneration, STEP export, or validation.
- HTML review surfaces should also support annotation records with editable text and optional targeted geometry refs so the user can point to parts, faces, edges, or features and then ask the coding agent for a modeling change. Global annotations without a target are valid.
- HTML review should let annotations snap directly to preview mesh vertices, edges, and faces even when the model generator did not emit explicit semantic refs.
- Model-project revision management should default to two slots: `current` and `previous`. Before every true iteration, copy current artifacts to previous; rollback is one step only. Beginning should support dry-run inspection and require explicit force before overwriting a populated `previous/` slot.
- Keep simple projects in one `spec/current.yaml`; allow local referenced sub-specs only when complexity creates independent reviewable domains, while keeping `spec/current.yaml` as the root contract.
- Use build123d as the V1 default backend and keep STEP as the CAD exchange/delivery output for accepted and handoff states. Assemblies should output an assembly STEP by default; separate per-part STEP files are optional when useful for handoff or inspection.
- Make validation phase-aware so `draft_review` can defer STEP or carry draft STEP, `accepted_current` and `release_handoff` require promoted STEP manifest state, and `--require-step` remains a forced delivery check.
- Require lifecycle phase promotion through a transactional script that blocks pending review data, unordered transitions, missing STEP, missing release snapshot evidence, and unaccepted backend overrides.
- Borrow text-to-cad/CAD Skills workflow ideas where they fit the project: CAD briefs, source-owned generation, explicit output targets, selector refs, geometry inspection, snapshot review, parameter contracts, and source-level assembly positioning.

## Assumptions
- The first implementation can start with instructions, templates, and examples before adding helper scripts.
- build123d source will carry precise construction logic for V1; specs and parameters remain the authoring contract and should not become a full CAD programming language.
- Persistent artifacts may include a CAD brief, structured spec with lifecycle phase, parameter table, input references, generated build123d source, STEP files when accepted or handed off, validation reports, snapshots, review HTML, annotations, and change notes.
- Complex models may need an interactive review surface that lets users point at geometry regions, features, faces, edges, or components.
- Existing Fusion 360 scripts should usually enter a model project through `inputs/legacy/` and be mined into specs/parameters before being refactored or replaced.
- Default model-project artifacts should stay small: `brief.md`, `spec/current.yaml`, `parameters.yaml`, `inputs/`, `source/`, `outputs/step/`, `validation/`, `review/`, and `previous/`. `review/` may contain HTML, screenshots, annotation JSON, parameter patches, and derived preview caches, but those are not CAD truth. `previous/` stores the immediately prior source/parameters/STEP/validation/review state for one-step rollback and comparison. Use sub-specs only when complexity justifies them.
- Formula modules may be backend-neutral when they produce points/curves/sections, while backend source consumes those outputs to construct solids.
- Imported components such as PCBs, batteries, motors, fasteners, and purchased parts should be represented as fixed geometry or envelopes with source/provenance, mounting features, keepouts, and required clearances.
- Cross-project component reuse is not a V1 requirement; component definitions can remain local to the model project.
- Real-time HTML preview may use WebGL/WebGPU rendering, derived preview assets, generic morphs, or model-specific formula preview adapters, but authoritative geometry still comes from backend regeneration. Fast previews may be approximate until saved and validated.
- A complex assembly is the primary signal to split by reviewable domain inside the same project: fixed components, shell/enclosure, airflow/ducting, mechanism, electronics mounting, generated parts, and validation.
- STEP/BREP exports from build123d can provide non-mesh solid handoff to Fusion. This should be described as BRep/direct-edit compatibility, not preservation of build123d's parametric history inside Fusion. Fusion API scripts are legacy inputs or explicit `backend_override` states unless a future decision changes the default backend.
- Zoo provides an official MCP route and KCL text-based CAD model source; this remains a serious optional adapter candidate, but not the V1 default until local reproducibility, export quality, cost/auth, and assembly needs are tested.

## Open Questions
- What exact trigger phrasing should activate the skill?
- What exact preview asset format should the HTML use internally without making non-STEP artifacts deliverables?
- What optional backend adapters, if any, should V1 expose beyond the build123d default?
- What reference examples should ship with the skill?
- How strict should the skill be about asking clarification questions before generation?
- Should the interactive review surface be an HTML viewer, a CAD-backend-native viewer workflow, or both?
- Which release artifacts should the skill generate by default, and which should require an explicit manufacturing/inspection target?
- What STEP geometry checks should V1 require by model type?
- What minimal reusable formula library should ship with the skill?
- How should formula references record provenance when they come from engineering standards or papers?
- What minimum assembly validation should V1 require: containment, collision, clearances, access openings, part visibility/isolation, annotations, or all of these by model type?
- What is the right implementation split for live preview: browser-side approximate geometry, debounced backend regeneration, or both?
- What minimal evidence should be required before adding a non-build123d backend adapter?

## Trigger Scenarios
- User asks Codex to create, modify, inspect, or export an engineering-style 3D model.
- User provides natural-language CAD intent and needs a parameterized model/script.
- User wants to convert a rough CAD idea into a structured modeling plan.
- User asks for validation of a generated CAD/modeling script or artifact.
- User provides an existing Fusion 360/build123d/CAD script and asks Codex to continue or refactor the model.
- User provides a standard CAD drawing and asks Codex to generate or adapt a model.
- User provides a photo as qualitative shape or structure reference, with precision limits stated explicitly.
- User asks for an enclosure, mechanism, fixture, or multi-part object that must contain or connect existing components.

## Core Workflows
- Gather intent, units, constraints, input modality, precision expectation, and STEP output needs.
- Normalize intent into a structured spec.
- Select or generate a deterministic model generator.
- Validate generated output with backend-appropriate checks and visual/rendered evidence when possible.
- For dimensioned CAD drawings, convert callouts into named parameters and validation targets. For photos, record qualitative assumptions and avoid claiming precise reproduction.
- Validate formula-driven geometry by checking parameter domains, sampled points/sections, expected dimensions, and generated curve/solid continuity where practical.
- For Fusion or other CAD handoff from build123d, prefer STEP/BREP for editable solid exchange.
- For assembly requests, extract fixed components and their envelopes, define hard and soft constraints, propose one or more layouts when design freedom is high, generate parts from the selected layout, and validate containment, interference, clearances, and access features.
- For complex projects, keep `spec/current.yaml` as the root manifest and split bulky local details into referenced sub-specs by reviewable domain before generating backend source.
- For HTML parameter adjustment, expose only parameters with explicit live preview metadata plus UI metadata, bounds, units, and validation rules; do not provide natural-language input; save changes as parameter updates, then regenerate and validate backend outputs through the review regeneration loop.
- Before consuming HTML patches/annotations or editing model truth, start an iteration so rollback does not rely on manual reverse edits.
- For accepted current or release handoff, run a consistency audit after promotion so `brief.md`, `spec/current.yaml`, `parameters.yaml`, `review/manifest.json`, `review/cache/current_mesh.json`, `outputs/step/manifest.json`, STEP files, and `validation/report.json` represent the same current snapshot.
- For lifecycle promotion, run `scripts/promote_model_project.py` instead of editing `spec/current.yaml` directly. `accepted_current` requires clean review state, STEP, and a refreshed validation report; `release_handoff` also requires strict accepted-current consistency and strict final consistency.
- For interactive annotations, create a record first, then optionally snap its target to a concrete vertex/edge/face/part/feature ref. Save selected refs, snapped world position, entity type, owning part/component, camera/view state, and editable text as structured review artifacts. Natural-language modeling requests based on those annotations must return to the coding agent workflow.
- Preserve model evolution through stable project artifacts so users and agents can review parameters, previews, exports, and changes across iterations.
- Record durable decisions and update project status when scope or workflow changes.

## Bundled Resources
- `scripts/init_model_project.py`: scaffolds a `draft_review` model project with brief/spec, parameters, inputs, build123d source, STEP output directory and draft manifest, validation directory, review data, and previous revision slot.
- `scripts/begin_model_iteration.py`: snapshots current project truth/output into `previous/`, records `validation/iteration.json`, returns accepted/release phases to `draft_review`, and marks existing STEP manifest state draft/stale before mutation.
- `scripts/check_environment.py`: checks build123d and PyYAML availability and can install missing dependencies into the active Python environment that will run model source.
- `scripts/apply_parameter_patch.py`: validates saved HTML review parameter patches against bundled schema, manifest exposure, editability, type, unit, bounds, and step rules before applying them into `parameters.yaml`.
- `scripts/audit_review_parameters.py`: audits `parameters.yaml`, `review/manifest.json`, `source/model.py`, `review/cache/current_mesh.json`, and optional preview adapters; reports valid preview parameters, disabled parameters, backend-only candidates, reasons, and suggested actions.
- `scripts/audit_project_consistency.py`: audits handoff/current consistency across lifecycle phase, brief, parameters, manifest current source and exposed parameter values, preview mesh cache, STEP outputs, STEP manifest state, backend override records, and validation report snapshot hashes; emits machine-readable JSON plus a human summary mode.
- `scripts/promote_model_project.py`: transactional lifecycle promotion gate for `accepted_current` and `release_handoff`; enforces ordered transitions, clean review state, phase-appropriate promoted STEP manifest state, backend override acceptance, accepted-current release preflight, report refresh, and human plus JSON output.
- `scripts/regenerate_from_review.py`: orchestrates the review regeneration loop by requiring or starting an iteration for saved review data or accepted/release projects, applying saved parameter patches, rebuilding backend CAD or review previews, syncing and auditing review sliders, validating draft state, marking generated STEP as draft, writing the current validation report, then clearing consumed review state after success.
- `scripts/restore_previous.py`: restores current project truth/output from `previous/`; defaults to dry-run and requires `--force` to write.
- `scripts/reset_review_state.py`: clears current annotations and parameter patches after the agent consumes them into a regenerated model revision.
- `scripts/sync_review_parameters.py`: syncs only explicit live-preview-bound parameters from `parameters.yaml` into `review/manifest.json` so the HTML exposes only parameters it can preview deliberately; command-line use audits the synced manifest by default.
- `scripts/roll_revision.py`: compatibility alias for copying current project state into `previous/`, with dry-run inspection and explicit force before overwriting a populated previous slot.
- `scripts/validate_model_project.py`: validates required project files/directories, bundled review JSON schemas, review JSON data, patch domain rules, phase-aware STEP presence and manifest state, review-parameter audit, release/strict handoff consistency audit, explicit parameter-to-geometry smoke checks, snapshot hashes, and forbidden downstream output formats.
- `scripts/quick_validate.py`: validates the skill package frontmatter when running the user-facing quick validation command from this repository.
- `scripts/serve_review.py`: serves a model project's review UI and safely writes `review/annotations.json` plus `review/parameter_patch.json` from the single save action after schema and patch-domain validation.
- `references/`: includes model project structure, input precision rules, build123d patterns, assemblies/layout, formulas, review HTML, and validation guidance.
- `assets/review-template/`: includes static bilingual review HTML plus JSON schemas for review manifests, annotations, and parameter patches.
- Optional model-specific preview adapters live in generated model projects, usually under `review/cache/preview_adapter.js`; they are not copied into every scaffold by default.

## Validation
- Skill behavior should be validated against at least one concrete engineering model example.
- Generated model workflows should include checks for units, required parameters, geometry creation success, and inspectable output.
- Validation should distinguish execution success, geometric validity, dimensional checks, visual review, exchange/export checks, and release-readiness checks.
- Validation reports for current/handoff states should include `generated_at`, phase, current artifact paths, and source/parameter/review-manifest/mesh/STEP/STEP-manifest hashes or equivalent evidence so stale reports cannot be mistaken for current truth.
- A `draft_review` pass may include `brief.md`, `parameters.yaml`, build123d source, validation report, and review HTML or a snapshot/review note without STEP, or with draft STEP, but it must not be called complete. Minimum accepted/handoff completion must include promoted STEP output and should have a previous rollback snapshot when it superseded a prior state.
- Promotion failure must not leave `spec/current.yaml` at the target phase. The promotion result should include both a human summary and machine-readable JSON so agents can report exactly which gate failed.
- V1 validation should focus on build success, STEP export, solid/BRep geometry, dimensions, clearances, assembly positioning, and review evidence; downstream slicer/printer checks are out of scope.
- Assembly validation should distinguish component import/extraction success, layout constraint satisfaction, collision/interference checks, clearance checks, containment checks, and review evidence such as annotations or part-isolated previews.
- HTML parameter saves should be validated as schema-correct review data and as manifest-exposed editable parameter updates with matching type, unit, bounds, and step first, then as regenerated geometry/export validation after backend rebuild; parameters that declare `validation.affects_geometry: true` must change the backend geometry signature when perturbed, and review-exposed adapter parameters must prove a changed adapter preview mesh signature in strict audit mode.
- Consistency audit failures should block `accepted_current` and `release_handoff`; `draft_review` may carry warnings for missing STEP or incomplete proof but must not be described as accepted, complete, or handed off.
