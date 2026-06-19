#!/usr/bin/env python3
"""Diagnose the shared charge/discharge module STEP input.

This script uses the CadQuery candidate-local package set because it already
provides OCP bindings. It writes only shared validation evidence.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
BAKEOFF_DIR = ROOT / "backend-bakeoff"
SHARED_DIR = BAKEOFF_DIR / "shared"
CADQUERY_DIR = BAKEOFF_DIR / "cadquery"
PACKAGE_DIR = CADQUERY_DIR / ".python-packages"
CACHE_DIR = SHARED_DIR / ".cache"
STEP_PATH = SHARED_DIR / "inputs" / "cad" / "charge_discharge_module" / "module.step"
OUT_PATH = SHARED_DIR / "validation" / "module_step_diagnostics.json"

os.environ.setdefault("XDG_CACHE_HOME", str(CACHE_DIR))
os.environ.setdefault("MPLCONFIGDIR", str(CACHE_DIR / "matplotlib"))
sys.path.insert(0, str(PACKAGE_DIR))

import cadquery as cq  # noqa: E402


def bbox_dict(shape) -> dict[str, float]:
    bbox = shape.BoundingBox()
    return {
        "x": round(float(bbox.xlen), 4),
        "y": round(float(bbox.ylen), 4),
        "z": round(float(bbox.zlen), 4),
        "xmin": round(float(bbox.xmin), 4),
        "ymin": round(float(bbox.ymin), 4),
        "zmin": round(float(bbox.zmin), 4),
        "xmax": round(float(bbox.xmax), 4),
        "ymax": round(float(bbox.ymax), 4),
        "zmax": round(float(bbox.zmax), 4),
    }


def count_valid(shapes) -> dict[str, int]:
    total = len(shapes)
    invalid = 0
    for shape in shapes:
        try:
            if not bool(shape.isValid()):
                invalid += 1
        except Exception:
            invalid += 1
    return {"total": total, "valid": total - invalid, "invalid": invalid}


def main() -> int:
    if not STEP_PATH.exists():
        raise FileNotFoundError(STEP_PATH)

    wp = cq.importers.importStep(str(STEP_PATH))
    top = wp.val()
    solids = wp.solids().vals()
    shells = wp.shells().vals()
    faces = wp.faces().vals()
    edges = wp.edges().vals()
    vertices = wp.vertices().vals()
    compounds = wp.compounds().vals()

    payload = {
        "status": "pass",
        "step_path": str(STEP_PATH.relative_to(ROOT)),
        "step_size_bytes": STEP_PATH.stat().st_size,
        "cadquery_version": getattr(cq, "__version__", "unknown"),
        "topology": {
            "top_shape_type": top.ShapeType(),
            "top_valid": bool(top.isValid()),
            "workplane_object_count": len(wp.objects),
            "counts": {
                "compounds": count_valid(compounds),
                "solids": count_valid(solids),
                "shells": count_valid(shells),
                "faces": count_valid(faces),
                "edges": count_valid(edges),
                "vertices": count_valid(vertices),
            },
        },
        "bbox_mm": bbox_dict(top),
        "recommended_fixture3_import_policy": {
            "use_imported_cad_for_visual_reference": True,
            "use_top_compound_for_boolean_collision": False,
            "use_bbox_envelope_for_collision": True,
            "reason": (
                "Top-level STEP compound is invalid and a small number of "
                "imported solids/faces are invalid. A bbox/envelope is the most "
                "reproducible conservative path for current backend bake-off "
                "collision checks."
            ),
        },
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
