from pathlib import Path

import numpy as np
import pytest
from numpy.typing import NDArray
from PIL import Image

from conftest import FixtureObject, FixturePart, write_3mf
from render import find_bambu_studio, find_blender, main, slice_plates

pytestmark = pytest.mark.skipif(find_blender() is None, reason="Blender is not installed")


@pytest.fixture(scope="module")
def rendered(tmp_path_factory: pytest.TempPathFactory) -> Path:
    tmp_path = tmp_path_factory.mktemp("render")
    source = write_3mf(
        tmp_path / "keychains.3mf",
        [
            FixtureObject(
                "red-on-black",
                [
                    FixturePart("plate", extruder=1, transform="40 0 0 0 20 0 0 0 2 0 0 0"),
                    FixturePart("logo", extruder=2, transform="10 0 0 0 10 0 0 0 2 15 5 2"),
                ],
            ),
            FixtureObject("white", [FixturePart("plate", extruder=3, transform="20 0 0 0 20 0 0 0 2 0 0 0")]),
        ],
        ["#131313", "#C42430", "#ECECEB"],
    )
    output = tmp_path / "images"
    assert main([str(source), "--output", str(output), "--samples", "4", "--resolution", "160x90"]) == 0
    return output


def test_renders_one_png_per_object(rendered: Path) -> None:
    assert sorted(path.name for path in rendered.iterdir()) == ["red-on-black.png", "white.png"]


def test_renders_at_the_requested_resolution(rendered: Path) -> None:
    with Image.open(rendered / "white.png") as image:
        assert image.size == (160, 90)
        assert image.mode == "RGBA"


def test_renders_the_object_on_a_transparent_background(rendered: Path) -> None:
    with Image.open(rendered / "white.png") as image:
        alpha = np.asarray(image)[:, :, 3]

    assert alpha[0, 0] == 0
    assert alpha[45, 80] == 255


def _reddish(path: Path) -> NDArray[np.bool_]:
    with Image.open(path) as image:
        pixels = np.asarray(image.convert("RGBA")).reshape(-1, 4).astype(int)
    opaque = pixels[pixels[:, 3] == 255]
    return (opaque[:, 0] > 2 * opaque[:, 1]) & (opaque[:, 0] > 2 * opaque[:, 2]) & (opaque[:, 0] > 60)


def test_renders_parts_with_their_filament_colour(rendered: Path) -> None:
    reddish = _reddish(rendered / "red-on-black.png")

    assert reddish.any()
    assert not reddish.all()


def _square_layers(filament: int, size: float, layers: int, z0: float = 0.0) -> list[str]:
    lines = [f"T{filament - 1}", "; FEATURE: Outer wall", "; LINE_WIDTH: 0.5", "; LAYER_HEIGHT: 0.2"]
    for layer in range(1, layers + 1):
        z = z0 + layer * 0.2
        lines += [f"G1 X0 Y0 Z{z:.2f}", f"G1 X{size} Y0 E1", f"G1 X{size} Y{size} E1", f"G1 X0 Y{size} E1", "G1 X0 Y0 E1"]
    return lines


@pytest.fixture(scope="module")
def rendered_toolpaths(tmp_path_factory: pytest.TempPathFactory) -> Path:
    tmp_path = tmp_path_factory.mktemp("toolpaths")
    source = write_3mf(
        tmp_path / "coasters.3mf",
        [FixtureObject("coaster", [FixturePart("plate")]), FixtureObject("other", [FixturePart("plate")])],
        ["#131313", "#C42430"],
        plates=[("coaster-plate", ["coaster"]), ("shared-plate", ["coaster", "other"])],
    )
    gcode = tmp_path / "gcode"
    gcode.mkdir()
    start = ["; MACHINE_START_GCODE_END", "M83", "G90"]
    (gcode / "plate_1.gcode").write_text("\n".join([*start, *_square_layers(1, 20, 5), *_square_layers(2, 10, 2, 1.0)]))
    (gcode / "plate_2.gcode").write_text("\n".join([*start, *_square_layers(1, 20, 2)]))
    output = tmp_path / "images"
    arguments = [str(source), "--gcode", str(gcode), "--output", str(output), "--samples", "4", "--resolution", "160x90"]
    assert main(arguments) == 0
    return output


def test_renders_one_png_per_plate_named_after_its_object(rendered_toolpaths: Path) -> None:
    assert sorted(path.name for path in rendered_toolpaths.iterdir()) == ["coaster.png", "shared-plate.png"]


@pytest.mark.skipif(find_bambu_studio() is None, reason="Bambu Studio is not installed")
def test_slices_one_gcode_per_plate(tmp_path: Path) -> None:
    bambu_studio = find_bambu_studio()
    assert bambu_studio is not None
    source = Path(__file__).resolve().parents[1] / "coasters" / "coasters.3mf"

    assert slice_plates(bambu_studio, source, tmp_path) == 0

    assert {"plate_1.gcode", "plate_2.gcode"} <= {path.name for path in tmp_path.iterdir()}


def test_renders_toolpaths_with_their_filament_colour(rendered_toolpaths: Path) -> None:
    reddish = _reddish(rendered_toolpaths / "coaster.png")

    assert reddish.any()
    assert not reddish.all()
