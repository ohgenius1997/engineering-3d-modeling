# Project Status

## Memory Metadata
- owner: current-state-index
- read_when: continuing long-running work, before handoff, when AGENTS.md says current state is needed
- update_when: phase, latest conclusion, next step, blocker, risk, or active branch changes
- max_lines: 90
- stale_if: next step is completed, blocker changes, or branch/workstream changes

## Maintenance Rules
- Keep this file short and current-state only.
- Do not store chronological history, debug attempts, or ordinary failures here.
- Put durable rationale in `docs/DECISIONS.md`.
- Put episodic process memory in agentmemory; use `docs/LOG.md` only as a sparse fallback if present.

## Current Snapshot
- Project: Engineering 3D Modeling Skill
- Kind: Codex skill
- Domain: engineering 3D model generation
- Profile: standard
- Dynamic memory: agentmemory
- Current phase: P0/P1/P2 review-regeneration and review-persistence hardening complete; repository initialized
- Current branch: main (local git repository; initial project snapshot committed)
- Latest conclusion: the review persistence path is now strict. `serve_review.py`, `apply_parameter_patch.py`, and `validate_model_project.py` share schema and parameter-domain validation for review JSON and patches; patches must target manifest-exposed editable parameters and pass type, unit, bounds, and step checks. `roll_revision.py` now supports dry-run and blocks overwriting populated `previous/` unless forced.
- Next step: continue broader review UI hardening such as fuller browser-level interaction tests and preview mesh quality checks.
- Blockers: no functional blocker. Default `python3` now passes the installed skill dependency check for build123d and PyYAML.
- Active risks: browser-level review UI regressions, preview mesh generation quality, persistent selector stability across regeneration, and exact model-specific live-preview bindings still need dogfood evidence.

## Handoff
- Last completed: initialized a local git repository on branch `main`, added `.gitignore`, implemented strict review schema/patch validation, added review workflow unittest coverage, made revision rolling safer, updated durable docs/decisions, and synced the installed skill copy.
- In progress: no active blocker; next workstream is deeper review UI interaction coverage.
- Validation done: `check_environment.py --json` passes; Python scripts/tests compile; `python3 -m unittest discover -s engineering-3d-modeling/tests` passes; scaffold-to-regenerate e2e passes with STEP generation, manifest parameter sync, review patch application, patch clearing, validation report writing, schema checks, patch domain checks, and geometry smoke checks; negative geometry smoke catches ignored parameter loading; strict patch CLI rejects wrong value types; roll revision CLI dry-run/block/force behavior passes.
- Known risks: historical CAD notes are sparse; interactive geometry selection/review may become a substantial subproject; browser-level review UI behavior still needs fuller end-to-end coverage beyond save API tests.
