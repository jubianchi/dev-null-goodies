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


def _opaque_aspect_ratio(path: Path) -> float:
    with Image.open(path) as image:
        alpha = np.asarray(image)[:, :, 3]
    rows, columns = np.nonzero(alpha > 128)
    return float(np.ptp(columns) + 1) / float(np.ptp(rows) + 1)


@pytest.mark.parametrize(("view", "square"), [("top", True), ("three-quarter", False)])
def test_renders_the_requested_view(tmp_path: Path, view: str, square: bool) -> None:
    source = write_3mf(
        tmp_path / "square.3mf",
        [FixtureObject("square", [FixturePart("plate", transform="20 0 0 0 20 0 0 0 1 0 0 0")])],
        ["#131313"],
    )
    output = tmp_path / "images"

    assert main([str(source), "--output", str(output), "--samples", "4", "--resolution", "160x90", "--view", view]) == 0

    assert (_opaque_aspect_ratio(output / "square.png") == pytest.approx(1, abs=0.1)) is square


def test_top_view_keeps_the_back_of_the_object_at_the_top(tmp_path: Path) -> None:
    source = write_3mf(
        tmp_path / "marker.3mf",
        [
            FixtureObject(
                "marker",
                [
                    FixturePart("plate", extruder=1, transform="20 0 0 0 20 0 0 0 1 0 0 0"),
                    FixturePart("marker", extruder=2, transform="4 0 0 0 4 0 0 0 1 8 15 1"),
                ],
            )
        ],
        ["#131313", "#C42430"],
    )
    output = tmp_path / "images"
    main([str(source), "--output", str(output), "--samples", "4", "--resolution", "160x90", "--view", "top"])

    with Image.open(output / "marker.png") as image:
        pixels = np.asarray(image.convert("RGBA")).astype(int)
    red = (pixels[:, :, 0] > 2 * pixels[:, :, 1]) & (pixels[:, :, 0] > 60) & (pixels[:, :, 3] == 255)
    rows = np.nonzero(red)[0]

    assert rows.mean() < pixels.shape[0] / 2


def _opaque_brightness(path: Path) -> float:
    with Image.open(path) as image:
        pixels = np.asarray(image.convert("RGBA")).reshape(-1, 4).astype(float)
    return float(pixels[pixels[:, 3] == 255, :3].mean())


def test_lowers_the_brightness_with_a_negative_exposure(tmp_path: Path, rendered: Path) -> None:
    source = write_3mf(
        tmp_path / "keychains.3mf",
        [FixtureObject("white", [FixturePart("plate", extruder=3, transform="20 0 0 0 20 0 0 0 2 0 0 0")])],
        ["#131313", "#C42430", "#ECECEB"],
    )
    output = tmp_path / "images"
    arguments = [str(source), "--output", str(output), "--samples", "4", "--resolution", "160x90", "--exposure", "-1"]

    assert main(arguments) == 0

    assert _opaque_brightness(output / "white.png") < _opaque_brightness(rendered / "white.png") - 10


def _relief_fixture(path: Path) -> Path:
    return write_3mf(
        path,
        [
            FixtureObject(
                "relief",
                [
                    FixturePart("plate", extruder=3, transform="40 0 0 0 40 0 0 0 1 0 0 0"),
                    FixturePart("ridge", extruder=3, transform="2 0 0 0 30 0 0 0 3 19 5 1"),
                ],
            )
        ],
        ["#131313", "#C42430", "#ECECEB"],
    )


def _render_relief(tmp_path: Path, lighting: str) -> NDArray[np.float64]:
    source = _relief_fixture(tmp_path / f"{lighting}.3mf")
    output = tmp_path / lighting
    arguments = [str(source), "--output", str(output), "--samples", "4", "--resolution", "160x90", "--lighting", lighting]
    assert main(arguments) == 0
    with Image.open(output / "relief.png") as image:
        return np.asarray(image.convert("RGBA")).astype(float)


def test_renders_with_the_requested_lighting(tmp_path: Path) -> None:
    front = _render_relief(tmp_path, "front")
    side = _render_relief(tmp_path, "side-low")

    assert np.abs(front[:, :, :3] - side[:, :, :3]).mean() > 1


def test_rejects_an_unknown_lighting(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        main([str(_relief_fixture(tmp_path / "relief.3mf")), "--lighting", "disco"])


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


def _two_plates(path: Path) -> Path:
    return write_3mf(
        path,
        [FixtureObject("whole", [FixturePart("plate")]), FixtureObject("piece", [FixturePart("plate")])],
        ["#131313"],
        plates=[("whole-plate", ["whole"]), ("pieces-plate", ["piece"])],
    )


def test_skips_the_objects_of_skipped_plates(tmp_path: Path) -> None:
    output = tmp_path / "images"
    arguments = [str(_two_plates(tmp_path / "p.3mf")), "--output", str(output), "--skip-plate", "2"]

    assert main([*arguments, "--samples", "4", "--resolution", "160x90"]) == 0

    assert [path.name for path in output.iterdir()] == ["whole.png"]


def test_rejects_skipping_an_unknown_plate(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        main([str(_two_plates(tmp_path / "p.3mf")), "--skip-plate", "9"])

    assert "no plate 9" in capsys.readouterr().err


def test_skips_the_toolpaths_of_skipped_plates(tmp_path: Path) -> None:
    gcode = tmp_path / "gcode"
    gcode.mkdir()
    for index in (1, 2):
        (gcode / f"plate_{index}.gcode").write_text("\n".join(["; MACHINE_START_GCODE_END", *_square_layers(1, 20, 2)]))
    output = tmp_path / "images"
    arguments = [str(_two_plates(tmp_path / "p.3mf")), "--gcode", str(gcode), "--output", str(output)]

    assert main([*arguments, "--skip-plate", "2", "--samples", "4", "--resolution", "160x90"]) == 0

    assert [path.name for path in output.iterdir()] == ["whole.png"]


def test_renders_toolpaths_with_their_filament_colour(rendered_toolpaths: Path) -> None:
    reddish = _reddish(rendered_toolpaths / "coaster.png")

    assert reddish.any()
    assert not reddish.all()
