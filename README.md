# Engineering 3D Modeling Skill

A Codex skill for building maintainable engineering CAD model projects from
natural-language requirements, dimensioned drawings, qualitative references,
existing modeling scripts, and fixed CAD components.

This is not a one-shot text-to-mesh generator. The skill is designed around
editable authoring truth, deterministic model source, reviewable iterations,
phase-aware validation, and STEP output for accepted or handoff states.

## Scope

Use this skill for engineering-style CAD work such as:

- Parameterized parts, brackets, fixtures, ducts, shrouds, mounts, and enclosures.
- Simple assemblies with fixed components, layout constraints, clearances, and generated parts.
- Math-defined geometry such as polynomial curves, NACA-style profiles, guide vanes, ribs, bosses, holes, and simple analytical surfaces.
- Continuing or refactoring existing CAD/modeling scripts into a structured model project.
- Producing editable build123d source and STEP/BRep exchange output.

Do not use this skill for:

- Slicer, printer, filament, Bambu, 3MF, STL, or G-code workflows.
- Simulation, animation, photoreal rendering, or downstream manufacturing setup.
- Freeform mesh sculpting or industrial-design-grade surfacing.
- Treating imported mesh files as recoverable parametric CAD truth.

## Core Ideas

The skill keeps three artifact layers separate:

1. **Authoring truth**

   The durable source of the model project:

   - `brief.md`
   - `spec/current.yaml`
   - `parameters.yaml`
   - `source/model.py`
   - validation evidence

2. **CAD exchange and delivery output**

   STEP files under `outputs/step/`, with state recorded in
   `outputs/step/manifest.json`. STEP is required for accepted and handoff
   states, but draft iterations may have either no STEP or draft STEP.

3. **Review artifacts**

   HTML review UI, preview meshes, annotations, and parameter patches under
   `review/`. These files support iteration and user feedback, but they do not
   become CAD truth until the backend regenerates and validation passes.

The default local CAD backend is build123d. Other backends, such as Fusion 360
API scripts, are treated as legacy inputs or explicit backend overrides unless a
project has a concrete reason to use them.

## Model Project Layout

New model projects use this shape:

```text
brief.md
AGENTS.md
spec/current.yaml
parameters.yaml
inputs/
source/model.py
outputs/step/
validation/
review/
previous/
```

Complex assemblies may split local specs by domain while keeping
`spec/current.yaml` as the root contract. The skill does not manage cross-project
component reuse in V1.

## Lifecycle

Model projects use an explicit lifecycle phase in `spec/current.yaml`:

```yaml
lifecycle:
  phase: draft_review
```

Supported phases:

- `draft_review`: work in progress. Authoring truth and review artifacts may
  exist without STEP. This phase must not be described as complete, accepted, or
  handed off.
- `accepted_current`: the current model is accepted as the baseline. STEP is
  required.
- `release_handoff`: the project is ready for handoff/release checks. STEP and
  strict consistency validation are required.
- `backend_override`: a temporary non-default backend state. The project must
  record the backend name and reason.

Lifecycle changes are script-owned. Agents should not edit `lifecycle.phase`
directly to claim completion.

`outputs/step/manifest.json` records whether STEP is `draft`,
`accepted_current`, or `release_handoff`. Draft STEP can support review, but it
does not satisfy accepted/release validation. Accepted and release manifest
states are written by `scripts/promote_model_project.py`.

## Typical Workflow

1. Initialize or continue a model project.
2. Convert user intent, drawings, references, or existing scripts into
   structured specs and parameters.
3. Generate or modify build123d source.
4. Create review artifacts, including the HTML review surface when useful.
5. Let the user adjust safe preview-bound parameters or add snapped annotations.
6. Start a new iteration, then consume review patches and annotations through
   the backend regeneration loop.
7. Validate the project according to its lifecycle phase.
8. Promote the project to `accepted_current` only after clean review state, STEP,
   and validation pass.
9. Promote to `release_handoff` only after strict consistency audit proves that
   specs, parameters, source, review artifacts, STEP, and reports describe the
   same snapshot.

## Installation

Copy the skill directory into your Codex skills directory:

```bash
mkdir -p "$HOME/.codex/skills"
cp -R engineering-3d-modeling "$HOME/.codex/skills/engineering-3d-modeling"
```

If you prefer to develop against the repository directly, use a symlink:

```bash
mkdir -p "$HOME/.codex/skills"
ln -sfn "$(pwd)/engineering-3d-modeling" "$HOME/.codex/skills/engineering-3d-modeling"
```

The bundled management scripts use only the Python standard library. Generated
model projects usually need build123d and PyYAML to execute CAD generation. The
skill provides an environment helper:

```bash
python3 engineering-3d-modeling/scripts/check_environment.py --json
python3 engineering-3d-modeling/scripts/check_environment.py --install
```

Run the helper with the same Python interpreter that will execute
`source/model.py`.

## Quick Start

Ask Codex to use the skill for an engineering CAD task, for example:

```text
Use the engineering-3d-modeling skill to create a compact enclosure for a
21700 cell and a PCB. Keep it as a maintainable model project and prepare an
HTML review surface.
```

For a new project, the agent should scaffold with:

```bash
python3 engineering-3d-modeling/scripts/init_model_project.py /path/to/model-project
```

Before consuming saved review data or making a new modeling change:

```bash
python3 engineering-3d-modeling/scripts/begin_model_iteration.py /path/to/model-project
```

After the user edits HTML review parameters or annotations:

```bash
python3 engineering-3d-modeling/scripts/regenerate_from_review.py /path/to/model-project --start-new-iteration
```

To accept the current model:

```bash
python3 engineering-3d-modeling/scripts/promote_model_project.py /path/to/model-project accepted_current
```

To prepare a handoff/release package:

```bash
python3 engineering-3d-modeling/scripts/promote_model_project.py /path/to/model-project release_handoff
```

To inspect a project without changing lifecycle state:

```bash
python3 engineering-3d-modeling/scripts/validate_model_project.py /path/to/model-project
python3 engineering-3d-modeling/scripts/audit_project_consistency.py /path/to/model-project --mode strict --format summary
```

## Review UI

The bundled review template is a lightweight browser-based review surface. V1
supports:

- 3D preview from derived review mesh data.
- Explicit live-preview-bound numeric parameters rendered as sliders.
- Optional model-specific formula preview adapters for equation-driven previews.
- Snapped annotation records for parts, faces, edges, vertices, and named
  features.
- Global annotations when no geometry target is selected.
- Assembly part visibility and isolation controls.
- One save action that writes structured review data through the local review
  server.
- English and Chinese UI switching.

The review page does not provide natural-language modeling input and does not
directly edit CAD topology. Saved review data must be consumed by the coding
agent, regenerated through the backend, and validated before it becomes model
truth.

## Main Scripts

- `scripts/init_model_project.py`: scaffold a `draft_review` model project.
- `scripts/check_environment.py`: check or install build123d and PyYAML for the
  active Python runtime.
- `scripts/apply_parameter_patch.py`: validate and apply saved HTML parameter
  patches.
- `scripts/begin_model_iteration.py`: save the current project into
  `previous/`, return accepted/release projects to `draft_review`, and mark
  existing STEP as draft/stale before mutation.
- `scripts/regenerate_from_review.py`: apply review patches, rebuild source or
  preview assets, sync review parameters, validate draft state, mark generated
  STEP as draft, and clear consumed review state after success.
- `scripts/sync_review_parameters.py`: expose only explicit live-preview-bound
  parameters in the review manifest.
- `scripts/audit_review_parameters.py`: detect stale, unsafe, or non-reactive
  review parameters.
- `scripts/validate_model_project.py`: validate required files, review data,
  phase-aware STEP requirements, snapshot hashes, and forbidden downstream
  output types.
- `scripts/audit_project_consistency.py`: detect drift among specs, brief,
  parameters, review manifest, preview mesh, STEP outputs, and validation report.
- `scripts/promote_model_project.py`: transactional lifecycle gate for
  `accepted_current` and `release_handoff`; this is the script that writes
  accepted/release STEP manifest state.
- `scripts/restore_previous.py`: dry-run or restore the one-step rollback
  snapshot from `previous/`.
- `scripts/roll_revision.py`: compatibility alias for snapshotting current
  state to `previous/`.
- `scripts/serve_review.py`: serve the HTML review UI and safely persist review
  annotations and parameter patches.
- `scripts/quick_validate.py`: validate the skill package shape.

## Validation

Validate the skill package:

```bash
python3 engineering-3d-modeling/scripts/quick_validate.py engineering-3d-modeling
```

Run unit tests:

```bash
python3 -m unittest discover -s engineering-3d-modeling/tests
```

Some review-server tests bind to `127.0.0.1`; managed sandboxes may require
permission for that operation.

Validate a generated model project:

```bash
python3 engineering-3d-modeling/scripts/validate_model_project.py /path/to/model-project
```

Force delivery-grade STEP checking regardless of phase:

```bash
python3 engineering-3d-modeling/scripts/validate_model_project.py /path/to/model-project --require-step
```

Run strict current/handoff consistency audit:

```bash
python3 engineering-3d-modeling/scripts/validate_model_project.py /path/to/model-project --strict-consistency
```

## Current Status

This project is an early engineering workflow skill. It is useful for structured
CAD authoring, review, validation, and STEP handoff, but it is not a complete
CAD system.

Known limitations:

- build123d is the default backend; other backends are not first-class V1 paths.
- Mesh reverse engineering is reference-only.
- Review preview meshes are derived artifacts and must be validated against the
  backend model before acceptance.
- Brief/report stale-state detection uses heuristics and may need tuning on more
  real projects.
- Promotion restores lifecycle state and validation reports on failure, but a
  source-driven STEP rebuild may still leave generated STEP artifacts if a later
  gate fails.

## Repository Structure

```text
engineering-3d-modeling/
  SKILL.md
  assets/review-template/
  references/
  scripts/
  tests/
docs/
  DECISIONS.md
  DOMAIN.md
  SKILL_SPEC.md
  WORKFLOWS.md
AGENTS.md
PROJECT_STATUS.md
```

## Contributing

Keep the skill package focused. `SKILL.md` should stay concise and route agents
to references only when needed. Prefer deterministic scripts for fragile gates
such as validation, review persistence, and lifecycle promotion.

Before opening a pull request, run:

```bash
python3 engineering-3d-modeling/scripts/check_environment.py --json
python3 engineering-3d-modeling/scripts/quick_validate.py engineering-3d-modeling
python3 -m unittest discover -s engineering-3d-modeling/tests
git diff --check
```

Do not add slicer, printer, simulation, animation, or freeform mesh workflows to
the V1 default path unless the scope is explicitly revised.

## License

No open-source license has been selected yet. Add a `LICENSE` file before public
release.
