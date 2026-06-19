# Archived Origin: Scope Pivot

## Status
- Archived on: 2026-06-16
- Active project relevance: historical only
- Do not load this file for normal `project-memory` work.

## Why This Archive Exists
This repository began as a discussion about building a natural-language engineering 3D modeling skill. During the design work, the project shifted toward a more general and reusable problem: how future Codex sessions should preserve project context, decisions, operating rules, and handoffs.

The implemented artifact is now the `project-memory` skill. The 3D modeling context below is kept only to preserve origin history.

## Original 3D Modeling Direction
- The starting point was a Fusion 360 Python script generated through vibe coding.
- The script modeled a CAD-native 4028 guide-vane solid using engineering equations.
- The core geometry intent included duct radius transitions, hub radius, NACA 0012 thickness, vane angle, vane count, wall thickness, loft sections, and boolean joins.
- Early discussion suggested moving from Fusion 360 script generation toward a build123d-first pipeline.

## Early Natural-Language CAD Conclusions
- Prefer deterministic model generators over asking an LLM to directly freehand CAD API calls.
- Separate natural-language interpretation from geometry construction.
- Use structured specs and parameter templates.
- Support progressive modeling rather than requiring users to specify final geometry upfront.
- Use assemblies through structured parts, connection points, and joints.
- Keep Fusion 360 as an optional downstream viewer/editor/export target.

## Why It Was Not Kept As Active Context
- The repository's implemented skill is not a CAD generator.
- The reusable artifact became an agent-facing project memory system.
- CAD/3D modeling is now just an example of a domain that could use `project-memory`.

## If This Direction Is Resumed Later
Start a separate repository or branch for an engineering CAD modeling skill. Treat this archive as background only; do not mix CAD-specific assumptions back into the active `project-memory` docs.
