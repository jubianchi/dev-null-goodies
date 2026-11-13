from pathlib import Path

import numpy as np
import pytest
from numpy.typing import NDArray

from conftest import FixtureObject, FixturePart, write_3mf
from export_stl import colour_name, main


def read_binary_stl(path: Path) -> tuple[NDArray[np.float32], NDArray[np.float32]]:
    data = path.read_bytes()
    count = int(np.frombuffer(data, dtype="<u4", count=1, offset=80)[0])
    record = np.dtype([("normal", "<f4", (3,)), ("vertices", "<f4", (3, 3)), ("attributes", "<u2")])
    triangles = np.frombuffer(data, dtype=record, count=count, offset=84)
    assert len(data) == 84 + count * 50
    return triangles["normal"], triangles["vertices"]


def volume(path: Path) -> float:
    _, corners = read_binary_stl(path)
    corners = corners.astype(np.float64)
    return float(np.einsum("ij,ij->i", corners[:, 0], np.cross(corners[:, 1], corners[:, 2])).sum() / 6)


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


@pytest.mark.parametrize(
    ("hex_colour", "name"),
    [("#131313", "black"), ("#C42430", "red"), ("#ECECEB", "white"), ("#1F5FD6", "blue"), ("#2E9E45", "green")],
)
def test_names_filament_colours(hex_colour: str, name: str) -> None:
    assert colour_name(hex_colour) == name


def test_writes_one_stl_per_object_and_filament(tmp_path: Path) -> None:
    out = tmp_path / "stl"

    assert main([str(two_colour_keychain(tmp_path)), "--output", str(out)]) == 0

    assert sorted(path.name for path in out.iterdir()) == ["keychain-1-black.stl", "keychain-2-red.stl"]


def test_merges_parts_sharing_a_filament(tmp_path: Path) -> None:
    out = tmp_path / "stl"
    main([str(two_colour_keychain(tmp_path)), "--output", str(out)])

    assert volume(out / "keychain-1-black.stl") == pytest.approx(8)
    assert volume(out / "keychain-2-red.stl") == pytest.approx(2)


def test_carves_later_parts_out_of_earlier_ones(tmp_path: Path) -> None:
    source = write_3mf(
        tmp_path / "coasters.3mf",
        [
            FixtureObject(
                "coaster",
                [
                    FixturePart("plate", extruder=1, transform="4 0 0 0 4 0 0 0 1 0 0 0"),
                    FixturePart("logo", extruder=2, transform="1 0 0 0 1 0 0 0 1 1 1 0"),
                ],
            )
        ],
        ["#131313", "#C42430"],
    )
    out = tmp_path / "stl"
    main([str(source), "--output", str(out)])

    assert volume(out / "coaster-1-black.stl") == pytest.approx(15)
    assert volume(out / "coaster-2-red.stl") == pytest.approx(1)


def test_merges_overlapping_shells_of_a_part(tmp_path: Path) -> None:
    cube = FixturePart("plate").vertices
    shells = FixturePart(
        "plate",
        vertices=[*cube, *[(x + 0.5, y, z) for x, y, z in cube]],
        triangles=[*FixturePart("plate").triangles, *[(a + 8, b + 8, c + 8) for a, b, c in FixturePart("plate").triangles]],
    )
    source = write_3mf(tmp_path / "keychains.3mf", [FixtureObject("keychain", [shells])], ["#131313"])
    out = tmp_path / "stl"
    main([str(source), "--output", str(out)])

    assert volume(out / "keychain-1-black.stl") == pytest.approx(1.5)


def test_keeps_colours_aligned_and_centres_the_object_on_the_bed(tmp_path: Path) -> None:
    out = tmp_path / "stl"
    main([str(two_colour_keychain(tmp_path)), "--output", str(out)])

    _, plate = read_binary_stl(out / "keychain-1-black.stl")
    _, slashes = read_binary_stl(out / "keychain-2-red.stl")

    np.testing.assert_allclose(plate.reshape(-1, 3).min(axis=0), [-2, -1, 0])
    np.testing.assert_allclose(plate.reshape(-1, 3).max(axis=0), [2, 1, 1])
    np.testing.assert_allclose(slashes.reshape(-1, 3).min(axis=0), [-2, -1, 1])
    np.testing.assert_allclose(slashes.reshape(-1, 3).max(axis=0), [1, 0, 2])


def test_writes_outward_unit_normals(tmp_path: Path) -> None:
    out = tmp_path / "stl"
    main([str(two_colour_keychain(tmp_path)), "--output", str(out)])

    normals, vertices = read_binary_stl(out / "keychain-1-black.stl")

    np.testing.assert_allclose(np.linalg.norm(normals, axis=1), 1, rtol=1e-5)
    centre = vertices.reshape(-1, 3).mean(axis=0)
    outward = np.einsum("ij,ij->i", normals, vertices.mean(axis=1) - centre)
    assert (outward > 0).all()


def test_replaces_previously_generated_stl_files(tmp_path: Path) -> None:
    out = tmp_path / "stl"
    out.mkdir()
    (out / "keychain.stl").write_bytes(b"stale")

    main([str(two_colour_keychain(tmp_path)), "--output", str(out)])

    assert not (out / "keychain.stl").exists()


def test_defaults_output_to_stl_folder_next_to_the_3mf(tmp_path: Path) -> None:
    main([str(two_colour_keychain(tmp_path))])

    assert (tmp_path / "stl" / "keychain-1-black.stl").is_file()
