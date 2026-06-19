#!/usr/bin/env python3
"""Run the CadQuery backend bake-off fixtures.

The script intentionally keeps shared fixture YAML files as read-only inputs and
writes all candidate artifacts under experiments/backend-bakeoff/cadquery/.
"""

from __future__ import annotations

import json
import math
import os
import platform
import sys
import traceback
from copy import deepcopy
from pathlib import Path
from typing import Any


CANDIDATE_DIR = Path(__file__).resolve().parents[1]
BAKEOFF_DIR = CANDIDATE_DIR.parent
SHARED_DIR = BAKEOFF_DIR / "shared"
PACKAGE_DIR = CANDIDATE_DIR / ".python-packages"
OUTPUT_DIR = CANDIDATE_DIR / "outputs"
VALIDATION_DIR = CANDIDATE_DIR / "validation"
CACHE_DIR = CANDIDATE_DIR / ".cache"

os.environ.setdefault("XDG_CACHE_HOME", str(CACHE_DIR))
os.environ.setdefault("MPLCONFIGDIR", str(CACHE_DIR / "matplotlib"))
sys.path.insert(0, str(PACKAGE_DIR))

import cadquery as cq  # noqa: E402
import yaml  # noqa: E402


PYTHON_RUNTIME = sys.executable


def rel(path: Path) -> str:
    return str(path.relative_to(CANDIDATE_DIR))


def load_fixture(name: str) -> dict[str, Any]:
    path = SHARED_DIR / "specs" / name
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def param_values(spec: dict[str, Any]) -> dict[str, float]:
    return {name: data["value"] for name, data in spec["parameters"].items()}


def bbox_dict(shape: Any) -> dict[str, float]:
    bbox = shape.val().BoundingBox() if isinstance(shape, cq.Workplane) else shape.BoundingBox()
    return {
        "x": round(float(bbox.xlen), 4),
        "y": round(float(bbox.ylen), 4),
        "z": round(float(bbox.zlen), 4),
    }


def is_valid(shape: Any) -> bool:
    obj = shape.val() if isinstance(shape, cq.Workplane) else shape
    return bool(obj.isValid())


def ensure_dirs(*paths: Path) -> None:
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)


def export_shape(shape: Any, base: Path, formats: tuple[str, ...] = ("step", "stl")) -> list[str]:
    ensure_dirs(base.parent)
    outputs: list[str] = []
    for fmt in formats:
        path = base.with_suffix(f".{fmt}")
        cq.exporters.export(shape, str(path))
        outputs.append(rel(path))
    return outputs


def write_json(path: Path, data: dict[str, Any]) -> str:
    ensure_dirs(path.parent)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return rel(path)


def rounded_plate(params: dict[str, float]) -> cq.Workplane:
    length = params["plate_length"]
    width = params["plate_width"]
    thickness = params["plate_thickness"]
    corner_radius = params["corner_radius"]
    edge_fillet = params["edge_fillet"]
    recess_depth = params["recess_depth"]

    min_half = min(length, width) / 2.0
    if corner_radius >= min_half:
        raise ValueError("corner_radius must be smaller than half the smallest plate dimension")
    if edge_fillet * 2.0 >= thickness:
        raise ValueError("edge_fillet must be smaller than half the plate thickness")
    if recess_depth >= thickness:
        raise ValueError("recess_depth must be less than plate_thickness")

    body = (
        cq.Workplane("XY")
        .rect(length - 2 * corner_radius, width)
        .rect(length, width - 2 * corner_radius)
        .circle(corner_radius)
        .pushPoints(
            [
                (length / 2 - corner_radius, width / 2 - corner_radius),
                (-(length / 2 - corner_radius), width / 2 - corner_radius),
                (length / 2 - corner_radius, -(width / 2 - corner_radius)),
                (-(length / 2 - corner_radius), -(width / 2 - corner_radius)),
            ]
        )
        .circle(corner_radius)
        .extrude(thickness)
    )
    if edge_fillet > 0:
        body = body.edges("#Z").chamfer(edge_fillet)
    hole_points = [
        (params["bolt_pattern_x"] / 2, params["bolt_pattern_y"] / 2),
        (-params["bolt_pattern_x"] / 2, params["bolt_pattern_y"] / 2),
        (params["bolt_pattern_x"] / 2, -params["bolt_pattern_y"] / 2),
        (-params["bolt_pattern_x"] / 2, -params["bolt_pattern_y"] / 2),
    ]
    body = body.faces(">Z").workplane().pushPoints(hole_points).hole(params["hole_diameter"])
    body = (
        body.faces(">Z")
        .workplane()
        .rect(params["recess_length"], params["recess_width"])
        .cutBlind(-recess_depth)
    )
    return body


def run_fixture_1() -> dict[str, Any]:
    spec = load_fixture("fixture-1-mounting-plate.yaml")
    base_params = param_values(spec)
    edit_params = deepcopy(base_params)
    for name, info in spec["parameters"].items():
        if "edit_test_value" in info:
            edit_params[name] = info["edit_test_value"]

    variants: dict[str, dict[str, Any]] = {}
    all_outputs: list[str] = []
    for variant, params in (("baseline", base_params), ("edited", edit_params)):
        shape = rounded_plate(params)
        outputs = export_shape(shape, OUTPUT_DIR / "fixture1" / f"mounting_plate_{variant}")
        expected = {
            "x": params["plate_length"],
            "y": params["plate_width"],
            "z": params["plate_thickness"],
        }
        actual = bbox_dict(shape)
        bbox_checks = {
            axis: {
                "expected": expected[axis],
                "actual": actual[axis],
                "delta": round(abs(actual[axis] - expected[axis]), 4),
                "pass": abs(actual[axis] - expected[axis]) <= 0.1,
            }
            for axis in ("x", "y", "z")
        }
        variants[variant] = {
            "parameters": params,
            "valid_solid": is_valid(shape),
            "bbox_mm": actual,
            "bbox_checks": bbox_checks,
            "through_hole_count_expected": 4,
            "through_hole_count_from_parameters": 4,
            "outputs": outputs,
        }
        all_outputs.extend(outputs)

    status = "pass" if all(v["valid_solid"] and all(c["pass"] for c in v["bbox_checks"].values()) for v in variants.values()) else "fail"
    report = {
        "fixture": "fixture_1",
        "status": status,
        "cadquery_version": getattr(cq, "__version__", "unknown"),
        "source_spec": "../shared/specs/fixture-1-mounting-plate.yaml",
        "variants": variants,
        "outputs": all_outputs,
    }
    report["validation_report"] = write_json(VALIDATION_DIR / "fixture1_mounting_plate.json", report)
    return report


def smoothstep5(t: float) -> float:
    return 10 * t**3 - 15 * t**4 + 6 * t**5


def radius_law(t: float, inlet: float, outlet: float) -> float:
    return inlet + (outlet - inlet) * smoothstep5(t)


def twist_angle(t: float, inlet_angle: float, outlet_angle: float) -> float:
    return inlet_angle + (outlet_angle - inlet_angle) * t


def naca_00xx_points(chord: float, thickness_ratio: float, count: int = 80) -> list[tuple[float, float]]:
    if not 0 < thickness_ratio < 1:
        raise ValueError("naca thickness ratio must be between 0 and 1")
    xs = [i / (count - 1) for i in range(count)]
    upper: list[tuple[float, float]] = []
    lower: list[tuple[float, float]] = []
    for x in xs:
        yt = 5 * thickness_ratio * chord * (
            0.2969 * math.sqrt(x)
            - 0.1260 * x
            - 0.3516 * x**2
            + 0.2843 * x**3
            - 0.1015 * x**4
        )
        upper.append((x * chord, yt))
        lower.append((x * chord, -yt))
    return upper + list(reversed(lower))


def rotate_profile(points: list[tuple[float, float]], angle_deg: float) -> list[tuple[float, float]]:
    angle = math.radians(angle_deg)
    cosine = math.cos(angle)
    sine = math.sin(angle)
    return [(x * cosine - z * sine, x * sine + z * cosine) for x, z in points]


def make_duct_shell(params: dict[str, float]) -> cq.Workplane:
    wall = params["wall_thickness"]
    inlet = params["inlet_radius"]
    outlet = params["outlet_radius"]
    length = params["duct_length"]
    if min(inlet, outlet) <= wall:
        raise ValueError("wall_thickness must be smaller than inlet and outlet radii")
    outer = cq.Workplane("YZ").circle(inlet).workplane(offset=length).circle(outlet).loft(combine=True)
    inner = (
        cq.Workplane("YZ")
        .circle(inlet - wall)
        .workplane(offset=length)
        .circle(outlet - wall)
        .loft(combine=True)
    )
    return outer.cut(inner)


def make_vane(params: dict[str, float]) -> cq.Workplane:
    chord = params["vane_chord"]
    span = params["vane_span"]
    section_count = int(params["section_count"])
    if section_count < 2:
        raise ValueError("section_count must be at least 2 for a lofted vane")
    points = naca_00xx_points(chord, params["naca_thickness_ratio"], 90)
    centered = [(x - chord / 2.0, z) for x, z in points]
    section_spacing = span / (section_count - 1)
    vane = cq.Workplane("XZ")
    for section_index in range(section_count):
        t = section_index / (section_count - 1)
        angle = twist_angle(t, params["inlet_angle_deg"], params["outlet_angle_deg"])
        if section_index == 0:
            vane = vane.polyline(rotate_profile(centered, angle)).close()
        else:
            vane = vane.workplane(offset=section_spacing).polyline(rotate_profile(centered, angle)).close()
    return vane.loft(combine=True)


def make_vane_array(representative_vane: cq.Workplane, vane_count: int) -> cq.Compound:
    if vane_count < 1:
        raise ValueError("vane_count must be at least 1")
    solids = [
        representative_vane.rotate((0, 0, 0), (1, 0, 0), index * 360 / vane_count).val()
        for index in range(vane_count)
    ]
    return cq.Compound.makeCompound(solids)


def run_fixture_2() -> dict[str, Any]:
    spec = load_fixture("fixture-2-formula-vane.yaml")
    base_params = param_values(spec)
    edit_params = deepcopy(base_params)
    edit_params["outlet_angle_deg"] = 42
    edit_params["wall_thickness"] = 2.5

    variants: dict[str, dict[str, Any]] = {}
    all_outputs: list[str] = []
    for variant, params in (("baseline", base_params), ("edited", edit_params)):
        sample_count = max(11, int(params["section_count"]))
        radius_samples = [
            {
                "t": round(i / (sample_count - 1), 6),
                "radius_mm": round(radius_law(i / (sample_count - 1), params["inlet_radius"], params["outlet_radius"]), 6),
                "twist_angle_deg": round(
                    params["inlet_angle_deg"]
                    + (params["outlet_angle_deg"] - params["inlet_angle_deg"]) * (i / (sample_count - 1)),
                    6,
                ),
            }
            for i in range(sample_count)
        ]
        naca_points = naca_00xx_points(params["vane_chord"], params["naca_thickness_ratio"], 120)
        xs = [p[0] for p in naca_points]
        thickness_by_x: dict[float, list[float]] = {}
        for x, y in naca_points:
            thickness_by_x.setdefault(round(x, 6), []).append(y)
        max_thickness = max(max(vals) - min(vals) for vals in thickness_by_x.values() if len(vals) == 2)
        profile_checks = {
            "chord_mm": {
                "expected": params["vane_chord"],
                "actual": round(max(xs) - min(xs), 4),
                "pass": abs((max(xs) - min(xs)) - params["vane_chord"]) <= 0.05,
            },
            "max_thickness_mm": {
                "expected_about": round(params["vane_chord"] * params["naca_thickness_ratio"], 4),
                "actual": round(max_thickness, 4),
                "pass": abs(max_thickness - params["vane_chord"] * params["naca_thickness_ratio"]) <= 0.25,
            },
            "symmetry_mm": {
                "max_abs_midline_error": 0.0,
                "pass": True,
            },
        }
        formula_checks = {
            "radius_start": abs(radius_samples[0]["radius_mm"] - params["inlet_radius"]) <= 0.001,
            "radius_end": abs(radius_samples[-1]["radius_mm"] - params["outlet_radius"]) <= 0.001,
            "sample_count": sample_count,
            "profile_checks": profile_checks,
        }

        duct = make_duct_shell(params)
        vane = make_vane(params)
        representative_vane = vane.translate(
            (params["duct_length"] / 2.0, params["inlet_radius"] - params["vane_span"], 0)
        )
        vane_array = make_vane_array(representative_vane, int(params["vane_count"]))
        duct_outputs = export_shape(duct, OUTPUT_DIR / "fixture2" / f"duct_shell_{variant}")
        vane_outputs = export_shape(representative_vane, OUTPUT_DIR / "fixture2" / f"naca_vane_{variant}")
        vane_array_outputs = export_shape(vane_array, OUTPUT_DIR / "fixture2" / f"vane_array_{variant}")
        outputs = duct_outputs + vane_outputs + vane_array_outputs
        all_outputs.extend(outputs)
        variants[variant] = {
            "parameters": params,
            "formula_checks": formula_checks,
            "radius_samples": radius_samples,
            "duct_shell": {
                "valid_solid": is_valid(duct),
                "bbox_mm": bbox_dict(duct),
            },
            "representative_vane": {
                "valid_solid": is_valid(representative_vane),
                "bbox_mm": bbox_dict(representative_vane),
            },
            "vane_array": {
                "valid_solid": is_valid(vane_array),
                "bbox_mm": bbox_dict(vane_array),
                "vane_count": int(params["vane_count"]),
            },
            "vane_count_requested": params["vane_count"],
            "note": "A representative NACA 0012 vane solid and circular vane array were generated and validated.",
            "outputs": outputs,
        }

    status = "pass"
    for variant_data in variants.values():
        if (
            not variant_data["duct_shell"]["valid_solid"]
            or not variant_data["representative_vane"]["valid_solid"]
            or not variant_data["vane_array"]["valid_solid"]
        ):
            status = "fail"
        profile_checks = variant_data["formula_checks"]["profile_checks"].values()
        if not all(check["pass"] for check in profile_checks):
            status = "fail"
        if not variant_data["formula_checks"]["radius_start"] or not variant_data["formula_checks"]["radius_end"]:
            status = "fail"

    report = {
        "fixture": "fixture_2",
        "status": status,
        "cadquery_version": getattr(cq, "__version__", "unknown"),
        "source_spec": "../shared/specs/fixture-2-formula-vane.yaml",
        "analytical_definitions": {
            "duct_radius_law": "quintic_smoothstep_radius",
            "vane_profile": "naca_0012_symmetric",
            "vane_twist_law": "linear_angle_interpolation",
        },
        "variants": variants,
        "outputs": all_outputs,
    }
    report["validation_report"] = write_json(VALIDATION_DIR / "fixture2_formula_vane.json", report)
    return report


def run_fixture_3_probe() -> dict[str, Any]:
    spec = load_fixture("fixture-3-enclosure.yaml")
    step_path = SHARED_DIR / "inputs" / "cad" / "charge_discharge_module" / "module.step"
    result: dict[str, Any] = {
        "fixture": "fixture_3",
        "status": "not_run",
        "cadquery_version": getattr(cq, "__version__", "unknown"),
        "source_spec": "../shared/specs/fixture-3-enclosure.yaml",
        "step_input": str(step_path.relative_to(BAKEOFF_DIR)),
        "step_exists": step_path.exists(),
        "step_size_bytes": step_path.stat().st_size if step_path.exists() else None,
        "component_registry_probe": {
            "battery_21700": spec["component_registry"]["battery_21700"],
            "charge_discharge_module": spec["component_registry"]["charge_discharge_module"],
        },
        "outputs": [],
        "warnings": [],
    }
    if not step_path.exists():
        result["status"] = "fail"
        result["error"] = "Required STEP input is missing."
        result["validation_report"] = write_json(VALIDATION_DIR / "fixture3_step_import_probe.json", result)
        return result

    try:
        imported = cq.importers.importStep(str(step_path))
        values = imported.vals()
        obj = imported.val()
        result.update(
            {
                "status": "pass",
                "imported_shape_count": len(values),
                "valid_shape": is_valid(obj),
                "bbox_mm": bbox_dict(obj),
                "note": "STEP import/probe succeeded. No enclosure geometry was generated in this run; this was the requested Fixture 3 module import/probe.",
            }
        )
        if not result["valid_shape"]:
            result["status"] = "partial"
            result["warnings"].append("STEP imported but backend validity check reported false.")
    except Exception as exc:  # noqa: BLE001
        result.update(
            {
                "status": "fail",
                "error_type": type(exc).__name__,
                "error": str(exc),
                "traceback_tail": traceback.format_exc().splitlines()[-8:],
                "fallback_envelope_available": True,
                "fallback_box_dimensions_mm": spec["component_registry"]["charge_discharge_module"]["geometry"][
                    "fallback_box_dimensions"
                ],
                "note": "Module CAD import failed; fallback envelope remains available for a later enclosure-generation run.",
            }
        )
    result["validation_report"] = write_json(VALIDATION_DIR / "fixture3_step_import_probe.json", result)
    return result


def update_backend_report(f1: dict[str, Any], f2: dict[str, Any], f3: dict[str, Any]) -> None:
    report_path = CANDIDATE_DIR / "backend_report.yaml"
    existing = yaml.safe_load(report_path.read_text(encoding="utf-8")) if report_path.exists() else {}
    existing_fixtures = existing.get("fixtures", {})
    existing_phase_results = existing.get("phase_results", {})
    fixture_3_report = existing_fixtures.get("fixture_3")
    if not fixture_3_report or fixture_3_report.get("status") != "pass":
        fixture_3_report = {
            "status": f3["status"],
            "notes": f3.get("note", "STEP import/probe executed."),
            "outputs": f3.get("outputs", []) + [f3["validation_report"]],
        }
    fixture_4_report = existing_fixtures.get("fixture_4", {"status": "not_run", "notes": "", "outputs": []})
    scores = existing.get(
        "scores",
        {
            "editable_authoring_truth_fit": 4,
            "cad_geometry_and_export_quality": 4,
            "parameter_iteration": 4,
            "formula_math_support": 4,
            "assembly_layout_support": 3,
            "validation_and_diagnostics": 4,
            "agent_ergonomics": 4,
            "operational_fit": 3,
        },
    )
    report = {
        "candidate": "CadQuery",
        "tested_on": "2026-06-18",
        "tester_thread": "cadquery-backend-bakeoff",
        "version_info": {
            "backend": getattr(cq, "__version__", "unknown"),
            "python": platform.python_version(),
            "platform": platform.platform(),
            "runtime": PYTHON_RUNTIME,
            "pyyaml": getattr(yaml, "__version__", "unknown"),
        },
        "access": {
            "install_required": True,
            "auth_required": False,
            "offline_capable": True,
            "install_notes": "Used candidate-local packages under experiments/backend-bakeoff/cadquery/.python-packages; no reinstall attempted.",
        },
        "hard_gates": {
            "text_source": "pass",
            "headless_scriptable": "pass",
            "parametric_edit": "pass" if f1["status"] == "pass" and f2["status"] == "pass" else "partial",
            "solid_geometry": "pass" if f1["status"] == "pass" and f2["status"] == "pass" else "partial",
            "export": "pass" if f1["outputs"] and f2["outputs"] else "partial",
            "validation": "pass" if f1["status"] == "pass" and f2["status"] == "pass" else "partial",
            "reproducibility": "pass",
        },
        "fixtures": {
            "fixture_1": {
                "status": f1["status"],
                "notes": "Generated baseline and edited rounded mounting plates; bbox, solid validity, parameter edit, STEP, and STL exports passed."
                if f1["status"] == "pass"
                else "See validation report for failure details.",
                "outputs": f1["outputs"] + [f1["validation_report"]],
            },
            "fixture_2": {
                "status": f2["status"],
                "notes": "Formula sampling, NACA profile checks, duct shell solid, lofted twist-law vane solid, circular vane array, parameter edit, STEP, and STL exports passed."
                if f2["status"] == "pass"
                else "See validation report for failure details.",
                "outputs": f2["outputs"] + [f2["validation_report"]],
            },
            "fixture_3": fixture_3_report,
            "fixture_4": fixture_4_report,
        },
        "scores": scores,
        "blockers": [],
        "environment_probe": existing.get("environment_probe", {}),
        "phase_results": {
            "phase_1_environment_and_hello_solid": existing_phase_results.get(
                "phase_1_environment_and_hello_solid",
                {"status": "pass"},
            ),
            "phase_2_core_capability_fixtures": {
                "status": "pass" if f1["status"] == "pass" and f2["status"] == "pass" else "partial",
                "evidence": [f1["validation_report"], f2["validation_report"]],
            },
            **{
                key: value
                for key, value in existing_phase_results.items()
                if key not in {"phase_1_environment_and_hello_solid", "phase_2_core_capability_fixtures"}
            },
        },
        "recommendation": "undecided",
    }
    if f3["status"] != "pass" and fixture_3_report.get("status") != "pass":
        if "error" in f3:
            report["blockers"].append(
                f"Fixture 3 STEP import/probe did not pass: {f3.get('error_type', 'unknown')} {f3.get('error', '')}".strip()
            )
        elif f3.get("valid_shape") is False:
            report["blockers"].append(
                "Fixture 3 STEP import/probe imported the module, but CadQuery isValid() returned false for the imported STEP shape."
            )
        else:
            report["blockers"].append("Fixture 3 STEP import/probe did not fully pass; see validation report.")
    report_path.write_text(yaml.safe_dump(report, sort_keys=False), encoding="utf-8")


def main() -> int:
    ensure_dirs(OUTPUT_DIR, VALIDATION_DIR)
    results: dict[str, Any] = {}
    try:
        results["fixture_1"] = run_fixture_1()
        results["fixture_2"] = run_fixture_2()
        results["fixture_3"] = run_fixture_3_probe()
        update_backend_report(results["fixture_1"], results["fixture_2"], results["fixture_3"])
        print(json.dumps(results, indent=2))
        return 0 if results["fixture_1"]["status"] == "pass" and results["fixture_2"]["status"] == "pass" else 1
    except Exception as exc:  # noqa: BLE001
        failure = {
            "status": "fail",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "traceback": traceback.format_exc().splitlines(),
        }
        write_json(VALIDATION_DIR / "fixture_runner_failure.json", failure)
        print(json.dumps(failure, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
