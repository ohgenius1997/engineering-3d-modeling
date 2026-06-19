#!/usr/bin/env python3
"""Verify the candidate-local CadQuery environment.

This is an environment probe only. It does not count as a fixture result.
"""

from __future__ import annotations

import json
import os
import platform
import sys
from pathlib import Path


CANDIDATE_DIR = Path(__file__).resolve().parents[1]
PACKAGE_DIR = CANDIDATE_DIR / ".python-packages"
OUTPUT_DIR = CANDIDATE_DIR / "outputs" / "env_probe"
VALIDATION_DIR = CANDIDATE_DIR / "validation"
CACHE_DIR = CANDIDATE_DIR / ".cache"

os.environ.setdefault("XDG_CACHE_HOME", str(CACHE_DIR))
os.environ.setdefault("MPLCONFIGDIR", str(CACHE_DIR / "matplotlib"))
sys.path.insert(0, str(PACKAGE_DIR))

import cadquery as cq  # noqa: E402
import yaml  # noqa: E402


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)

    box = cq.Workplane("XY").box(10, 20, 3)
    solid = box.val()
    bbox = solid.BoundingBox()

    step_path = OUTPUT_DIR / "cadquery_env_box.step"
    stl_path = OUTPUT_DIR / "cadquery_env_box.stl"
    cq.exporters.export(box, str(step_path))
    cq.exporters.export(box, str(stl_path))

    report = {
        "status": "pass",
        "cadquery_version": getattr(cq, "__version__", "unknown"),
        "python": sys.version,
        "platform": platform.platform(),
        "pyyaml_version": getattr(yaml, "__version__", "unknown"),
        "package_dir": str(PACKAGE_DIR.relative_to(CANDIDATE_DIR)),
        "bbox_mm": {
            "x": round(float(bbox.xlen), 4),
            "y": round(float(bbox.ylen), 4),
            "z": round(float(bbox.zlen), 4),
        },
        "outputs": [
            str(step_path.relative_to(CANDIDATE_DIR)),
            str(stl_path.relative_to(CANDIDATE_DIR)),
        ],
    }
    (VALIDATION_DIR / "environment_probe.json").write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
