# Backend Bake-off Comparison

Created: 2026-06-18

## Scope
This comparison covers the current executable bake-off evidence for:
- build123d
- CadQuery

Zoo/KCL is not compared here because MCP/API access has not been tested.

This report is the executable bake-off evidence record. The final V1 default decision is now recorded in `docs/DECISIONS.md`: build123d is selected as the V1 default local CAD backend.

## Summary

| Candidate | Weighted Score | Hard Gates | Fixture 1 | Fixture 2 | Fixture 3 | Fixture 4 | Fixture 5 |
| --- | ---: | --- | --- | --- | --- | --- | --- |
| build123d | 76.0 | pass | pass | pass | pass | pass | pass |
| CadQuery | 78.0 | pass | pass | pass | pass | pass | pass |

Score interpretation from `docs/BACKEND_BAKEOFF_PLAN.md`:
- 70-84: viable default or optional backend depending on weaknesses.
- 55-69: useful adapter or niche backend.

Both candidates are in the viable-default or optional-backend band. CadQuery remains slightly ahead on the executable scorecard, but build123d no longer has an incomplete Fixture 2 result and both candidates passed the complex sustained assembly fixture.

Fixture 5 maintainability edits were also applied after the initial pass. Both candidates regenerated baseline, edited, and left-hand switch cases, exported a separately named front grille, added handle screw bosses, and passed the expanded validation checks. See `experiments/backend-bakeoff/reports/fixture5_maintainability_review.md`.

## build123d Evidence

Report: `experiments/backend-bakeoff/build123d/backend_report.yaml`

Results:
- Fixture 1 passed. It generated baseline and edited mounting plates with STEP/STL exports and valid bbox checks.
- Fixture 2 passed after the fuller rerun. It sampled the quintic radius law and linear twist law, generated a valid duct shell, generated a lofted NACA twist-law vane, exported a circular vane array, and regenerated the edited case with `outlet_angle_deg` 42 and `wall_thickness` 2.5 mm.
- Fixture 3 passed using the shared measured module bbox envelope. It generated lower shell, lid, and component envelope outputs, and passed containment, clearance, component-intersection, port alignment, and target-size checks.
- Fixture 4 passed hard checks after increasing `pcb_clearance` by 0.4 mm and `wall_thickness` by 0.5 mm. The edited shell exceeds the 34 mm target height soft goal at 34.6914 mm.
- Fixture 5 passed. It generated named handheld-fan assembly outputs for front shell, rear shell, internal frame, switch mechanism, and component envelopes across baseline and edited cases, with shared layout validation passing hard checks.
- The raw imported module STEP shape still reports invalid through build123d/OCP validity checks, so it is retained as reference rather than used as the boolean collision body.

Observed strengths:
- Clean local Python/text-source workflow.
- Solid generation and STEP/STL export worked for single parts, duct shell geometry, lofted twist-law vane geometry, and a vane array compound.
- Formula code was easy to isolate and sample, and the fuller rerun kept formula checks separate from CAD generation.
- Complex assembly code stayed organized around named generated parts and shared validation inputs.

Observed weaknesses:
- Vane array STEP export emitted a non-blocking build123d/OCP warning about unknown compound color metadata.
- Fixture 5 still uses simplified solids and AABB validation; it does not prove robust complex boolean recovery or topology-stable feature editing.
- Battery envelope export is a conservative box in the current Fixture 3 validation run; layout checks still use the 21700 cylinder dimensions as an AABB.
- Candidate-local dependency directory is large, about 973 MB total with about 959 MB in `.python-packages`.

## CadQuery Evidence

Report: `experiments/backend-bakeoff/cadquery/backend_report.yaml`

Results:
- Environment blocker was resolved by installing candidate-local packages under `experiments/backend-bakeoff/cadquery/.python-packages`.
- Fixture 1 passed. It generated baseline and edited mounting plates with STEP/STL exports, valid solids, and bbox checks within tolerance.
- Fixture 2 passed for this fixture scope. It generated formula samples, NACA profile checks, a duct shell solid, lofted twist-law vane solids, and circular vane array outputs with STEP/STL exports.
- Fixture 3 passed using the shared measured module bbox envelope. It generated lower shell, lid, and component envelope outputs, and passed containment, clearance, component-intersection, port alignment, and target-size checks.
- Fixture 4 passed hard checks after increasing `pcb_clearance` by 0.4 mm and `wall_thickness` by 0.5 mm. The edited shell exceeds the 34 mm target height soft goal at 34.6914 mm.
- Fixture 5 passed. It generated named handheld-fan assembly outputs for front shell, rear shell, internal frame, switch mechanism, and component envelopes across baseline and edited cases, with shared layout validation passing hard checks.
- The raw imported module STEP shape still returns invalid from CadQuery `isValid()`, so it is retained as reference rather than used as the boolean collision body.

Observed strengths:
- Strong formula-driven geometry evidence, with duct shell, lofted twist-law vane, and circular vane array outputs.
- Headless script execution and STEP/STL export worked after environment setup.
- Validation JSON is detailed and separates formula checks from geometry checks.
- Complex assembly code used the same named-output pattern as build123d without relying on face selectors for Fixture 5.

Observed weaknesses:
- Fixture 1 used chamfer for the `edge_fillet` parameter after an OpenCascade fillet attempt failed; this is acceptable for the fixture wording but should be noted as an API/robustness issue.
- Fixture 5 still uses simplified solids and AABB validation; it does not prove robust complex boolean recovery or topology-stable feature editing.
- Candidate-local dependency directory is large, about 876 MB total with about 873 MB in `.python-packages`.

## Shared Findings

### Module STEP Validity
Both candidates imported the charge/discharge module STEP, and both reported the top-level imported shape as invalid:
- build123d/OCP validity: false
- CadQuery `isValid()`: false

The shared diagnostic report is `experiments/backend-bakeoff/shared/validation/module_step_diagnostics.json`.

It shows:
- top shape type: Compound
- top valid: false
- solids: 229 total, 224 valid, 5 invalid
- faces: 4706 total, 4701 valid, 5 invalid
- edges and vertices: all valid in this diagnostic

Current measured module bbox is about:
- x: 28.05 mm
- y: 18.50 mm
- z: 5.19 mm

This differs from the fallback envelope in Fixture 3:
- x: 45 mm
- y: 20 mm
- z: 7 mm

Fixture 3 now uses the measured bbox envelope for containment, clearance, and collision checks while retaining the raw STEP as reference input. This is a deliberate validation policy, not a silent fallback.

### Dependency Footprint
Both local Python BRep routes require large package trees due to OCCT/OCP/VTK dependencies. These directories are acceptable for experiments but must not become part of the final skill package.

## Current Recommendation

Choose build123d as the V1 default local CAD backend.

CadQuery has slightly stronger executable scorecard evidence, with a weighted score of 78 vs build123d at 76. That two-point gap is from current agent ergonomics, not from observed geometry capability in the fixtures. The final decision gives more weight to external text-to-cad/CAD Skills workflow evidence for sustained editing: build123d source per STEP, source-level labels and assembly positioning, selector-based review, mandatory snapshots, and geometry inspection loops.

Recommended next technical steps:
1. Design the V1 model-project template around build123d source plus STEP-first outputs.
2. Keep specs and parameters as the authoring contract, but let build123d source carry precise construction logic that is too detailed for YAML.
3. Borrow text-to-cad workflow ideas selectively: CAD brief, explicit target generation, hidden topology/selector sidecars or equivalent, mandatory snapshots, geometry facts/measurements, parameter contracts, and source-level assembly positioning.
4. Treat CadQuery as an optional adapter/reference path rather than the default. Reopen only if a future task reveals build123d-specific blockers.
5. Optionally investigate STEP repair if exact imported module topology becomes important; current Fixture 3 validation can proceed with the measured bbox envelope.
