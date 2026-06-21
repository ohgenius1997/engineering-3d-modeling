# Assemblies And Layout

## Assembly Normalization

For unstructured prompts, first normalize the problem before generating parts. A compact enclosure request, for example, should become:

- fixed components,
- component envelopes,
- keepouts,
- interfaces and mounting points,
- hard constraints,
- soft goals,
- generated parts,
- layout assumptions,
- validation targets.

## Component Registry

A component registry is a same-project list of parts that the generated model must contain, mount, avoid, or connect to. It is not cross-project reuse in V1.

Useful fields:

- `id`,
- `name`,
- `source`: STEP, drawing, datasheet, user dimension, or generated envelope,
- `role`: fixed component, generated part, fastener, clearance volume, or keepout,
- `bbox` or measured envelope,
- `mount_points`,
- `connectors`,
- `keepouts`,
- `required_clearance`,
- `placement`,
- `visibility_default`.

## Layout Spec

The layout spec records where components go and why. It should include:

- coordinate system and origin,
- selected layout direction,
- hard constraints such as containment, connector access, and screw alignment,
- soft goals such as compactness or ergonomics,
- component placements,
- clearance rules,
- open assumptions.

When the user gives high design freedom, propose one to three options and ask them to select one active direction. Only the selected direction should enter the active model project.

## Generated Parts

Generated parts are source-owned CAD features, such as:

- front and rear shells,
- lids and bezels,
- cradles and clips,
- bosses and posts,
- ribs,
- cutouts,
- ducts,
- guards,
- simple knobs, wheels, shafts, and gears.

Each generated part should have a stable part id and, where practical, named feature refs for review.

## Simple Gear Trains

V1 can support simple one to three stage gear transmission structures. Keep scope explicit:

- spur or simple bevel-like approximations only when suitable;
- record module, tooth counts, pressure angle, center distances, gear thickness, shaft positions, and clearances;
- validate center distances and collisions;
- do not claim full dynamic simulation or production gear engineering unless separately validated.

## Assembly Validation

At minimum, validate:

- fixed component import or envelope creation,
- containment inside generated shells,
- collisions/interferences,
- required clearances,
- access to ports, switches, screws, batteries, and service openings,
- generated-part alignment,
- assembly STEP export.

Review HTML should support per-part visibility toggles. Explosion view is not required in V1.
