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
- Current phase: P2 caller-centered optimization proposal documented on `dev-full`
- Current branch: dev-full
- Latest conclusion: P0/P1 implementation remains complete on `dev-full`; the next optimization direction is documented in `docs/caller-centered-skill-optimization-plan.md`, focused on making `validation/current_context.json` the caller-facing control plane for low-token routing, parameter/review state, ready states, risk escalation, and gate planning.
- Next step: start a new implementation session that first audits the current repo against `docs/caller-centered-skill-optimization-plan.md`, adjusts the plan where the existing code suggests a better path, then implements incrementally; decide separately which public-safe skill changes should be synced to `main`, and do not merge or push without explicit user request.
- Blockers: no functional blocker.
- Active risks: legacy `promote_model_project.py` still exists for old accepted/release projects and should remain out of the default path; when syncing installed copies later, avoid editing `/Users/bytedance/.codex/skills` or `/Users/bytedance/.agents/skills` without explicit permission.

## Handoff
- Last completed: documented the caller-centered P2 optimization proposal for a future implementation session.
- In progress: no active implementation.
- Validation done: `check_environment.py --json`, `quick_validate.py engineering-3d-modeling`, full unittest discovery, and `git diff --check` passed for P0/P1 safeguards.
- Known risks: `experiments/` remains an unrelated untracked directory and should not be touched by this workstream.
