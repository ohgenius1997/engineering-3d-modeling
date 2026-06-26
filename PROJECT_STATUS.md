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
- Current phase: product-level preview/export/handoff workflow refactor complete
- Current branch: dev-full
- Latest conclusion: New daily CAD workflow is implemented and documented: preview revision rollback is the default previous-version restore, STEP exports directly with fresh/stale manifest tracking, and handoff is an optional strict zip package. Legacy promotion remains as compatibility.
- Next step: review/commit the refactor on `dev-full`; publishing to remote `main` should still be handled separately after checking branch policy.
- Blockers: no functional blocker.
- Active risks: existing projects with legacy `accepted_current`/`release_handoff` phase metadata remain supported, but agents should avoid treating those states as mandatory daily flow; strict handoff package creation requires enough current preview/validation evidence to prove consistency.

## Handoff
- Last completed: read AGENTS, PROJECT_STATUS, DECISIONS, SKILL, and relevant model-project/review/validation/script context for the workflow refactor.
- In progress: complete.
- Validation done: `check_environment.py --json` pass; `quick_validate.py engineering-3d-modeling` pass; full unittest pass with 48 tests and 1 environment-gated skip when run outside sandbox for local review-server binding; `git diff --check` pass; installed `.codex` and `.agents` skill copies synced and quick-validated.
- Known risks: legacy promotion language remains only in compatibility sections and scripts.
