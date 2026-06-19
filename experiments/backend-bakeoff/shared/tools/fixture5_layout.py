"""Backend-neutral layout math for Fixture 5.

The helper returns a deterministic handheld-fan assembly layout without importing
any CAD backend. Candidate scripts use these placements to generate equivalent
named parts and validation artifacts.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from itertools import combinations
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
        data.update({"size_x": self.size_x, "size_y": self.size_y, "size_z": self.size_z})
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


def ranges_overlap(a_min: float, a_max: float, b_min: float, b_max: float) -> bool:
    return a_min < b_max and b_min < a_max


def boxes_intersect(a: BoxBounds, b: BoxBounds) -> bool:
    return (
        ranges_overlap(a.min_x, a.max_x, b.min_x, b.max_x)
        and ranges_overlap(a.min_y, a.max_y, b.min_y, b.max_y)
        and ranges_overlap(a.min_z, a.max_z, b.min_z, b.max_z)
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


def axis_gap(a: BoxBounds, b: BoxBounds) -> float:
    gaps = [
        max(b.min_x - a.max_x, a.min_x - b.max_x, 0),
        max(b.min_y - a.max_y, a.min_y - b.max_y, 0),
        max(b.min_z - a.max_z, a.min_z - b.max_z, 0),
    ]
    return max(gaps)


def parameter_values(spec: dict[str, Any], edited: bool = False) -> dict[str, float]:
    values: dict[str, float] = {}
    for name, info in spec["parameters"].items():
        value = float(info["value"])
        if edited and "edit_test_delta" in info:
            value += float(info["edit_test_delta"])
        values[name] = value
    return values


def component_dims(spec: dict[str, Any], name: str, params: dict[str, float]) -> tuple[float, float, float]:
    geometry = spec["component_registry"][name]["geometry"]
    if "dimensions" in geometry:
        return tuple(float(v) for v in geometry["dimensions"])  # type: ignore[return-value]
    if geometry["type"] == "cylinder_envelope":
        diameter = params.get(str(geometry["diameter"]), geometry["diameter"])
        thickness = params.get(str(geometry.get("thickness", diameter)), geometry.get("thickness", diameter))
        axis = geometry["axis"]
        if axis == "x":
            return (float(thickness), float(diameter), float(diameter))
        if axis == "y":
            return (float(diameter), float(geometry["length"]), float(diameter))
        if axis == "z":
            return (float(diameter), float(diameter), float(thickness))
    raise ValueError(f"Unsupported Fixture 5 component geometry for {name}")


def add_component(
    components: dict[str, dict[str, Any]],
    spec: dict[str, Any],
    params: dict[str, float],
    name: str,
    center: tuple[float, float, float],
) -> BoxBounds:
    dims = component_dims(spec, name, params)
    bounds = bounds_from_center(center, dims)
    components[name] = {
        "center": {"x": round(center[0], 4), "y": round(center[1], 4), "z": round(center[2], 4)},
        "dimensions_mm": tuple(round(v, 4) for v in dims),
        "bounds": bounds.as_dict(),
        "required_clearance": spec["component_registry"][name].get("required_clearance"),
    }
    return bounds


def generated_bound(
    generated: dict[str, dict[str, Any]],
    name: str,
    center: tuple[float, float, float],
    dims: tuple[float, float, float],
) -> BoxBounds:
    bounds = bounds_from_center(center, dims)
    generated[name] = {
        "center": {"x": round(center[0], 4), "y": round(center[1], 4), "z": round(center[2], 4)},
        "dimensions_mm": tuple(round(v, 4) for v in dims),
        "bounds": bounds.as_dict(),
    }
    return bounds


def point3(values: list[float]) -> tuple[float, float, float]:
    return (float(values[0]), float(values[1]), float(values[2]))


def point2(values: list[float]) -> tuple[float, float]:
    return (float(values[0]), float(values[1]))


def compute_fixture5_layout(
    spec: dict[str, Any],
    edited: bool = False,
    switch_side: str | None = None,
) -> dict[str, Any]:
    params = parameter_values(spec, edited=edited)
    if switch_side == "left":
        params["switch_side_sign"] = -1.0
    elif switch_side == "right":
        params["switch_side_sign"] = 1.0
    wall = params["wall_thickness"]
    fan_clearance = params["fan_clearance"]
    battery_clearance = params["battery_clearance"]
    electronics_clearance = params["electronics_clearance"]
    switch_clearance = params["switch_clearance"]
    head_radius = params["head_outer_radius"]
    handle_width = params["handle_width"]
    handle_length = params["handle_length"]
    switch_offset_y = params["switch_offset_y"]
    switch_side_sign = params["switch_side_sign"]
    layout_defaults = spec["layout_defaults"]

    fan_center = point3(layout_defaults["fan_center"])
    handle_center = point3(layout_defaults["handle_center"])
    handle_outer_depth = max(58.0, 18.6 + 8.0 + 2 * electronics_clearance + 2 * wall + 12.0)
    head_outer_depth = 30.0 + 2 * fan_clearance + 2 * wall
    outer_depth = max(head_outer_depth, handle_outer_depth)
    outer_width = max(2 * head_radius, handle_width, 60.0)
    outer_y_min = handle_center[1] - handle_length / 2 - 8.0
    outer_y_max = fan_center[1] + head_radius
    outer = BoxBounds(
        min_x=-outer_width / 2,
        max_x=outer_width / 2,
        min_y=outer_y_min,
        max_y=outer_y_max,
        min_z=-outer_depth / 2,
        max_z=outer_depth / 2,
    )
    inner = BoxBounds(
        min_x=outer.min_x + wall,
        max_x=outer.max_x - wall,
        min_y=outer.min_y + wall,
        max_y=outer.max_y - wall,
        min_z=outer.min_z + wall,
        max_z=outer.max_z - wall,
    )

    components: dict[str, dict[str, Any]] = {}
    component_bounds: dict[str, BoxBounds] = {}
    component_bounds["fan_4028"] = add_component(components, spec, params, "fan_4028", fan_center)

    battery_defaults = layout_defaults["battery_pair"]
    battery_x = float(battery_defaults["half_spacing_x"])
    battery_center_y = float(battery_defaults["center_y"])
    battery_center_z = float(battery_defaults["center_z"])
    component_bounds["battery_left_18650"] = add_component(
        components, spec, params, "battery_left_18650", (-battery_x, battery_center_y, battery_center_z)
    )
    component_bounds["battery_right_18650"] = add_component(
        components, spec, params, "battery_right_18650", (battery_x, battery_center_y, battery_center_z)
    )
    electronics = layout_defaults["electronics"]
    component_bounds["pwm_controller_board"] = add_component(
        components, spec, params, "pwm_controller_board", point3(electronics["pwm_controller_board_center"])
    )
    component_bounds["battery_protection_board"] = add_component(
        components, spec, params, "battery_protection_board", point3(electronics["battery_protection_board_center"])
    )
    component_bounds["charge_module"] = add_component(
        components, spec, params, "charge_module", point3(electronics["charge_module_center"])
    )
    component_bounds["boost_output_module"] = add_component(
        components, spec, params, "boost_output_module", point3(electronics["boost_output_module_center"])
    )

    switch_y = components["pwm_controller_board"]["center"]["y"] + switch_offset_y
    switch_x = switch_side_sign * (outer.max_x + params["switch_wheel_diameter"] / 4)
    component_bounds["switch_thumbwheel"] = add_component(
        components, spec, params, "switch_thumbwheel", (switch_x, switch_y, 6.0)
    )
    component_bounds["switch_drive_gear"] = add_component(
        components,
        spec,
        params,
        "switch_drive_gear",
        (switch_side_sign * (inner.max_x - switch_clearance - 2.0), switch_y, 6.0),
    )

    generated: dict[str, dict[str, Any]] = {}
    front_z = outer.max_z - wall / 2
    rear_z = outer.min_z + wall / 2
    generated_bounds: dict[str, BoxBounds] = {}
    generated_bounds["front_shell_slab"] = generated_bound(
        generated, "front_shell_slab", (0.0, -8.0, front_z), (outer_width, outer.size_y, wall)
    )
    generated_bounds["rear_shell_slab"] = generated_bound(
        generated, "rear_shell_slab", (0.0, -8.0, rear_z), (outer_width, outer.size_y, wall)
    )
    generated_bounds["battery_left_rail"] = generated_bound(
        generated, "battery_left_rail", (-battery_x, battery_center_y, battery_center_z - 10.2), (22.0, 66.0, 1.6)
    )
    generated_bounds["battery_right_rail"] = generated_bound(
        generated, "battery_right_rail", (battery_x, battery_center_y, battery_center_z - 10.2), (22.0, 66.0, 1.6)
    )
    generated_bounds["pcb_shelf"] = generated_bound(generated, "pcb_shelf", (-4.0, -36.0, 2.1), (38.0, 72.0, 1.4))
    screw_boss_defaults = layout_defaults["screw_bosses"]
    for index, (x, y) in enumerate(point2(item) for item in screw_boss_defaults["head_centers_xy"]):
        generated_bounds[f"head_screw_boss_{index + 1}"] = generated_bound(
            generated, f"head_screw_boss_{index + 1}", (x, y, 0.0), (params["screw_boss_outer_diameter"], params["screw_boss_outer_diameter"], 8.0)
        )
    for index, (x, y) in enumerate(point2(item) for item in screw_boss_defaults["handle_centers_xy"]):
        generated_bounds[f"handle_screw_boss_{index + 1}"] = generated_bound(
            generated,
            f"handle_screw_boss_{index + 1}",
            (x, y, 0.0),
            (params["screw_boss_outer_diameter"], params["screw_boss_outer_diameter"], 8.0),
        )
    generated_bounds["charge_port_marker"] = generated_bound(
        generated, "charge_port_marker", (0.0, outer.min_y, 7.0), (12.0, wall + 1.0, 7.0)
    )

    fixed_names = [
        "fan_4028",
        "battery_left_18650",
        "battery_right_18650",
        "pwm_controller_board",
        "battery_protection_board",
        "charge_module",
        "boost_output_module",
    ]
    fixed_bounds = {name: component_bounds[name] for name in fixed_names}
    fixed_intersections = [
        (a, b)
        for a, b in combinations(fixed_names, 2)
        if boxes_intersect(component_bounds[a], component_bounds[b])
    ]
    generated_intersections = [
        (g_name, c_name)
        for g_name, g_bounds in generated_bounds.items()
        for c_name, c_bounds in fixed_bounds.items()
        if boxes_intersect(g_bounds, c_bounds)
    ]

    containment_checks = {name: contains(inner, bounds) for name, bounds in fixed_bounds.items()}
    clearance_checks: dict[str, dict[str, Any]] = {}
    for name, bounds in fixed_bounds.items():
        clearance = min_clearance(inner, bounds)
        required_key = spec["component_registry"][name]["required_clearance"]
        required = params[required_key]
        clearance_checks[name] = {
            "required_mm": round(required, 4),
            "actual_min_to_inner_envelope_mm": round(clearance, 4),
            "pass": clearance >= required - 1e-6,
        }

    battery_gap = axis_gap(component_bounds["battery_left_18650"], component_bounds["battery_right_18650"])
    battery_geometry = spec["component_registry"]["battery_left_18650"]["geometry"]
    battery_radius = float(battery_geometry["diameter"]) / 2
    battery_length = float(battery_geometry["length"])
    battery_cylinder_checks: dict[str, dict[str, Any]] = {}
    for name in ("battery_left_18650", "battery_right_18650"):
        center = components[name]["center"]
        radial_and_axis_clearance = min(
            center["x"] - battery_radius - inner.min_x,
            inner.max_x - (center["x"] + battery_radius),
            center["y"] - battery_length / 2 - inner.min_y,
            inner.max_y - (center["y"] + battery_length / 2),
            center["z"] - battery_radius - inner.min_z,
            inner.max_z - (center["z"] + battery_radius),
        )
        battery_cylinder_checks[name] = {
            "axis": battery_geometry["axis"],
            "radius_mm": round(battery_radius, 4),
            "length_mm": round(battery_length, 4),
            "actual_min_to_inner_envelope_mm": round(radial_and_axis_clearance, 4),
            "required_mm": round(battery_clearance, 4),
            "pass": radial_and_axis_clearance >= battery_clearance - 1e-6,
        }
    handle_boss_names = [name for name in generated_bounds if name.startswith("handle_screw_boss")]
    handle_boss_battery_intersections = [
        (boss_name, battery_name)
        for boss_name in handle_boss_names
        for battery_name in ("battery_left_18650", "battery_right_18650")
        if boxes_intersect(generated_bounds[boss_name], component_bounds[battery_name])
    ]
    fan_centered = abs(components["fan_4028"]["center"]["x"]) <= 1e-6 and abs(components["fan_4028"]["center"]["z"]) <= 1e-6
    charge_port_aligned = abs(components["charge_module"]["center"]["x"]) <= 1e-6 and generated["charge_port_marker"]["center"]["y"] <= outer.min_y + 1e-6
    switch_distance_y = abs(components["switch_thumbwheel"]["center"]["y"] - components["pwm_controller_board"]["center"]["y"])
    switch_near_pwm = switch_distance_y <= abs(switch_offset_y) + 1e-6
    switch_side_matches_parameter = (
        components["switch_thumbwheel"]["center"]["x"] > outer.max_x if switch_side_sign > 0 else components["switch_thumbwheel"]["center"]["x"] < outer.min_x
    )

    checks = {
        "containment": containment_checks,
        "clearance": clearance_checks,
        "fixed_components_do_not_intersect": len(fixed_intersections) == 0,
        "fixed_component_intersections": fixed_intersections,
        "generated_features_do_not_intersect_fixed_components": len(generated_intersections) == 0,
        "generated_feature_intersections": generated_intersections,
        "fan_centered_in_head": fan_centered,
        "battery_pair_separated": battery_gap >= battery_clearance,
        "battery_pair_gap_mm": round(battery_gap, 4),
        "battery_cylinder_like_clearance": battery_cylinder_checks,
        "battery_cylinder_like_clearance_pass": all(item["pass"] for item in battery_cylinder_checks.values()),
        "handle_screw_bosses_do_not_intersect_batteries": len(handle_boss_battery_intersections) == 0,
        "handle_screw_boss_battery_intersections": handle_boss_battery_intersections,
        "charge_port_marker_aligned": charge_port_aligned,
        "switch_mechanism_near_pwm": switch_near_pwm,
        "switch_distance_y_mm": round(switch_distance_y, 4),
        "switch_side_matches_parameter": switch_side_matches_parameter,
    }
    all_hard_checks_pass = all(containment_checks.values()) and all(
        item["pass"] for item in clearance_checks.values()
    )
    all_hard_checks_pass = all_hard_checks_pass and checks["fixed_components_do_not_intersect"]
    all_hard_checks_pass = all_hard_checks_pass and checks["generated_features_do_not_intersect_fixed_components"]
    all_hard_checks_pass = all_hard_checks_pass and checks["fan_centered_in_head"]
    all_hard_checks_pass = all_hard_checks_pass and checks["battery_pair_separated"]
    all_hard_checks_pass = all_hard_checks_pass and checks["battery_cylinder_like_clearance_pass"]
    all_hard_checks_pass = all_hard_checks_pass and checks["handle_screw_bosses_do_not_intersect_batteries"]
    all_hard_checks_pass = all_hard_checks_pass and checks["charge_port_marker_aligned"]
    all_hard_checks_pass = all_hard_checks_pass and checks["switch_mechanism_near_pwm"]
    all_hard_checks_pass = all_hard_checks_pass and checks["switch_side_matches_parameter"]

    return {
        "parameters": {k: round(v, 4) for k, v in params.items()},
        "iteration_mode": "left_hand" if switch_side == "left" else ("edited" if edited else "baseline"),
        "outer_dimensions_mm": {
            "x": round(outer.size_x, 4),
            "y": round(outer.size_y, 4),
            "z": round(outer.size_z, 4),
        },
        "inner_envelope": inner.as_dict(),
        "outer_envelope": outer.as_dict(),
        "placements": {
            "fan_center": {"x": fan_center[0], "y": fan_center[1], "z": fan_center[2]},
            "handle_center": {"x": handle_center[0], "y": handle_center[1], "z": handle_center[2]},
            "switch_center": components["switch_thumbwheel"]["center"],
            "switch_side": "right" if switch_side_sign > 0 else "left",
        },
        "components": components,
        "generated_feature_bounds": generated,
        "checks": checks,
        "all_hard_checks_pass": all_hard_checks_pass,
    }
