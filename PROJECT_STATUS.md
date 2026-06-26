# Project Status

## 2026-06-25

- Updated `engineering-3d-modeling` review HTML template to remove the CAD edges / Mesh / Off display-mode toolbar and always render clean CAD-style edges.
- Kept preview mesh data as the face-rendering, annotation-picking, and adapter-preview source.
- Added review render cache responsibilities for normalized faces, face world/original points, face normals, edge adjacency, and CAD edge candidates so camera movement does not rebuild the complete edge index each frame.
- Updated annotation picking behavior to use hover targets and precise snapped points:
  - explicit refs first,
  - vertices second,
  - visible CAD edge candidates third,
  - face interiors last.
- Face picks now use screen-space barycentric coordinates to interpolate a 3D snapped point instead of storing a face centroid.
- Edge picks now interpolate along visible CAD edge candidates and do not expose all triangle edges as preferred user targets.
- Updated review HTML reference documentation and added static template assertions for cached CAD edges and precise pick helper coverage.
- Follow-up: strengthened default CAD edge visibility by drawing feature transitions when either side has a different `feature_id`, always drawing view-dependent silhouette edges, and slightly increasing CAD edge stroke opacity/width. The CAD edge toolbar remains intentionally removed; CAD-style edges are the default rendering.
- Follow-up: restored large preview mesh protection in the skill template. Meshes above the edge-cache face limit skip full CAD edge adjacency construction and use a lightweight direct preview-edge fallback for display only; fallback triangle edges are not used as annotation edge targets.
- Follow-up: upgraded large mesh protection from a global cutoff to part/feature-group budgeting. Small groups still build clean CAD edge candidates, while oversized imported/reference groups use a low-opacity, screen-thinned preview-edge fallback that is excluded from edge picking.
