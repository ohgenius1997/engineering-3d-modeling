# Domain

## Memory Metadata
- owner: domain-knowledge
- read_when: domain terminology, user mental model, business rules, professional constraints, or success criteria matter
- update_when: domain facts, terminology, constraints, workflows, or assumptions change
- max_lines: 240
- stale_if: target domain, user type, regulatory/manufacturing/business constraints, or accepted domain assumptions change

## Maintenance Rules
- Use this file for business or technical domain knowledge, not generic project management.
- Keep project shape and implementation roadmap in `PLAN.md` or project-specific addon docs.
- Separate known facts, decisions, assumptions, open questions, and risks.
- Do not create one-off domain addons; use this file for domain-specific context.

## Domain Summary
- Domain: engineering 3D model generation

## Known Facts
- The origin direction involved CAD-native engineering geometry, including a 4028 guide-vane solid.
- Example parameters included duct radius transitions, hub radius, NACA 0012 thickness, vane angle, vane count, wall thickness, loft sections, and boolean joins.
- Assemblies should be represented through structured parts, connection points, and joints.
- Fusion 360 can remain an optional downstream viewer, editor, or export target.
- Model work is expected to be iterative and versioned, not one-shot generation.
- Standard CAD drawings are acceptable inputs; hand-drawn sketches are not a target for the initial scope.
- Model-based definition practices use annotated 3D models plus associated data to communicate product definition, including geometry, dimensions, tolerances, material, and other manufacturing/inspection information.
- Product and manufacturing information may be semantic machine-readable data or graphical human-readable presentation; both matter for downstream CAD/CAM/CMM workflows.
- STEP is a neutral exchange family for product data; STEP AP242 is relevant to managed model-based 3D engineering, while STL/glTF are better treated as mesh/visualization outputs rather than authoritative CAD definition.
- build123d is a Python parametric BREP modeling framework built on Open Cascade and supports STEP/BREP solid export in addition to mesh/visualization exports.
- CadQuery is another Python/OpenCascade parametric CAD-as-code route with strong documentation, headless library usage, STEP/STL/3MF/glTF-related export workflows, and visible use in recent text-to-CAD research.
- Zoo offers an official MCP path, API/SDK tooling, KCL as text-based CAD source, and cloud-backed CAD/modeling workflows. It is the strongest currently identified official MCP-native CAD route, but it introduces platform, auth, cloud, pricing, and maturity questions.
- Fusion supports importing STEP through its import API and represents solid geometry as BRep bodies. Imported build123d STEP/BREP output should be treated as editable direct-modeling solid geometry, not as native Fusion feature history.
- Product data management separates mutable workspaces/history from immutable versions, released revisions, approval state, and release candidates.
- V1 focuses on lightweight editable engineering CAD model projects with STEP as the CAD exchange/delivery output for accepted or handoff states, not full production CAD/MBD, 3D printing, slicing, simulation, animation, or rendering workflows.
- STL, OBJ, and other mesh files are reference-only inputs for V1. Parameterized reverse engineering from meshes is out of scope.
- Dimensioned CAD drawings can drive precise modeling and validation. Photos can provide qualitative form or structure references, but cannot be treated as dimensionally precise unless scale and dimensions are supplied separately.
- Engineering models may depend on analytical math definitions such as polynomial curves, spline profiles, airfoil definitions, parametric ducts, guide vanes, and other equation-driven geometry.
- Assembly modeling must distinguish fixed/imported components from generated parts. Fixed components are represented by CAD geometry or conservative envelopes, plus interfaces, keepouts, and required clearances.
- Underspecified enclosure requests should be treated as layout problems before part-generation problems.
- build123d is the selected V1 default local CAD backend. CadQuery and Zoo/KCL remain useful comparison points or optional adapters, not the default path.
- V1 supports simple gear transmission structures such as 1-3 stage gear trains when modeled as engineering geometry with explicit parameters and validation. Complex high-precision gear design, contact analysis, and manufacturing optimization are out of scope.
- V1 supports simple appearance only when it is expressed through mathematical or parametric geometry. It does not target hand-sculpted or industrial-design-grade complex surfaces.

## Terms
- Structured spec: A machine-readable description of intent, parameters, constraints, units, and requested outputs.
- Deterministic model generator: Code that builds geometry from explicit parameters rather than improvised CAD operations.
- Progressive modeling: A workflow that lets users refine a model through intermediate states instead of specifying the final object upfront.
- Connection point: A named location and orientation used to assemble parts.
- Joint: A structured relationship between parts in an assembly.
- Model project: A durable folder of model intent, parameters, source code, previews, exports, validation reports, and change records for one modeled object or assembly.
- Review surface: A visual interface or artifact that helps a user identify parts, faces, edges, features, or components when requesting changes.
- Review HTML: A lightweight project-local review surface for preview, explicit preview-bound parameter adjustment, and geometry annotation. It is not CAD truth and does not accept natural-language modeling instructions.
- Snapped selector ref: A review reference created by selecting a concrete model entity such as a point, edge, face, part, or feature. It records the selector token plus enough context, such as owning part and world position, to support later agent interpretation.
- Authoring truth: The structured spec, parameter table, backend source or formula modules, and validation evidence that can regenerate and revise the model.
- STEP CAD output: The CAD exchange/delivery artifact generated from authoring truth for accepted current or release/handoff states.
- Review artifact: HTML, preview cache, annotations, and parameter patches used for feedback; these are not CAD truth until consumed into authoring truth and regenerated.
- Geometry validation: Checks on generated BRep/STEP geometry such as solid validity, dimensions, clearances, wall thickness, containment, and assembly relationships.
- Analytical definition: A reusable mathematical description of geometry, such as a polynomial path, parametric cross-section, or named engineering profile.
- Formula module: Tested source code that evaluates an analytical definition for use by a backend model generator.
- Component registry: A structured list of purchased, imported, fixed, and generated components with geometry sources, envelopes, interfaces, keepouts, and provenance.
- Envelope: A conservative bounding shape or simplified solid used for layout, clearance, and containment checks.
- Keepout: A region that generated geometry must not occupy because it is needed for motion, heat, connectors, buttons, wires, service access, or other physical constraints.
- Layout proposal: A candidate arrangement of components and generated parts, with explicit assumptions and tradeoffs, created before detailed geometry.
- Interactive parameter surface: An HTML review UI that edits only explicit live-preview-bound model parameters without becoming the source of CAD truth or accepting natural-language modeling requests.
- Parameter patch: A schema-valid saved parameter update from a review UI for a manifest-exposed, editable parameter. It must pass type, unit, bounds, and step checks before being applied to `parameters.yaml`, then backend geometry must be regenerated and validated.
- Root spec: The top-level `spec/current.yaml` file that identifies the active model or assembly, declares units and project-wide intent, and references any same-project sub-specs.
- Sub-spec: A local spec file referenced by the root spec to keep a complex model-project domain reviewable, such as components, enclosure, mechanism, electronics mounting, airflow, formulas, or validation.

## User Mental Model
- Users describe engineering intent in natural language, often incompletely.
- The agent should ask for missing constraints only when needed for safe model generation.
- The output should feel like an engineering workflow: parameters, assumptions, generated geometry, validation, and export options.
- Users may want to point to specific geometry regions or features instead of describing every change in natural language.
- Users expect modeling to be iterative; the workflow should assume repeated adjustment, inspection, and refinement rather than one-pass correctness.
- Users usually need one-step rollback and current-vs-previous comparison more than full internal version management inside a single model project.

## Business Or Technical Rules
- Do not rely on freehand CAD API calls as the primary modeling method.
- Separate intent parsing, spec normalization, geometry generation, and validation.
- Prefer parameterized, repeatable model-generation flows that can be inspected and revised.
- Preserve adjustable parameters and generated previews as first-class outputs.
- Design early part templates so they can later grow into assembly templates.
- Treat each model project as the authoring truth for one chosen model or assembly, not a container for multiple product variants.
- Do not describe `spec/current.yaml` or `parameters.yaml` as the full production source of truth; call them authoring truth unless release-grade CAD/PMI/validation artifacts are present.
- Separate authoring artifacts, review artifacts, validation artifacts, and release artifacts in the model-project template.
- Treat face/edge-level selection as unstable unless mapped through stable feature/component IDs or backend-supported persistent identifiers.
- For V1 CAD scope, prioritize editable parametric geometry, STEP export, solid validity, dimensions, clearances, and assembly relationships.
- Treat STL/OBJ/mesh files as reference inputs only unless a future explicit adapter adds mesh export or reverse-engineering support.
- Treat STEP/BREP as the preferred build123d-to-CAD handoff when downstream users need non-mesh editable solid geometry.
- Keep the architecture adapter-oriented even though build123d is the V1 default. Do not let build123d-specific templates block optional CadQuery, Zoo/KCL, Fusion, or viewer adapters if they later prove necessary.
- Treat official MCP-native CAD tooling as promising but not automatically superior to local code-first BRep generation; evaluate export quality, source readability, assembly support, validation APIs, cost/auth, privacy, offline operation, and long-term maintainability.
- Keep slicer settings, G-code, material/process profiles, print operations, simulation, animation, and rendering out of default V1 scope.
- Represent formulas in specs by stable identifiers, parameters, units, domains, and references; implement them in source or formula modules.
- Do not let `spec/current.yaml` become a full symbolic math/CAD language; complex math belongs in tested code with concise spec bindings.
- For assemblies, record hard constraints separately from soft design goals. Hard constraints include containment, no collision, minimum clearances, access openings, and mounting alignment. Soft goals include compactness, aesthetics, preferred orientation, and ease of assembly.
- Do not silently invent critical component dimensions. Use user-provided CAD, extracted dimensions, datasheets, or explicit conservative assumptions with review notes.
- Candidate variants or layouts are preselection artifacts. Once the user chooses one direction, `spec/current.yaml` should describe that active direction only; rejected options should not become durable project files by default.
- Expose only declared, bounded parameters with explicit live preview bindings in HTML adjustment surfaces. Suitable examples include wall thickness, fillets, clearances, lengths, hole diameters, thread specs, chamfer widths, and shell thickness when the browser preview effect is known to match the model intent.
- Route layout, exterior-form, structural, feature-topology, and natural-language change requests back to the coding agent's modeling workflow. The user may request a new adjustable parameter there, and the agent should decide whether it is suitable to expose.
- GPU acceleration helps render previews, but CAD regeneration remains a backend responsibility. Treat browser-side live preview as approximate unless it is backed by regenerated geometry and validation.
- HTML review may use derived preview assets or caches, but these are review artifacts, not committed CAD outputs. STEP remains the accepted/handoff CAD exchange output.
- V1 HTML review should support preview, parameter controls, snapped selector annotations with text notes, assembly part show/hide, and optional current-vs-previous comparison. Lasso/freehand markup, explosion view, natural-language input, and direct geometry editing are out of V1 scope.
- Use one-file specs for simple models. Split specs only when complexity creates independent reviewable domains; do not turn one YAML file into a full pseudo-CAD database.
- Let `spec/current.yaml` be a root manifest with explicit local references to sub-specs for complex projects. Complex assemblies are the main V1 trigger, but heavy formula, validation, or imported-data domains may also justify local sub-specs.
- Split complex specs by reviewable domain, not by project variant: fixed components, generated parts, shell/enclosure, airflow, mechanisms, electronics mounting, formulas, and validation are suitable internal sections.
- Treat build123d source as the precise construction layer for V1. Specs and parameters define intent and authoring contract; source code implements the geometry that would be too detailed or fragile to encode in YAML.
- STEP-first accepted/handoff workflows should still keep source provenance, labels, selector refs, geometry facts, snapshots, and validation reports tied back to the model project.
- Default assembly output is one assembly STEP; exporting separate STEP files per generated part is optional and should be enabled only when it helps review, handoff, or downstream CAD use.
- Good V1 parameters include lengths, widths, heights, offsets, wall/shell thickness, clearances, hole diameters, hole spacing, hole-to-edge distances, thread standard and depth, fillet/chamfer size, boss/standoff dimensions, rib count/thickness/spacing, pattern counts, curve/profile controls, and assembly gaps. User-specific feature dimensions can be added through annotation plus natural-language request when the agent judges them stable enough to parameterize.
- Minimum V1 accepted/handoff completion should preserve enough project state for iteration: brief, parameters, build123d source, STEP output, validation evidence, and a review artifact such as HTML or snapshot/review notes. Draft review states may defer STEP but must not be described as complete.
- V1 model-project history should be a two-slot rolling scheme: `current` plus `previous`. Full multi-version history is out of scope unless handled by outer Git/project history.

## Decisions
- See `docs/DECISIONS.md` for the active decision log.

## Assumptions
- CAD backends may vary by target output, installability, and validation needs.
- The first version can stay process-light: generate STEP-oriented engineering CAD without committing to manufacturing, printing, simulation, or rendering workflows.
- Early assembly support can begin with enclosure-style projects where fixed components are packed into generated shells, cradles, lids, bosses, cutouts, and ribs.
- Component libraries and cross-project reuse can be deferred until a later scope.
- Complex spec decomposition stays inside one model project and should not imply reusable component libraries.

## Open Questions
- Can Zoo/KCL satisfy optional agent-native workflows better than the local build123d path, and what evidence would justify adding it as an adapter?
- Should the skill expose only the build123d default in V1, or also define optional backend-specific workflows?
- What model classes should the first version support?
- What validation proof should the skill require: STEP inspection, dimensional checks, review snapshots, source assertions, or all of these by model type?
- Should the skill generate a reusable CLI/template project, or only provide agent instructions and reference examples?
- What model-project artifact set is the smallest useful default?
- What internal preview/cache format best supports snapped selector annotations and part visibility without turning non-STEP files into deliverables?
- What UI schema is sufficient for parameter controls: sliders, numeric inputs, selects, toggles, units, bounds, dependency hints, and validation messages?
- What minimum PMI/GD&T representation should V1 support: none, textual placeholders, structured tolerance fields, or backend-native annotations?
- Should release management remain lightweight model-project metadata, or eventually integrate with Git/PDM-like workflows?
- Which STEP/BRep geometry checks are the minimum useful set for V1?
- What should be bundled as reusable formula references in V1: NACA 4-digit airfoils, polynomial curve templates, splines, loft-section generators, or only examples?
- Should formula modules live under `source/` with the active backend, or under a backend-neutral `formulas/` directory?

## Risks
- Engineering geometry can silently look plausible while violating constraints.
- Backend installation and STEP inspection/review dependencies may be heavy.
- Natural-language requests may omit units, tolerances, manufacturing constraints, or assembly relationships.
- Interactive 3D review UI could become too broad unless scoped around model feedback rather than general CAD editing.
- YAML specs may become a parallel pseudo-CAD system if they try to encode every geometric detail instead of model intent and constraints.
- Exporting viewable meshes can create false confidence because mesh previews do not preserve full CAD topology, tolerances, or manufacturing semantics.
- Treating photos as precise inputs can create false confidence unless scale and dimensions are independently supplied.
- Over-focusing on STL/mesh outputs would weaken the core goal of preserving editable parametric CAD authoring truth and accepted/handoff STEP exchange output.
- Incorrect or undocumented formulas can generate plausible-looking but wrong engineering geometry.
- Layout freedom can cause the agent to make arbitrary industrial-design choices unless assumptions, options, and constraints are made inspectable before geometry generation.
- Real-time parameter previews can create false confidence if the browser preview diverges from backend-generated CAD geometry or skips validation.
- Selector refs can become stale after regeneration; annotations must keep enough context to help the agent rediscover the intended feature when topology changes.
- Cloud/MCP-native CAD routes may improve agent integration while adding dependency, auth, cost, privacy, and reproducibility risks.
