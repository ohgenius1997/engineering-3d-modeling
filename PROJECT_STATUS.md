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
- Current phase: P2 caller-centered current-context control plane plus risk/ready-state guardrails implemented on `dev-full`
- Current branch: dev-full
- Latest conclusion: `validation/current_context.json` now acts as the existing-project caller control plane with `routing.next_action`, context cost, minimum reads, trust, ready states, `parameter_state`, `review_state`, gate plan, blockers, assumptions, and risk escalation. Small safe parameter patches avoid spec/source reads; Chinese/snake_case high-risk annotations or parameter patches escalate to clarification or larger context; `draft_review_ready` now requires both authoring readiness and current review preview; draft-review projects no longer recommend STEP export just because STEP is missing.
- Next step: decide which public-safe changes should be synced to `main` or installed skill copies; do not merge, push, or edit `/Users/bytedance/.codex/skills` or `/Users/bytedance/.agents/skills` without explicit user request.
- Blockers: no functional blocker.
- Active risks: source-anchor/feature-registry automation was intentionally deferred; `summarize_model_project.py` now owns the first route-planning implementation and may merit extraction only if external intent-aware routing is added later. Full unittest discovery binds a local review server and may need unsandboxed execution in restricted environments. High-risk term coverage is heuristic and should be expanded from real review data over time.

## Handoff
- Last completed: implemented caller-centered P2 routing/projection/gate-plan support, then tightened high-risk recognition, ready-state semantics, and next-action documentation.
- In progress: no active implementation.
- Validation done: `python3 engineering-3d-modeling/scripts/check_environment.py --json`, `python3 engineering-3d-modeling/scripts/quick_validate.py engineering-3d-modeling`, `python3 -m unittest discover -s engineering-3d-modeling/tests` (70 tests passed after unsandboxed rerun for local socket bind), and `git diff --check`.
- Known risks: `experiments/` remains unrelated and should not be touched by this workstream; installed skill copies are not synced.
