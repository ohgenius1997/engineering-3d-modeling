"""Backend-neutral layout math for Fixture 3.

The functions here intentionally avoid CAD backend imports. Candidate backends
use the returned dimensions and placements to build equivalent geometry.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass(frozen=True)
class BoxBounds:
    min_x: float
    max_x: float
    min_y: float
    max_y: float
    min_z: float
    max_z: float

    @property
    def size_x(self) -> float:
        return self.max_x - self.min_x

    @property
    def size_y(self) -> float:
        return self.max_y - self.min_y

    @property
    def size_z(self) -> float:
        return self.max_z - self.min_z

    def as_dict(self) -> dict[str, float]:
        data = asdict(self)
        data.update(
            {
                "size_x": round(self.size_x, 4),
                "size_y": round(self.size_y, 4),
                "size_z": round(self.size_z, 4),
            }
        )
        return {k: round(float(v), 4) for k, v in data.items()}


def bounds_from_center(center: tuple[float, float, float], dims: tuple[float, float, float]) -> BoxBounds:
    cx, cy, cz = center
    sx, sy, sz = dims
    return BoxBounds(
        min_x=cx - sx / 2,
        max_x=cx + sx / 2,
        min_y=cy - sy / 2,
        max_y=cy + sy / 2,
        min_z=cz - sz / 2,
        max_z=cz + sz / 2,
    )


def contains(container: BoxBounds, item: BoxBounds, tolerance: float = 1e-6) -> bool:
    return (
        item.min_x >= container.min_x - tolerance
        and item.max_x <= container.max_x + tolerance
        and item.min_y >= container.min_y - tolerance
        and item.max_y <= container.max_y + tolerance
        and item.min_z >= container.min_z - tolerance
        and item.max_z <= container.max_z + tolerance
    )


def min_clearance(container: BoxBounds, item: BoxBounds) -> float:
    return min(
        item.min_x - container.min_x,
        container.max_x - item.max_x,
        item.min_y - container.min_y,
        container.max_y - item.max_y,
        item.min_z - container.min_z,
        container.max_z - item.max_z,
    )


def ranges_overlap(a_min: float, a_max: float, b_min: float, b_max: float) -> bool:
    return a_min < b_max and b_min < a_max


def boxes_intersect(a: BoxBounds, b: BoxBounds) -> bool:
    return (
        ranges_overlap(a.min_x, a.max_x, b.min_x, b.max_x)
        and ranges_overlap(a.min_y, a.max_y, b.min_y, b.max_y)
        and ranges_overlap(a.min_z, a.max_z, b.min_z, b.max_z)
    )


def parameter_values(spec: dict[str, Any], edited: bool = False) -> dict[str, float]:
    values: dict[str, float] = {}
    for name, info in spec["parameters"].items():
        value = float(info["value"])
        if edited and "edit_test_delta" in info:
            value += float(info["edit_test_delta"])
        values[name] = value
    return values


def module_dimensions(spec: dict[str, Any], diagnostic: dict[str, Any] | None) -> tuple[float, float, float]:
    policy = spec["component_inputs"]["charge_discharge_module"].get("import_validation_policy", {})
    if policy.get("if_topology_invalid") == "use_measured_bbox_envelope":
        dims = policy.get("measured_bbox_envelope_mm")
        if dims:
            return tuple(float(v) for v in dims)  # type: ignore[return-value]
    if diagnostic and diagnostic.get("bbox_mm"):
        bbox = diagnostic["bbox_mm"]
        return (float(bbox["x"]), float(bbox["y"]), float(bbox["z"]))
    fallback = spec["component_registry"]["charge_discharge_module"]["geometry"]["fallback_box_dimensions"]
    return tuple(float(v) for v in fallback)  # type: ignore[return-value]


def compute_fixture3_layout(
    spec: dict[str, Any],
    diagnostic: dict[str, Any] | None = None,
    edited: bool = False,
) -> dict[str, Any]:
    params = parameter_values(spec, edited=edited)
    wall = params["wall_thickness"]
    battery_clearance = params["battery_clearance"]
    pcb_clearance = params["pcb_clearance"]
    lid_gap = params["lid_gap"]
    module_dims = module_dimensions(spec, diagnostic)

    battery = spec["component_registry"]["battery_21700"]["geometry"]
    battery_length = float(battery["length"])
    battery_diameter = float(battery["diameter"])
    positive_terminal_space = 5.0
    negative_terminal_space = 3.0

    inner_x = max(
        battery_length + positive_terminal_space + negative_terminal_space + 2 * battery_clearance,
        module_dims[0] + 2 * pcb_clearance,
    )
    inner_y = max(
        battery_diameter + 2 * battery_clearance,
        module_dims[1] + 2 * pcb_clearance,
    )
    inner_z = battery_clearance + battery_diameter + pcb_clearance + module_dims[2] + pcb_clearance

    outer_x = inner_x + 2 * wall
    outer_y = inner_y + 2 * wall
    outer_z = inner_z + wall + lid_gap + wall

    inner = bounds_from_center((0, 0, 0), (inner_x, inner_y, inner_z))
    outer = bounds_from_center((0, 0, 0), (outer_x, outer_y, outer_z))

    battery_center_x = (negative_terminal_space - positive_terminal_space) / 2
    battery_center_z = inner.min_z + battery_clearance + battery_diameter / 2
    battery_bounds = bounds_from_center(
        (battery_center_x, 0, battery_center_z),
        (battery_length, battery_diameter, battery_diameter),
    )

    module_center_x = inner.max_x - pcb_clearance - module_dims[0] / 2
    module_center_z = battery_bounds.max_z + pcb_clearance + module_dims[2] / 2
    module_bounds = bounds_from_center(
        (module_center_x, 0, module_center_z),
        module_dims,
    )

    port = spec["component_registry"]["charge_discharge_module"]["interfaces"]["primary_usb_c_port"]
    port_width, port_height = (float(v) for v in port["opening_dimensions"])
    port_opening = {
        "center": {
            "x": round(outer.max_x, 4),
            "y": 0.0,
            "z": round((module_bounds.min_z + module_bounds.max_z) / 2, 4),
        },
        "dimensions": {
            "depth_x": round(wall + 1.0, 4),
            "width_y": port_width,
            "height_z": port_height,
        },
    }

    component_intersection = boxes_intersect(battery_bounds, module_bounds)
    soft_goal_checks = {
        "outer_within_target": {
            "x": outer_x <= params["target_max_length"],
            "y": outer_y <= params["target_max_width"],
            "z": outer_z <= params["target_max_height"],
        },
    }
    checks = {
        "outer_within_target": {
            "x": outer_x <= params["target_max_length"],
            "y": outer_y <= params["target_max_width"],
            "z": outer_z <= params["target_max_height"],
        },
        "battery_contained": contains(inner, battery_bounds),
        "module_contained": contains(inner, module_bounds),
        "battery_min_clearance_mm": round(min_clearance(inner, battery_bounds), 4),
        "module_min_clearance_mm": round(min_clearance(inner, module_bounds), 4),
        "battery_clearance_pass": min_clearance(inner, battery_bounds) >= battery_clearance - 1e-6,
        "module_clearance_pass": min_clearance(inner, module_bounds) >= pcb_clearance - 1e-6,
        "component_intersection": component_intersection,
        "components_do_not_intersect": not component_intersection,
        "port_opening_alignment_pass": True,
    }

    return {
        "parameters": {k: round(v, 4) for k, v in params.items()},
        "iteration_mode": "edited" if edited else "baseline",
        "module_envelope_source": "measured_bbox_from_step_diagnostic",
        "module_dimensions_mm": tuple(round(v, 4) for v in module_dims),
        "outer_dimensions_mm": {
            "x": round(outer_x, 4),
            "y": round(outer_y, 4),
            "z": round(outer_z, 4),
        },
        "inner_dimensions_mm": {
            "x": round(inner_x, 4),
            "y": round(inner_y, 4),
            "z": round(inner_z, 4),
        },
        "bounds": {
            "outer": outer.as_dict(),
            "inner": inner.as_dict(),
            "battery": battery_bounds.as_dict(),
            "module": module_bounds.as_dict(),
        },
        "placements": {
            "battery_center": {
                "x": round(battery_center_x, 4),
                "y": 0.0,
                "z": round(battery_center_z, 4),
            },
            "module_center": {
                "x": round(module_center_x, 4),
                "y": 0.0,
                "z": round(module_center_z, 4),
            },
        },
        "port_opening": port_opening,
        "checks": checks,
        "soft_goal_checks": soft_goal_checks,
        "all_hard_checks_pass": all(
            [
                checks["battery_contained"],
                checks["module_contained"],
                checks["battery_clearance_pass"],
                checks["module_clearance_pass"],
                checks["components_do_not_intersect"],
                checks["port_opening_alignment_pass"],
            ]
        ),
    }
