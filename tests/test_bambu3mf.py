from pathlib import Path

import numpy as np
import pytest

from bambu3mf import read_project, skip_plates
from conftest import FixtureObject, FixturePart, write_3mf


def test_reads_filament_colours(tmp_path: Path) -> None:
    path = write_3mf(tmp_path / "p.3mf", [FixtureObject("cube", [FixturePart("body")])], ["#131313", "#C42430"])

    assert read_project(path).filament_colours == ("#131313", "#C42430")


def test_reads_models_and_parts_names(tmp_path: Path) -> None:
    path = write_3mf(
        tmp_path / "p.3mf",
        [
            FixtureObject("first", [FixturePart("plate"), FixturePart("logo")]),
            FixtureObject("second", [FixturePart("plate")]),
        ],
        ["#000000"],
    )

    project = read_project(path)

    assert [model.name for model in project.models] == ["first", "second"]
    assert [part.name for part in project.models[0].parts] == ["plate", "logo"]


def test_part_filament_falls_back_to_object_extruder(tmp_path: Path) -> None:
    path = write_3mf(
        tmp_path / "p.3mf",
        [FixtureObject("cube", [FixturePart("plate", extruder=3), FixturePart("logo")], extruder=2)],
        ["#000000", "#111111", "#222222"],
    )

    parts = read_project(path).models[0].parts

    assert [part.filament for part in parts] == [3, 2]


def test_reads_mesh_triangles(tmp_path: Path) -> None:
    path = write_3mf(tmp_path / "p.3mf", [FixtureObject("cube", [FixturePart("body")])], ["#000000"])

    part = read_project(path).models[0].parts[0]

    assert part.vertices.shape == (8, 3)
    assert part.triangles.shape == (12, 3)


def test_applies_component_then_build_item_transforms(tmp_path: Path) -> None:
    path = write_3mf(
        tmp_path / "p.3mf",
        [
            FixtureObject(
                "cube",
                [FixturePart("body", transform="2 0 0 0 2 0 0 0 2 10 0 0")],
                item_transform="0.5 0 0 0 0.5 0 0 0 0.5 100 200 0",
            )
        ],
        ["#000000"],
    )

    vertices = read_project(path).models[0].parts[0].vertices

    np.testing.assert_allclose(vertices.min(axis=0), [105, 200, 0])
    np.testing.assert_allclose(vertices.max(axis=0), [106, 201, 1])


def test_applies_rotations(tmp_path: Path) -> None:
    path = write_3mf(
        tmp_path / "p.3mf",
        [FixtureObject("cube", [FixturePart("body", transform="0 1 0 -1 0 0 0 0 1 0 0 0")])],
        ["#000000"],
    )

    vertices = read_project(path).models[0].parts[0].vertices

    np.testing.assert_allclose(vertices.min(axis=0), [-1, 0, 0])
    np.testing.assert_allclose(vertices.max(axis=0), [0, 1, 1])


def test_mirroring_keeps_triangles_facing_outward(tmp_path: Path) -> None:
    path = write_3mf(
        tmp_path / "p.3mf",
        [FixtureObject("cube", [FixturePart("body", transform="-1 0 0 0 1 0 0 0 1 0 0 0")])],
        ["#000000"],
    )

    part = read_project(path).models[0].parts[0]

    corners = part.vertices[part.triangles]
    normals = np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0])
    outward = np.einsum("ij,ij->i", normals, corners.mean(axis=1) - part.vertices.mean(axis=0))
    assert (outward > 0).all()


def test_reads_plates_and_their_objects(tmp_path: Path) -> None:
    path = write_3mf(
        tmp_path / "p.3mf",
        [FixtureObject("a", [FixturePart("plate")]), FixtureObject("b", [FixturePart("plate")])],
        ["#000000"],
        plates=[("second-plate", ["b"]), ("first-plate", ["a", "b"])],
    )

    plates = read_project(path).plates

    assert [(plate.index, plate.name, plate.objects) for plate in plates] == [
        (1, "second-plate", ("b",)),
        (2, "first-plate", ("a", "b")),
    ]


def test_skips_plates_and_the_objects_only_found_on_them(tmp_path: Path) -> None:
    path = write_3mf(
        tmp_path / "p.3mf",
        [
            FixtureObject("whole", [FixturePart("plate")]),
            FixtureObject("piece", [FixturePart("plate")]),
            FixtureObject("shared", [FixturePart("plate")]),
        ],
        ["#000000"],
        plates=[("whole-plate", ["whole", "shared"]), ("pieces-plate", ["piece", "shared"])],
    )

    project = skip_plates(read_project(path), [2])

    assert [plate.name for plate in project.plates] == ["whole-plate"]
    assert [model.name for model in project.models] == ["whole", "shared"]


def test_skipping_no_plate_keeps_every_object(tmp_path: Path) -> None:
    path = write_3mf(tmp_path / "p.3mf", [FixtureObject("a", [FixturePart("plate")])], ["#000000"])

    assert [model.name for model in skip_plates(read_project(path), []).models] == ["a"]


def test_rejects_skipping_an_unknown_plate(tmp_path: Path) -> None:
    path = write_3mf(
        tmp_path / "p.3mf", [FixtureObject("a", [FixturePart("plate")])], ["#000000"], plates=[("a-plate", ["a"])]
    )

    with pytest.raises(ValueError, match="no plate 3"):
        skip_plates(read_project(path), [3])


def test_rejects_non_3mf_files(tmp_path: Path) -> None:
    path = tmp_path / "p.3mf"
    path.write_text("not a zip")

    with pytest.raises(ValueError, match="not a 3MF archive"):
        read_project(path)
