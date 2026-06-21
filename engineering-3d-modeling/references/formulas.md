# Formulas

## Role

Formula-driven geometry is first-class in this skill. Named curves, airfoils, splines, guide-vane laws, ducts, and analytic exterior forms should be represented explicitly in specs, parameters, source, and validation.

## Recording A Formula

Record:

- formula id and name,
- source or provenance when applicable,
- parameter bindings,
- units,
- valid domain,
- sampled validation targets,
- expected endpoint or continuity constraints,
- generated feature ids that depend on it.

## Common Patterns

### Smooth Radius Transition

For ducts or shrouds, a fifth-degree smoothstep can define a radius transition:

```text
s = x / length
blend = 6*s^5 - 15*s^4 + 10*s^3
radius = inlet_radius + (outlet_radius - inlet_radius) * blend
```

This gives zero first and second derivative at both ends when used inside the valid domain.

### NACA 4-Digit Profiles

For NACA profiles, record the profile code, chord length, thickness, camber values when applicable, sampling density, and trailing-edge convention. Validate chord, thickness, and section orientation before using the points to create solid geometry.

### Splines And Sampled Curves

If a formula yields sampled points, validate:

- point count,
- monotonic axes when required,
- endpoint coordinates,
- minimum wall/radius constraints,
- self-intersection risk,
- smoothness expectations.

## Implementation Guidance

Keep formula functions separate from build123d construction blocks. The formula should produce points, sections, dimensions, or transforms; backend code should turn those values into CAD.

Do not bury formula constants in geometry calls. Bind them through `parameters.yaml` or explicit source constants with comments explaining provenance.
