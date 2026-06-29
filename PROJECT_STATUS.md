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
- Current phase: context-routing and model-project documentation optimization planned
- Current branch: dev-full
- Latest conclusion: `docs/context-and-routing-optimization.md` now captures the next product-level optimization: project `AGENTS.md` should wake `$engineering-3d-modeling` at a high level, detailed task routing should live in `references/context-routing.md`, existing projects should start from `validation/current_context.json` or `summarize_model_project.py`, `brief.md` should be a short confirmed human design summary with no open questions, and `spec/current.yaml` should carry structured authoring truth with coordinate systems, placements, features, formal constraints, decisions, and validation targets without becoming a second CAD implementation.
- Next step: implement the optimization on `dev-full`, then decide separately which public-safe skill changes should be synced to `main`.
- Blockers: no functional blocker.
- Active risks: keep project-local `AGENTS.md` concise so it does not become a stale copy of skill internals; avoid turning controlled modeling intent templates into another source of duplicate truth.

## Handoff
- Last completed: moved the context-routing/model-project documentation optimization plan from accidental `main` worktree changes onto `dev-full`.
- In progress: commit the planning checkpoint on `dev-full`.
- Validation done: documentation-only planning update; no code validation required yet.
- Known risks: `experiments/` remains an unrelated untracked directory and should not be touched by this workstream.
