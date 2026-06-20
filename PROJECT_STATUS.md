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
- Current phase: iteration rollback and STEP manifest workflow implemented
- Current branch: main (local git repository; initial project snapshot committed)
- Latest conclusion: Added explicit iteration boundaries with `begin_model_iteration.py`, `restore_previous.py`, active iteration metadata, and STEP manifest state so draft regeneration cannot preserve or overwrite accepted/release semantics.
- Next step: decide whether to sync the updated skill package into `/Users/bytedance/.codex/skills/engineering-3d-modeling`, then dogfood repairing the guide-vane sample's stale validation/report/STEP-manifest evidence.
- Blockers: no functional blocker. Full unit tests pass when run outside the managed sandbox because the review-server test must bind `127.0.0.1`.
- Active risks: existing model projects with STEP files but no `outputs/step/manifest.json` now fail strict current/handoff checks until regenerated or promoted; guide-vane sample still has stale validation report fields and missing mesh parameter snapshot; brief/report stale-parameter detection remains heuristic.

## Handoff
- Last completed: implemented one-step rollback iteration entry, restore-from-previous, STEP manifest state enforcement, regenerate protection rules, promotion-manifest updates, docs/spec/workflow updates, unit tests, and guide-vane real-sample regression checks.
- In progress: no active blocker.
- Validation done: `python3 engineering-3d-modeling/scripts/check_environment.py --json` passes; `python3 engineering-3d-modeling/scripts/quick_validate.py engineering-3d-modeling` passes; `python3 -m unittest discover -s engineering-3d-modeling/tests` passes with 39 tests when run with permission to bind the local review server; `git diff --check` passes; guide-vane strict audit fails as expected on missing STEP manifest plus stale validation/report evidence.
- Known risks: guide-vane has a populated `previous/`, so a real begin-iteration rollback refresh would require explicit `--force`; existing projects may need one-time STEP manifest creation through regeneration/promotion.
