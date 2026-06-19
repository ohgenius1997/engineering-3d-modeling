# Validation

## Validation Layers

V1 validation should distinguish:

- project-structure checks,
- parameter/schema checks,
- bundled review JSON schema checks for manifest, annotations, and parameter patches,
- source execution,
- STEP export,
- solid/BRep validity when the backend can report it,
- parameter-to-backend-geometry smoke checks for parameters that declare `validation.affects_geometry: true`,
- dimensional checks,
- assembly containment and clearance checks,
- collision/interference checks,
- review data checks,
- current-vs-previous regression checks when relevant.

## Minimum Project Checks

Check that these exist:

- `brief.md`,
- `AGENTS.md`,
- `spec/current.yaml`,
- `parameters.yaml`,
- `source/model.py`,
- `outputs/step/`,
- `validation/`,
- `review/index.html`,
- `review/manifest.json`,
- `review/annotations.json`,
- `review/parameter_patch.json`,
- `previous/`.

## Geometry Checks

For parts:

- build completes,
- STEP exports,
- model is non-empty,
- explicitly geometry-affecting parameters change the backend model signature when perturbed within declared bounds,
- key dimensions match parameters,
- wall thickness, fillets, holes, threads, ribs, and chamfers are within allowed bounds.

For assemblies:

- fixed components import or envelopes generate,
- generated parts are positioned,
- components are contained where required,
- collisions are absent or explicitly intentional,
- clearances meet rules,
- access openings align with components,
- assembly STEP exports.

## Review Checks

Check that:

- review manifest parses as JSON,
- review manifest, annotations, and parameter patch files pass their bundled schemas,
- parts and refs use stable ids,
- part projects use at most one real manifest part and distinguish subregions with `feature_id`,
- preview mesh face groups match part-vs-feature semantics,
- preview mesh is closed when the source solid is closed, including caps on revolved cones, ducts, hubs, and other surfaces,
- annotations parse and have target refs when provided,
- current annotations are user-authored open review records, not agent diagnostics or already-consumed notes,
- parameter patches refer to declared manifest parameters that remain editable in `parameters.yaml`,
- parameter patch values pass type, unit, min, max, and step checks before they are applied,
- saved parameter changes are applied to `parameters.yaml`, regenerated, and revalidated before becoming current model truth.

## Out Of Scope Checks

Do not make V1 validation depend on slicer output, printer profiles, material selection, G-code, 3MF packaging, simulation, animation, or photoreal rendering.

## Report Shape

Prefer a machine-readable report plus a short human summary:

```json
{
  "schema": "engineering-3d-modeling.validation_report.v1",
  "status": "pass",
  "checks": [],
  "warnings": [],
  "errors": [],
  "outputs": {
    "assembly_step": "outputs/step/example.step",
    "part_steps": []
  }
}
```
