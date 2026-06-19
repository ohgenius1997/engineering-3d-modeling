#!/usr/bin/env python3
"""Run CadQuery Fixture 5: complex handheld-fan assembly."""

from __future__ import annotations

import json
import math
import os
import platform
import sys
from datetime import date
from pathlib import Path
from typing import Any


CANDIDATE_DIR = Path(__file__).resolve().parents[1]
BAKEOFF_DIR = CANDIDATE_DIR.parent
SHARED_DIR = BAKEOFF_DIR / "shared"
PACKAGE_DIR = CANDIDATE_DIR / ".python-packages"
OUTPUT_DIR = CANDIDATE_DIR / "outputs" / "fixture5_handheld_fan"
VALIDATION_DIR = CANDIDATE_DIR / "validation"
CACHE_DIR = CANDIDATE_DIR / ".cache"

os.environ.setdefault("XDG_CACHE_HOME", str(CACHE_DIR))
os.environ.setdefault("MPLCONFIGDIR", str(CACHE_DIR / "matplotlib"))
sys.path.insert(0, str(PACKAGE_DIR))
sys.path.insert(0, str(SHARED_DIR / "tools"))

import cadquery as cq  # noqa: E402
import yaml  # noqa: E402
from fixture5_layout import compute_fixture5_layout  # noqa: E402


def rel(path: Path) -> str:
    return str(path.relative_to(CANDIDATE_DIR))


def load_spec() -> dict[str, Any]:
    return yaml.safe_load((SHARED_DIR / "specs" / "fixture-5-handheld-fan.yaml").read_text(encoding="utf-8"))


def shape_obj(shape: Any) -> Any:
    return shape.val() if isinstance(shape, cq.Workplane) else shape


def is_valid(shape: Any) -> bool:
    return bool(shape_obj(shape).isValid())


def bbox_dict(shape: Any) -> dict[str, float]:
    bbox = shape_obj(shape).BoundingBox()
    return {"x": round(float(bbox.xlen), 4), "y": round(float(bbox.ylen), 4), "z": round(float(bbox.zlen), 4)}


def export_shape(shape: Any, base: Path, stl: bool = True) -> list[str]:
    base.parent.mkdir(parents=True, exist_ok=True)
    step_path = base.with_suffix(".step")
    cq.exporters.export(shape, str(step_path))
    outputs = [rel(step_path)]
    if stl:
        stl_path = base.with_suffix(".stl")
        cq.exporters.export(shape, str(stl_path))
        outputs.append(rel(stl_path))
    return outputs


def box_shape(center: dict[str, float], dims: tuple[float, float, float]) -> cq.Workplane:
    return cq.Workplane("XY").box(*dims).translate((center["x"], center["y"], center["z"]))


def cylinder_shape(center: dict[str, float], radius: float, height: float) -> cq.Workplane:
    return cq.Workplane("XY").circle(radius).extrude(height).translate((center["x"], center["y"], center["z"] - height / 2))


def combine(shapes: list[Any]) -> cq.Compound:
    return cq.Compound.makeCompound([shape_obj(shape) for shape in shapes])


def build_front_shell(layout: dict[str, Any]) -> cq.Compound:
    params = layout["parameters"]
    fan = layout["placements"]["fan_center"]
    handle = layout["placements"]["handle_center"]
    wall = params["wall_thickness"]
    front_z = layout["outer_envelope"]["max_z"] - wall / 2
    shapes: list[Any] = [
        cylinder_shape({"x": 0, "y": fan["y"], "z": front_z}, params["head_outer_radius"], wall),
        box_shape({"x": 0, "y": handle["y"], "z": front_z}, (params["handle_width"], params["handle_length"], wall)),
    ]
    return combine(shapes)


def build_front_grille(layout: dict[str, Any]) -> cq.Compound:
    params = layout["parameters"]
    fan = layout["placements"]["fan_center"]
    wall = params["wall_thickness"]
    front_z = layout["outer_envelope"]["max_z"] - wall / 2
    shapes: list[Any] = [
        cylinder_shape({"x": 0, "y": fan["y"], "z": front_z + wall * 0.55}, params["front_grille_ring_radius"], wall * 0.7),
    ]
    spoke_count = int(params["front_grille_spoke_count"])
    for index in range(spoke_count):
        angle = 2 * math.pi * index / spoke_count
        x = math.cos(angle) * 10.0
        y = fan["y"] + math.sin(angle) * 10.0
        shapes.append(box_shape({"x": x, "y": y, "z": front_z + wall * 0.95}, (2.0, 22.0, wall * 0.5)))
    return combine(shapes)


def build_rear_shell(layout: dict[str, Any]) -> cq.Compound:
    params = layout["parameters"]
    fan = layout["placements"]["fan_center"]
    handle = layout["placements"]["handle_center"]
    wall = params["wall_thickness"]
    rear_z = layout["outer_envelope"]["min_z"] + wall / 2
    return combine(
        [
            cylinder_shape({"x": 0, "y": fan["y"], "z": rear_z}, params["head_outer_radius"], wall),
            box_shape({"x": 0, "y": handle["y"], "z": rear_z}, (params["handle_width"], params["handle_length"], wall)),
            box_shape(layout["generated_feature_bounds"]["charge_port_marker"]["center"], (12.0, wall + 1.0, 7.0)),
        ]
    )


def build_internal_frame(layout: dict[str, Any]) -> cq.Compound:
    shapes: list[Any] = []
    for name, feature in layout["generated_feature_bounds"].items():
        if name in {"front_shell_slab", "rear_shell_slab", "charge_port_marker"}:
            continue
        center = feature["center"]
        dims = tuple(float(v) for v in feature["dimensions_mm"])
        if "screw_boss" in name:
            shapes.append(cylinder_shape(center, dims[0] / 2, dims[2]))
        else:
            shapes.append(box_shape(center, dims))
    return combine(shapes)


def build_switch_mechanism(layout: dict[str, Any]) -> cq.Compound:
    return combine(
        [
            box_shape(layout["components"][name]["center"], tuple(float(v) for v in layout["components"][name]["dimensions_mm"]))
            for name in ("switch_thumbwheel", "switch_drive_gear")
        ]
    )


def build_component_envelopes(layout: dict[str, Any]) -> cq.Compound:
    return combine(
        [
            box_shape(item["center"], tuple(float(v) for v in item["dimensions_mm"]))
            for name, item in layout["components"].items()
            if name not in {"switch_thumbwheel", "switch_drive_gear"}
        ]
    )


def run_case(spec: dict[str, Any], case_name: str, edited: bool = False, switch_side: str | None = None) -> dict[str, Any]:
    layout = compute_fixture5_layout(spec, edited=edited, switch_side=switch_side)
    case_dir = OUTPUT_DIR / case_name
    shapes = {
        "front_shell": build_front_shell(layout),
        "front_grille": build_front_grille(layout),
        "rear_shell": build_rear_shell(layout),
        "internal_frame": build_internal_frame(layout),
        "switch_mechanism": build_switch_mechanism(layout),
        "component_envelopes": build_component_envelopes(layout),
    }
    outputs: list[str] = []
    generated: dict[str, Any] = {}
    for name, shape in shapes.items():
        generated[name] = {"valid_solid": is_valid(shape), "bbox_mm": bbox_dict(shape)}
        outputs.extend(export_shape(shape, case_dir / name, stl=name != "component_envelopes"))
    geometry_pass = all(item["valid_solid"] for item in generated.values())
    return {
        "parameters": layout["parameters"],
        "layout": layout,
        "generated_geometry": generated,
        "outputs": outputs,
        "status": "pass" if layout["all_hard_checks_pass"] and geometry_pass else "fail",
    }


def update_backend_report(report: dict[str, Any]) -> None:
    path = CANDIDATE_DIR / "backend_report.yaml"
    existing = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}
    fixtures = existing.setdefault("fixtures", {})
    fixtures["fixture_5"] = {
        "status": report["status"],
        "notes": "Complex handheld-fan assembly generated with named front/rear shells, separate front grille, internal frame, switch mechanism, component envelopes, baseline/edited/left-hand regeneration, and validation.",
        "outputs": report["outputs"] + [report["validation_report"]],
    }
    phase_results = existing.setdefault("phase_results", {})
    phase_results["phase_5_complex_assembly"] = {
        "status": report["status"],
        "evidence": [report["validation_report"]],
    }
    existing["tested_on"] = date.today().isoformat()
    path.write_text(yaml.safe_dump(existing, sort_keys=False), encoding="utf-8")


def main() -> int:
    spec = load_spec()
    cases = {
        "baseline": run_case(spec, "baseline"),
        "edited": run_case(spec, "edited", edited=True),
        "left_hand": run_case(spec, "left_hand", switch_side="left"),
    }
    status = "pass" if all(case["status"] == "pass" for case in cases.values()) else "fail"
    all_outputs: list[str] = []
    for case in cases.values():
        all_outputs.extend(case["outputs"])
    report = {
        "fixture": "fixture_5",
        "status": status,
        "backend": "CadQuery",
        "backend_version": getattr(cq, "__version__", "unknown"),
        "python": platform.python_version(),
        "source_spec": "../shared/specs/fixture-5-handheld-fan.yaml",
        "cases": cases,
        "outputs": all_outputs,
    }
    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    validation_path = VALIDATION_DIR / "fixture5_handheld_fan_validation.json"
    validation_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    report["validation_report"] = rel(validation_path)
    update_backend_report(report)
    print(json.dumps({"status": status, "validation_report": report["validation_report"]}, indent=2))
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
