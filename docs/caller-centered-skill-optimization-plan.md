# Caller-Centered Skill Optimization Plan

Date: 2026-06-30

This document is a product-level implementation proposal for the next
`engineering-3d-modeling` optimization pass. It is intentionally written as a
directional plan, not a 1:1 coding checklist. A future implementation session
must first inspect the current repository state, compare this proposal against
the already-implemented P0/P1 safeguards, adjust the plan where the code has a
better local shape, and then implement incrementally.

Out of scope for this document:

- installed-skill vs repo-skill drift;
- automatic migration of old model projects;
- edits under `experiments/`;
- edits to `/Users/bytedance/Documents/cdb`;
- writing installed copies under `/Users/bytedance/.codex/skills` or
  `/Users/bytedance/.agents/skills`;
- merging `main` or pushing remote branches.

## Product Thesis

The P0/P1 work closed the most dangerous correctness gaps: spec coverage,
source contracts, annotation clarity, preview provenance, STEP freshness, and
regenerate transaction safety.

The next optimization should make the skill easier and cheaper for a future
agent to call correctly. The core issue is no longer only "can validation catch
bad states?" It is "can the invoking agent immediately know what small action is
safe, what files are required, and which gates matter without re-reading the
whole skill documentation tree?"

The answer should be a caller-facing control plane centered on
`validation/current_context.json`. References remain important, but they should
explain the system. The daily caller should route from a compact, generated
project digest.

## Cost Model Invariant

The product goal is "large changes pay large context cost; small changes stay
small." This should be a measurable workflow property, not just guidance.

Small work should usually read only:

- `validation/current_context.json`;
- a pending patch or annotation artifact when present;
- the directly affected parameter, manifest, or source section only if the
  context says it is needed.

Large work should intentionally expand context to:

- `spec/current.yaml`;
- `parameters.yaml`;
- `source/model.py`;
- feature registry or layout/report evidence;
- validation, review, and consistency artifacts relevant to the risk.

The control plane should make this expansion explicit through
`routing.context_cost`, `routing.minimum_reads`, `routing.required_gates`, and
`routing.escalation_reasons`.

## Modeling Iteration Rings

From a caller perspective, one modeling iteration should be decomposed into
rings. A future implementation does not need to expose these names to end
users, but the routing and tests should preserve the cost shape.

| Ring | Purpose | Typical token cost | Spatial understanding | Code ability | Math ability |
| --- | --- | --- | --- | --- | --- |
| Route and inspect | Identify project state and next safe action from `current_context` | Tiny | Low | Low | Low |
| Intent normalization | Convert user/review intent into controlled target/reference/operation/dimension/validation fields | Small to medium | Medium to high when geometry is ambiguous | Low | Medium |
| Authoring truth update | Update spec, parameters, decisions, assumptions, or feature registry | Small to medium | Medium | Low to medium | Medium |
| CAD implementation | Modify `source/model.py`, placements, constraints, or adapters | Medium to large | High | High | Medium to high |
| Preview and validation | Build/smoke, update review preview, run targeted gates, refresh context | Small to medium | Medium | Medium | Low to medium |
| User review consumption | Apply parameter patch or annotation after clarity checks | Small when patch-only, medium when geometry changes | Medium | Medium | Low to medium |
| Explicit export or handoff | Export STEP or package handoff after user asks or delivery is required | Small to medium | Low to medium | Medium | Low |

The route should not automatically move through every ring. For example, a
first-pass model should normally stop at preview and `draft_review_ready`.
Parameter-only review feedback should avoid the full CAD implementation ring
when the current parameter state proves the change is safe.

## Diagnosis From Caller Perspective

### 1. The Skill Is Still Too Document-Driven

The current design asks agents to understand `SKILL.md`, context routing,
model-project roles, review HTML, validation, source contracts, and multiple
scripts. That is defensible for development, but expensive for ordinary model
iteration.

A future agent usually needs one of these actions:

- inspect current state;
- apply a pending parameter patch;
- consume an annotation;
- make one geometry change;
- update review preview;
- export STEP;
- create handoff package;
- ask for clarification.

The project should tell the agent which one applies, what to read, and what not
to touch.

### 2. Parameter Truth Is Repeated In Too Many Places

The same parameter can appear in:

- `parameters.yaml`;
- `review/manifest.json`;
- `review/parameter_patch.json`;
- `review/cache/current_mesh.json`;
- preview adapter code;
- `source/model.py`;
- validation reports.

P0/P1 added audits around consumption and freshness, but a caller still has to
compose the state mentally. The next pass should expose a compact parameter
state projection so small slider changes remain small.

### 3. Review HTML Still Carries Too Much Meaning

Review HTML currently mixes:

- visual preview;
- exposed parameter controls;
- pending parameter patch;
- annotations;
- selectable refs;
- preview mesh cache;
- optional adapter semantics;
- provenance;
- local save mechanics.

That is fine for UI implementation, but not fine as the caller's mental model.
The next pass should summarize review state into explicit categories:

- pending input;
- preview trust;
- parameter-panel trust;
- annotation clarity;
- refs availability.

### 4. First Iteration Stop Point Must Be Machine-Visible

The desired first iteration is not "STEP generated". It is:

1. authoring truth drafted;
2. source can build or smoke;
3. review preview is available;
4. coverage and validation summaries are present;
5. user can inspect the HTML and give feedback.

This should be represented as `draft_review_ready`. STEP export should remain an
explicit later action unless the user requests it.

### 5. Validation Is Becoming A Script Matrix

There are now multiple useful gates: environment, quick validation, project
validation, coverage audit, consistency audit, review validation, source
interface checks, STEP export checks. This is correct internally, but the caller
needs a generated gate plan for the current task.

The same project state should say:

- which gates are required for this next action;
- which gates are optional;
- which gates can be skipped and why;
- which warnings block export or handoff.

### 6. Feature Registry Can Become Manual Debt

`validation/feature_registry.json` is useful, but it should not become a second
CAD implementation or a hand-maintained checklist that drifts. The next pass
should prefer lightweight source anchors and generated registry updates.

Example anchors:

```python
# feature: fan_grille
# parameter: grille_pitch
# placement: motor_axis
# constraint: blade_clearance
```

The generated registry can then index anchors, while hand-authored registry
entries remain supplemental evidence for complex models.

### 7. Small Words Can Hide Large CAD Risk

A user may phrase a request as a small change, but terms like hole, clearance,
fit, axis, mount, connector, PCB, battery, thread, cutout, bearing, or wall
thickness often imply geometry, assembly, manufacturing, or validation risk.

Routing should upgrade context cost and gates based on risk signals, not only
on request length.

### 8. Legacy Paths Should Not Appear In Daily Routing

`previous/`, `promote_model_project.py`, old accepted/release lifecycle states,
and compatibility rollback paths still matter for old projects. They should not
be default daily routes for new projects unless current context shows a legacy
phase or active compatibility workflow.

### 9. Input Precision Should Be Explicit

The skill accepts natural language, photos, dimensioned drawings, STEP/STP, and
fixed components. These have different precision levels. Future agents should
not infer precise engineering dimensions from qualitative references.

The project digest should separate:

- precise facts;
- qualitative references;
- fixed components;
- assumptions requiring confirmation.

## Proposed Target Architecture

### Brief And Spec Boundary

`brief.md` should remain a short human-facing summary generated from confirmed
intent. It should not be a hidden context cache for the agent.

The scaffold and summary flow should preserve these rules:

- no open questions in `brief.md`;
- no long requirement lists;
- no parameter tables;
- no bbox, placement, transform, or validation evidence;
- no iteration history or agent diagnostics;
- point readers to structured truth files instead of duplicating them.

`spec/current.yaml` remains the structured authoring truth for coordinate
system, placements, features, constraints, decisions, and validation targets.
This boundary matters for token cost: future agents should not need to read a
long `brief.md` to recover exact engineering state.

### Current Context As Agent Control Plane

Extend `validation/current_context.json` so it becomes the caller's first
machine-readable control plane, not just a summary.

Recommended shape:

```json
{
  "routing": {
    "next_action": "inspect",
    "intent": "continue_existing_project",
    "context_cost": "tiny",
    "recommended_tags": ["continue_existing_project"],
    "minimum_reads": [
      "validation/current_context.json"
    ],
    "optional_reads": [],
    "required_gates": [],
    "forbidden_actions": [
      "export_step",
      "handoff_package"
    ],
    "escalation_reasons": []
  },
  "trust": {
    "authoring_truth": "current",
    "review_preview": "current",
    "parameters": "current",
    "step": "not_exported",
    "handoff": "not_requested"
  },
  "ready_states": {
    "draft_review_ready": true,
    "export_ready": false,
    "handoff_ready": false
  },
  "blockers": [],
  "assumptions": []
}
```

The exact schema should be chosen after inspecting the current
`summarize_model_project.py` output and tests. The important product behavior is
that a caller can read one compact artifact and know the next safe route.

### Parameter State Projection

Add a compact parameter projection, preferably inside `current_context` first.
Do not create a new artifact unless the implementation becomes too large.

Recommended shape:

```json
{
  "parameters_state": [
    {
      "id": "wall_thickness",
      "truth_value": 2.0,
      "review_value": 2.0,
      "pending_patch_value": null,
      "preview_snapshot_value": 2.0,
      "affects_geometry": true,
      "source_consumed": true,
      "review_exposed": true,
      "preview_bound": true,
      "status": "current"
    }
  ]
}
```

Useful statuses:

- `current`;
- `patch_pending`;
- `manifest_mismatch`;
- `preview_stale`;
- `source_unconsumed`;
- `backend_only`;
- `invalid`.

The goal is to let a parameter-only change avoid full spec/source reads unless
the projection says it is unsafe.

### Review State Projection

Add a review-state summary to `current_context`.

Recommended shape:

```json
{
  "review_state": {
    "pending_input": {
      "parameter_patches": 0,
      "annotations": 0
    },
    "annotation_clarity": {
      "status": "clear",
      "blocking_count": 0,
      "assumption_count": 0
    },
    "preview": {
      "status": "current",
      "provenance": "current",
      "mesh": "review/cache/current_mesh.json"
    },
    "parameter_panel": {
      "status": "current",
      "exposed_count": 4,
      "stale_count": 0
    },
    "refs": {
      "status": "available",
      "count": 12
    }
  }
}
```

This reduces the need to inspect `review/manifest.json`,
`review/parameter_patch.json`, `review/annotations.json`, and preview cache for
ordinary continuation.

### Gate Plan

Generate a task-aware validation plan in `current_context`.

Recommended shape:

```json
{
  "gate_plan": {
    "for_next_action": "consume_annotation",
    "required": [
      "review_clarity",
      "source_build_smoke",
      "coverage_audit",
      "update_current_context"
    ],
    "optional": [
      "project_consistency"
    ],
    "skipped": [
      {
        "gate": "step_export",
        "reason": "draft review iteration; user did not request STEP"
      }
    ]
  }
}
```

The generated gate plan should avoid heavy commands for small edits unless
current state or risk terms require escalation.

### First Iteration Ready State

Define `draft_review_ready` as the expected first modeling stop point.

Minimum evidence:

- `brief.md` exists and is short;
- `spec/current.yaml` has structured sections for coordinate system,
  placements, features, constraints, decisions, validation targets;
- `parameters.yaml` exists or is explicitly empty/minimal;
- `source/model.py` has the required source interface;
- source build/smoke succeeds;
- review manifest and preview artifacts exist, or current context explains why
  preview is missing;
- coverage audit has run or is summarized as `not_run` with a reason;
- `validation/current_context.json` is refreshed.

Explicitly not required:

- STEP export;
- handoff package;
- accepted/release promotion;
- complete feature release proof.

### Source Anchors And Generated Feature Registry

Add a lightweight convention for source anchors and then consider a script such
as `scripts/update_feature_registry.py` after inspecting existing tests and
registry handling.

Candidate behavior:

- scan `source/model.py` comments for `feature:`, `parameter:`, `placement:`,
  and `constraint:` anchors;
- merge discovered anchors with existing `validation/feature_registry.json`;
- mark generated entries as generated evidence;
- never overwrite hand-authored registry details unless explicitly safe;
- let `audit_spec_coverage.py` use anchors as evidence.

This keeps the registry useful without making agents manually duplicate every
feature in JSON.

### Risk Escalation

Add a small risk classifier used by summary/routing logic.

Candidate risk signals:

- holes, slots, cutouts, ports, openings;
- mounts, bosses, standoffs, threads;
- clearance, gap, fit, collision, interference;
- axes, alignment, placement, origin, coordinate direction;
- PCB, battery, connector, motor, bearing, gear, fan, impeller;
- wall thickness, ribs, chamfers, fillets when manufacturing or fit matters.

Suggested behavior:

- tiny: inspect-only or already-summarized state;
- small: declared safe parameter patch with current preview and no high-risk
  mismatch;
- medium: one feature change, one annotation, stale preview, or source edit;
- large: assembly alignment, fixed components, multiple feature changes,
  coverage gaps, stale STEP before delivery, or high-risk unclear annotation.

### Input Precision Summary

Add input precision to `current_context` when enough data exists.

Recommended shape:

```json
{
  "input_precision": {
    "precise": [
      "motor diameter from dimensioned drawing"
    ],
    "qualitative": [
      "rounded handheld enclosure proportions from photo"
    ],
    "fixed_components": [
      "battery pack envelope"
    ],
    "assumptions_requiring_confirmation": [
      "handle grip radius inferred from ergonomic target"
    ]
  }
}
```

This helps future agents avoid treating qualitative references as exact CAD
constraints.

### Legacy Route Suppression

Current context should hide or de-prioritize legacy daily routes unless current
project state requires them.

Examples:

- Do not recommend `promote_model_project.py` for normal first iteration.
- Do not recommend reading `previous/` unless rollback or comparison is active.
- Do not recommend handoff package unless user asks for delivery.
- Keep legacy compatibility visible in references, not in daily route output.

## Implementation Strategy

Future implementation should proceed in small, testable steps.

### Step 1: Audit Current State Before Coding

Read:

- `AGENTS.md`;
- `PROJECT_STATUS.md`;
- `docs/caller-centered-skill-optimization-plan.md`;
- `engineering-3d-modeling/SKILL.md`;
- `engineering-3d-modeling/references/context-routing.md`;
- `engineering-3d-modeling/references/model-project.md`;
- `engineering-3d-modeling/references/review-html.md`;
- `engineering-3d-modeling/references/validation.md`;
- current scripts and tests around summarization, coverage, validation, review,
  consistency, regenerate, and scaffolding.

Then answer before implementing:

- What already exists from P0/P1?
- Which proposal items are redundant with current code?
- What is the smallest schema extension that gives the caller a real benefit?
- Which tests should fail first?

### Step 2: Enrich `current_context` Routing

Update `summarize_model_project.py` and scaffold initialization so
`validation/current_context.json` exposes:

- `routing.next_action`;
- `routing.context_cost`;
- `routing.minimum_reads`;
- `routing.required_gates`;
- `routing.forbidden_actions`;
- `trust`;
- `ready_states`;
- `blockers`;
- `assumptions`.

Keep the human summary concise and aligned with the JSON fields.

### Step 3: Add Parameter And Review Projections

Extend summary logic to compute:

- `parameters_state`;
- `review_state`;
- pending patch counts;
- pending annotation clarity state;
- preview/manifest/parameter mismatch signals.

Do this as a projection over existing artifacts. Do not introduce another source
of truth.

### Step 4: Add Gate Plan And Risk Escalation

Implement task-aware gate recommendations from existing project facts.

The first implementation can be simple and deterministic:

- no pending work and current preview: tiny inspect route;
- pending parameter patch only and no mismatch: small patch route;
- pending annotation: clarity gate plus source/build/coverage route;
- stale preview or coverage gaps: medium route;
- assembly/fixed-component/high-risk terms: medium or large route;
- STEP/handoff requested or stale delivery proof: explicit export/handoff route.

### Step 5: Add Source Anchors If Current Code Supports It Cleanly

After inspecting `audit_spec_coverage.py`, decide whether to add source anchors
in this pass.

If added:

- document the anchor format;
- update coverage audit to treat anchors as evidence;
- optionally add a lightweight registry update script;
- add tests showing a source anchor satisfies a declared feature or parameter.

If not added, document why the current feature-registry path is enough for now.

### Step 6: Update References Without Expanding `SKILL.md`

`SKILL.md` should remain short. It should point to the relevant references and
state the daily rule:

- existing project: read `validation/current_context.json` first when present;
- use its recommended route and required gates;
- first iteration stops at draft review unless STEP is explicitly requested;
- unclear high-risk review feedback must trigger the clarity gate.

Detailed schema and examples belong in references.

### Step 7: Validate And Record Status

Expected validation after implementation:

```bash
python3 engineering-3d-modeling/scripts/check_environment.py --json
python3 engineering-3d-modeling/scripts/quick_validate.py engineering-3d-modeling
python3 -m unittest discover -s engineering-3d-modeling/tests
git diff --check
```

Update `PROJECT_STATUS.md` with the completed phase, validation result, next
step, and remaining risks. Do not merge, push, or edit installed skill copies.

## Test Ideas

Add or update unittest coverage for:

- `current_context` includes routing control-plane fields.
- A no-pending-change project recommends a tiny inspect route.
- A pending parameter patch with current preview recommends a small route and
  minimum reads.
- A stale preview changes trust and gate plan.
- A first scaffold reports `draft_review_ready` and `export_ready: false`.
- Coverage gaps appear in blockers or warnings and raise route cost.
- High-risk unclear annotations block regenerate.
- Low-risk assumptions are surfaced in `assumptions`.
- Parameter state reports patch pending, preview stale, source unconsumed, and
  backend-only parameters.
- Review state reports pending annotation count and parameter panel mismatch.
- Legacy phase or rollback state is the only case where legacy route reads are
  recommended.
- Optional source anchors, if implemented, satisfy coverage evidence without
  requiring a fully hand-authored feature registry.

## Acceptance Criteria

The next pass is successful when:

- a future agent can continue an existing model project by reading
  `validation/current_context.json` first;
- tiny/small changes do not require reading the entire skill reference tree;
- medium/large changes still escalate to the right specs, source, and gates;
- review HTML is treated as input/provenance, not implicit CAD truth;
- first iteration does not imply STEP export;
- parameters have a visible single-state projection despite multiple derived
  artifacts;
- docs explain the system, while generated context routes the daily work.

## Non-Goals

- Do not replace YAML authoring truth with a build123d operation AST.
- Do not make review HTML a CAD editor.
- Do not force every project to generate a complete feature registry.
- Do not require STEP for draft review.
- Do not make handoff package creation part of ordinary review iteration.
- Do not add old-project migration tooling.
- Do not add PCB-specific routing in this pass.
- Do not add installed-skill synchronization checks to the skill body.
