# Backend Bake-off Plan

## Memory Metadata
- owner: backend-selection-validation-plan
- read_when: evaluating CAD backends, running candidate spikes, or choosing the default modeling route
- update_when: candidate set, gates, fixtures, scoring, or execution ownership changes
- max_lines: 360
- stale_if: a default backend is selected or the skill scope changes away from editable engineering CAD

## Purpose
Status: completed for V1 default selection on 2026-06-18; see `docs/DECISIONS.md` and `experiments/backend-bakeoff/reports/comparison.md`. Keep this file as the historical test protocol unless evaluating optional adapters.

## Maintenance Rules
- Keep this file as backend bake-off protocol/evidence context.
- Update only when candidate set, gates, fixtures, scoring, or optional adapter evaluation changes.
- Do not store run logs, debug traces, or session history here.

Choose the default modeling backend for the engineering 3D modeling skill with evidence, not preference.

The bake-off tests how each candidate supports the project's actual skill contract:
- editable text-based authoring truth
- deterministic regeneration from specs and parameters
- BRep/non-mesh solid handoff where practical
- print-targeted STL/3MF or mesh export as downstream artifacts
- formula-driven geometry
- assembly/enclosure workflows
- validation and diagnostics
- agent ergonomics during creation and iteration

This plan is not trying to find the universally best CAD system.

## Candidate Tiers

### Tier A: implementation bake-off
- `build123d`: local Python BRep candidate.
- `CadQuery`: local Python/OpenCascade candidate and close comparison point.

### Tier B: implementation if access is available, otherwise research-plus-probe
- `Zoo/KCL/MCP`: official MCP-native and KCL text-CAD candidate. Test executable workflows only if MCP/API access and credentials are available without storing secrets in project docs.

### Tier C: reference or adapter analysis only for now
- Fusion 360 API: downstream editor/import/export or explicit Fusion-native adapter candidate.
- FreeCAD: open-source CAD/Python validation or adapter candidate.
- Onshape FeatureScript/API: cloud CAD/API candidate, likely later-stage because of platform dependency.
- OpenSCAD/JSCAD: useful for simple printable CSG, not primary BRep truth candidate.
- Blender/MCP: useful for visualization/mesh assets, not primary engineering CAD truth candidate.

## Hard Gates
A backend cannot be the V1 default unless it satisfies all hard gates:

1. Text source gate: model source is inspectable text that can be versioned and regenerated.
2. Headless/scriptable gate: generation can run from a command, script, API, or MCP tool without manual GUI modeling.
3. Parametric edit gate: simple parameter changes regenerate predictable geometry without manual repair.
4. Solid geometry gate: backend can create valid solid/BRep-style geometry, not only display meshes.
5. Export gate: backend can export at least one CAD exchange artifact and one print/view artifact appropriate for the project.
6. Validation gate: backend exposes enough geometry data or outputs to check dimensions, solid validity, and export success.
7. Reproducibility gate: another agent can run or review the workflow from project artifacts without hidden session state.

Zoo/KCL may remain an optional MCP-native adapter even if cloud/auth constraints prevent it from being the local default.

## Test Fixtures

Use the same intent and acceptance criteria across candidates. Candidate-specific code is allowed, but the model meaning must stay the same.

### Fixture 1: printable parametric part
Model: rounded mounting plate.

Required features:
- Units: millimeters.
- Base body: 80 x 50 x 4 mm rectangular plate.
- Rounded outside corners: 4 mm radius.
- Four M3 clearance holes on a rectangular bolt pattern.
- Optional counterbore or countersink if backend supports it cleanly.
- Center pocket or recess with bounded depth.
- Edge fillets or chamfers controlled by parameters.

Parameter edits:
- `plate_thickness`: 4 -> 6 mm.
- `corner_radius`: 4 -> 6 mm.
- `hole_diameter`: 3.2 -> 3.6 mm.
- `edge_fillet`: 1 -> 1.5 mm.

Acceptance:
- Script executes from a clean command.
- Generated solid is valid according to backend-accessible checks where possible.
- Bounding box matches expected dimensions within 0.1 mm after each parameter set.
- Exports include STEP or equivalent solid exchange when available, plus STL or mesh/view export.
- Source remains readable and parameterized.

### Fixture 2: formula-driven geometry
Model: small guide-vane or duct section using analytical definitions.

Required features:
- A fifth-degree polynomial radius or centerline law with documented boundary conditions.
- A NACA 0012 or similarly named profile generated from formula parameters.
- Parameters for chord, span, thickness ratio, angle/twist, and section count.
- Formula implementation separated enough to be tested independently or clearly identified in KCL/code.

Acceptance:
- Formula values can be sampled and checked before CAD generation.
- Profile dimensions match expected chord and thickness behavior.
- Generated geometry is a valid solid or clearly reported if a backend only supports surface/mesh at this stage.
- Parameter changes regenerate geometry without rewriting topology by hand.
- Failure modes such as self-intersection or invalid domains are reported clearly.

### Fixture 3: power-bank assembly/enclosure
Model: compact 21700 power-bank enclosure with fixed component envelopes and optional module CAD.

Fixed components:
- One 21700 cell envelope: cylinder, 21 mm diameter x 70 mm length.
- One charge/discharge module imported from `experiments/backend-bakeoff/shared/inputs/cad/charge_discharge_module/` when available.
- One fallback charge/discharge module envelope: 45 x 20 x 7 mm box.
- One connector keepout on the module edge.

Generated parts:
- Lower shell or cradle with wall thickness and clearance parameters.
- Lid or cover with simple attachment features.
- Access opening or cutout for connector/service access.

Validation targets:
- Fixed components fit inside the enclosure.
- Minimum clearance around fixed components is enforced.
- No generated solid intersects fixed component envelopes.
- Wall thickness and screw/boss dimensions are parameterized.
- Assembly export or preview preserves named components where practical.

Acceptance:
- Component registry/layout data is explicit, not buried only in geometry code.
- At least one generated preview or exploded/annotated output can support user review.
- Collision/clearance validation is implemented or a precise backend limitation is recorded.

### Fixture 4: iteration and adoption
Use the candidate output from Fixtures 1-3 and apply one change request:
- Increase clearance around the PCB by 0.4 mm.
- Change shell wall thickness by 0.5 mm.
- Move or resize one simple cutout.

Acceptance:
- Change is made through parameters/specs when suitable.
- Generated source remains maintainable.
- Previous outputs can be regenerated for comparison.
- The agent can explain what changed without manually reverse-engineering opaque geometry.

### Fixture 5: complex sustained assembly modeling
Model: handheld fan enclosure/assembly with fan, batteries, boards, switch mechanism, shells, grille, and internal features.

Required features:
- Fixed component registry for a 4028 fan, two 18650 cells, PWM controller board, battery protection board, charge module, boost module, thumbwheel, and drive gear.
- Generated front shell, rear shell, internal frame, switch mechanism, and component-envelope outputs.
- Named outputs that can support future visual review and selection/annotation workflows.
- Backend-neutral layout/validation report that checks containment, clearances, fixed-component intersections, generated-feature intersections, fan centering, battery separation, charge-port marker alignment, and switch placement.

Iteration case:
- Increase `wall_thickness` by 0.4 mm.
- Increase `fan_clearance` by 0.5 mm.
- Increase `electronics_clearance` by 0.4 mm.
- Move `switch_offset_y` 4 mm toward the fan head.

Acceptance:
- Baseline and edited cases regenerate from the same source.
- Named generated parts export successfully.
- Validation report records component placements, generated feature bounds, clearance checks, changed parameters, and footprint changes.
- The backend implementation remains maintainable enough for an agent to identify and modify each named generated part.
- This fixture is still an engineering proxy, not a finished industrial design.

## Scorecard
Score each candidate from 0 to 5 per category, then weight to 100.

| Category | Weight | What to Measure |
| --- | ---: | --- |
| Editable authoring truth fit | 15 | Text source clarity, spec/parameter mapping, regenerate-from-source workflow |
| CAD geometry and export quality | 15 | Solid validity, STEP/BREP or equivalent, STL/3MF/preview exports |
| Parameter iteration | 10 | Simple edits, bounded parameters, predictable rebuilds |
| Formula/math support | 10 | Independent formula checks, units/domains, curve/profile generation |
| Assembly/layout support | 15 | Components, envelopes, named parts, joints/placements, collision/clearance |
| Validation and diagnostics | 15 | Dimensions, volume/bounds, solid validity, export checks, actionable failures |
| Agent ergonomics | 10 | API readability, docs, error repair, generated code maintainability |
| Operational fit | 10 | Install/auth friction, offline/locality, licensing, privacy, cost, maturity |

Decision guidance:
- 85+: strong default candidate if hard gates pass.
- 70-84: viable default or optional backend depending on weaknesses.
- 55-69: useful adapter or niche backend.
- Below 55: not a V1 backend unless it uniquely solves a required workflow.

## Output Layout
Use this structure for executable tests:

```text
experiments/backend-bakeoff/
  shared/
    specs/
      fixture-1-mounting-plate.yaml
      fixture-2-formula-vane.yaml
      fixture-3-enclosure.yaml
      fixture-5-handheld-fan.yaml
    parameters/
    inputs/
      cad/
        charge_discharge_module/
          manifest.yaml
          # local CAD inputs such as module.step are intentionally ignored
          # and are not part of the public repository
  build123d/
    source/
    outputs/
    validation/
    backend_report.yaml
  cadquery/
    source/
    outputs/
    validation/
    backend_report.yaml
  zoo-kcl/
    source/
    outputs/
    validation/
    backend_report.yaml
  reports/
    comparison.md
```

Do not store API tokens, private credentials, raw cloud responses with secrets, or large generated binary artifacts in project-memory docs.

Generated CAD/mesh artifacts may be kept under `experiments/` during the bake-off if they are useful for review. If they become large, keep only small representative outputs and validation summaries.

## Backend Report Schema
Each candidate should produce `backend_report.yaml`:

```yaml
candidate: build123d
tested_on: 2026-06-17
tester_thread: ""
version_info:
  backend: ""
  python: ""
  platform: ""
access:
  install_required: true
  auth_required: false
  offline_capable: true
hard_gates:
  text_source: pass
  headless_scriptable: pass
  parametric_edit: pass
  solid_geometry: pass
  export: pass
  validation: pass
  reproducibility: pass
fixtures:
  fixture_1:
    status: pass
    notes: ""
    outputs: []
  fixture_2:
    status: not_run
    notes: ""
    outputs: []
  fixture_3:
    status: not_run
    notes: ""
    outputs: []
  fixture_4:
    status: not_run
    notes: ""
    outputs: []
scores:
  editable_authoring_truth_fit: 0
  cad_geometry_and_export_quality: 0
  parameter_iteration: 0
  formula_math_support: 0
  assembly_layout_support: 0
  validation_and_diagnostics: 0
  agent_ergonomics: 0
  operational_fit: 0
blockers: []
recommendation: undecided
```

## Execution Strategy

### Phase 0: finalize fixtures
Create shared specs and parameters before candidate-specific code. Keep fixture definitions backend-neutral.

Exit criteria:
- Shared fixture specs exist.
- Acceptance criteria are explicit.
- Candidate threads can work independently.

### Phase 1: environment and hello-solid probe
For each candidate:
- Install or identify required runtime.
- Generate a simple box or plate.
- Export one review artifact.
- Record setup friction and version info.

Exit criteria:
- Candidate passes or fails hard gates 1, 2, 4, and basic export.
- Zoo/KCL is marked executable only if MCP/API access is available.

### Phase 2: core capability fixtures
Run Fixture 1 and Fixture 2 for candidates that pass Phase 1.

Exit criteria:
- Parameter iteration and formula support are scored.
- Validation evidence exists.

### Phase 3: assembly/enclosure fixture
Run Fixture 3 for candidates that are still plausible V1 defaults.

Exit criteria:
- Assembly/layout and collision/clearance approach is clear.
- Limitations are explicit.

### Phase 4: iteration workflow
Run Fixture 4 to test change handling, not just initial generation.

Exit criteria:
- Candidate shows whether source/specs stay maintainable after edits.

### Phase 5: comparison and decision
Create `experiments/backend-bakeoff/reports/comparison.md` with:
- hard gate results
- score table
- major failure modes
- recommended default backend
- optional backend/adapters
- implications for skill templates

Only after this phase should `docs/DECISIONS.md` record a default backend decision.

## Multi-thread Guidance
Use the current/main thread for strategy, criteria, and final comparison.

Use a separate Codex conversation per candidate when running executable tests. This reduces context contamination and makes setup/debug traces easier to isolate.

Suggested candidate-thread prompt:

```text
Work in /Users/bytedance/Documents/3d skill.
Read AGENTS.md, PROJECT_STATUS.md, docs/BACKEND_BAKEOFF_PLAN.md, docs/SKILL_SPEC.md, and docs/DOMAIN.md.

Run only the <candidate-name> backend bake-off from docs/BACKEND_BAKEOFF_PLAN.md.
Do not choose the overall winner and do not compare against other candidates.
Create or update only files under experiments/backend-bakeoff/<candidate-name>/ unless shared fixture files are missing, in which case create the minimal shared files under experiments/backend-bakeoff/shared/.

Execute phases 1 and 2 first. If phase 1 fails due to install/auth/runtime constraints, record the failure in backend_report.yaml and stop.
Do not store secrets or credentials in the repository.
At the end, summarize hard gates, completed fixtures, blockers, and remaining work.
```

For Zoo/KCL:
- Start a separate thread only after deciding how credentials/MCP access will be provided.
- If credentials are not available, run a documentation/API feasibility pass instead of pretending to execute the backend.

## Anti-goals
- Do not optimize for the nicest rendered demo.
- Do not choose a backend because it has MCP alone.
- Do not choose a backend because it is local alone.
- Do not let a backend-specific source file replace the structured spec/parameter contract.
- Do not treat STL or glTF preview success as proof of editable CAD truth.
