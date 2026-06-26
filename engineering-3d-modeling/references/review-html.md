# Review HTML

## Purpose

The review HTML is a lightweight review and annotation surface. It is not the CAD truth and not a natural-language modeling agent.

V1 review data lives in:

- `review/manifest.json`,
- `review/annotations.json`,
- `review/parameter_patch.json`,
- optional derived preview assets under `review/cache/`.

Annotations are user-authored review input. Do not store agent diagnostics, baseline analysis, implementation notes, or already-consumed comments in `review/annotations.json`; write those to `validation/`, `brief.md`, or source comments instead. Clear current annotations after converting them into the next model revision.

Review artifacts and cache files are derived from authoring truth. They are useful for feedback, live preview, and annotations, but they do not replace `spec/current.yaml`, `parameters.yaml`, source/formula modules, validation evidence, or accepted/release STEP output.

## Allowed V1 Features

- Preview current generated geometry using STEP-derived or source-derived preview assets.
- Optionally compare current and previous revisions.
- Show/hide or isolate assembly parts from a canvas-attached part rail.
- Render clean CAD-style preview edges by default. The review page does not expose a mesh wireframe/debug display mode, although the full preview mesh data remains available for shaded faces, annotation picking, and adapter-backed previews.
- Display only explicit live-preview-bound parameter controls with bounds and units.
- Let each annotation record carry editable text plus an optional snapped part, face, edge, vertex, or named feature ref.
- Allow global annotations with no target.
- Show labels for targeted annotations in the preview and support preview-label to annotation-record navigation.
- Save annotation records and parameter patches together through one review save action.

## Disallowed V1 Features

- Natural-language modeling input inside the page.
- Direct CAD topology editing.
- Lasso or freehand markup.
- Required explosion view.
- Slicer, printer, material, G-code, STL, or 3MF controls.

## Manifest

`review/manifest.json` should describe the reviewable model:

```json
{
  "schema": "engineering-3d-modeling.review_manifest.v1",
  "project": {"name": "example", "kind": "assembly", "units": "mm"},
  "versions": {
    "current": {"step": "../outputs/step/example.step"},
    "previous": null
  },
  "preview": {"mesh_json": "cache/current_mesh.json", "mesh_closed": true},
  "parts": [],
  "parameters": [],
  "refs": []
}
```

The manifest may point to derived preview assets. These assets are not committed CAD deliverables and may exist during `draft_review` before STEP is generated.

For equation-driven models, `preview.adapter_js` may point to a same-project JavaScript preview adapter under `review/`, typically `review/cache/preview_adapter.js`:

```json
{
  "preview": {
    "mesh_json": "cache/current_mesh.json",
    "mesh_closed": true,
    "adapter_js": "cache/preview_adapter.js",
    "adapter_config": {"formula": "guide_vane_v1"}
  }
}
```

The adapter must assign `window.Engineering3DPreviewAdapter.generateMesh(context)`. The template passes:

- `context.parameters`: current review parameter values after unsaved slider patches,
- `context.parameterRecords`: manifest parameter entries,
- `context.manifest`: the full review manifest,
- `context.baseMesh`: the backend-generated baseline preview mesh, when available,
- `context.units`: project units.

Use `preview.adapter_config` for fixed formula settings, sampling resolution, or non-editable constants that the preview adapter needs but should not appear as user-editable sliders.

`generateMesh()` must return the standard review mesh shape `{vertices: [[x,y,z], ...], faces: [...]}`. Faces may be index arrays or objects with `indices`, `part_id`, `feature_id`, `world_point`, `normal`, and optional `color`/`edge`. For convenience during migration from older model-specific previews, the template can also normalize adapter output shaped as `{faces: [{pts: [[x,y,z], ...], part, feature_id, ...}]}`.

Adapter-backed parameters use `preview.effect: "adapter"`:

```json
{
  "id": "vane_count",
  "value": 6,
  "unit": "count",
  "preview": {"effect": "adapter", "baseline": 6}
}
```

Use an adapter only when the model-specific formula preview is kept aligned with backend source and validation. It may change vertex counts, face counts, and topology for review preview, such as blade count changes, but it is still not CAD truth. Saving still writes parameter patches, then backend regeneration and validation must update authoring truth and, for `accepted_current` or `release_handoff`, produce authoritative STEP plus refreshed preview assets.

For a single-part project, `parts` should be empty or contain one real part. Use mesh face `feature_id` to identify shroud walls, hubs, vanes, holes, bosses, ribs, and other subregions. Multiple `part_id` values are for assembly components or separate generated parts, not features inside one joined solid.

Preview meshes should match the visible CAD intent. If the STEP/BRep body is closed, include cap faces and set `preview.mesh_closed` to `true` or omit it. Set `preview.mesh_closed` to `false` only for intentionally open reference surfaces.

## Selector Refs

A selector ref should be concrete enough for an agent to find the target later:

```json
{
  "id": "front_shell:face:usb_cutout_inner",
  "part_id": "front_shell",
  "entity_type": "face",
  "feature_id": "usb_cutout",
  "label": "USB cutout inner face",
  "world_point": [12.0, -4.0, 8.5],
  "normal": [0, -1, 0]
}
```

Use stable ids for generated parts and named features where possible. Raw topology ids may change after regeneration, so pair them with semantic part and feature ids.

If no explicit refs are declared, the review HTML can still snap annotations to preview mesh vertices, edges, and faces. Explicit refs are still preferred for important semantic targets such as screw holes, gasket grooves, mounting faces, airfoil sections, and connector openings.

Annotation picking priority is:

1. Explicit manifest refs.
2. Visible preview vertices.
3. Visible CAD edge candidates.
4. Visible face interiors.

CAD edge candidates are derived from preview mesh edge adjacency, feature/part boundaries, creases, boundaries, and view-dependent silhouette checks. Do not expose all triangulation edges as user-visible or preferred targets; internal triangle edges are implementation detail and should not attract annotation snaps.

For large preview meshes, the template should budget edge adjacency by reviewable part or feature group rather than falling back globally. Small groups continue to build clean CAD edge candidates; oversized imported/reference groups may skip full adjacency and use a low-emphasis, screen-thinned direct preview-edge fallback to avoid browser memory spikes. This fallback is not a user-facing Mesh mode and its triangle edges must not become annotation edge targets. Annotation priority remains explicit refs, vertices, CAD edge candidates when available, then face interiors.

Face picks store the exact clicked point, not the face centroid. The review page tests whether the pointer is inside the visible triangle projection, computes barycentric coordinates in screen space, and interpolates the 3D face vertices to write `target.snapped_point`. Edge picks use the nearest point on the visible CAD edge segment, interpolate the two 3D edge endpoints by `t`, and write that precise point. Vertex picks write the vertex coordinate directly.

## Local Save

Static `file://` pages cannot overwrite project files directly. When the user needs direct local persistence, run the review UI through `scripts/serve_review.py`:

```bash
python3 engineering-3d-modeling/scripts/serve_review.py /path/to/model-project --port 0
```

`serve_review.py` serves one model project per process. Passing `--port 0` asks the operating system for an available local port and the script prints the exact URL, which is the preferred mode when multiple CAD projects may be reviewed at the same time. Use a fixed `--port` only when the caller needs a stable URL and has already checked that the port is free.

The server exposes `POST /api/save-review` and writes only these project-scoped files:

- `review/annotations.json`
- `review/parameter_patch.json`

Existing files are overwritten. Missing files are recreated at the default paths. Renamed or moved files are not followed, because later agents need stable paths.

The save endpoint must validate both review documents before writing. `annotations` and `parameter_patch` must match the bundled schemas. Parameter patches must reference known `parameters.yaml` entries that are currently exposed in `review/manifest.json`, must not target `ui.editable: false` parameters, and must pass value type, unit, min, max, and step validation.

## Annotations

`review/annotations.json` stores review comments:

```json
{
  "schema": "engineering-3d-modeling.annotations.v1",
  "annotations": [
    {
      "id": "ann-001",
      "created_at": "2026-06-18T00:00:00Z",
      "text": "Increase clearance here.",
      "target": {
        "ref": "front_shell:face:usb_cutout_inner",
        "entity_type": "face",
        "part_id": "front_shell",
        "feature_id": "usb_cutout",
        "snapped_point": [12.0, -4.0, 8.5],
        "normal": [0, -1, 0],
        "pick": {
          "kind": "face",
          "face_id": "front_shell:face:usb_cutout_inner",
          "face_index": 123,
          "barycentric": [0.2, 0.5, 0.3],
          "screen_point": [420, 260]
        }
      },
      "camera": {},
      "status": "open"
    }
  ]
}
```

`target` may be `null` for a global annotation. Annotations are review data and are normally cleared after the agent consumes them into spec, parameter, or source changes for the next model revision. `scripts/promote_model_project.py` treats any current annotation record as unconsumed review input and blocks `accepted_current` or `release_handoff` promotion until the record is consumed and cleared.

The optional `target.pick` block is current-review helper data only. It may record face barycentric coordinates, an edge key plus interpolation parameter `t`, or a vertex index and screen point. Do not treat `pick` as stable topology truth across regeneration. Agents should rely on `snapped_point`, `feature_id`, `label`, `normal`, and nearby spec/source context when consuming annotation intent.

## Parameter Patches

`review/parameter_patch.json` stores pending HTML parameter changes:

```json
{
  "schema": "engineering-3d-modeling.parameter_patch.v1",
  "patches": [
    {
      "parameter_id": "wall_thickness",
      "value": 2.4,
      "unit": "mm",
      "reason": "review-html",
      "source": "review-html"
    }
  ]
}
```

A parameter patch is not final model truth until an iteration has begun, the backend regenerates, and validation passes. A non-empty `review/parameter_patch.json` blocks lifecycle promotion; run `scripts/regenerate_from_review.py --start-new-iteration` or begin the iteration manually, apply, regenerate, validate, and clear the patch before promoting.

Patches are intentionally narrow. They are for HTML review parameters only, not a generic way to change hidden model parameters. A patch that references an unknown parameter, a parameter omitted from `review/manifest.json`, a locked parameter, a wrong value type, a unit mismatch, an out-of-bounds value, or a value off the declared slider step should be rejected before it changes `parameters.yaml`.

Before regenerating from a reviewed project, prefer the total review loop command:

```bash
python3 engineering-3d-modeling/scripts/regenerate_from_review.py /path/to/model-project --start-new-iteration
```

It starts a new iteration when needed, applies saved parameter patches, runs `source/model.py`, syncs preview-bound parameters into the manifest, writes `validation/report.json`, and clears consumed review state after validation succeeds. If the project was `accepted_current` or `release_handoff`, the iteration starts by snapshotting current state into `previous/` and returning `spec/current.yaml` to `draft_review`. Regenerated STEP is marked as draft in `outputs/step/manifest.json`; accepted/release STEP state must come later from `scripts/promote_model_project.py`.

Without `--start-new-iteration`, the command fails when `review/parameter_patch.json` or `review/annotations.json` is non-empty and no active `validation/iteration.json` exists. It also fails instead of regenerating directly from `accepted_current` or `release_handoff`.

For manual debugging, begin the iteration before applying saved patches or editing spec/source:

```bash
python3 engineering-3d-modeling/scripts/begin_model_iteration.py /path/to/model-project --reason "consume saved review patch"
```

Then apply saved patches before backend regeneration:

```bash
python3 engineering-3d-modeling/scripts/apply_parameter_patch.py /path/to/model-project --keep-patch
```

Then rebuild the model, update preview assets, validate, and clear consumed review state after success:

```bash
python3 engineering-3d-modeling/scripts/reset_review_state.py /path/to/model-project
```

The HTML parameter panel is opt-in. A parameter appears in the panel only when it has an explicit live preview binding, either through the manifest parameter's `preview` object or a matching explicit mesh `parameter_effects` entry. Numeric review parameters render as sliders and must trigger an immediate preview update. Do not infer preview behavior from parameter ids, labels, roles, or units. If a parameter cannot be previewed correctly in static HTML, keep it out of `review/manifest.json` and route the change through the coding agent's backend regeneration workflow.

Explicit example:

```json
{
  "id": "body_length",
  "label": "Body length",
  "value": 80,
  "unit": "mm",
  "preview": {"effect": "scale_axis", "axis": "x", "baseline": 80, "anchor": "center"}
}
```

Supported V1 preview effects are `scale_axis`, `scale_radial`, `scale_uniform`, `offset_axis`, `offset_radial`, `twist_z`, `ripple_radial`, `generic_morph`, and `adapter`. Morph effects are review approximations over an existing mesh; `adapter` delegates preview mesh generation to the model-specific adapter declared by `preview.adapter_js`. Backend regeneration remains authoritative. Use `generic_morph` only when the preview mesh generator intentionally supplies a model-specific approximation. Do not use `preview.effect: none` to keep a parameter visible; `none` means the parameter is not review-panel eligible.

`generic_morph` is never a fallback for localized engineering semantics. If a parameter affects a chamfer, fillet, hole, mount, connector cutout, PCB or battery clearance, base position, rib, slot, thread, or layout position, use `preview.effect: "adapter"` with a model-specific preview adapter, or keep the parameter out of the review panel until backend regeneration can show the result. Intentional generic morphs must declare at least one of:

- `preview.scope`: human-readable region or whole-model scope,
- `preview.feature_refs`: semantic feature ids expected to move,
- `preview.rationale`: why this approximation is acceptable for review.

Parameter preview decision table:

| Parameter type | Review preview binding |
| --- | --- |
| Global length, width, height, or uniform envelope scale | Simple effect such as `scale_axis` or `scale_uniform` may be allowed when it matches backend intent. |
| Whole-model radial or axial offsets | Simple effect may be allowed when the transformation is explicitly declared and validated. |
| Simple shell or wall thickness | Simple effect only when the current geometry really maps to a uniform offset; otherwise adapter or backend-only. |
| Localized chamfer or fillet | Adapter required, or backend-only. Do not use `generic_morph`. |
| Hole, thread, slot, boss, rib, mount, connector cutout, or port geometry | Adapter required, or backend-only. |
| PCB, battery, fixed component clearance, base position, or layout parameter | Adapter plus backend validation, or backend-only. |
| Formula-generated topology such as blade count, airfoil thickness, camber angle, gear count, or repeated features | Adapter required because topology, vertex counts, or feature counts may change. |
| Cosmetic or intentionally approximate whole-model review deformation | `generic_morph` only with explicit `scope`, `feature_refs`, or `rationale`. |

## Review Parameter Audit

After changing model geometry, formulas, preview adapters, or parameter metadata, audit the parameter panel before treating `review/manifest.json` as current:

```bash
python3 engineering-3d-modeling/scripts/audit_review_parameters.py /path/to/model-project --mode strict
```

The audit reads `parameters.yaml`, `review/manifest.json`, `source/model.py`, `review/cache/current_mesh.json` when declared, and `review/cache/preview_adapter.js` when declared through `manifest.preview.adapter_js`.

Basic audit checks that every manifest preview parameter still exists in `parameters.yaml`, is explicitly `ui.editable: true`, does not use placeholder preview metadata such as `factor: 0`, has `manifest.preview.adapter_js` when `preview.effect` is `adapter`, and does not bind localized engineering features to `generic_morph`.

Strict audit perturbs exposed numeric parameters. Parameters declaring `validation.affects_geometry: true` must change the backend geometry signature produced by `source/model.py`. Adapter-only preview parameters must change the adapter-generated preview mesh signature. Non-adapter preview parameters are checked against the declared preview mesh when possible. `generic_morph` without `preview.scope`, `preview.feature_refs`, or `preview.rationale` fails strict audit because it is indistinguishable from a placeholder. Failed manifest parameters are reported under `disabled_parameters` with a reason and suggested action. Geometry-affecting parameters that are not safely preview-bound are reported under `new_candidates`.

`scripts/validate_model_project.py` runs phase-aware review-parameter audit by default and supports `--review-parameter-audit strict`. `scripts/regenerate_from_review.py` syncs review parameters and runs phase-aware audit before validation and before clearing consumed review state; use `--review-parameter-audit strict` when a draft or accepted iteration also needs strict proof.

After changing `parameters.yaml`, refresh review sliders:

```bash
python3 engineering-3d-modeling/scripts/sync_review_parameters.py /path/to/model-project
```
