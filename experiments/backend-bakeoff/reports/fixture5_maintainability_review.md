# Fixture 5 Maintainability Review

Created: 2026-06-18

## Scope

This review exercises source maintainability after both local Python BRep candidates already passed Fixture 5.

Applied edit tasks:
- Add a left-hand switch variant without duplicating backend-specific switch geometry code.
- Export the front grille as a separately named part.
- Add two handle screw bosses and validate they do not intersect the batteries.
- Add cylinder-like battery validation fields in addition to AABB checks.
- Move hardcoded layout positions into the shared Fixture 5 spec where practical.

This is not a finished industrial-design test. The geometry remains a simplified engineering proxy.

## Files Touched

Shared authoring and validation:
- `experiments/backend-bakeoff/shared/specs/fixture-5-handheld-fan.yaml`
- `experiments/backend-bakeoff/shared/tools/fixture5_layout.py`

Backend-specific generators:
- `experiments/backend-bakeoff/build123d/source/run_fixture5_handheld_fan.py`
- `experiments/backend-bakeoff/cadquery/source/run_fixture5_handheld_fan.py`

Reports/status:
- `experiments/backend-bakeoff/reports/fixture5_maintainability_review.md`
- `experiments/backend-bakeoff/reports/comparison.md`
- `PROJECT_STATUS.md`

## Validation Result

Both backends passed after the maintainability edits.

| Candidate | Cases | Outputs Per Case | New Front Grille Outputs | Result |
| --- | --- | ---: | ---: | --- |
| build123d | baseline, edited, left_hand | 11 | 2 | pass |
| CadQuery | baseline, edited, left_hand | 11 | 2 | pass |

Validated checks now include:
- baseline, edited, and left-hand switch cases
- `switch_side_matches_parameter`
- `battery_cylinder_like_clearance`
- `handle_screw_bosses_do_not_intersect_batteries`
- named `front_grille` STEP/STL outputs
- existing containment, clearance, fixed-component intersection, generated-feature intersection, port alignment, and switch proximity checks

Current scores remain:
- CadQuery: 78.0
- build123d: 76.0

## Maintainability Observations

The most important result is architectural: most of the change landed in shared spec/layout, not duplicated backend code. That supports the skill architecture direction of keeping natural-language interpretation, layout, and validation outside backend-specific CAD scripts.

build123d:
- The named part functions stayed easy to scan: `build_front_shell`, `build_front_grille`, `build_rear_shell`, `build_internal_frame`, `build_switch_mechanism`, and `build_component_envelopes`.
- Adding `front_grille` was a local function extraction from `build_front_shell`.
- Adding handle screw bosses required only broadening the internal-frame screw-boss condition from head-only to any `screw_boss` feature.
- The builder/context style remains readable, but primitives require more ceremony around `BuildPart`, `Locations`, and `add`.

CadQuery:
- The same named part structure remained intact.
- Adding `front_grille` was also a local function extraction.
- Because Fixture 5 avoids face selectors and mostly composes primitives into compounds, CadQuery stayed concise and predictable.
- This result does not test CadQuery's riskier selector-heavy workflow; it tests the skill architecture pattern where layout drives named primitive/compound outputs.

## Score Impact

No score change is recommended from this exercise.

Reason:
- Both candidates completed the same maintainability edits with similar locality.
- The two-point score gap still comes from `agent_ergonomics`, not from observed Fixture 5 geometry or layout capability.
- The exercise strengthened confidence in the shared spec/layout/validation architecture more than it differentiated the backends.

## Residual Risk

Fixture 5 still does not prove:
- topology-stable feature references after deep local edits
- robust shelling/filleting/boolean recovery under complex real surfaces
- exact imported CAD collision using repaired topology
- real hinge, latch, thread, snap-fit, or tolerance-stack behavior
- long-term evolution across many user-requested revisions

The next discriminating test should be a topology-stability/deep-edit fixture rather than another simplified assembly expansion.
