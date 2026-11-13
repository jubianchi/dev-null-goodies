from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from conftest import FixtureObject, FixturePart, write_3mf
from render import find_blender, main

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


def test_renders_parts_with_their_filament_colour(rendered: Path) -> None:
    with Image.open(rendered / "red-on-black.png") as image:
        pixels = np.asarray(image.convert("RGBA")).reshape(-1, 4).astype(int)

    opaque = pixels[pixels[:, 3] == 255]
    reddish = (opaque[:, 0] > 2 * opaque[:, 1]) & (opaque[:, 0] > 2 * opaque[:, 2]) & (opaque[:, 0] > 60)
    assert reddish.any()
    assert not reddish.all()
