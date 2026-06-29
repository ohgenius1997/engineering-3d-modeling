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
- Current phase: context-routing and model-project documentation optimization implemented on `dev-full`
- Current branch: dev-full
- Latest conclusion: The skill now has `references/context-routing.md` for global routing, composable task tags, artifact boundaries, controlled modeling intent templates, and the review annotation clarity gate. New scaffolds keep project `AGENTS.md` high-level, generate a short `brief.md`, initialize structured `spec/current.yaml` sections, and create `validation/current_context.json`. `scripts/summarize_model_project.py` provides the existing-project continuation summary, and `regenerate_from_review.py` refreshes current context after successful review regeneration.
- Next step: decide separately which public-safe skill changes should be synced to `main`; do not merge or push without explicit user request.
- Blockers: no functional blocker.
- Active risks: keep controlled modeling intent templates as intake guidance rather than duplicate CAD truth; when syncing installed copies later, avoid editing `/Users/bytedance/.codex/skills` or `/Users/bytedance/.agents/skills` without explicit permission.

## Handoff
- Last completed: implemented the context-routing/model-project documentation optimization on `dev-full`.
- In progress: review and decide public-safe sync scope for `main`.
- Validation done: `python3 engineering-3d-modeling/scripts/check_environment.py --json`; `python3 engineering-3d-modeling/scripts/quick_validate.py engineering-3d-modeling`; `python3 -m unittest discover -s engineering-3d-modeling/tests` (rerun outside sandbox because localhost binding is required); `git diff --check`.
- Known risks: `experiments/` remains an unrelated untracked directory and should not be touched by this workstream.
