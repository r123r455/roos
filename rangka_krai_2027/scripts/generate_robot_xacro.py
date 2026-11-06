#!/usr/bin/env python3
"""Split CAD visuals into chassis, full left claw carriage, and mecanum modules."""

import math
import re
import struct
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_URDF = ROOT / "urdf/rangka_krai_2027.urdf"
OUTPUT_XACRO = ROOT / "urdf/rangka_krai_2027.urdf.xacro"
WHEEL_GROUPS = {
    "Mecanum__3__MIR2_1__": "front_left",
    "Mecanum__3__MIR1_MIR_1__": "front_right",
    "Mecanum__3__1__": "rear_left",
    "Mecanum__3__MIR1_1__": "rear_right",
}
ROLLER_SOLIDS = {7, 24, 25, 26, 27, 28, 29, 30}
WHEEL_RADIUS = 0.075
LEFT_CLAW_MASS = 0.25
LEFT_CLAW_RAIL_ORIGIN = (-0.437238, 0.840582, 0.471923)
LEFT_CLAW_RAIL_MESH = "MGN12H_430MM_Assembly_1__Solid1.stl"
LEFT_CLAW_JAW_MESH = "_9459859_MIR_MIR_1__Solid1.stl"
RIGHT_CLAW_JAW_MESH = "_9459859_MIR_MIR_MIR1_1__Solid1.stl"
RIGHT_CLAW_JAW_ORIGIN = (-0.0319864, 0.84866, 0.455204)
LEFT_CLAW_CARRIAGE_ORIGIN = LEFT_CLAW_RAIL_ORIGIN
LEFT_CLAW_CARRIAGE_MIN_SOLID = 2
LEFT_CLAW_SLIDE_MARGIN = 0.01
CLAW_COLLISION_PADDING = 0.002
LEFT_CLAW_ATTACHED_PARTS = {
    "_9459859_MIR_MIR_1__Solid1.stl": (-0.143769, 0.861019, 0.457591),
    "Part2_1__Solid1.stl": (-0.143618, 1.05384, 0.438962),
    "Part4_1__Solid1.stl": (-0.124129, 0.818549, 0.448958),
    "_5656_MIR6_1__Solid1.stl": (-0.174348, 0.830256, 0.439742),
    "_5656_1__Solid1.stl": (-0.124366, 0.830091, 0.438436),
}


def matrix_from_rpy(rpy):
    roll, pitch, yaw = rpy
    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)
    return (
        (cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr),
        (sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr),
        (-sp, cp * sr, cp * cr),
    )


def rpy_from_matrix(matrix):
    pitch = math.asin(max(-1.0, min(1.0, -matrix[2][0])))
    if abs(math.cos(pitch)) > 1e-8:
        roll = math.atan2(matrix[2][1], matrix[2][2])
        yaw = math.atan2(matrix[1][0], matrix[0][0])
    else:
        roll = 0.0
        yaw = math.atan2(-matrix[0][1], matrix[1][1])
    return roll, pitch, yaw


def transform_point(rotation, translation, point):
    return tuple(
        sum(rotation[i][j] * point[j] for j in range(3)) + translation[i]
        for i in range(3)
    )


def rotate(rotation, point):
    return tuple(sum(rotation[i][j] * point[j] for j in range(3)) for i in range(3))


def transpose(matrix):
    return tuple(tuple(matrix[j][i] for j in range(3)) for i in range(3))


def dot(left, right):
    return sum(left[i] * right[i] for i in range(3))


def cross(left, right):
    return (
        left[1] * right[2] - left[2] * right[1],
        left[2] * right[0] - left[0] * right[2],
        left[0] * right[1] - left[1] * right[0],
    )


def normalize(vector):
    length = math.sqrt(dot(vector, vector))
    if length < 1e-12:
        raise ValueError("Cannot derive a robot frame from coincident wheel centers")
    return tuple(value / length for value in vector)


def multiply(left, right):
    return tuple(
        tuple(sum(left[i][k] * right[k][j] for k in range(3)) for j in range(3))
        for i in range(3)
    )


def format_vector(vector):
    return " ".join(f"{value:.8g}" for value in vector)


def read_stl_vertices(path):
    data = path.read_bytes()
    if len(data) < 84:
        raise ValueError(f"Truncated binary STL: {path}")
    triangles = struct.unpack_from("<I", data, 80)[0]
    if len(data) != 84 + 50 * triangles:
        raise ValueError(f"Unexpected binary STL size: {path}")
    for offset in range(84, len(data), 50):
        triangle = struct.unpack_from("<12fH", data, offset)
        yield triangle[3:6]
        yield triangle[6:9]
        yield triangle[9:12]


def transformed_bounds_center(path, translation, rpy):
    low, high = transformed_bounds(path, translation, rpy)
    return tuple((low[i] + high[i]) / 2 for i in range(3))


def transformed_bounds(path, translation, rpy):
    rotation = matrix_from_rpy(rpy)
    low = [math.inf] * 3
    high = [-math.inf] * 3
    for vertex in read_stl_vertices(path):
        point = transform_point(rotation, translation, vertex)
        for axis in range(3):
            low[axis] = min(low[axis], point[axis])
            high[axis] = max(high[axis], point[axis])
    return tuple(low), tuple(high)


def principal_axis(vertices):
    mean = tuple(sum(point[i] for point in vertices) / len(vertices) for i in range(3))
    covariance = tuple(
        tuple(
            sum((point[i] - mean[i]) * (point[j] - mean[j]) for point in vertices)
            / len(vertices)
            for j in range(3)
        )
        for i in range(3)
    )
    axis = (1.0, 1.0, 1.0)
    norm = math.sqrt(sum(value * value for value in axis))
    axis = tuple(value / norm for value in axis)
    for _ in range(48):
        next_axis = tuple(sum(covariance[i][j] * axis[j] for j in range(3)) for i in range(3))
        norm = math.sqrt(sum(value * value for value in next_axis))
        if norm < 1e-15:
            raise ValueError("Could not derive a roller axis from mesh geometry")
        axis = tuple(value / norm for value in next_axis)
    return mean, axis


def visual_data(visual):
    origin = visual.find("origin")
    mesh = Path(visual.find("geometry/mesh").get("filename")).name
    material = visual.find("material")
    rgba = material.find("color").get("rgba") if material is not None else "0.7 0.7 0.7 1"
    material_name = (
        re.sub(r"[^A-Za-z0-9_]", "_", material.get("name"))
        if material is not None and material.get("name")
        else "cad_default"
    )
    return {
        "mesh": mesh,
        "xyz": tuple(float(value) for value in origin.get("xyz").split()),
        "rpy": tuple(float(value) for value in origin.get("rpy").split()),
        "rgba": rgba,
        "material": material_name,
    }


def append_visual(lines, record, xyz=None, rpy=None, indent="    "):
    lines.append(
        f'{indent}<xacro:cad_visual mesh="{record["mesh"]}" '
        f'xyz="{format_vector(record["xyz"] if xyz is None else xyz)}" '
        f'rpy="{format_vector(record["rpy"] if rpy is None else rpy)}" '
        f'rgba="{record["rgba"]}" material="{record["material"]}"/>'
    )


def same_origin(actual, expected):
    return all(abs(actual[i] - expected[i]) < 1e-5 for i in range(3))


def is_left_claw_carriage_visual(record):
    mesh = record["mesh"]
    match = re.fullmatch(r"MGN12H_430MM_Assembly_1__Solid(\d+)\.stl", mesh)
    return (
        match is not None
        and int(match.group(1)) >= LEFT_CLAW_CARRIAGE_MIN_SOLID
        and same_origin(record["xyz"], LEFT_CLAW_CARRIAGE_ORIGIN)
    )


def is_left_claw_attached_visual(record):
    expected_origin = LEFT_CLAW_ATTACHED_PARTS.get(record["mesh"])
    return expected_origin is not None and same_origin(
        record["xyz"], expected_origin
    )


def is_left_claw_visual(record):
    return is_left_claw_carriage_visual(record) or is_left_claw_attached_visual(
        record
    )


def wheel_roller_frames(record, wheel_center, mesh_path):
    mesh_rotation = matrix_from_rpy(record["rpy"])
    vertices = list(read_stl_vertices(mesh_path))
    mean_local, axis_local = principal_axis(vertices)
    axis_cad = rotate(mesh_rotation, axis_local)
    major = max(range(3), key=lambda i: abs(axis_cad[i]))
    if axis_cad[major] < 0:
        axis_cad = tuple(-value for value in axis_cad)

    x_axis = (1.0 - axis_cad[0] ** 2, -axis_cad[0] * axis_cad[1], -axis_cad[0] * axis_cad[2])
    norm = math.sqrt(sum(value * value for value in x_axis))
    if norm < 1e-6:
        x_axis = (0.0, 1.0, 0.0)
        projection = sum(x_axis[i] * axis_cad[i] for i in range(3))
        x_axis = tuple(x_axis[i] - projection * axis_cad[i] for i in range(3))
        norm = math.sqrt(sum(value * value for value in x_axis))
    x_axis = tuple(value / norm for value in x_axis)
    y_axis = (
        axis_cad[1] * x_axis[2] - axis_cad[2] * x_axis[1],
        axis_cad[2] * x_axis[0] - axis_cad[0] * x_axis[2],
        axis_cad[0] * x_axis[1] - axis_cad[1] * x_axis[0],
    )
    roller_rotation = tuple(
        (x_axis[i], y_axis[i], axis_cad[i]) for i in range(3)
    )
    roller_center = transformed_bounds_center(mesh_path, record["xyz"], record["rpy"])
    visual_translation = tuple(
        sum(
            roller_rotation[j][i] * (record["xyz"][j] - roller_center[j])
            for j in range(3)
        )
        for i in range(3)
    )
    visual_rotation = multiply(transpose(roller_rotation), mesh_rotation)
    joint_translation = tuple(roller_center[i] - wheel_center[i] for i in range(3))
    return (
        joint_translation,
        rpy_from_matrix(roller_rotation),
        visual_translation,
        rpy_from_matrix(visual_rotation),
    )


def main():
    robot = ET.parse(SOURCE_URDF).getroot()
    source_link = robot.find("link[@name='root']")
    groups = defaultdict(list)
    visuals = []
    for visual in source_link.findall("visual"):
        record = visual_data(visual)
        visuals.append(record)
        prefix = record["mesh"].rsplit("Solid", 1)[0]
        if prefix in WHEEL_GROUPS:
            groups[prefix].append(record)
    if set(groups) != set(WHEEL_GROUPS):
        raise ValueError(f"Expected four mecanum mesh groups; found {sorted(groups)}")

    mesh_dir = ROOT / "meshes"
    wheel_centers = {}
    for prefix, records in groups.items():
        hubs = [
            record
            for record in records
            if int(re.search(r"Solid(\d+)\.stl$", record["mesh"]).group(1)) in (1, 3)
        ]
        if len(hubs) != 2:
            raise ValueError(f"Expected two hub faces for {prefix}; found {len(hubs)}")
        centers = [
            transformed_bounds_center(
                mesh_dir / record["mesh"], record["xyz"], record["rpy"]
            )
            for record in hubs
        ]
        wheel_centers[prefix] = tuple(
            sum(center[i] for center in centers) / len(centers) for i in range(3)
        )

    centers = {WHEEL_GROUPS[prefix]: center for prefix, center in wheel_centers.items()}
    lateral = tuple(
        centers["front_left"][i] - centers["front_right"][i] for i in range(3)
    )
    forward = tuple(
        centers["front_left"][i] - centers["rear_left"][i] for i in range(3)
    )
    normal = normalize(cross(lateral, forward))
    if normal[2] < 0:
        normal = tuple(-value for value in normal)
    forward_axis = (0.0, 1.0, 0.0)
    projection = dot(forward_axis, normal)
    forward_axis = normalize(
        tuple(forward_axis[i] - projection * normal[i] for i in range(3))
    )
    lateral_axis = normalize(cross(normal, forward_axis))
    cad_to_base = (forward_axis, lateral_axis, normal)
    base_to_cad = transpose(cad_to_base)
    cad_link_rpy = rpy_from_matrix(cad_to_base)
    base_to_cad_rpy = rpy_from_matrix(base_to_cad)
    wheel_axis_cad = tuple(-value for value in lateral_axis)
    wheel_center_mean = tuple(
        sum(center[i] for center in wheel_centers.values()) / len(wheel_centers)
        for i in range(3)
    )
    ground_origin_cad = tuple(
        wheel_center_mean[i] - WHEEL_RADIUS * normal[i] for i in range(3)
    )
    base_origin = tuple(
        -sum(cad_to_base[i][j] * ground_origin_cad[j] for j in range(3))
        for i in range(3)
    )
    chassis_com = source_link.find("inertial/origin").get("xyz").split()
    left_claw_carriage_visuals = [
        record for record in visuals if is_left_claw_carriage_visual(record)
    ]
    left_claw_attached_visuals = [
        record for record in visuals if is_left_claw_attached_visual(record)
    ]
    left_claw_visuals = left_claw_carriage_visuals + left_claw_attached_visuals
    if len(left_claw_carriage_visuals) != 43 or len(left_claw_attached_visuals) != len(
        LEFT_CLAW_ATTACHED_PARTS
    ):
        raise ValueError(
            "Expected 43 left MGN12 carriage meshes and all five attached claw "
            f"meshes; found {len(left_claw_carriage_visuals)} and "
            f"{len(left_claw_attached_visuals)}."
        )
    left_claw_rails = [
        record
        for record in visuals
        if record["mesh"] == LEFT_CLAW_RAIL_MESH
        and same_origin(record["xyz"], LEFT_CLAW_RAIL_ORIGIN)
    ]
    if len(left_claw_rails) != 1:
        raise ValueError(
            f"Expected one fixed front MGN12 rail; found {len(left_claw_rails)}."
        )
    left_jaw_visuals = [
        record
        for record in left_claw_attached_visuals
        if record["mesh"] == LEFT_CLAW_JAW_MESH
    ]
    right_jaw_visuals = [
        record
        for record in visuals
        if record["mesh"] == RIGHT_CLAW_JAW_MESH
        and same_origin(record["xyz"], RIGHT_CLAW_JAW_ORIGIN)
    ]
    if len(left_jaw_visuals) != 1 or len(right_jaw_visuals) != 1:
        raise ValueError(
            "Expected one moving left jaw and one fixed right jaw; found "
            f"{len(left_jaw_visuals)} and {len(right_jaw_visuals)}."
        )

    def bounds_for(records):
        bounds = [
            transformed_bounds(
                mesh_dir / record["mesh"], record["xyz"], record["rpy"]
            )
            for record in records
        ]
        low = tuple(min(item[0][axis] for item in bounds) for axis in range(3))
        high = tuple(max(item[1][axis] for item in bounds) for axis in range(3))
        return low, high

    rail_bounds = bounds_for(left_claw_rails)
    carriage_bounds = bounds_for(left_claw_carriage_visuals)
    claw_bounds = bounds_for(left_claw_visuals)
    left_claw_slide = (
        carriage_bounds[0][0] - rail_bounds[0][0] - LEFT_CLAW_SLIDE_MARGIN
    )
    if left_claw_slide <= 0:
        raise ValueError(
            "The left carriage position is not inside the usable front rail span."
        )
    claw_center = tuple(
        (claw_bounds[0][axis] + claw_bounds[1][axis]) / 2 for axis in range(3)
    )
    claw_size = tuple(
        claw_bounds[1][axis] - claw_bounds[0][axis] for axis in range(3)
    )

    def collision_box(records):
        bounds = bounds_for(records)
        center = tuple((bounds[0][axis] + bounds[1][axis]) / 2 for axis in range(3))
        size = tuple(
            bounds[1][axis] - bounds[0][axis] + CLAW_COLLISION_PADDING
            for axis in range(3)
        )
        return center, size

    moving_jaw_center, moving_jaw_size = collision_box(left_jaw_visuals)
    fixed_jaw_center, fixed_jaw_size = collision_box(right_jaw_visuals)
    lower_collision_center = tuple(
        ground_origin_cad[i] + 0.14 * normal[i] for i in range(3)
    )
    upper_collision_center = tuple(
        ground_origin_cad[i] + 0.42 * normal[i] for i in range(3)
    )

    lines = [
        '<?xml version="1.0"?>',
        '<robot name="rangka_krai_2027" xmlns:xacro="http://www.ros.org/wiki/xacro">',
        '  <xacro:arg name="chassis_mass" default="5.0"/>',
        '  <xacro:arg name="wheel_mass" default="0.20"/>',
        '  <xacro:arg name="roller_mass" default="0.012"/>',
        f'  <xacro:arg name="left_claw_mass" default="{LEFT_CLAW_MASS}"/>',
        f'  <xacro:arg name="left_claw_slide" default="{left_claw_slide:.8g}"/>',
        '  <xacro:property name="chassis_mass" value="$(arg chassis_mass)"/>',
        '  <xacro:property name="wheel_mass" value="$(arg wheel_mass)"/>',
        '  <xacro:property name="roller_mass" value="$(arg roller_mass)"/>',
        '  <xacro:property name="left_claw_mass" value="$(arg left_claw_mass)"/>',
        '  <xacro:property name="left_claw_slide" value="$(arg left_claw_slide)"/>',
        '',
        '  <xacro:macro name="cad_visual" params="mesh xyz rpy rgba material">',
        '    <visual>',
        '      <origin xyz="${xyz}" rpy="${rpy}"/>',
        '      <geometry><mesh filename="package://rangka_krai_2027/meshes/${mesh}"/></geometry>',
        '      <material name="${material}"><color rgba="${rgba}"/></material>',
        '    </visual>',
        '  </xacro:macro>',
        '',
        '  <link name="base_footprint"/>',
        '  <link name="base_link">',
        '    <inertial>',
        f'      <origin xyz="{" ".join(chassis_com)}" rpy="{format_vector(base_to_cad_rpy)}"/>',
        '      <mass value="${chassis_mass}"/>',
        '      <inertia ixx="${chassis_mass * (0.601**2 + 0.580**2) / 12}" ixy="0" ixz="0"',
        '               iyy="${chassis_mass * (1.604**2 + 0.580**2) / 12}" iyz="0"',
        '               izz="${chassis_mass * (1.604**2 + 0.601**2) / 12}"/>',
        '    </inertial>',
        '    <collision name="lower_frame_collision">',
        f'      <origin xyz="{format_vector(lower_collision_center)}" rpy="{format_vector(base_to_cad_rpy)}"/>',
        '      <geometry><box size="0.44 0.44 0.10"/></geometry>',
        '    </collision>',
        '    <collision name="upper_frame_collision">',
        f'      <origin xyz="{format_vector(upper_collision_center)}" rpy="{format_vector(base_to_cad_rpy)}"/>',
        '      <geometry><box size="0.60 0.50 0.06"/></geometry>',
        '    </collision>',
        '    <collision name="fixed_right_claw_jaw_collision">',
        f'      <origin xyz="{format_vector(fixed_jaw_center)}" rpy="0 0 0"/>',
        f'      <geometry><box size="{format_vector(fixed_jaw_size)}"/></geometry>',
        '    </collision>',
    ]
    for record in visuals:
        if not record["mesh"].startswith("Mecanum") and not is_left_claw_visual(record):
            append_visual(lines, record)
    lines += [
        '  </link>',
        '  <joint name="base_footprint_joint" type="fixed">',
        '    <parent link="base_footprint"/><child link="base_link"/>',
        f'    <origin xyz="{format_vector(base_origin)}" rpy="{format_vector(cad_link_rpy)}"/>',
        '  </joint>',
        '',
        '  <link name="left_claw_link">',
        '    <inertial>',
        f'      <origin xyz="{format_vector(claw_center)}" rpy="0 0 0"/>',
        '      <mass value="${left_claw_mass}"/>',
        f'      <inertia ixx="${{left_claw_mass * ({claw_size[1]:.8g}**2 + {claw_size[2]:.8g}**2) / 12}}" ixy="0" ixz="0"',
        f'               iyy="${{left_claw_mass * ({claw_size[0]:.8g}**2 + {claw_size[2]:.8g}**2) / 12}}" iyz="0"',
        f'               izz="${{left_claw_mass * ({claw_size[0]:.8g}**2 + {claw_size[1]:.8g}**2) / 12}}"/>',
        '    </inertial>',
        '    <collision name="moving_left_claw_jaw_collision">',
        f'      <origin xyz="{format_vector(moving_jaw_center)}" rpy="0 0 0"/>',
        f'      <geometry><box size="{format_vector(moving_jaw_size)}"/></geometry>',
        '    </collision>',
    ]
    for record in left_claw_visuals:
        append_visual(lines, record)
    lines += [
        '  </link>',
        '  <gazebo reference="base_link"><mu1>1.2</mu1><mu2>1.2</mu2></gazebo>',
        '  <gazebo reference="left_claw_link"><mu1>1.2</mu1><mu2>1.2</mu2></gazebo>',
        '  <joint name="left_claw_joint" type="prismatic">',
        '    <parent link="base_link"/><child link="left_claw_link"/>',
        '    <origin xyz="0 0 0" rpy="0 0 0"/>',
        '    <axis xyz="-1 0 0"/>',
        '    <limit lower="0.0" upper="${left_claw_slide}" effort="20" velocity="0.15"/>',
        '    <dynamics damping="0.1" friction="0.0"/>',
        '  </joint>',
        '',
    ]

    for prefix, wheel_name in WHEEL_GROUPS.items():
        wheel_center = wheel_centers[prefix]
        records = groups[prefix]
        lines += [
            f'  <link name="{wheel_name}_wheel">',
            '    <inertial>',
            '      <origin xyz="0 0 0" rpy="0 0 0"/>',
            '      <mass value="${wheel_mass}"/>',
            '      <inertia ixx="${wheel_mass * 0.5 * 0.075**2}" ixy="0" ixz="0"',
            '               iyy="${wheel_mass * (3 * 0.075**2 + 0.085**2) / 12}" iyz="0"',
            '               izz="${wheel_mass * (3 * 0.075**2 + 0.085**2) / 12}"/>',
            '    </inertial>',
        ]
        for record in records:
            solid = int(re.search(r"Solid(\d+)\.stl$", record["mesh"]).group(1))
            if solid not in ROLLER_SOLIDS:
                append_visual(
                    lines,
                    record,
                    xyz=tuple(record["xyz"][i] - wheel_center[i] for i in range(3)),
                )
        lines += [
            '  </link>',
            f'  <joint name="{wheel_name}_wheel_joint" type="continuous">',
            '    <parent link="base_link"/>',
            f'    <child link="{wheel_name}_wheel"/>',
            f'    <origin xyz="{format_vector(wheel_center)}" rpy="0 0 0"/>',
            f'    <axis xyz="{format_vector(wheel_axis_cad)}"/>',
            '    <limit effort="20" velocity="20"/>',
            '    <dynamics damping="0.002" friction="0.0"/>',
            '  </joint>',
            '',
        ]

        roller_index = 0
        for record in records:
            solid = int(re.search(r"Solid(\d+)\.stl$", record["mesh"]).group(1))
            if solid not in ROLLER_SOLIDS:
                continue
            roller_index += 1
            joint_xyz, joint_rpy, visual_xyz, visual_rpy = wheel_roller_frames(
                record, wheel_center, mesh_dir / record["mesh"]
            )
            name = f"{wheel_name}_roller_{roller_index}"
            lines += [
                f'  <link name="{name}">',
                '    <inertial>',
                '      <mass value="${roller_mass}"/>',
                '      <inertia ixx="${roller_mass * (3 * 0.0075**2 + 0.0724**2) / 12}" ixy="0" ixz="0"',
                '               iyy="${roller_mass * (3 * 0.0075**2 + 0.0724**2) / 12}" iyz="0"',
                '               izz="${roller_mass * 0.5 * 0.0075**2}"/>',
                '    </inertial>',
            ]
            append_visual(lines, record, xyz=visual_xyz, rpy=visual_rpy)
            lines += [
                '    <collision name="roller_collision">',
                '      <geometry><cylinder radius="0.0075" length="0.0724"/></geometry>',
                '    </collision>',
                '  </link>',
                f'  <joint name="{name}_joint" type="continuous">',
                f'    <parent link="{wheel_name}_wheel"/><child link="{name}"/>',
                f'    <origin xyz="{format_vector(joint_xyz)}" rpy="{format_vector(joint_rpy)}"/>',
                '    <axis xyz="0 0 1"/>',
                '    <limit effort="2" velocity="50"/>',
                '    <dynamics damping="0.0001" friction="0.0"/>',
                '  </joint>',
                f'  <gazebo reference="{name}"><mu1>1.2</mu1><mu2>1.2</mu2></gazebo>',
                '',
            ]

    lines += [
        '  <ros2_control name="GazeboSimSystem" type="system">',
        '    <hardware><plugin>gz_ros2_control/GazeboSimSystem</plugin></hardware>',
        '    <joint name="left_claw_joint">',
        '      <command_interface name="position"><param name="min">0.0</param><param name="max">${left_claw_slide}</param></command_interface>',
        '      <state_interface name="position"/>',
        '      <state_interface name="velocity"/>',
        '    </joint>',
    ]
    for wheel_name in WHEEL_GROUPS.values():
        joint = f"{wheel_name}_wheel_joint"
        lines += [
            f'    <joint name="{joint}">',
            '      <command_interface name="velocity"><param name="min">-20</param><param name="max">20</param></command_interface>',
            '      <state_interface name="position"/>',
            '      <state_interface name="velocity"/>',
            '    </joint>',
        ]
        for roller_index in range(1, len(ROLLER_SOLIDS) + 1):
            lines += [
                f'    <joint name="{wheel_name}_roller_{roller_index}_joint">',
                '      <state_interface name="position"/>',
                '      <state_interface name="velocity"/>',
                '    </joint>',
            ]
    lines += [
        '  </ros2_control>',
        '  <gazebo>',
        '    <plugin filename="gz_ros2_control-system" name="gz_ros2_control::GazeboSimROS2ControlPlugin">',
        '      <parameters>$(find rangka_krai_2027)/config/ros2_controllers.yaml</parameters>',
        '      <ros>',
        '        <remapping>/mecanum_drive_controller/reference:=/cmd_vel</remapping>',
        '        <remapping>/mecanum_drive_controller/odometry:=/odom</remapping>',
        '        <remapping>/mecanum_drive_controller/tf_odometry:=/tf</remapping>',
        '      </ros>',
        '    </plugin>',
        '  </gazebo>',
        '</robot>',
    ]
    OUTPUT_XACRO.write_text("\n".join(lines) + "\n")
    print(
        f"Generated {OUTPUT_XACRO.relative_to(ROOT)} with {len(visuals)} source visuals, "
        f"1 left claw joint, 4 drive joints and "
        f"{len(WHEEL_GROUPS) * len(ROLLER_SOLIDS)} passive roller joints."
    )
    print(
        f"Left claw carriage: {len(left_claw_visuals)} moving visuals "
        f"({len(left_claw_carriage_visuals)} carriage + "
        f"{len(left_claw_attached_visuals)} jaw/mount), with the MGN12 rail fixed."
    )
    print(
        f"Usable left slide from CAD rail bounds: {left_claw_slide:.4f} m "
        f"(includes {LEFT_CLAW_SLIDE_MARGIN:.3f} m end margin)."
    )
    print(f"Ground plane normal in CAD frame: {format_vector(normal)}")
    print(f"base_footprint origin in base frame: {format_vector(base_origin)}")
    for prefix, wheel_name in WHEEL_GROUPS.items():
        print(f"{wheel_name}: CAD wheel center {format_vector(wheel_centers[prefix])}")


if __name__ == "__main__":
    main()
