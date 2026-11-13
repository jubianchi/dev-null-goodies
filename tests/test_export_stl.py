from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from conftest import FixtureObject, FixturePart, write_3mf
from export_stl import main


def read_binary_stl(path: Path) -> tuple[NDArray[np.float32], NDArray[np.float32]]:
    data = path.read_bytes()
    count = int(np.frombuffer(data, dtype="<u4", count=1, offset=80)[0])
    record = np.dtype([("normal", "<f4", (3,)), ("vertices", "<f4", (3, 3)), ("attributes", "<u2")])
    triangles = np.frombuffer(data, dtype=record, count=count, offset=84)
    assert len(data) == 84 + count * 50
    return triangles["normal"], triangles["vertices"]


def two_colour_keychain(tmp_path: Path) -> Path:
    return write_3mf(
        tmp_path / "keychains.3mf",
        [
            FixtureObject(
                "keychain",
                [
                    FixturePart("plate", extruder=1, transform="4 0 0 0 2 0 0 0 1 0 0 0"),
                    FixturePart("first-slash", extruder=2, transform="1 0 0 0 1 0 0 0 1 0 0 1"),
                    FixturePart("second-slash", extruder=2, transform="1 0 0 0 1 0 0 0 1 2 0 1"),
                ],
                item_transform="1 0 0 0 1 0 0 0 1 100 100 5",
            )
        ],
        ["#131313", "#C42430"],
    )


def test_writes_one_stl_per_object(tmp_path: Path) -> None:
    source = write_3mf(
        tmp_path / "keychains.3mf",
        [FixtureObject("large", [FixturePart("plate")]), FixtureObject("small", [FixturePart("plate")])],
        ["#131313"],
    )
    out = tmp_path / "stl"

    assert main([str(source), "--output", str(out)]) == 0

    assert sorted(path.name for path in out.iterdir()) == ["large.stl", "small.stl"]


def test_merges_all_parts_of_an_object(tmp_path: Path) -> None:
    out = tmp_path / "stl"
    main([str(two_colour_keychain(tmp_path)), "--output", str(out)])

    _, triangles = read_binary_stl(out / "keychain.stl")

    assert len(triangles) == 36


def test_centres_the_object_on_the_bed(tmp_path: Path) -> None:
    out = tmp_path / "stl"
    main([str(two_colour_keychain(tmp_path)), "--output", str(out)])

    _, triangles = read_binary_stl(out / "keychain.stl")

    np.testing.assert_allclose(triangles.reshape(-1, 3).min(axis=0), [-2, -1, 0])
    np.testing.assert_allclose(triangles.reshape(-1, 3).max(axis=0), [2, 1, 2])


def test_writes_outward_unit_normals(tmp_path: Path) -> None:
    source = write_3mf(
        tmp_path / "keychains.3mf",
        [FixtureObject("plate", [FixturePart("plate", transform="4 0 0 0 2 0 0 0 1 0 0 0")])],
        ["#131313"],
    )
    out = tmp_path / "stl"
    main([str(source), "--output", str(out)])

    normals, vertices = read_binary_stl(out / "plate.stl")

    np.testing.assert_allclose(np.linalg.norm(normals, axis=1), 1, rtol=1e-6)
    centre = vertices.reshape(-1, 3).mean(axis=0)
    outward = np.einsum("ij,ij->i", normals, vertices.mean(axis=1) - centre)
    assert (outward > 0).all()


def test_defaults_output_to_stl_folder_next_to_the_3mf(tmp_path: Path) -> None:
    main([str(two_colour_keychain(tmp_path))])

    assert (tmp_path / "stl" / "keychain.stl").is_file()
