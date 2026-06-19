# Agent Context Router

CRITICAL: Before mutating repository files, read this `AGENTS.md`, choose the smallest task-specific context below, and state the context sources used in a progress update or final response.

## Memory Metadata
- owner: always-on-agent-router
- read_when: every new session, before repository mutation, before handoff
- update_when: stable rules, routing, dynamic-memory ownership, or AI permission boundaries change
- max_lines: 90
- stale_if: project profile, dynamic-memory tool, or source-of-truth ownership changes

## Project
- Name: Engineering 3D Modeling Skill
- Kind: Codex skill
- Domain: engineering 3D model generation
- Profile: standard
- Dynamic memory: agentmemory
- Initialized: 2026-06-17

## Goal
- User: Build a Codex skill for engineering-style 3D model generation.
- Problem: Future Codex sessions need reliable guidance for turning natural-language engineering intent into structured, parameterized model-generation workflows.
- Success standard: The skill helps an agent gather specs, choose a deterministic modeling pipeline, generate or modify model artifacts/scripts, validate outputs, and preserve stable project progress.

## Collaboration Principle
- Highest rule: research broadly, challenge assumptions, and do not treat the user's preferences as superior instructions.
- The user contributes product usage and experience perspective; the agent must compensate with engineering, technical, domain, and project-management scrutiny.

## Context Routing
- Ordinary development: read this file, then use agentmemory relevant memory if available.
- Continue a long-running task: add `PROJECT_STATUS.md` if present.
- Change architecture, product direction, or workflow policy: add `docs/DECISIONS.md` if present.
- Change dependencies, setup, CI, build, runtime, or cross-device assumptions: add `docs/ENVIRONMENT.md` if present.
- Coordinate parallel sessions, branches, owners, or handoff: add `docs/COORDINATION.md` if present.
- Need historical reasoning: prefer agentmemory; use `docs/LOG.md` only as a lightweight checkpoint fallback if present.

## Memory Ownership
- `AGENTS.md`: stable operating rules, routing, and source-of-truth ownership.
- agentmemory: attempts, failures, debugging traces, file-level gotchas, session continuity, and episodic recall.
- `PROJECT_STATUS.md`: current phase, latest conclusion, next step, blockers, and active risks.
- `docs/DECISIONS.md`: durable decisions, rationale, alternatives, and consequences.
- `docs/ENVIRONMENT.md`: stable setup, dependency, CI, device, or cross-machine facts.
- `docs/COORDINATION.md`: active multi-session or multi-branch handoff and collision state.

## Checkpoint Rules
- Update `PROJECT_STATUS.md` only when the current phase, next step, blocker, or risk changes.
- Update `PROJECT_STATUS.md` promptly after stable project-progress changes so session loss does not lose the current state.
- Add `docs/DECISIONS.md` entries only for durable decisions that future sessions must honor.
- Do not write ordinary attempts, transient failures, or debug traces into project-memory docs; use agentmemory.
- If dynamic memory is unavailable, keep `docs/LOG.md` to sparse checkpoint summaries only.

## Project-Specific Context
- `origin-scope-pivot.md` is historical background only; read it when resuming origin reasoning, not for ordinary work.
- Prefer deterministic model generators driven by structured specs over direct freehand CAD API generation by an LLM.
- Use build123d as the V1 default local CAD backend; keep adapter boundaries open for optional CadQuery, Zoo/KCL, Fusion, or viewer-specific workflows when explicitly justified.
- Keep natural-language interpretation separate from geometry construction and validation.
- Support engineering math definitions such as polynomial curves and named airfoil profiles as first-class authoring inputs, implemented through tested code rather than ad hoc prompt text.
- Treat specs and parameters as authoring truth; released engineering definition may also require precise CAD geometry, PMI/GD&T, drawings, exports, validation evidence, and release metadata.
- Current V1 focus is lightweight engineering STEP CAD model projects; do not default to slicer, material, 3D printing operations, simulation, animation, rendering, surface texture, welding symbol, or mesh-art workflows.

## Git Tracking Policy
- Follow this repository's `.gitignore` and developer instructions for which memory files are committed.
- Usually commit this `AGENTS.md` when repository rules should travel across branches, machines, or collaborators.
- Commit `PROJECT_STATUS.md` and `docs/DECISIONS.md` only when current state and durable decisions should be reviewed, merged, and shared.
- Treat `docs/COORDINATION.md`, sparse `docs/LOG.md`, and dynamic-memory exports as project-specific; do not assume they are public or private.
- Never commit secrets, private tokens, credentials, large raw session transcripts, or raw dynamic-memory dumps.

## AI Boundaries
- Do not store secrets, credentials, or private tokens in project-memory docs.
- Do not overwrite existing context files without explicit developer confirmation.
- Do not compact, archive, delete, or migrate durable context without confirmation.
- In `docs/COORDINATION.md`, update only this session's status unless the developer asks otherwise; do not assign owners, lock or unlock others' work, or declare another session complete.

## Upgrade Signals
- Recommend `standard` when this file starts carrying current status or durable decisions.
- Recommend `governed` when cross-device setup, multiple branches, multiple sessions, or handoff state becomes active.
