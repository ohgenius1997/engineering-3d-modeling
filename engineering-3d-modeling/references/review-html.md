# Review HTML

## Purpose

The review HTML is a lightweight review and annotation surface. It is not the CAD truth and not a natural-language modeling agent.

V1 review data lives in:

- `review/manifest.json`,
- `review/annotations.json`,
- `review/parameter_patch.json`,
- optional derived preview assets under `review/cache/`.

Annotations are user-authored review input. Do not store agent diagnostics, baseline analysis, implementation notes, or already-consumed comments in `review/annotations.json`; write those to `validation/`, `brief.md`, or source comments instead. Clear current annotations after converting them into the next model revision.

## Allowed V1 Features

- Preview current generated geometry using STEP-derived or source-derived preview assets.
- Optionally compare current and previous revisions.
- Show/hide or isolate assembly parts from a canvas-attached part rail.
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

The manifest may point to derived preview assets. These assets are not committed CAD deliverables.

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

## Local Save

Static `file://` pages cannot overwrite project files directly. When the user needs direct local persistence, run the review UI through `scripts/serve_review.py`:

```bash
python3 engineering-3d-modeling/scripts/serve_review.py /path/to/model-project
```

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
        "normal": [0, -1, 0]
      },
      "camera": {},
      "status": "open"
    }
  ]
}
```

`target` may be `null` for a global annotation. Annotations are review data and are normally cleared after the agent consumes them into spec, parameter, or source changes for the next model revision.

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

A parameter patch is not final model truth until the backend regenerates and validation passes.

Patches are intentionally narrow. They are for HTML review parameters only, not a generic way to change hidden model parameters. A patch that references an unknown parameter, a parameter omitted from `review/manifest.json`, a locked parameter, a wrong value type, a unit mismatch, an out-of-bounds value, or a value off the declared slider step should be rejected before it changes `parameters.yaml`.

Before regenerating from a reviewed project, prefer the total review loop command:

```bash
python3 engineering-3d-modeling/scripts/regenerate_from_review.py /path/to/model-project
```

It applies saved parameter patches, runs `source/model.py`, syncs preview-bound parameters into the manifest, writes `validation/report.json`, and clears consumed review state after validation succeeds.

For manual debugging, apply saved patches before backend regeneration:

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

Supported V1 preview effects are `scale_axis`, `scale_radial`, `scale_uniform`, `offset_axis`, `offset_radial`, `twist_z`, `ripple_radial`, and `generic_morph`. These are review approximations; backend regeneration remains authoritative. Use `generic_morph` only when the preview mesh generator intentionally supplies a model-specific approximation. Do not use `preview.effect: none` to keep a parameter visible; `none` means the parameter is not review-panel eligible.

After changing `parameters.yaml`, refresh review sliders:

```bash
python3 engineering-3d-modeling/scripts/sync_review_parameters.py /path/to/model-project
```
