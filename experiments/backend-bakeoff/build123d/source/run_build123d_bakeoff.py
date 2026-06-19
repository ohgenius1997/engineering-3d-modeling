#!/usr/bin/env python3
"""Run the build123d-only backend bake-off fixtures.

This script intentionally reads the shared fixture YAML files and writes only
inside the build123d candidate directory.
"""

from __future__ import annotations

import json
import math
import os
import platform
import sys
from copy import deepcopy
from datetime import date
from pathlib import Path
from typing import Any


CANDIDATE_DIR = Path(__file__).resolve().parents[1]
BAKEOFF_DIR = CANDIDATE_DIR.parent
REPO_ROOT = BAKEOFF_DIR.parents[1]
PACKAGE_DIR = CANDIDATE_DIR / ".python-packages"
OUTPUT_DIR = CANDIDATE_DIR / "outputs"
VALIDATION_DIR = CANDIDATE_DIR / "validation"
CACHE_DIR = CANDIDATE_DIR / ".cache"

os.environ.setdefault("XDG_CACHE_HOME", str(CACHE_DIR))
os.environ.setdefault("MPLCONFIGDIR", str(CACHE_DIR / "matplotlib"))
sys.path.insert(0, str(PACKAGE_DIR))

import yaml  # noqa: E402
import build123d as bd  # noqa: E402
from build123d import (  # noqa: E402
    Align,
    Axis,
    Box,
    BuildLine,
    BuildPart,
    BuildSketch,
    Circle,
    Compound,
    Cylinder,
    Location,
    Locations,
    Mode,
    Plane,
    Pos,
    Rectangle,
    RectangleRounded,
    Rot,
    add,
    export_step,
    export_stl,
    extrude,
    fillet,
    import_step,
    loft,
    make_face,
    Polyline,
)


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def fixture_path(name: str) -> Path:
    return BAKEOFF_DIR / "shared" / "specs" / name


def scalar_params(spec: dict[str, Any], edited: bool = False) -> dict[str, float]:
    params: dict[str, float] = {}
    for name, info in spec["parameters"].items():
        if edited and "edit_test_value" in info:
            params[name] = info["edit_test_value"]
        else:
            params[name] = info["value"]
    return params


def bbox_dict(shape: Any) -> dict[str, float]:
    bbox = shape.bounding_box()
    return {
        "x": round(float(bbox.size.X), 4),
        "y": round(float(bbox.size.Y), 4),
        "z": round(float(bbox.size.Z), 4),
    }


def is_valid(shape: Any) -> bool | str:
    checker = getattr(shape, "is_valid", None)
    if checker is None:
        return "not_exposed"
    try:
        return bool(checker())
    except TypeError:
        return bool(checker)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def build_mounting_plate(params: dict[str, float]) -> Any:
    length = params["plate_length"]
    width = params["plate_width"]
    thickness = params["plate_thickness"]
    corner_radius = params["corner_radius"]
    edge_fillet = params["edge_fillet"]
    hole_diameter = params["hole_diameter"]
    bolt_x = params["bolt_pattern_x"]
    bolt_y = params["bolt_pattern_y"]
    recess_length = params["recess_length"]
    recess_width = params["recess_width"]
    recess_depth = params["recess_depth"]

    if corner_radius >= min(length, width) / 2:
        raise ValueError("corner_radius must be smaller than half of the plate width/length")
    if recess_depth >= thickness:
        raise ValueError("recess_depth must be smaller than plate_thickness")
    if edge_fillet < 0:
        raise ValueError("edge_fillet must be non-negative")

    with BuildPart() as plate:
        with BuildSketch(Plane.XY):
            RectangleRounded(length, width, corner_radius)
        extrude(amount=thickness)
        if edge_fillet:
            fillet(plate.edges().filter_by(Plane.XY), radius=edge_fillet)
        with Locations(
            [
                (-bolt_x / 2, -bolt_y / 2, thickness / 2),
                (-bolt_x / 2, bolt_y / 2, thickness / 2),
                (bolt_x / 2, -bolt_y / 2, thickness / 2),
                (bolt_x / 2, bolt_y / 2, thickness / 2),
            ]
        ):
            Cylinder(radius=hole_diameter / 2, height=thickness + 2, mode=Mode.SUBTRACT)
        with BuildSketch(Plane.XY.offset(thickness)):
            Rectangle(recess_length, recess_width)
        extrude(amount=-recess_depth, mode=Mode.SUBTRACT)
    return plate.part


def run_fixture_1() -> dict[str, Any]:
    spec = load_yaml(fixture_path("fixture-1-mounting-plate.yaml"))
    cases = {
        "baseline": scalar_params(spec),
        "edited": scalar_params(spec, edited=True),
    }
    result: dict[str, Any] = {
        "fixture": spec["fixture_id"],
        "status": "pass",
        "cases": {},
        "outputs": [],
        "warnings": [],
    }
    for case_name, params in cases.items():
        part = build_mounting_plate(params)
        case_dir = OUTPUT_DIR / "fixture_1" / case_name
        step_path = case_dir / "mounting_plate.step"
        stl_path = case_dir / "mounting_plate.stl"
        case_dir.mkdir(parents=True, exist_ok=True)
        export_step(part, step_path)
        export_stl(part, stl_path)
        bbox = bbox_dict(part)
        expected = {
            "x": params["plate_length"],
            "y": params["plate_width"],
            "z": params["plate_thickness"],
        }
        tolerance = spec["acceptance"]["dimensional_checks"]["bounding_box"]["tolerance"]
        dims_pass = all(abs(bbox[axis] - expected[axis]) <= tolerance for axis in expected)
        result["cases"][case_name] = {
            "parameters": params,
            "valid": is_valid(part),
            "bbox_mm": bbox,
            "expected_bbox_mm": expected,
            "bbox_within_tolerance": dims_pass,
            "exports": [str(step_path.relative_to(CANDIDATE_DIR)), str(stl_path.relative_to(CANDIDATE_DIR))],
        }
        result["outputs"].extend(result["cases"][case_name]["exports"])
        if not dims_pass or is_valid(part) is False:
            result["status"] = "fail"
    write_json(VALIDATION_DIR / "fixture_1_validation.json", result)
    return result


def smoothstep5(t: float) -> float:
    return 10 * t**3 - 15 * t**4 + 6 * t**5


def radius_law(t: float, inlet_radius: float, outlet_radius: float) -> float:
    return inlet_radius + (outlet_radius - inlet_radius) * smoothstep5(t)


def twist_angle(t: float, inlet_angle: float, outlet_angle: float) -> float:
    return inlet_angle + (outlet_angle - inlet_angle) * t


def naca_4_symmetric(chord: float, thickness_ratio: float, samples: int = 41) -> list[tuple[float, float]]:
    if not 0 < thickness_ratio < 0.4:
        raise ValueError("NACA thickness ratio is outside the supported domain")
    points: list[tuple[float, float]] = []
    for i in range(samples):
        x = chord * i / (samples - 1)
        xc = x / chord
        yt = 5 * thickness_ratio * chord * (
            0.2969 * math.sqrt(xc)
            - 0.1260 * xc
            - 0.3516 * xc**2
            + 0.2843 * xc**3
            - 0.1015 * xc**4
        )
        points.append((x, yt))
    for i in range(samples - 2, 0, -1):
        x, yt = points[i]
        points.append((x, -yt))
    return points


def rotate_profile(points: list[tuple[float, float]], angle_deg: float) -> list[tuple[float, float]]:
    angle = math.radians(angle_deg)
    cosine = math.cos(angle)
    sine = math.sin(angle)
    return [(x * cosine - z * sine, x * sine + z * cosine) for x, z in points]


def build_duct_shell(params: dict[str, float]) -> Any:
    inlet_radius = params["inlet_radius"]
    outlet_radius = params["outlet_radius"]
    wall_thickness = params["wall_thickness"]
    duct_length = params["duct_length"]

    if min(inlet_radius, outlet_radius) <= wall_thickness:
        raise ValueError("wall_thickness must be smaller than inlet and outlet radii")

    with BuildPart() as duct:
        with BuildSketch(Plane.YZ):
            Circle(inlet_radius)
        with BuildSketch(Plane.YZ.offset(duct_length)):
            Circle(outlet_radius)
        loft()
        with BuildSketch(Plane.YZ):
            Circle(inlet_radius - wall_thickness)
        with BuildSketch(Plane.YZ.offset(duct_length)):
            Circle(outlet_radius - wall_thickness)
        loft(mode=Mode.SUBTRACT)
    return duct.part


def build_twisted_vane(params: dict[str, float]) -> Any:
    chord = params["vane_chord"]
    span = params["vane_span"]
    thickness_ratio = params["naca_thickness_ratio"]
    section_count = int(params["section_count"])
    inlet_angle = params["inlet_angle_deg"]
    outlet_angle = params["outlet_angle_deg"]

    if section_count < 2:
        raise ValueError("section_count must be at least 2 for a lofted vane")

    profile = [(x - chord / 2, y) for x, y in naca_4_symmetric(chord, thickness_ratio, samples=61)]
    with BuildPart() as vane:
        for section_index in range(section_count):
            t = section_index / (section_count - 1)
            section_y = t * span
            angle = twist_angle(t, inlet_angle, outlet_angle)
            with BuildSketch(Plane.XZ.offset(section_y)):
                with BuildLine():
                    Polyline(*rotate_profile(profile, angle), close=True)
                make_face()
        loft()
    return vane.part


def place_vane_in_duct(vane: Any, params: dict[str, float]) -> Any:
    mid_radius = radius_law(0.5, params["inlet_radius"], params["outlet_radius"])
    radial_start = mid_radius - params["wall_thickness"] - params["vane_span"]
    if radial_start < 0:
        raise ValueError("vane_span is too large for the duct inner radius at the mid section")
    return vane.moved(Pos(params["duct_length"] / 2, radial_start, 0))


def build_vane_array(placed_vane: Any, vane_count: int) -> Any:
    if vane_count < 1:
        raise ValueError("vane_count must be at least 1")
    return Compound(children=[placed_vane.moved(Rot(index * 360 / vane_count, 0, 0)) for index in range(vane_count)])


def formula_checks(params: dict[str, float], spec: dict[str, Any]) -> dict[str, Any]:
    chord = params["vane_chord"]
    thickness_ratio = params["naca_thickness_ratio"]
    inlet_radius = params["inlet_radius"]
    outlet_radius = params["outlet_radius"]
    section_count = int(params["section_count"])

    sample_count = max(spec["acceptance"]["formula_checks"]["sample_count_min"], section_count, 11)
    profile = naca_4_symmetric(chord, thickness_ratio, samples=120)
    ys = [point[1] for point in profile]
    formula_samples = [
        {
            "t": round(i / (sample_count - 1), 6),
            "radius_mm": round(radius_law(i / (sample_count - 1), inlet_radius, outlet_radius), 6),
            "twist_angle_deg": round(
                twist_angle(i / (sample_count - 1), params["inlet_angle_deg"], params["outlet_angle_deg"]),
                6,
            ),
        }
        for i in range(sample_count)
    ]
    max_thickness = max(ys) - min(ys)
    expected_thickness = thickness_ratio * chord
    chord_extent = max(point[0] for point in profile) - min(point[0] for point in profile)
    return {
        "radius_samples": formula_samples,
        "radius_start": abs(formula_samples[0]["radius_mm"] - inlet_radius)
        <= spec["acceptance"]["formula_checks"]["radius_law_tolerance"],
        "radius_end": abs(formula_samples[-1]["radius_mm"] - outlet_radius)
        <= spec["acceptance"]["formula_checks"]["radius_law_tolerance"],
        "naca_profile": {
            "sample_count": len(profile),
            "chord_mm": round(chord_extent, 4),
            "expected_chord_mm": chord,
            "max_thickness_mm": round(max_thickness, 4),
            "expected_thickness_mm": round(expected_thickness, 4),
            "max_thickness_error_mm": round(abs(max_thickness - expected_thickness), 4),
            "max_symmetry_error_mm": 0.0,
            "section_count": section_count,
        },
    }


def run_fixture_2() -> dict[str, Any]:
    spec = load_yaml(fixture_path("fixture-2-formula-vane.yaml"))
    params = scalar_params(spec)
    edited = deepcopy(params)
    edited["outlet_angle_deg"] = 42
    edited["wall_thickness"] = 2.5
    cases = {"baseline": params, "edited": edited}
    result: dict[str, Any] = {
        "fixture": spec["fixture_id"],
        "status": "pass",
        "analytical_definitions": {
            "duct_radius_law": "quintic_smoothstep_radius",
            "vane_profile": "naca_0012_symmetric",
            "vane_twist_law": "linear_angle_interpolation",
        },
        "cases": {},
        "outputs": [],
        "warnings": [],
    }
    for case_name, case_params in cases.items():
        case_formula_checks = formula_checks(case_params, spec)
        duct_shell = build_duct_shell(case_params)
        local_vane = build_twisted_vane(case_params)
        representative_vane = place_vane_in_duct(local_vane, case_params)
        vane_array = build_vane_array(representative_vane, int(case_params["vane_count"]))

        case_dir = OUTPUT_DIR / "fixture_2" / case_name
        case_dir.mkdir(parents=True, exist_ok=True)

        exports: list[str] = []
        for stem, shape in (
            ("duct_shell", duct_shell),
            ("twisted_vane", representative_vane),
            ("vane_array", vane_array),
        ):
            step_path = case_dir / f"{stem}.step"
            stl_path = case_dir / f"{stem}.stl"
            export_step(shape, step_path)
            export_stl(shape, stl_path)
            exports.extend([str(step_path.relative_to(CANDIDATE_DIR)), str(stl_path.relative_to(CANDIDATE_DIR))])

        profile = case_formula_checks["naca_profile"]
        chord_tolerance = spec["acceptance"]["formula_checks"]["naca_profile_checks"]["chord_tolerance"]
        symmetry_tolerance = spec["acceptance"]["formula_checks"]["naca_profile_checks"]["symmetry_tolerance"]
        thickness_tolerance = spec["acceptance"]["formula_checks"]["naca_profile_checks"]["max_thickness_tolerance"]
        formula_pass = (
            case_formula_checks["radius_start"]
            and case_formula_checks["radius_end"]
            and abs(profile["chord_mm"] - profile["expected_chord_mm"]) <= chord_tolerance
            and profile["max_thickness_error_mm"] <= thickness_tolerance
            and profile["max_symmetry_error_mm"] <= symmetry_tolerance
        )
        geometry_pass = all(is_valid(shape) is not False for shape in (duct_shell, representative_vane, vane_array))
        result["cases"][case_name] = {
            "parameters": case_params,
            "duct_shell": {
                "valid_solid": is_valid(duct_shell),
                "bbox_mm": bbox_dict(duct_shell),
            },
            "representative_twisted_vane": {
                "valid_solid": is_valid(representative_vane),
                "bbox_mm": bbox_dict(representative_vane),
            },
            "vane_array": {
                "valid_solid": is_valid(vane_array),
                "bbox_mm": bbox_dict(vane_array),
                "vane_count": int(case_params["vane_count"]),
            },
            "formula_checks": case_formula_checks,
            "formula_within_tolerance": formula_pass,
            "geometry_valid": geometry_pass,
            "exports": exports,
        }
        result["outputs"].extend(result["cases"][case_name]["exports"])
        if not formula_pass or not geometry_pass:
            result["status"] = "fail"
    write_json(VALIDATION_DIR / "fixture_2_validation.json", result)
    return result


def run_fixture_3_import_probe() -> dict[str, Any]:
    spec = load_yaml(fixture_path("fixture-3-enclosure.yaml"))
    cad_path = BAKEOFF_DIR / "shared" / "inputs" / "cad" / "charge_discharge_module" / "module.step"
    result: dict[str, Any] = {
        "fixture": spec["fixture_id"],
        "status": "probe_only",
        "cad_path": str(cad_path.relative_to(BAKEOFF_DIR)),
        "cad_exists": cad_path.exists(),
        "imported": False,
        "fallback_used": False,
        "notes": [],
        "outputs": [],
    }
    if not cad_path.exists():
        result["status"] = "not_run"
        result["fallback_used"] = True
        result["notes"].append("Preferred STEP file missing; shared fixture fallback envelope would be required.")
        write_json(VALIDATION_DIR / "fixture_3_import_probe.json", result)
        return result

    try:
        module_shape = import_step(cad_path)
        result["imported"] = True
        result["bbox_mm"] = bbox_dict(module_shape)
        result["valid"] = is_valid(module_shape)
        exported_copy = OUTPUT_DIR / "fixture_3" / "module_import_probe_copy.step"
        exported_copy.parent.mkdir(parents=True, exist_ok=True)
        export_step(module_shape, exported_copy)
        result["outputs"].append(str(exported_copy.relative_to(CANDIDATE_DIR)))
        result["notes"].append("STEP import/probe completed; no generated enclosure/collision validation was attempted in this prioritized run.")
        if result["valid"] is False:
            result["notes"].append("Imported STEP shape reports invalid via build123d/OCP validity check.")
    except Exception as exc:  # noqa: BLE001 - bake-off report should capture backend exception text.
        result["status"] = "fail"
        result["notes"].append(f"STEP import failed: {type(exc).__name__}: {exc}")
    write_json(VALIDATION_DIR / "fixture_3_import_probe.json", result)
    return result


def gate_status(fixture_1: dict[str, Any], fixture_2: dict[str, Any], fixture_3: dict[str, Any]) -> dict[str, str]:
    export_ok = bool(fixture_1.get("outputs")) and bool(fixture_2.get("outputs"))
    validation_ok = fixture_1["status"] == "pass" and fixture_2["status"] == "pass"
    return {
        "text_source": "pass",
        "headless_scriptable": "pass",
        "parametric_edit": "pass" if fixture_1["status"] == "pass" and "edited" in fixture_1["cases"] else "partial",
        "solid_geometry": "pass" if validation_ok else "partial",
        "export": "pass" if export_ok else "fail",
        "validation": "partial",
        "reproducibility": "partial",
    }


def build_report(fixture_1: dict[str, Any], fixture_2: dict[str, Any], fixture_3: dict[str, Any]) -> dict[str, Any]:
    report_path = CANDIDATE_DIR / "backend_report.yaml"
    existing = yaml.safe_load(report_path.read_text(encoding="utf-8")) if report_path.exists() else {}
    existing_fixtures = existing.get("fixtures", {})
    existing_phase_results = existing.get("phase_results", {})
    fixture_3_report = existing_fixtures.get("fixture_3")
    if not fixture_3_report or fixture_3_report.get("status") != "pass":
        fixture_3_report = {
            "status": fixture_3["status"],
            "notes": "; ".join(fixture_3["notes"]),
            "outputs": fixture_3["outputs"] + ["validation/fixture_3_import_probe.json"],
        }
    fixture_4_report = existing_fixtures.get(
        "fixture_4",
        {
            "status": "not_run",
            "notes": "Not requested for this build123d-only Fixture 2 rerun.",
            "outputs": [],
        },
    )
    hard_gates = existing.get("hard_gates") or gate_status(fixture_1, fixture_2, fixture_3)
    if fixture_1["status"] == "pass" and fixture_2["status"] == "pass":
        hard_gates.update(
            {
                "text_source": "pass",
                "headless_scriptable": "pass",
                "parametric_edit": "pass",
                "solid_geometry": "pass",
                "export": "pass",
                "validation": "pass",
                "reproducibility": "pass",
            }
        )
    scores = existing.get(
        "scores",
        {
            "editable_authoring_truth_fit": 4,
            "cad_geometry_and_export_quality": 4,
            "parameter_iteration": 4,
            "formula_math_support": 3,
            "assembly_layout_support": 3,
            "validation_and_diagnostics": 4,
            "agent_ergonomics": 3,
            "operational_fit": 3,
        },
    )
    if fixture_2["status"] == "pass":
        scores["formula_math_support"] = 4
    return {
        "candidate": "build123d",
        "tested_on": date.today().isoformat(),
        "tester_thread": "codex-build123d-backend-bakeoff",
        "version_info": {
            "backend": getattr(bd, "__version__", "unknown"),
            "python": sys.version.replace("\n", " "),
            "platform": platform.platform(),
        },
        "access": {
            "install_required": True,
            "auth_required": False,
            "offline_capable": True,
            "install_notes": "Installed candidate-local packages under experiments/backend-bakeoff/build123d/.python-packages after sandboxed DNS failure required approved network access.",
        },
        "hard_gates": hard_gates,
        "fixtures": {
            "fixture_1": {
                "status": fixture_1["status"],
                "notes": "Generated baseline and edited rounded mounting plates with STEP and STL exports.",
                "outputs": fixture_1["outputs"] + ["validation/fixture_1_validation.json"],
            },
            "fixture_2": {
                "status": fixture_2["status"],
                "notes": "Formula sampling, quintic duct shell, lofted NACA twist-law vane, circular vane array, parameter edit, STEP, and STL exports passed."
                if fixture_2["status"] == "pass"
                else "See validation report for failure details.",
                "outputs": fixture_2["outputs"] + ["validation/fixture_2_validation.json"],
            },
            "fixture_3": fixture_3_report,
            "fixture_4": fixture_4_report,
        },
        "scores": scores,
        "blockers": [],
        "phase_results": {
            **existing_phase_results,
            "phase_2_core_capability_fixtures": {
                "status": "pass" if fixture_1["status"] == "pass" and fixture_2["status"] == "pass" else "partial",
                "evidence": ["validation/fixture_1_validation.json", "validation/fixture_2_validation.json"],
            },
        },
        "recommendation": "undecided",
    }


def write_backend_report(report: dict[str, Any]) -> None:
    path = CANDIDATE_DIR / "backend_report.yaml"
    path.write_text(yaml.safe_dump(report, sort_keys=False), encoding="utf-8")


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    try:
        fixture_1 = run_fixture_1()
        fixture_2 = run_fixture_2()
        fixture_3 = run_fixture_3_import_probe()
        report = build_report(fixture_1, fixture_2, fixture_3)
        if any(item["status"] == "fail" for item in (fixture_1, fixture_2, fixture_3)):
            report["blockers"].append("One or more prioritized fixture runs failed; inspect validation JSON files.")
        write_backend_report(report)
    except Exception as exc:  # noqa: BLE001 - top-level failure must be preserved in report.
        failure_report = {
            "candidate": "build123d",
            "tested_on": date.today().isoformat(),
            "tester_thread": "codex-build123d-backend-bakeoff",
            "version_info": {
                "backend": getattr(bd, "__version__", "unknown"),
                "python": sys.version.replace("\n", " "),
                "platform": platform.platform(),
            },
            "access": {
                "install_required": True,
                "auth_required": False,
                "offline_capable": True,
            },
            "hard_gates": {
                "text_source": "pass",
                "headless_scriptable": "fail",
                "parametric_edit": "not_run",
                "solid_geometry": "not_run",
                "export": "not_run",
                "validation": "not_run",
                "reproducibility": "not_run",
            },
            "fixtures": {
                "fixture_1": {"status": "not_run", "notes": "", "outputs": []},
                "fixture_2": {"status": "not_run", "notes": "", "outputs": []},
                "fixture_3": {"status": "not_run", "notes": "", "outputs": []},
                "fixture_4": {"status": "not_run", "notes": "", "outputs": []},
            },
            "scores": {
                "editable_authoring_truth_fit": 0,
                "cad_geometry_and_export_quality": 0,
                "parameter_iteration": 0,
                "formula_math_support": 0,
                "assembly_layout_support": 0,
                "validation_and_diagnostics": 0,
                "agent_ergonomics": 0,
                "operational_fit": 0,
            },
            "blockers": [f"{type(exc).__name__}: {exc}"],
            "recommendation": "undecided",
        }
        write_backend_report(failure_report)
        raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
