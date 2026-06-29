# Context, Routing, And Model-Project Documentation Optimization

Date: 2026-06-29

This document records the agreed optimization plan for the `engineering-3d-modeling` skill after reviewing real usage from the `cdb/power_bank_enclosure` project and the latest workflow changes.

The goal is not to add more ceremony. The goal is to make long-running CAD model projects cheaper and safer for future agents to continue by clarifying:

- when the skill should wake up,
- which project files are authoritative,
- which files to read for each task,
- where unresolved questions belong,
- how `spec/current.yaml`, `brief.md`, `source/model.py`, validation reports, and review artifacts should divide responsibilities.

## Current Diagnosis

The `cdb/power_bank_enclosure` project is a useful stress case:

- `brief.md` had become a human-readable duplicate of `spec/current.yaml`.
- `PROJECT_STATUS.md` had become a long history log, useful for archaeology but expensive as default context.
- `source/model.py` carried geometry generation plus STEP manifest and layout-report writing.
- `spec/current.yaml` was better than prose for agent context, but many important engineering constraints were still natural-language strings.
- Review iteration, parameter preview, fixed-component alignment, STEP freshness, and rollback each required different files, but the skill did not yet provide an explicit context-routing table.
- Existing model-project `AGENTS.md` files can lag behind the current skill flow, so new scaffolds must be stronger about skill wake-up and daily workflow rules.

Recent workflow refactors already changed the main product flow:

- daily modeling is continuous preview revision, not `accept -> handoff`;
- "go back one version" means restoring the previous visible preview checkpoint;
- STEP export is direct via `scripts/export_step.py`;
- handoff is an optional zip package action via `scripts/create_handoff_package.py`;
- legacy `accepted_current` and `release_handoff` promotion remains compatibility behavior only.

This plan focuses on context and documentation architecture on top of that workflow.

## Design Principles

1. Keep `SKILL.md` as a concise router.
   Detailed routing, artifact roles, and schema examples should move to references.

2. Prefer structured project facts over long Markdown history.
   Existing projects should be continued from a compact current-context summary when available.

3. Do not create a second CAD implementation in YAML.
   YAML should express engineering intent, constraints, reference geometry, and validation targets. `source/model.py` remains the executable CAD construction.

4. Avoid duplicate truth.
   A fact should have one authoritative home. Other documents may summarize or reference it, but should not restate it in detail.

5. Route unresolved questions out of `brief.md`.
   Agents should resolve questions before writing confirmed design intent into `brief.md`. Remaining blockers belong in current-context/status artifacts.

6. Use controlled modeling intent as an intake aid.
   User language may stay natural, but agents should translate it through structured target/reference/operation/dimension/validation fields before changing CAD truth.

7. Ask when review feedback is under-specified.
   HTML annotations are not permission for an agent to invent geometry. If a review request lacks critical target, reference, direction, dimension, scope, or validation information, the agent should ask or record an explicit assumption before implementation.

8. Keep this forward-looking.
   The skill is still under active design. Do not add heavy migration tooling for old projects. Future agents can manually clean stale historical docs using the newest rules.

## Target Artifact Roles

### `brief.md`

Human-facing design entry point. It should be short.

Allowed content:

- project purpose in 1-3 sentences;
- current design summary in a few bullets;
- key confirmed user intent that affects design direction;
- review focus if useful;
- pointers to structured truth files.

Not allowed:

- full requirement lists;
- parameter tables;
- bbox, placement, or transform details;
- validation evidence;
- long iteration history;
- open questions;
- agent diagnostics.

`brief.md` is not the source of truth for exact dimensions or constraints.

### `spec/current.yaml`

Root structured authoring contract for the selected model or assembly.

It should own:

- project identity, kind, units, and precision class;
- coordinate system definition;
- input references and interpreted fixed components;
- selected layout direction;
- generated parts/components;
- placements for fixed components and generated parts;
- feature-level engineering intent where useful;
- formal constraints that reduce ambiguity;
- active design decisions with authority metadata;
- validation targets;
- source/output/review/validation file pointers.

It may reference same-project sub-specs for complex assemblies, but V1 should not force every project to create separate `model_spec.yaml`.

### `parameters.yaml`

Parameter truth.

It should own:

- parameter values, units, bounds, steps;
- whether a parameter affects geometry;
- review UI metadata;
- preview binding metadata;
- why a parameter is exposed or not exposed in review when that decision is non-obvious.

Recommended optional fields:

```yaml
review:
  exposed: true
  reason: "adapter updates the center opening preview from the same formula family"
```

or:

```yaml
review:
  exposed: false
  reason: "localized fillet/chamfer; backend-only until a model-specific adapter exists"
```

### `source/model.py`

Executable CAD generation truth.

It should own:

- build123d geometry construction;
- parameter loading;
- deterministic model building;
- source functions for generated parts and features;
- optional layout report generation if that is the local project pattern.

It should not become the only place where engineering intent is documented. Important layout rules and feature intent should be represented in `spec/current.yaml` and/or feature registry so agents do not have to infer the whole design from code.

STEP export and manifest writing may remain supported for compatibility, but the preferred daily flow is direct export through `scripts/export_step.py` so manifest semantics stay consistent.

### `validation/current_context.json`

Machine-readable first-read digest for continuing an existing model project.

It should be generated by a script such as `scripts/summarize_model_project.py`.

It should include:

- project name, kind, units;
- current source entrypoint;
- pending annotation count;
- pending parameter patch count;
- review mesh path, timestamp/hash when available;
- STEP existence and freshness;
- preview checkpoint state;
- latest validation status, errors, warnings;
- key parameter summary;
- key bbox/clearance summary when available;
- unresolved questions/blockers;
- recommended next files to read.

This artifact replaces default full reads of `PROJECT_STATUS.md` for ordinary continuation.

### `validation/feature_registry.json`

Optional index for complex models and assemblies.

It should map model features to implementation and evidence:

- `feature_id`;
- part/component id;
- source function or source anchor;
- relevant parameters;
- representative bbox/points;
- review refs;
- preview adapter involvement;
- validation targets;
- known warnings.

This is an index, not a second implementation.

### `validation/layout_report.json`

Generated engineering facts.

It should own:

- placement results;
- transformed fixed-component bboxes;
- clearances;
- alignment checks;
- generated feature bboxes;
- computed dimensions needed for validation or review diagnostics.

### `validation/report.json`

Validation status and evidence.

It should own:

- validation status;
- errors/warnings;
- snapshot hashes when relevant;
- STEP freshness checks when STEP is required;
- review-parameter audit results when relevant.

It should not become a long narrative log.

### Review Artifacts

Review artifacts are user-feedback and preview data, not CAD truth.

- `review/annotations.json`: user-authored review requests only.
- `review/parameter_patch.json`: saved slider changes waiting to be applied.
- `review/manifest.json`: preview parts, refs, exposed parameters, adapter configuration.
- `review/cache/current_mesh.json`: preview mesh/picking data.
- `review/cache/*adapter.js`: model-specific live preview logic.

Consumed annotations and parameter patches should be cleared after they are incorporated into authoring truth.

### STEP And Handoff Artifacts

- `outputs/step/manifest.json`: STEP freshness and hashes.
- `outputs/step/*.step`: CAD exchange output.
- `outputs/handoff/*.zip`: optional reproducible delivery/release package.

STEP export is a daily action. Handoff package creation is a deliberate package action.

### Rollback Artifacts

- `checkpoints/preview_previous/`: previous visible preview revision, used for "go back one version."
- `previous/`: coarse whole-attempt compatibility snapshot, not the default rollback meaning.

## Controlled Modeling Intent Intake

Freeform natural language is useful for conversation, but it is a weak format for precise CAD reconstruction. The skill should guide users and agents toward controlled modeling intent templates. These templates are not meant to become `brief.md`; they are intake and clarification tools that help the agent update structured project truth.

### Purpose

Controlled modeling intent should help convert:

- natural-language requests,
- dimensioned drawings,
- qualitative photo references,
- STEP/fixed-component facts,
- HTML review annotations,
- parameter slider requests,

into updates to:

- `spec/current.yaml`,
- `parameters.yaml`,
- `validation/feature_registry.json`,
- `source/model.py`,
- `review/manifest.json` and preview adapters when needed.

### New Model Intent Template

For initial modeling, agents should extract or ask for:

- purpose: what the model is for;
- units and coordinate conventions;
- fixed components and their sources;
- generated parts;
- key interfaces, openings, contact faces, and mounting features;
- layout constraints and clearances;
- adjustable parameters;
- validation targets;
- manufacturing or handoff assumptions only when relevant to the model geometry.

### Geometry Feature Template

For a feature request, use fields like:

```text
Feature: button_cutout
Target: lower_body negative-Y side wall
Purpose: expose PCB KEY1 button
Reference: align to KEY1 bbox from pcb.step
Operation: through cut
Shape: rectangle
Dimensions: length X = 5.8 mm, height Z = 2.8 mm
Placement: center X = KEY1 center X, top Z = annotated side-wall edge
Direction: cut from outside negative-Y wall inward
Scope: this cutout only
Preserve: PCB placement and LED openings
Adjustable: length and height can be review sliders
Validation: cutout intersects side wall and aligns to KEY1
```

The agent should translate this into feature entries, parameter entries, source functions, review refs, and validation targets as appropriate.

### Constraint Template

For relationship requests, use fields like:

```text
Constraint: pcb_to_battery_gap
Subject: PCB lowest component-side envelope
Reference: battery top envelope
Relation: Z offset
Value: 2.0 mm
Priority: hard requirement
Validation: layout report gap equals 2.0 mm
```

### Assembly Alignment Template

For fixed-component or assembly positioning, use fields like:

```text
Placement: pcb
Source component: inputs/pcb.step
Reference feature: USB2 mouth face
Target feature: enclosure positive-X inner wall plane
Rotation: 180 deg around Y
Alignment:
  - USB2 mouth face coincident with positive-X inner wall
  - USB2 centerline Y = 0
  - lowest component-side envelope Z = battery top + pcb_battery_gap
Validation:
  - transformed PCB bbox recorded in layout report
  - USB cutout aligns with USB2 bbox
```

### Parameterization Template

For review sliders or backend parameters, use fields like:

```text
Parameter: pcb_wall_base_hole_diameter
Feature: pcb_inner_wall_bases
Unit: mm
Current value: 2.4
Allowed range: 1.6..3.2
Step: 0.1
Review exposure: yes
Preview behavior: adapter required
Reason: localized hole geometry cannot use generic morph
Validation: regenerated hole diameter matches parameter
```

### Review Annotation Clarity Gate

When consuming `review/annotations.json`, the agent should check whether each annotation has enough information to act.

Required clarity dimensions:

- target: which part, face, edge, hole, feature, or global model region;
- operation: add, remove, move, resize, cut, fillet, chamfer, align, offset, avoid, preserve, parameterize;
- reference: selected ref, drawing dimension, STEP feature, existing edge/face/axis, or named component;
- direction: X/Y/Z, normal, radial, axial, inward/outward, toward/away from a reference;
- dimensions: numeric values, units, ranges, tolerance, or named parameter;
- scope: one selected feature, all same-type features, one part, or whole model;
- preserve constraints: what must not change;
- validation: how to determine the change is correct.

If a request is clear, implement it and update structured truth.

If a request has one safe interpretation and the risk is low, the agent may proceed only after recording the assumption in `spec/current.yaml` decisions/constraints or in the current-context blocker/assumption summary, and should report the assumption.

If multiple interpretations are reasonable, or if the request affects assembly fit, holes, clearances, directions, collision risk, or manufacturability, the agent should ask a clarifying question before modeling.

Examples that should trigger clarification:

- "move this hole right a bit" without direction, distance, or coordinate frame;
- "make this wall thicker" without target face, thickness, and growth direction;
- "open a button hole" without button reference, side, shape, clearance, and direction;
- "make it more compact" without axis, adjustable clearances, and preserved features.

Examples that can usually proceed:

- "change this selected circular hole from 2.4 mm to 3.0 mm diameter";
- "set PCB-to-battery Z clearance to 2.0 mm, preserving other layout rules";
- "add M3 internal thread to the selected hole, 4 mm deep, non-through."

### Where The Intake Goes

The templates should feed project truth as follows:

- layout, feature, placement, decisions, constraints, validation targets -> `spec/current.yaml`;
- parameter values, bounds, UI, preview exposure, exposure reason -> `parameters.yaml`;
- feature-to-source/parameter/ref/bbox mapping -> `validation/feature_registry.json`;
- executable geometry -> `source/model.py`;
- live preview parameter exposure and adapter configuration -> `review/manifest.json` and `review/cache/*adapter.js`;
- unresolved questions/blockers -> `validation/current_context.json` or equivalent current-context artifact.

`brief.md` may use the same vocabulary in short human prose, but should not contain the detailed templates or unresolved questions.

## `spec/current.yaml` Structure Direction

`spec/current.yaml` should remain the root contract, but it needs stronger structure for complex models.

### Coordinate System

Use geometry-level fields instead of only prose:

```yaml
coordinate_system:
  origin:
    description: enclosure center in XY at body floor plane
    point_mm: [0, 0, 0]
  axes:
    x:
      vector: [1, 0, 0]
      positive_direction: toward_usb_c_end
    y:
      vector: [0, 1, 0]
      positive_direction: opposite_key1_side
    z:
      vector: [0, 0, 1]
      positive_direction: toward_upper_cover
```

### Fixed Components And Placements

For assemblies, fixed-component transforms should be explicit enough that an agent can reason about alignment without re-parsing prose.

```yaml
placements:
  pcb:
    source_component: pcb_step
    transform:
      rotation:
        axis: y
        angle_deg: 180
      rules:
        - id: usb2_mouth_to_positive_x_wall
          type: coincident
          subject: pcb.usb2.mouth_face
          reference: enclosure.positive_x_inner_wall_plane
        - id: usb2_center_y
          type: align_to_axis
          subject: pcb.usb2.center_y
          reference_axis: y
          value_mm: 0.0
```

Use rule-based placement first. Only require transform matrices when the project actually needs matrix-level evidence.

### Features

Feature-level specs should capture engineering intent, not every CAD operation.

```yaml
features:
  - id: pcb_inner_wall_bases
    parent_part: body_shell
    type: support_base_pair
    centers_assembled_mm:
      - [34.154, -7.0]
      - [34.154, 7.0]
    top_contact:
      target: pcb.board_underside
      z_mm: 30.2
    blind_hole:
      diameter_parameter: pcb_wall_base_hole_diameter
      depth_mm: 3.0
      through: false
      require_bottom_material: true
    underside:
      type: continuous_ramp
      angle_deg: 45
      low_end: type_c_end
```

The source function still decides how to construct this in build123d.

### Formal Constraints

Avoid writing all critical constraints as plain strings.

```yaml
constraints:
  formal:
    - id: battery_to_pcb_gap
      type: clearance
      subject: pcb.lowest_component_side_envelope
      reference: battery.top_envelope
      relation: offset_z
      value_parameter: pcb_battery_gap
    - id: usb_mouth_to_positive_x_wall
      type: placement
      subject: pcb.usb2.mouth_face
      reference: enclosure.positive_x_inner_wall_plane
      relation: coincident
  narrative:
    - PCB is stacked above the 21700 cell to reduce case width.
```

Narrative constraints are allowed for orientation, but critical geometry should be formalized when feasible.

### Decisions

Use explicit decision metadata when a choice was inferred, reviewed, or user-confirmed.

```yaml
decisions:
  - id: pcb_orientation_flip_y_180
    status: active
    statement: PCB is flipped 180 degrees around Y so the component side faces the battery.
    authority: agent_inferred_from_review
    confidence: high
    user_confirmed: false
    affects:
      - pcb_placement
      - usb_cutout
      - led_cutouts
      - key1_cutout
```

This helps agents understand what is stable and what may need confirmation.

### Validation Targets

Validation targets should reference parameters, features, and placements where possible.

```yaml
validation_targets:
  clearances:
    battery_to_pcb_parallel_gap:
      equals_parameter: pcb_battery_gap
  features:
    pcb_inner_wall_bases:
      blind_hole_non_through: true
      bottom_material_min_mm: 0.2
```

## Skill Wake-Up Strategy

`init_model_project.py` should generate project `AGENTS.md` that explicitly wakes the skill for:

- model creation and modification;
- continuing an existing model project;
- HTML review annotations and parameter patches;
- preview regeneration;
- preview rollback;
- STEP export;
- handoff package creation;
- review server work;
- validation and diagnostics.

The generated instructions should also say:

- start from `validation/current_context.json` or `scripts/summarize_model_project.py` output when available;
- do not default to full history reads;
- do not hand-roll replacement review HTML;
- do not treat review artifacts as CAD truth;
- do not use legacy `accept`/`handoff` promotion as the daily path;
- "go back one version" means preview checkpoint restore;
- "export STEP" means direct `scripts/export_step.py`;
- handoff is an optional zip package action.

Project `AGENTS.md` should stay high-level. It should wake the skill and name the local project rules, but it should not copy the full task-routing table, schema examples, or controlled-intent templates. Detailed routing should live in the installed skill reference:

```text
references/context-routing.md
```

This keeps new projects from freezing a long copy of skill internals that will drift as the skill evolves.

## Global Context Routing Flow

The intended read path for an existing model project is:

```text
project AGENTS.md
  -> $engineering-3d-modeling SKILL.md
  -> validation/current_context.json or summarize_model_project.py
  -> composable task tags
  -> exact truth/evidence files for those tags
  -> optional human/history files only when needed
```

Use this flow to avoid defaulting to full reads of `brief.md`, `spec/current.yaml`, `source/model.py`, `validation/report.json`, and long history files every turn.

General rules:

- `AGENTS.md` wakes the skill and states local boundaries.
- `SKILL.md` provides the main workflow and routes to references.
- `validation/current_context.json` gives the current project state and recommended next reads.
- `references/context-routing.md` decides which project files to load for the current task tags.
- `brief.md` is a human summary and should not be required for ordinary implementation.
- `PROJECT_STATUS.md`, `previous/`, historical logs, and handoff packages are not default context; read them only for archaeology, rollback, handoff review, or explicit user questions.

## Composable Context Routing

Task routing should use composable tags. A single user request may include multiple tags.

Planned tags:

- `new_model_project`
- `continue_existing_project`
- `consume_review_feedback`
- `update_review_preview`
- `parameter_preview_or_adapter`
- `geometry_feature_change`
- `assembly_alignment`
- `step_export`
- `handoff_package`
- `preview_rollback`
- `preview_vs_cad_mismatch`
- `validation_failure`

When multiple tags apply:

1. Start with `validation/current_context.json` or run `summarize_model_project.py` when available.
2. Merge the minimum read sets for all matching tags.
3. Prefer structured files over long Markdown.
4. Prefer feature registry and `rg`-located source functions over full `source/model.py` reads.
5. Do not read `previous/` unless rollback or comparison is requested.
6. Do not read full history logs by default.

## Artifact Directory For Routing

`references/context-routing.md` should include a quick artifact directory:

- `brief.md`: short human design brief and intent summary.
- `spec/current.yaml`: root structured authoring contract.
- `parameters.yaml`: parameter truth and review/preview metadata.
- `source/model.py`: executable CAD generation truth.
- `validation/current_context.json`: first-read project digest.
- `validation/layout_report.json`: generated placement, bbox, clearance, alignment facts.
- `validation/report.json`: validation status and evidence.
- `validation/feature_registry.json`: feature-to-source/parameter/ref index when available.
- `review/annotations.json`: pending user review requests.
- `review/parameter_patch.json`: pending saved slider changes.
- `review/manifest.json`: preview parts, refs, exposed parameters, adapter config.
- `review/cache/current_mesh.json`: preview geometry and picking data.
- `review/cache/*adapter.js`: live preview logic.
- `outputs/step/manifest.json`: STEP freshness and hash evidence.
- `checkpoints/preview_previous/`: previous visible preview revision.
- `previous/`: coarse whole-attempt rollback snapshot.

This lets agents reason about tasks not explicitly covered by a tag.

## Review Iteration Read/Write Discipline

Review iteration is the highest-frequency path.

Typical reads:

- `validation/current_context.json` or `summarize_model_project.py` output;
- `review/annotations.json`;
- `review/parameter_patch.json`;
- related `parameters.yaml` entries;
- related `review/manifest.json` refs and exposed parameters;
- `validation/feature_registry.json` when available;
- targeted `source/model.py` functions;
- related `validation/layout_report.json` sections.

Typical writes:

- create preview checkpoint before visible model changes;
- apply parameter patches into `parameters.yaml`;
- convert annotations into `spec/current.yaml`, `parameters.yaml`, or `source/model.py`;
- regenerate `review/cache/current_mesh.json`;
- update `review/manifest.json`;
- clear consumed annotations and patches;
- update validation report and current context;
- mark existing STEP stale when authoring truth or preview output changes.

Forbidden writes:

- do not store agent diagnostics in `review/annotations.json`;
- do not carry consumed annotations forward;
- do not use `brief.md` as a long iteration log;
- do not create a handoff package as part of ordinary review iteration.

## Implementation Plan

### Phase 1: Documentation And Scaffold Rules

- Update `SKILL.md` resource routing to include `references/context-routing.md`.
- Add or reference controlled modeling intent templates for natural-language, review-annotation, feature, constraint, assembly-alignment, and parameterization requests.
- Add `references/context-routing.md`.
- Update `references/model-project.md` with the new artifact roles.
- Update `init_model_project.py` generated `AGENTS.md` so it wakes `$engineering-3d-modeling`, points to `references/context-routing.md` for detailed task routing, and stays short enough to avoid becoming a stale copy of the skill.
- Update `init_model_project.py` generated `brief.md` so it is short and has no `Open Questions` section.
- Update `init_model_project.py` generated `spec/current.yaml` skeleton to include stronger sections for coordinate system, placements, features, constraints, decisions, and validation targets.

### Phase 2: Current Context Summary

- Add `scripts/summarize_model_project.py`.
- Generate human summary by default.
- Support writing `validation/current_context.json`.
- Include pending review counts, STEP freshness, validation status, key parameters, key layout facts, blockers, and recommended next reads.
- Use the script in context-routing guidance for continuing existing projects.

### Phase 3: Feature Registry Convention

- Document `validation/feature_registry.json`.
- Add lightweight validation or schema checks if practical.
- Prefer generation from `source/model.py` or layout report where feasible, but do not require all projects to implement it.

### Phase 4: Review Iteration And Validation Integration

- Ensure `regenerate_from_review.py` updates current context after successful regeneration.
- Ensure STEP stale marking is reflected in current context.
- Add review annotation clarity-gate guidance so agents ask clarifying questions when annotations are not executable enough.
- Add tests for review iteration read/write expectations where script behavior is involved.

### Phase 5: Optional Schema Tightening

- Add validation warnings for overly long `brief.md`, `brief.md` containing `Open Questions`, or `brief.md` duplicating obvious validation/parameter tables.
- Add validation warnings when `spec/current.yaml` has only narrative constraints in complex assembly projects and no structured placements/features.
- Keep these as guidance first, not hard failures.

## Out Of Scope

- Automatic migration of old projects.
- `audit_project_agents.py`.
- Installed-skill consistency checks.
- PCB-specific routing categories.
- Requiring a separate `model_spec.yaml` for all projects.
- Encoding every build123d operation as YAML.
- Making `PROJECT_STATUS.md` a standard model-project interface.

## Acceptance Criteria

- New project scaffolds strongly wake `$engineering-3d-modeling` for model/review/export/rollback tasks.
- Project `AGENTS.md` initializes high-level wake-up and local boundaries, but delegates detailed routing to `references/context-routing.md`.
- New `brief.md` templates are short, human-facing, and do not include open questions.
- New `spec/current.yaml` templates point toward structured constraints and feature/placement sections.
- Agents have a dedicated context-routing reference with composable task tags and artifact roles.
- Agents have controlled modeling intent templates and a review-annotation clarity gate before converting ambiguous review feedback into CAD changes.
- Existing projects can be summarized through `summarize_model_project.py` without reading long history files first.
- Review iteration guidance clearly says what to read, what to write, and what not to write.
- The plan preserves the core truth split: `spec/current.yaml` for structured intent, `parameters.yaml` for parameter truth, `source/model.py` for executable CAD, validation reports for generated facts, review artifacts for user feedback.
