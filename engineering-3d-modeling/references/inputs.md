# Inputs

## Precision Classes

Always record the input class because it controls how strongly the model can claim accuracy.

### Natural Language

Natural-language requests are design intent. Extract:

- object and purpose,
- units and scale,
- required fixed components,
- hard constraints,
- soft goals,
- assumed manufacturing context,
- output requirements.

Ask only for information that blocks a safe first model. Otherwise write assumptions into `brief.md` and `spec/current.yaml`.

### Dimensioned CAD Drawings

Dimensioned drawings are precise requirements. Convert callouts into named parameters and validation checks. Preserve ambiguous drawing interpretation as assumptions or open questions.

When a drawing conflicts with user prose, surface the conflict before modeling if it affects dimensions, fit, or structure.

### Photos

Photos are qualitative references in V1. Use them for exterior-form direction, structural ideas, ergonomics, and relative placement, but do not claim precise reproduction unless the user supplies independent dimensions or scale references.

### Existing Source

For Fusion 360 scripts, build123d scripts, CadQuery scripts, or other CAD code:

1. Store the original under `inputs/legacy/` or an equivalent input location.
2. Identify parameters, construction sequence, exports, and validation gaps.
3. Extract durable intent into specs and parameters before large rewrites.
4. Preserve backend-specific source only when it remains the active implementation or an important reference.

### STEP/STP

STEP/STP files are BRep CAD references or fixed components. They can be imported, measured, placed in assemblies, and used as handoff geometry. They usually do not preserve the original parametric CAD feature history.

### STL/OBJ/Mesh

Mesh files are reference-only in V1. They may help with rough shape comparison, but parameterized reverse engineering from mesh into editable CAD is out of scope.

## Input Manifests

For non-trivial projects, record each input with:

- `id`,
- `path`,
- `type`,
- `precision_class`,
- `source/provenance`,
- `units` if known,
- `role` such as fixed component, drawing, photo reference, or legacy source,
- assumptions and open questions.
