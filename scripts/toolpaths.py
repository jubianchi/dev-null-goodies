import math
import re
from collections.abc import Iterable
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

START_MARKER = "; MACHINE_START_GCODE_END"
EXCLUDED_FEATURES = frozenset({"Prime tower", "Custom"})
MAX_TOOL = 255
ARC_MAX_ANGLE = math.pi / 18
ARC_MAX_LENGTH = 1.0
MAX_TURN_COSINE = math.cos(math.radians(120))
BEAD_FILL = 0.98
WORD = re.compile(r"([A-Z])(-?\d*\.?\d+)")


@dataclass(frozen=True)
class Toolpaths:
    starts: NDArray[np.float64]
    ends: NDArray[np.float64]
    widths: NDArray[np.float64]
    heights: NDArray[np.float64]
    filaments: NDArray[np.int64]


@dataclass(frozen=True)
class Polyline:
    points: NDArray[np.float64]
    width: float
    height: float
    filament: int


def _arc(
    start: NDArray[np.float64], end: NDArray[np.float64], centre: NDArray[np.float64], clockwise: bool
) -> NDArray[np.float64]:
    radius = float(np.linalg.norm(start[:2] - centre))
    first = math.atan2(start[1] - centre[1], start[0] - centre[0])
    last = math.atan2(end[1] - centre[1], end[0] - centre[0])
    sweep = last - first
    if clockwise:
        sweep = sweep - 2 * math.pi if sweep >= 0 else sweep
    else:
        sweep = sweep + 2 * math.pi if sweep <= 0 else sweep
    steps = max(1, math.ceil(abs(sweep) / ARC_MAX_ANGLE), math.ceil(abs(sweep) * radius / ARC_MAX_LENGTH))
    fractions = np.arange(1, steps + 1) / steps
    angles = first + sweep * fractions
    points = np.column_stack(
        [centre[0] + radius * np.cos(angles), centre[1] + radius * np.sin(angles), start[2] + (end[2] - start[2]) * fractions]
    )
    points[-1] = end
    return points


def parse_gcode(lines: Iterable[str]) -> Toolpaths:
    position = np.zeros(3)
    relative_position = False
    absolute_extrusion = False
    extruder = 0.0
    started = False
    feature = ""
    width = 0.4
    height = 0.2
    filament = 1
    starts: list[NDArray[np.float64]] = []
    ends: list[NDArray[np.float64]] = []
    attributes: list[tuple[float, float, int]] = []

    for raw in lines:
        line = raw.strip()
        if line.startswith(";"):
            if line.startswith(START_MARKER):
                started = True
            elif line.startswith("; FEATURE:"):
                feature = line.partition(":")[2].strip()
            elif line.startswith("; LINE_WIDTH:"):
                width = float(line.partition(":")[2])
            elif line.startswith("; LAYER_HEIGHT:"):
                height = float(line.partition(":")[2])
            continue

        code = line.split(";", 1)[0].strip()
        if not code:
            continue
        command, _, arguments = code.partition(" ")
        words = {letter: float(value) for letter, value in WORD.findall(arguments)}

        if command == "G90":
            relative_position = False
        elif command == "G91":
            relative_position = True
        elif command == "M82":
            absolute_extrusion = True
        elif command == "M83":
            absolute_extrusion = False
        elif command == "G92" and "E" in words:
            extruder = words["E"]
        elif command.startswith("T") and command[1:].isdigit():
            if int(command[1:]) < MAX_TOOL:
                filament = int(command[1:]) + 1
        elif command in ("G0", "G1", "G2", "G3"):
            target = position.copy()
            for axis, letter in enumerate("XYZ"):
                if letter in words:
                    target[axis] = target[axis] + words[letter] if relative_position else words[letter]

            extruded = 0.0
            if "E" in words:
                extruded = words["E"] - extruder if absolute_extrusion else words["E"]
                extruder = words["E"] if absolute_extrusion else extruder

            printing = started and extruded > 0 and feature not in EXCLUDED_FEATURES
            if command in ("G2", "G3") and ("I" in words or "J" in words):
                centre = position[:2] + np.array([words.get("I", 0.0), words.get("J", 0.0)])
                points = _arc(position, target, centre, clockwise=command == "G2") if printing else np.array([target])
            else:
                points = np.array([target])

            if printing:
                previous = position
                for point in points:
                    if np.linalg.norm(point[:2] - previous[:2]) > 1e-9:
                        starts.append(previous)
                        ends.append(point)
                        attributes.append((width, height, filament))
                    previous = point
            position = target

    attributes_array = np.array(attributes, dtype=np.float64).reshape(-1, 3)
    return Toolpaths(
        starts=np.array(starts, dtype=np.float64).reshape(-1, 3),
        ends=np.array(ends, dtype=np.float64).reshape(-1, 3),
        widths=attributes_array[:, 0],
        heights=attributes_array[:, 1],
        filaments=attributes_array[:, 2].astype(np.int64),
    )


def _continues(paths: Toolpaths, previous: int, current: int) -> bool:
    if not np.allclose(paths.ends[previous], paths.starts[current], atol=1e-6):
        return False
    if (paths.widths[previous], paths.heights[previous], paths.filaments[previous]) != (
        paths.widths[current],
        paths.heights[current],
        paths.filaments[current],
    ):
        return False
    before = paths.ends[previous, :2] - paths.starts[previous, :2]
    after = paths.ends[current, :2] - paths.starts[current, :2]
    return float(before @ after) >= MAX_TURN_COSINE * np.linalg.norm(before) * np.linalg.norm(after)


def polylines(paths: Toolpaths) -> list[Polyline]:
    lines: list[Polyline] = []
    first = 0
    for index in range(1, len(paths.starts) + 1):
        if index < len(paths.starts) and _continues(paths, index - 1, index):
            continue
        points = np.vstack([paths.starts[first : first + 1], paths.ends[first:index]])
        lines.append(
            Polyline(
                points=points,
                width=float(paths.widths[first]),
                height=float(paths.heights[first]),
                filament=int(paths.filaments[first]),
            )
        )
        first = index
    return lines


def tube_mesh(points: NDArray[np.float64], width: float, height: float) -> tuple[NDArray[np.float64], NDArray[np.int64]]:
    directions = np.diff(points[:, :2], axis=0)
    directions /= np.linalg.norm(directions, axis=1, keepdims=True)
    tangents = np.vstack([directions[:1], directions[:-1] + directions[1:], directions[-1:]])
    tangents /= np.linalg.norm(tangents, axis=1, keepdims=True)
    laterals = np.column_stack([-tangents[:, 1], tangents[:, 0]])
    segment_laterals = np.column_stack([-directions[:, 1], directions[:, 0]])
    miters = np.ones(len(points))
    miters[1:-1] = 1 / np.einsum("ij,ij->i", laterals[1:-1], segment_laterals[:-1])
    laterals *= miters[:, None]

    half_width, half_height = width / 2, height * BEAD_FILL / 2
    section = np.array([(1, 0), (0.5, 1), (-0.5, 1), (-1, 0), (-0.5, -1), (0.5, -1)]) * [half_width, half_height]
    centres = points - [0, 0, height / 2]
    vertices = np.empty((len(points), len(section), 3))
    vertices[:, :, :2] = centres[:, None, :2] + laterals[:, None, :] * section[None, :, 0, None]
    vertices[:, :, 2] = centres[:, None, 2] + section[None, :, 1]

    sides = len(section)
    ring = np.arange(sides)
    following = (ring + 1) % sides
    triangles: list[NDArray[np.int64]] = []
    for index in range(len(points) - 1):
        here, there = index * sides, (index + 1) * sides
        triangles.append(np.column_stack([here + ring, here + following, there + ring]))
        triangles.append(np.column_stack([here + following, there + following, there + ring]))
    fan = np.arange(1, sides - 1)
    last = (len(points) - 1) * sides
    triangles.append(np.column_stack([np.zeros_like(fan), fan + 1, fan]))
    triangles.append(np.column_stack([last + np.zeros_like(fan), last + fan, last + fan + 1]))

    return vertices.reshape(-1, 3), np.concatenate(triangles).astype(np.int64)
