import numpy as np
import pytest

from toolpaths import parse_gcode, polylines, tube_mesh

START = ["; MACHINE_START_GCODE_END", "M83", "T0", "; FEATURE: Outer wall", "; LINE_WIDTH: 0.4", "; LAYER_HEIGHT: 0.2"]


def gcode(*lines: str) -> list[str]:
    return [*START, *lines]


def test_keeps_extruding_moves() -> None:
    paths = parse_gcode(gcode("G1 X0 Y0 Z0.2 F3000", "G1 X10 Y0 E0.5", "G1 X10 Y5 E0.2"))

    np.testing.assert_allclose(paths.starts, [[0, 0, 0.2], [10, 0, 0.2]])
    np.testing.assert_allclose(paths.ends, [[10, 0, 0.2], [10, 5, 0.2]])
    np.testing.assert_allclose(paths.widths, [0.4, 0.4])
    np.testing.assert_allclose(paths.heights, [0.2, 0.2])
    assert paths.filaments.tolist() == [1, 1]


def test_ignores_travels_retractions_and_wipes() -> None:
    paths = parse_gcode(gcode("G1 X0 Y0 Z0.2", "G1 X5 Y0 F60000", "G1 E-0.4", "G1 X6 Y0 E-0.2", "G1 E0.4"))

    assert len(paths.starts) == 0


def test_ignores_everything_before_the_end_of_the_start_gcode() -> None:
    paths = parse_gcode(["M83", "T0", "G1 X0 Y0 Z0.2", "G1 X10 Y0 E5", *START, "G1 X20 Y0 E1"])

    np.testing.assert_allclose(paths.starts, [[10, 0, 0.2]])


def test_ignores_the_prime_tower() -> None:
    paths = parse_gcode(gcode("G1 X0 Y0 Z0.2", "; FEATURE: Prime tower", "G1 X10 Y0 E1", "; FEATURE: Inner wall", "G1 X20 Y0 E1"))

    np.testing.assert_allclose(paths.starts, [[10, 0, 0.2]])


def test_tracks_tool_changes_and_ignores_machine_tools() -> None:
    paths = parse_gcode(gcode("G1 X0 Y0 Z0.2", "G1 X1 Y0 E1", "T2", "G1 X2 Y0 E1", "T1000", "G1 X3 Y0 E1", "T65535"))

    assert paths.filaments.tolist() == [1, 3, 3]


def test_tracks_line_width_and_layer_height() -> None:
    paths = parse_gcode(
        gcode("G1 X0 Y0 Z0.2", "G1 X1 Y0 E1", "; LINE_WIDTH: 0.5", "; LAYER_HEIGHT: 0.28", "G1 X2 Y0 Z0.48 E1")
    )

    np.testing.assert_allclose(paths.widths, [0.4, 0.5])
    np.testing.assert_allclose(paths.heights, [0.2, 0.28])


def test_supports_relative_positioning() -> None:
    paths = parse_gcode(gcode("G1 X5 Y5 Z0.2", "G91", "G1 X1 Y0 E1", "G90", "G1 X0 Y5 E1"))

    np.testing.assert_allclose(paths.starts, [[5, 5, 0.2], [6, 5, 0.2]])
    np.testing.assert_allclose(paths.ends, [[6, 5, 0.2], [0, 5, 0.2]])


def test_supports_absolute_extrusion() -> None:
    paths = parse_gcode(gcode("M82", "G92 E10", "G1 X0 Y0 Z0.2", "G1 X1 Y0 E11", "G1 X2 Y0 E10.5", "G1 X3 Y0 E12"))

    np.testing.assert_allclose(paths.starts, [[0, 0, 0.2], [2, 0, 0.2]])


@pytest.mark.parametrize(("command", "middle_y"), [("G3", 1.0), ("G2", -1.0)])
def test_tessellates_arcs(command: str, middle_y: float) -> None:
    paths = parse_gcode(gcode("G1 X1 Y0 Z0.2", f"{command} X-1 Y0 I-1 J0 E1"))

    assert len(paths.starts) > 8
    np.testing.assert_allclose(paths.starts[0], [1, 0, 0.2])
    np.testing.assert_allclose(paths.ends[-1], [-1, 0, 0.2], atol=1e-9)
    np.testing.assert_allclose(np.linalg.norm(paths.ends[:, :2], axis=1), 1)
    assert paths.ends[len(paths.ends) // 2 - 1, 1] == pytest.approx(middle_y, abs=0.1)


def test_ignores_arcs_without_extrusion() -> None:
    paths = parse_gcode(gcode("G1 X1 Y0 Z0.2", "G3 Z0.6 I1.2 J0 P1 F60000"))

    assert len(paths.starts) == 0


def test_groups_contiguous_segments_into_polylines() -> None:
    paths = parse_gcode(
        gcode(
            "G1 X0 Y0 Z0.2",
            "G1 X1 Y0 E1",
            "G1 X1 Y1 E1",
            "G1 X5 Y5",
            "G1 X6 Y5 E1",
            "T1",
            "G1 X7 Y5 E1",
        )
    )

    lines = polylines(paths)

    assert [line.points.shape[0] for line in lines] == [3, 2, 2]
    assert [line.filament for line in lines] == [1, 1, 2]
    np.testing.assert_allclose(lines[0].points, [[0, 0, 0.2], [1, 0, 0.2], [1, 1, 0.2]])


def test_splits_polylines_on_sharp_turns() -> None:
    paths = parse_gcode(gcode("G1 X0 Y0 Z0.2", "G1 X1 Y0 E1", "G1 X0 Y0.1 E1"))

    assert len(polylines(paths)) == 2


def _signed_volume(vertices: np.ndarray, triangles: np.ndarray) -> float:
    corners = vertices[triangles]
    return float(np.einsum("ij,ij->i", corners[:, 0], np.cross(corners[:, 1], corners[:, 2])).sum() / 6)


def test_tube_mesh_follows_the_bead_section() -> None:
    vertices, triangles = tube_mesh(np.array([[0, 0, 0.2], [10, 0, 0.2]]), width=0.4, height=0.2)

    np.testing.assert_allclose(vertices.min(axis=0), [0, -0.2, 0.0], atol=0.01)
    np.testing.assert_allclose(vertices.max(axis=0), [10, 0.2, 0.2], atol=0.01)
    assert triangles.max() < len(vertices)


def test_tube_mesh_is_closed_and_faces_outward() -> None:
    points = np.array([[0, 0, 0.2], [10, 0, 0.2], [10, 10, 0.2], [0, 10, 0.2]])

    vertices, triangles = tube_mesh(points, width=0.4, height=0.2)

    edges = np.sort(np.concatenate([triangles[:, [0, 1]], triangles[:, [1, 2]], triangles[:, [2, 0]]]), axis=1)
    _, counts = np.unique(edges, axis=0, return_counts=True)
    assert (counts == 2).all()
    assert _signed_volume(vertices, triangles) > 0


def test_tube_mesh_keeps_the_width_at_corners() -> None:
    vertices, _ = tube_mesh(np.array([[0, 0, 0.2], [10, 0, 0.2], [10, 10, 0.2]]), width=0.4, height=0.2)

    np.testing.assert_allclose(vertices[:, 1].min(), -0.2, atol=1e-9)
    np.testing.assert_allclose(vertices[:, 0].max(), 10.2, atol=1e-9)
