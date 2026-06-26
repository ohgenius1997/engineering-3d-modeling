# build123d Patterns

## Backend Position

Use build123d as the V1 default backend for local Python BRep generation and STEP export. Prefer readable source that mirrors the modeling sequence over clever chained code.

STEP/BRep output can be opened in CAD tools such as Fusion 360 for direct editing, but it does not preserve build123d's parametric history inside those tools. The authoring truth remains the model project source, specs, parameters, and validation evidence. STEP is the CAD exchange/delivery artifact generated from that truth.

## Source Organization

Prefer this shape for `source/model.py`:

```python
def load_parameters(path):
    ...

def build_model(params):
    ...
    return model

def write_step(model, path):
    ...

def main():
    params = load_parameters(...)
    model = build_model(params)
    write_step(model, ...)
```

For assemblies, separate:

- fixed component imports or envelope construction,
- generated parts,
- placement/layout transforms,
- assembly composition,
- optional per-part exports.

Keep formulas in small functions or modules. Do not hide engineering relationships inside long geometry blocks.

## Units

Use millimeters by default unless the project states otherwise. Record units in `parameters.yaml`, `spec/current.yaml`, and validation output. Do not mix unit systems without explicit conversion helpers.

## Parameters

Expose only parameters that should be reviewed or edited. Good parameter candidates include:

- edge lengths and key dimensions,
- wall and shell thickness,
- clearances,
- fillet radii,
- chamfer widths,
- hole diameters and depths,
- thread specs and thread depths,
- rib count, rib thickness, and rib spacing,
- boss diameter and height,
- gasket grooves and offsets,
- fastener spacing,
- component offsets,
- gear module, tooth count, center distance, and pressure angle for simple gear trains.

Layout, structural topology, major exterior form, and part count changes should return to the agent workflow unless explicitly parameterized with safe bounds.

## STEP Output

Export STEP with `scripts/export_step.py` when the current preview is satisfactory or a CAD handoff needs a fresh exchange file. Work/review iterations may defer STEP while the model is still being reviewed. Do not export STL, 3MF, or G-code as default deliverables. Temporary preview meshes are allowed only as derived review cache assets.

Assemblies should export one assembly STEP by default. Per-part STEP files are optional and should be controlled by the spec or user request.

Fusion 360 API scripts or other non-build123d routes are allowed only as explicit backend overrides or legacy inputs. Record them in `spec/current.yaml` under `backend.override` with a reason; do not make them the implicit default authoring truth shape.

## Source Quality

Readable source is a design artifact. Keep:

- named functions for major features,
- named parameters instead of magic numbers,
- short comments for non-obvious construction logic,
- stable part and feature identifiers when review refs depend on them,
- deterministic output paths,
- explicit validation hooks for critical dimensions.
