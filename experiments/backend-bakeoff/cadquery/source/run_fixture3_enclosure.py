#!/usr/bin/env python3
"""Run CadQuery Fixture 3 enclosure generation and validation."""

from __future__ import annotations

import json
import os
import sys
import argparse
from pathlib import Path
from typing import Any


CANDIDATE_DIR = Path(__file__).resolve().parents[1]
BAKEOFF_DIR = CANDIDATE_DIR.parent
SHARED_DIR = BAKEOFF_DIR / "shared"
PACKAGE_DIR = CANDIDATE_DIR / ".python-packages"
DEFAULT_OUTPUT_DIR = CANDIDATE_DIR / "outputs" / "fixture3"
VALIDATION_DIR = CANDIDATE_DIR / "validation"
CACHE_DIR = CANDIDATE_DIR / ".cache"

os.environ.setdefault("XDG_CACHE_HOME", str(CACHE_DIR))
os.environ.setdefault("MPLCONFIGDIR", str(CACHE_DIR / "matplotlib"))
sys.path.insert(0, str(PACKAGE_DIR))
sys.path.insert(0, str(SHARED_DIR / "tools"))

import cadquery as cq  # noqa: E402
import yaml  # noqa: E402
from fixture3_layout import compute_fixture3_layout  # noqa: E402


def rel(path: Path) -> str:
    return str(path.relative_to(CANDIDATE_DIR))


def center_from_bounds(bounds: dict[str, float]) -> tuple[float, float, float]:
    return (
        (bounds["min_x"] + bounds["max_x"]) / 2,
        (bounds["min_y"] + bounds["max_y"]) / 2,
        (bounds["min_z"] + bounds["max_z"]) / 2,
    )


def box_from_bounds(bounds: dict[str, float]) -> cq.Workplane:
    return (
        cq.Workplane("XY")
        .box(bounds["size_x"], bounds["size_y"], bounds["size_z"])
        .translate(center_from_bounds(bounds))
    )


def export_shape(
    shape: cq.Workplane,
    name: str,
    output_dir: Path,
    formats: tuple[str, ...] = ("step", "stl"),
) -> list[str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[str] = []
    for fmt in formats:
        path = output_dir / f"{name}.{fmt}"
        cq.exporters.export(shape, str(path))
        outputs.append(rel(path))
    return outputs


def valid(shape: cq.Workplane) -> bool:
    return bool(shape.val().isValid())


def build_lower_shell(layout: dict[str, Any]) -> cq.Workplane:
    outer = layout["bounds"]["outer"]
    inner = layout["bounds"]["inner"]
    wall = layout["parameters"]["wall_thickness"]
    lid_gap = layout["parameters"]["lid_gap"]
    lower_z = outer["size_z"] - wall - lid_gap
    lower_center_z = outer["min_z"] + lower_z / 2

    lower_outer = cq.Workplane("XY").box(outer["size_x"], outer["size_y"], lower_z).translate((0, 0, lower_center_z))
    cut_height = max(0.1, lower_z - wall + 1.0)
    cut_center_z = outer["min_z"] + wall + cut_height / 2
    inner_cut = cq.Workplane("XY").box(inner["size_x"], inner["size_y"], cut_height).translate((0, 0, cut_center_z))
    shell = lower_outer.cut(inner_cut)

    port = layout["port_opening"]
    port_cut = (
        cq.Workplane("XY")
        .box(port["dimensions"]["depth_x"], port["dimensions"]["width_y"], port["dimensions"]["height_z"])
        .translate((outer["max_x"] - wall / 2, port["center"]["y"], port["center"]["z"]))
    )
    return shell.cut(port_cut)


def build_lid(layout: dict[str, Any]) -> cq.Workplane:
    outer = layout["bounds"]["outer"]
    wall = layout["parameters"]["wall_thickness"]
    lid_center_z = outer["max_z"] - wall / 2
    return cq.Workplane("XY").box(outer["size_x"], outer["size_y"], wall).translate((0, 0, lid_center_z))


def build_component_envelopes(layout: dict[str, Any]) -> cq.Workplane:
    battery = layout["bounds"]["battery"]
    module = layout["bounds"]["module"]
    battery_center = layout["placements"]["battery_center"]
    battery_shape = (
        cq.Workplane("YZ")
        .circle(battery["size_y"] / 2)
        .extrude(battery["size_x"])
        .translate((battery_center["x"] - battery["size_x"] / 2, battery_center["y"], battery_center["z"]))
    )
    module_shape = box_from_bounds(module)
    return battery_shape.union(module_shape)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iteration", action="store_true", help="Apply Fixture 4 edit deltas")
    args = parser.parse_args()

    spec = yaml.safe_load((SHARED_DIR / "specs" / "fixture-3-enclosure.yaml").read_text(encoding="utf-8"))
    diagnostic = json.loads((SHARED_DIR / "validation" / "module_step_diagnostics.json").read_text(encoding="utf-8"))
    layout = compute_fixture3_layout(spec, diagnostic, edited=args.iteration)
    output_dir = CANDIDATE_DIR / "outputs" / ("fixture4" if args.iteration else "fixture3")
    fixture_id = "fixture_4" if args.iteration else "fixture_3"
    validation_name = "fixture4_iteration_validation.json" if args.iteration else "fixture3_enclosure_validation.json"

    lower_shell = build_lower_shell(layout)
    lid = build_lid(layout)
    component_envelopes = build_component_envelopes(layout)

    outputs = []
    outputs += export_shape(lower_shell, "lower_shell", output_dir)
    outputs += export_shape(lid, "lid", output_dir)
    outputs += export_shape(component_envelopes, "component_envelopes", output_dir, formats=("step",))

    report = {
        "fixture": fixture_id,
        "status": "pass" if layout["all_hard_checks_pass"] and valid(lower_shell) and valid(lid) else "fail",
        "cadquery_version": getattr(cq, "__version__", "unknown"),
        "source_spec": "../shared/specs/fixture-3-enclosure.yaml",
        "module_step_diagnostic": "../shared/validation/module_step_diagnostics.json",
        "module_import_policy": spec["component_inputs"]["charge_discharge_module"]["import_validation_policy"],
        "layout": layout,
        "generated_geometry": {
            "lower_shell_valid": valid(lower_shell),
            "lid_valid": valid(lid),
            "component_envelopes_valid": valid(component_envelopes),
        },
        "outputs": outputs,
        "warnings": [
            "Imported module STEP is retained as reference only; collision validation uses measured bbox envelope because the top-level STEP compound is invalid.",
        ],
    }
    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    report_path = VALIDATION_DIR / validation_name
    report["validation_report"] = rel(report_path)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
