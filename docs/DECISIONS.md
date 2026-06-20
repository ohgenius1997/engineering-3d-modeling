# Decisions

## Memory Metadata
- owner: durable-decisions-and-rationale
- read_when: changing architecture, product direction, workflow policy, or explaining why
- update_when: durable technical, product, workflow, or operational decisions are made
- max_lines: 260
- stale_if: accepted decisions are superseded without a new entry

## Maintenance Rules
- Record only durable decisions future sessions must honor.
- Include decision, rationale, alternatives, and consequences.
- Do not record ordinary attempts, transient failures, or daily progress.
- Prefer agentmemory for episodic process history.

## Decision Index
- 2026-06-17 - Use AGENTS-first project context routing
- 2026-06-17 - Build the 3D modeling work as a separate active skill project
- 2026-06-17 - Separate natural-language interpretation from geometry construction
- 2026-06-17 - Make specs and parameters the model-project truth
- 2026-06-17 - Research and challenge assumptions as the highest collaboration rule
- 2026-06-17 - Distinguish authoring truth from released engineering definition
- 2026-06-17 - Focus V1 on editable model truth for 3D printing
- 2026-06-17 - Support engineering math as first-class authoring inputs
- 2026-06-17 - Model assemblies through components, constraints, and layout proposals
- 2026-06-17 - Keep each model project scoped to one selected model or assembly
- 2026-06-17 - Scope HTML adjustment to declared simple parameters
- 2026-06-17 - Use root specs with local sub-specs for complex model projects
- 2026-06-17 - Treat Fusion handoff as BRep exchange, not parametric-history transfer
- 2026-06-17 - Keep backend selection open until a bake-off
- 2026-06-18 - Use build123d as the V1 default local CAD backend
- 2026-06-18 - Scope V1 to lightweight STEP engineering CAD model projects
- 2026-06-18 - Treat V1 as a CAD model-project workflow with lightweight review HTML
- 2026-06-18 - Limit V1 review HTML and model-project revisions
- 2026-06-19 - Make HTML parameter controls explicit preview-bound
- 2026-06-19 - Validate review persistence before writing or applying patches
- 2026-06-19 - Add optional formula-driven review preview adapters
- 2026-06-19 - Audit review-exposed parameters after model changes
- 2026-06-19 - Make STEP validation phase-aware
- 2026-06-19 - Audit handoff/current consistency across artifacts
- 2026-06-19 - Make lifecycle promotion script-owned
- 2026-06-20 - Make iteration rollback and STEP state explicit

## Decision Log

### 2026-06-17 - Use AGENTS-first project context routing
- Decision: Keep stable operating rules in `AGENTS.md` and use project-memory docs only for stable facts that should be audited or resumed across sessions.
- Rationale: Agents need a short always-on router more than a large documentation tree.
- Alternatives considered: full multi-document project memory by default; rejected because it increases context and maintenance cost for lightweight projects.
- Consequences: Dynamic attempts and session history should be handled by agentmemory; only current state and durable decisions belong in project-memory docs.

### 2026-06-17 - Build the 3D modeling work as a separate active skill project
- Decision: Treat `origin-scope-pivot.md` as historical background and use this directory as the active start for an engineering 3D modeling Codex skill.
- Rationale: The archived origin document says the 3D modeling direction should be resumed separately rather than mixed back into the prior `project-memory` implementation.
- Alternatives considered: fold CAD-specific assumptions into the `project-memory` skill; rejected because project memory and CAD/model-generation guidance have different purposes.
- Consequences: Future sessions may read the archive for origin context, but active scope, rules, and progress must live in the current project-memory files.

### 2026-06-17 - Separate natural-language interpretation from geometry construction
- Decision: The skill should guide agents to convert user intent into structured specs before generating CAD/model geometry.
- Rationale: Engineering models need deterministic parameters, constraints, and validation; direct freehand CAD API calls from a prompt are fragile.
- Alternatives considered: prompt an LLM to write complete CAD scripts directly; acceptable only for prototypes, not as the core workflow.
- Consequences: The skill should define spec templates, parameter checks, model-generation workflows, and validation steps as first-class resources.

### 2026-06-17 - Make specs and parameters the model-project truth
- Decision: Treat `spec/current.yaml` and `parameters.yaml` as the durable model intent, structure, parameters, and constraints. Treat backend scripts under `source/` as generated or maintained implementations of that truth.
- Rationale: Model projects must support iteration, backend migration, old-script adoption, validation, and human review. Specs and parameter tables expose design changes more clearly than CAD API code.
- Alternatives considered: make the generated CAD script the source of truth; rejected because it couples model intent to a backend and makes migration/refactoring harder.
- Consequences: The default model-project template should not precreate multiple backend source trees. Fusion 360 scripts usually belong in `inputs/legacy/` first, and adapters or shared code should be added only when needed by a specific project.

### 2026-06-17 - Research and challenge assumptions as the highest collaboration rule
- Decision: Treat broad research, assumption-challenging, and engineering scrutiny as the highest collaboration rule for this project.
- Rationale: The user brings product usage and experience perspective, but does not claim production engineering CAD expertise. The agent must actively compensate with engineering, technical, domain, and project-management analysis.
- Alternatives considered: follow the user's preferences as strong design directives; rejected because this could overfit the skill to intuition rather than reliable CAD practice.
- Consequences: Future sessions should surface uncertainty, cite research when making domain claims, and challenge architecture choices that conflict with engineering practice.

### 2026-06-17 - Distinguish authoring truth from released engineering definition
- Decision: `spec/current.yaml` and `parameters.yaml` are the model project's authoring truth, not a complete released engineering definition.
- Rationale: Industry model-based definition and product data management practices treat released engineering data as more than editable intent: precise geometry, PMI/GD&T, drawings or model-based annotations, exchange files, validation evidence, lifecycle state, and approvals may matter.
- Alternatives considered: call specs/parameters the single source of truth for all engineering use; rejected because it would understate manufacturing, inspection, interchange, and release-management requirements.
- Consequences: The model-project template should distinguish authoring artifacts, review artifacts, validation artifacts, and release artifacts.

### 2026-06-17 - Focus V1 on editable model truth for 3D printing
- Status: Refined by `2026-06-18 - Scope V1 to lightweight STEP engineering CAD model projects`.
- Decision: Scope V1 around creating and maintaining an editable parametric model truth whose eventual use is 3D printing.
- Rationale: The skill should own model intent, parameters, geometry generation, preview/export artifacts, and geometry-level validation. Slicing, print material selection, G-code, and printer operations belong to downstream slicer/printer workflows unless explicitly requested.
- Alternatives considered: make V1 a full additive-manufacturing workflow including slicer projects, printer profiles, material/process management, and test-print tracking; rejected because it expands beyond the skill's core modeling responsibility.
- Consequences: Default model-project artifacts should preserve `spec/current.yaml`, `parameters.yaml`, backend source, previews, phase-appropriate CAD exports, validation evidence, review annotations, and change summaries. STL remains an export artifact, not editable truth.

### 2026-06-17 - Support engineering math as first-class authoring inputs
- Decision: The model-project architecture must support analytical definitions such as polynomial curves, parametric profiles, and named engineering standards like NACA airfoils.
- Rationale: Engineering 3D modeling often depends on equations and domain-specific profiles that should be inspectable, parameterized, testable, and reusable across model revisions.
- Alternatives considered: embed formulas only as comments in generated CAD code; rejected because formulas would be hard to review, validate, or migrate across backends.
- Consequences: Specs should reference formulas/profiles and bind parameters, while backend source or formula modules should implement the math with tests or validation checks. YAML specs should not become a full CAD programming language.

### 2026-06-17 - Model assemblies through components, constraints, and layout proposals
- Decision: Assembly requests should first normalize fixed or imported components, envelopes, keepouts, interfaces, placements, and hard/soft constraints before generating part geometry.
- Rationale: Assemblies fail through interference, missing access, wrong clearances, and arbitrary layout assumptions. A prompt-to-parts workflow hides these risks and makes later edits harder.
- Alternatives considered: generate each part directly from natural language and let visual review catch issues; rejected because plausible-looking assemblies can still violate containment, access, serviceability, or clearance constraints.
- Consequences: Model projects should support a component registry, an assembly/layout spec, generated parts derived from that layout, collision/clearance validation, and review previews such as annotated or part-isolated views. When user input is underspecified, the agent should create explicit layout proposals and assumptions before committing to detailed geometry.

### 2026-06-17 - Keep each model project scoped to one selected model or assembly
- Decision: A single model project should develop only one chosen model or assembly. Alternatives such as compact, rugged, or desk-stand variants may be proposed for user selection, but only the selected direction continues as the active project.
- Rationale: The skill is meant to preserve an editable truth for one evolving design, not manage a product-line or portfolio of related variants.
- Alternatives considered: support multiple peer variants in one project by default; rejected for V1 because it complicates specs, validation, previews, change history, and user review.
- Consequences: Templates should not optimize for cross-project resource reuse or parallel variant management. Rejected candidate layouts should not be persisted by default; if their rationale matters, keep only a concise selection note while `spec/current.yaml` represents the active chosen design.

### 2026-06-17 - Scope HTML adjustment to declared simple parameters
- Status: Refined by `2026-06-19 - Make HTML parameter controls explicit preview-bound`.
- Decision: The HTML review surface may adjust only declared, bounded parameters such as wall thickness, fillets, clearances, lengths, holes, thread specs, chamfers, and shell thickness. It must not accept natural-language modeling input. Layout, exterior-form, structural, or feature-topology changes must return to the coding agent's modeling workflow.
- Rationale: Simple scalar or enumerated parameters are practical to expose safely. Layout and structural edits usually change constraints, feature topology, validation expectations, or generated source, so they need agent-mediated modeling changes.
- Alternatives considered: make the HTML page a broad CAD editing surface; rejected because it would compete with the editable-truth model and introduce hard-to-validate geometry edits.
- Consequences: Parameter metadata should define controls, bounds, units, validation rules, and preview labels. The page may provide GPU-accelerated 3D preview, but saving must update `parameters.yaml` or a parameter patch and then trigger backend regeneration/validation before the project truth changes. Natural-language change requests remain a responsibility of the invoking coding agent, not the review page.

### 2026-06-17 - Use root specs with local sub-specs for complex model projects
- Decision: For simple models, `spec/current.yaml` should contain the full structured spec. For complex model projects, `spec/current.yaml` should act as the root manifest and contract, referencing same-project sub-specs for independent reviewable domains such as component registries, subassemblies, mechanisms, generated parts, formulas, or validation plans.
- Rationale: A monolithic YAML file becomes hard to review and risky to edit when a project contains multiple mechanical systems, imported parts, electronics, mechanisms, heavy analytical definitions, or validation domains. A rooted spec graph preserves one project truth while keeping each section understandable.
- Alternatives considered: force all spec data into one YAML file; rejected because it would encourage an unreadable pseudo-CAD file. Split each subassembly or domain into separate model projects; rejected because the project should still represent one selected model or assembly.
- Consequences: The editable authoring truth is rooted at `spec/current.yaml` and may include referenced files under `spec/`. References must be local, explicit, and part of the same model project; cross-project reuse is still out of V1 scope. Complex assemblies are the primary V1 trigger for sub-specs, but any project with genuinely independent reviewable domains may use the same pattern.

### 2026-06-17 - Treat Fusion handoff as BRep exchange, not parametric-history transfer
- Decision: When using build123d with Fusion, treat STEP/BREP export as a non-mesh solid-geometry handoff. Do not claim that Fusion receives the original build123d parameter tree, feature timeline, or generator logic.
- Rationale: build123d is a Python BREP modeling system and can export STEP/BREP solids, while Fusion can import STEP and work with BRep bodies. The interoperable artifact is precise boundary geometry, not the source parametric program.
- Alternatives considered: treat Fusion as the primary editable source after import; rejected because edits in Fusion would not automatically update `spec/current.yaml`, `parameters.yaml`, or build123d source.
- Consequences: Fusion is suitable as a downstream direct editor/viewer/checker for solid bodies. The authoring truth remains the model project spec, parameters, and build123d source unless an explicit Fusion-native workflow or backend override is added.

### 2026-06-17 - Keep backend selection open until a bake-off
- Status: Superseded by `2026-06-18 - Use build123d as the V1 default local CAD backend`.
- Decision: Do not choose build123d as a durable default yet. Keep the skill backend-neutral while evaluating build123d, CadQuery, and Zoo/KCL against the same representative modeling tasks.
- Rationale: build123d fits the local Python BRep/spec-driven workflow well, but CadQuery has similar OCCT foundations and strong text-to-CAD research adoption. Zoo/KCL is a serious official MCP-native CAD route that may better match agent workflows, but it adds platform, auth, cost, cloud, and maturity questions.
- Alternatives considered: commit immediately to build123d as the default; rejected because backend choice is high-leverage and current evidence shows at least two credible alternatives. Choose Zoo/MCP first; rejected because official MCP integration does not by itself prove reproducible editable truth, export quality, or local project fit.
- Consequences: The skill should define a backend contract and run a small bake-off before finalizing templates around one default backend. The bake-off should compare model source readability, parameter iteration, formula support, assembly layout, validation, STEP/mesh/export handoff, installation/auth friction, and long-term maintainability.

### 2026-06-18 - Use build123d as the V1 default local CAD backend
- Status: Refined by `2026-06-19 - Make STEP validation phase-aware`.
- Decision: Use build123d as the V1 default backend for generated engineering CAD source, with STEP as the CAD exchange output for accepted or handoff states. Non-STEP artifacts are not default V1 deliverables.
- Rationale: Fixture 1-5 showed both build123d and CadQuery are viable, with CadQuery leading 78 to 76 on the current scorecard. The final choice favors build123d because external text-to-cad/CAD Skills experience adds evidence for sustained agent workflows: editable Python source per STEP, source-level labels and assembly positioning, selector-based review, mandatory snapshots, and geometry inspection loops.
- Alternatives considered: choose CadQuery because it led the executable bake-off by two points; rejected because that gap came from current generation ergonomics, not observed geometry capability, and did not cover long-running selector/review workflows. Keep backend selection open; rejected because V1 templates need a default. Choose Zoo/KCL first; rejected for V1 because cloud/auth/reproducibility and local editable-truth questions remain unresolved.
- Consequences: Skill templates should be build123d-first while keeping a backend contract for optional adapters. Specs and parameters remain the model-project authoring truth, but precise construction logic lives in build123d source. Future work should borrow text-to-cad ideas selectively: CAD brief, explicit generation targets, STEP topology/selector refs, source labels, geometry inspection, snapshot review, parameter contracts, and source-level assembly joints/placements.

### 2026-06-18 - Scope V1 to lightweight STEP engineering CAD model projects
- Status: Refined by `2026-06-19 - Make STEP validation phase-aware`.
- Decision: V1 should create or modify engineering CAD models from natural language, dimensioned CAD drawings, existing model/source files, and qualitative photo references. The accepted/handoff CAD exchange output is STEP. Assembly STEP is default for assemblies, and separate per-part STEP export is optional. Mesh files are reference-only inputs for now.
- Rationale: The skill should stay focused on sustainable engineering model development rather than becoming a broad text-to-CAD, 3D printing, simulation, robotics, or rendering suite. STEP plus build123d source, specs, parameters, and validation evidence keeps the model editable without taking responsibility for downstream manufacturing workflows.
- Alternatives considered: follow text-to-cad into downstream Bambu/G-code/robotics/viewer ecosystems; rejected as too heavy for this skill. Promise parameterized reverse engineering from STL/OBJ meshes; rejected as a separate hard problem. Treat photos like CAD drawings; rejected because photos are useful for qualitative shape and structure hints but do not provide precise dimensions.
- Consequences: The V1 template should include brief/spec, parameters, inputs, build123d source, STEP outputs, validation, and review notes. CAD drawings require dimension/shape/structure fidelity and validation against callouts. Photos can guide exterior form or structural ideas but must be labeled as non-precise reference. STL, 3MF, G-code, slicer settings, simulation, animation, and rendering are non-goals unless added later as explicit adapters.

### 2026-06-18 - Treat V1 as a CAD model-project workflow with lightweight review HTML
- Decision: Treat V1 as a workflow for developing one durable CAD model project, not as a one-shot CAD file generator. The model project should include a lightweight HTML review surface for preview, declared-parameter adjustment, and interactive geometry annotations.
- Rationale: CAD modeling is iterative and usually has no single correct answer; even skilled modelers adjust, inspect, and refine. A review surface gives the user and agent a shared object for targeted feedback without turning the skill into a full CAD editor or renderer.
- Alternatives considered: output only STEP with no review UI; rejected because it weakens iteration and makes targeted feedback hard. Build a full CAD web editor or general viewer platform; rejected because it would make the skill too heavy and compete with CAD tools. Accept natural language in the HTML page; rejected because modeling changes should route through the coding agent.
- Consequences: Minimum accepted/handoff completion should include build123d source, parameters, STEP output, validation evidence, and a review artifact. Draft review states may defer STEP but are not complete. The HTML may use derived preview/cache assets internally, but those are review artifacts, not deliverables at the same level as STEP. HTML parameter edits save parameter patches and annotations; backend regeneration and validation remain authoritative.

### 2026-06-18 - Limit V1 review HTML and model-project revisions
- Decision: V1 review HTML should support model preview, declared-parameter adjustment, assembly part show/hide, snapped selector refs, and text annotations tied to selected points, edges, faces, parts, or features. It may support current-vs-previous comparison. It should not support lasso/freehand markup, explosion view, natural-language input, or direct geometry editing in V1.
- Rationale: These controls preserve the feedback loop needed for iterative CAD work without turning the skill into a general CAD editor or heavy viewer platform. Snapping annotations to concrete geometry refs gives users confirmation and gives the agent actionable context.
- Alternatives considered: add lasso drawing and rich markup immediately; rejected as unnecessary for V1. Add exploded assembly views; rejected because per-part visibility is enough for initial assembly inspection. Keep full multi-version history; rejected because most failed iterations only need one-step rollback and comparison, while long-term history can be handled by outer Git/project history if needed.
- Consequences: Text annotations should be stored as structured review data, not as accepted model truth. A selected annotation becomes model truth only after the coding agent turns it into a spec, parameter, or source change. The default model project should keep only `current` and `previous` revision slots; before regenerating, the current slot is copied to previous, enabling one-step rollback and current-vs-previous review.

### 2026-06-19 - Make HTML parameter controls explicit preview-bound
- Decision: The review HTML parameter panel should show only parameters with explicit live preview bindings. Parameters without correct preview metadata must stay out of `review/manifest.json` and be handled through the agent-led backend regeneration flow. The template must not infer geometry effects from parameter names, labels, roles, or units.
- Rationale: Dogfood on the guide-vane shroud showed name-based preview inference can create plausible but wrong browser morphs for real engineering geometry, which is worse than requiring backend regeneration.
- Alternatives considered: keep all editable parameters visible and mark unbound changes as approximate; rejected because users reasonably interpret visible immediate geometry changes as corresponding to the edited parameter. Keep `preview.effect: none` parameters visible; rejected because it still makes the HTML parameter area look like a general parameter editor.
- Consequences: `sync_review_parameters.py` syncs only explicit live-preview-bound parameters. `parameters.yaml` may still contain non-previewable parameters, but they are adjusted by the coding agent, regenerated by the backend, and validated before becoming current model truth.

### 2026-06-19 - Validate review persistence before writing or applying patches
- Decision: Local review saves and parameter-patch application must validate bundled JSON schemas plus parameter-domain rules before writing review files or changing `parameters.yaml`. Parameter patches must reference manifest-exposed parameters that remain editable in `parameters.yaml`, and values must match type, unit, min, max, and step constraints.
- Rationale: The review HTML is not CAD truth. Accepting malformed patches, hidden-parameter edits, wrong value types, or out-of-bounds values lets browser state bypass backend regeneration assumptions and makes later validation misleading.
- Alternatives considered: trust the static HTML to emit valid patches; rejected because local files and API calls can be edited manually, and dogfood already showed malformed payloads were accepted. Validate only during backend regeneration; rejected because it still lets invalid review files overwrite project state and confuse future sessions.
- Consequences: `serve_review.py`, `apply_parameter_patch.py`, and `validate_model_project.py` share strict review validation. Non-previewable or locked parameters must be changed through the coding agent workflow, not through `review/parameter_patch.json`. Revision rolling also requires dry-run/force discipline before overwriting a populated `previous/` slot.

### 2026-06-19 - Add optional formula-driven review preview adapters
- Decision: Keep the standard review HTML as the single UI for parameters, annotations, refs, part visibility, and saving, but allow model projects to declare a same-project formula preview adapter with `manifest.preview.adapter_js`. Adapter-backed parameters use `preview.effect: "adapter"` and let the template regenerate a derived preview mesh from model formulas.
- Rationale: Dogfood on the guide-vane shroud showed some engineering parameters, such as vane count, NACA thickness, hub profile, and inlet camber angle, cannot be represented by generic mesh morphs but can be previewed accurately enough by re-running lightweight source-derived formulas in the browser.
- Alternatives considered: replace the standard review template with model-specific HTML; rejected because it loses the required save, annotation, ref, bilingual, and validation workflow. Force all non-morph parameters through backend-only regeneration; rejected because it removes useful real-time feedback for equation-driven models where a safe preview generator is practical.
- Consequences: Adapter code is preview-only and must stay under `review/`. It may change preview topology, but it must not become CAD truth or bypass `review/parameter_patch.json`, backend build123d regeneration, phase-appropriate STEP export, and validation. Formula drift between backend source and JavaScript adapters is an active validation risk.

### 2026-06-19 - Audit review-exposed parameters after model changes
- Decision: Add a review-parameter audit that runs against `parameters.yaml`, `review/manifest.json`, `source/model.py`, preview mesh cache, and optional preview adapters. Basic audit guards manifest exposure rules; strict audit perturbs parameters and requires declared geometry or adapter/preview effects to change a trusted signature.
- Rationale: Dogfood exposed a failure mode where historical parameters such as `shroud_wall` stayed in the HTML panel after the model shape changed, even though they no longer affected the current envelope or live preview. A visible slider with no trustworthy effect is worse than hiding the parameter and routing the edit through backend regeneration.
- Alternatives considered: rely on `sync_review_parameters.py` to copy current metadata only; rejected because stale preview metadata can remain in `parameters.yaml`. Rely on humans to manually remove obsolete sliders; rejected because model-shape changes are exactly when this is easy to miss. Always auto-delete failing parameters; rejected because validation failure is safer when the agent needs to inspect why a parameter became stale.
- Consequences: Regeneration now syncs and audits review parameters before validation and before clearing consumed review state, with strict audit for release handoff or explicit strict requests. `validate_model_project.py` runs phase-aware audit by default and can run strict audit. Backend-only geometry parameters are reported as candidates until a safe preview binding is defined.

### 2026-06-19 - Make STEP validation phase-aware
- Decision: Distinguish authoring truth, CAD exchange/delivery STEP output, and review-derived artifacts. Model projects should record `spec/current.yaml` `lifecycle.phase` as `draft_review`, `accepted_current`, `release_handoff`, or `backend_override`. Validators require STEP by default only for `accepted_current` and `release_handoff`, while `--require-step` remains a forced delivery check.
- Rationale: Earlier wording made committed STEP sound like durable truth for every iteration, which could make agents fail reasonable draft/review states or waste context generating STEP after every small review change. It also risked calling review/cache artifacts or parameter patches model truth before backend regeneration.
- Alternatives considered: Always require STEP on every validation; rejected because it makes review-only drafts too heavy. Never require STEP unless `--require-step` is passed; rejected because accepted and handoff states must not silently pass without CAD exchange output. Store phase only in review metadata; rejected because review files are derived artifacts, not lifecycle truth.
- Consequences: New scaffolds start in `draft_review`. Missing STEP in draft/review is reported with an explicit phase warning and must not be described as complete. `accepted_current` and `release_handoff` fail without STEP; `release_handoff` defaults to strict review-parameter audit. Fusion 360 API or other non-default backend use must be recorded as `backend_override` with backend/name and reason, not treated as the default authoring truth shape.

### 2026-06-19 - Audit handoff/current consistency across artifacts
- Decision: Add a project consistency audit that compares authoring truth, review artifacts, STEP outputs, validation reports, and backend override metadata before accepted or release handoff claims.
- Rationale: Dogfood on the guide-vane shroud showed a model project can have valid-looking source, review HTML, STEP, and reports while still mixing old Fusion/current-source claims, stale brief parameters, old validation fields, and missing lifecycle metadata.
- Alternatives considered: Rely on `validate_model_project.py` structure checks and review-parameter audit alone; rejected because those checks do not prove `brief.md`, manifest current source, validation report, mesh cache, and STEP describe the same snapshot. Hard-code a guide-vane-specific checker; rejected because the failure mode applies to any model project.
- Consequences: `scripts/audit_project_consistency.py` emits machine-readable JSON and a human summary. `validate_model_project.py` runs strict consistency for `release_handoff` and with `--strict-consistency`. `draft_review` may carry warnings for incomplete proof, but `accepted_current` and `release_handoff` should fail when current source, STEP, report, mesh, or exposed parameter state is inconsistent.

### 2026-06-19 - Make lifecycle promotion script-owned
- Decision: Lifecycle phase advancement must go through `scripts/promote_model_project.py` instead of direct YAML edits or oral completion claims.
- Rationale: Agents need a transaction boundary that checks pending review data, ordered phase movement, STEP presence, backend override acceptance, and report snapshot evidence before changing `spec/current.yaml`.
- Alternatives considered: Tell agents to run validators manually before editing phase; rejected because it is easy to skip a gate, write stale reports, or leave a project half-promoted after failure.
- Consequences: `draft_review -> accepted_current -> release_handoff` is the only default order. Failed promotions restore the original phase/report, and direct draft-to-release requires explicit `--allow-skip-accepted` while still running both validation gates.

### 2026-06-20 - Make iteration rollback and STEP state explicit
- Decision: Treat `previous/` as a one-step rollback snapshot for every true modeling iteration, and treat `outputs/step/manifest.json` as the authority for whether STEP is draft, accepted current, or release handoff.
- Rationale: Dogfood continuation showed two unsafe paths: agents could regenerate over accepted/handoff projects without first preserving rollback state, and STEP files could remain present after a new iteration while still being implicitly treated as accepted or release output.
- Alternatives considered: Keep `previous/` as accepted-only and rely on agents to remember manual reverse edits; rejected because it loses rollback for failed draft iterations. Use STEP file presence alone; rejected because file presence cannot distinguish draft preview output from promotion-gate output.
- Consequences: `scripts/begin_model_iteration.py` must run before consuming saved review patches/annotations or editing authoring truth/derived outputs. It snapshots current state, records `validation/iteration.json`, returns accepted/release projects to `draft_review`, and marks STEP draft/stale. `scripts/regenerate_from_review.py` fails by default unless an iteration boundary exists or `--start-new-iteration` is explicit. `scripts/promote_model_project.py` is the only bundled script that writes accepted/release STEP manifest state.
