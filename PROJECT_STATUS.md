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
- Current phase: review HTML navigation aids implemented on dev-full
- Current branch: dev-full
- Latest conclusion: The review template now shows a rotating lower-right XYZ axis triad, supports left-drag rotate and right-drag pan, and resets pan with the view reset command.
- Next step: sync the updated skill package into `/Users/bytedance/.codex/skills/engineering-3d-modeling`, then replace existing projects' `review/index.html` from the installed template when they need the new navigation UI.
- Blockers: no functional blocker. Full unit tests pass when run outside the managed sandbox because the review-server test must bind `127.0.0.1`.
- Active risks: existing model projects with STEP files but no `outputs/step/manifest.json` now fail strict current/handoff checks until regenerated or promoted; guide-vane sample still has stale validation report fields and missing mesh parameter snapshot; brief/report stale-parameter detection remains heuristic.

## Handoff
- Last completed: added review-canvas navigation aids on top of prior CAD edge rendering and parameter-preview guardrails.
- In progress: no active blocker.
- Validation done: review-template inline JavaScript parses; `quick_validate.py engineering-3d-modeling` passes; prior full test suite has 42 passing tests when run with permission to bind the local review server; `git diff --check` passes.
- Known risks: guide-vane has a populated `previous/`, so a real begin-iteration rollback refresh would require explicit `--force`; existing projects may need one-time STEP manifest creation through regeneration/promotion.
