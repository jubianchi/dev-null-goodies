from pathlib import Path

import numpy as np
import pytest
from manifold3d import CrossSection, JoinType, Manifold

from bambu3mf import Model, Part, read_project
from keycap import (
    INLAY_DEPTH,
    MIN_OUTLINE_WIDTH,
    Logo,
    LogoPart,
    fit_logo,
    keycap,
    keycap_parts,
    read_logo,
    thicken_outlines,
    thin_parts,
)

REPOSITORY = Path(__file__).parent.parent
CUBE_VERTICES = np.array(
    [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0), (0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)], dtype=np.float64
)
CUBE_TRIANGLES = np.array(
    [(0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7), (0, 1, 5), (0, 5, 4), (1, 2, 6), (1, 6, 5), (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7)],
    dtype=np.int64,
)


def box_part(name: str, filament: int, low: tuple[float, float, float], high: tuple[float, float, float]) -> Part:
    return Part(name, filament, CUBE_VERTICES * (np.array(high) - np.array(low)) + np.array(low), CUBE_TRIANGLES)


def fixture_model() -> Model:
    return Model(
        "keychain-dark",
        (
            box_part("plate", 1, (0, 0, 0), (20, 10, 2)),
            box_part("left", 3, (2, 2, 2), (6, 8, 3)),
            box_part("right", 2, (10, 4, 2), (18, 6, 3)),
        ),
    )


def fitted_logo() -> Logo:
    return fit_logo(read_logo(fixture_model()), 8, 8)


def test_reads_the_logo_parts_and_the_background_filament_from_a_keychain() -> None:
    logo = read_logo(fixture_model())

    assert logo.background == 1
    assert [(part.name, part.filament) for part in logo.parts] == [("left", 3), ("right", 2)]


def test_centres_the_logo_on_the_origin() -> None:
    bounds = np.array([part.outline.bounds() for part in read_logo(fixture_model()).parts])

    assert (bounds[:, 0].min(), bounds[:, 1].min()) == pytest.approx((-8, -3))
    assert (bounds[:, 2].max(), bounds[:, 3].max()) == pytest.approx((8, 3))


def test_scales_the_logo_to_fit_a_box_keeping_its_proportions() -> None:
    bounds = np.array([part.outline.bounds() for part in fitted_logo().parts])

    assert (bounds[:, 0].min(), bounds[:, 1].min()) == pytest.approx((-4, -1.5))
    assert (bounds[:, 2].max(), bounds[:, 3].max()) == pytest.approx((4, 1.5))


def test_splits_the_keycap_into_one_solid_per_filament() -> None:
    parts = keycap_parts(1, fitted_logo())

    assert sorted(parts) == [1, 2, 3]
    assert sum(solid.volume() for solid in parts.values()) == pytest.approx(keycap(1).volume(), rel=1e-4)


def test_inlays_the_logo_flush_with_the_top_face_on_the_plate() -> None:
    parts = keycap_parts(1, fitted_logo())

    for filament in (2, 3):
        box = parts[filament].bounding_box()
        assert (box[2], box[5]) == pytest.approx((0, INLAY_DEPTH))
    assert parts[3].volume() == pytest.approx(2 * 3 * INLAY_DEPTH, rel=1e-3)
    assert parts[2].volume() == pytest.approx(4 * 1 * INLAY_DEPTH, rel=1e-3)


def test_logo_and_body_do_not_overlap() -> None:
    parts = keycap_parts(1, fitted_logo())

    for filament in (2, 3):
        assert (parts[1] ^ parts[filament]).volume() == pytest.approx(0, abs=1e-6)


def test_keeps_the_logo_readable_once_the_printed_keycap_is_turned_over() -> None:
    model = Model(
        "keychain-dark",
        (
            box_part("plate", 1, (0, 0, 0), (20, 10, 2)),
            box_part("upper-left", 3, (2, 6, 2), (6, 8, 3)),
            box_part("lower-right", 2, (14, 2, 2), (18, 4, 3)),
        ),
    )
    parts = keycap_parts(1, fit_logo(read_logo(model), 8, 8))

    upright = {filament: solid.rotate([180, 0, 0]) for filament, solid in parts.items()}
    upper_left, lower_right = upright[3].bounding_box(), upright[2].bounding_box()
    assert upper_left[3] < 0 and upper_left[1] > 0
    assert lower_right[0] > 0 and lower_right[4] < 0


def test_rejects_a_logo_larger_than_the_top_face() -> None:
    with pytest.raises(ValueError, match="top face"):
        keycap_parts(1, fit_logo(read_logo(fixture_model()), 16, 16))


def test_finds_logo_parts_thinner_than_the_line_width() -> None:
    model = Model(
        "keychain-dark",
        (
            box_part("plate", 1, (0, 0, 0), (20, 10, 2)),
            box_part("wide", 3, (2, 2, 2), (6, 8, 3)),
            box_part("thin", 2, (10, 2, 2), (10.2, 8, 3)),
        ),
    )
    logo = read_logo(model)

    assert thin_parts(logo, 0.4) == ["thin"]
    assert thin_parts(logo, 0.1) == []


def ring_logo(wall: float) -> Logo:
    ring = CrossSection.square([4, 4], center=True) - CrossSection.square([4 - 2 * wall, 4 - 2 * wall], center=True)
    return Logo(1, (LogoPart("ring", 2, ring), LogoPart("solid", 3, CrossSection.square([1, 1]).translate([5, 0]))))


def test_thickens_thin_outlines_inward_up_to_the_minimum_width() -> None:
    thickened = thicken_outlines(ring_logo(0.1), 0.3).parts[0].outline

    band = CrossSection.square([4, 4], center=True) - CrossSection.square([3.4, 3.4], center=True)
    assert (band - thickened).area() == pytest.approx(0, abs=1e-6)
    assert thickened.bounds() == pytest.approx((-2, -2, 2, 2))
    assert thickened.area() == pytest.approx(16 - 3.4**2, rel=1e-3)


def test_leaves_wide_enough_outlines_and_solid_parts_unchanged() -> None:
    logo = ring_logo(0.5)
    thickened = thicken_outlines(logo, 0.3)

    for before, after in zip(logo.parts, thickened.parts):
        assert after.outline.area() == pytest.approx(before.outline.area())
        assert (after.name, after.filament) == (before.name, before.filament)


def test_two_unit_logo_outlines_are_thickened_for_a_02_mm_nozzle() -> None:
    project = read_project(REPOSITORY / "keychains" / "keychains.3mf")
    model = next(model for model in project.models if model.name == "keychain-large-dark")
    logo = thicken_outlines(fit_logo(read_logo(model), 30, 11), MIN_OUTLINE_WIDTH)

    for part in logo.parts:
        filled = CrossSection([contour for contour in part.outline.to_polygons() if signed_area(contour) > 0])
        band = filled - filled.offset(-MIN_OUTLINE_WIDTH, JoinType.Miter)
        assert (band - part.outline).area() == pytest.approx(0, abs=1e-4), part.name
    assert sorted(keycap_parts(2, logo)) == [1, 2, 3]


def signed_area(contour: np.ndarray) -> float:
    x, y = np.asarray(contour)[:, 0], np.asarray(contour)[:, 1]
    return float(np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y) / 2)


def test_one_unit_mark_prints_with_a_04_mm_nozzle() -> None:
    project = read_project(REPOSITORY / "keychains" / "keychains.3mf")
    model = next(model for model in project.models if model.name == "keychain-small-dark")
    logo = fit_logo(read_logo(model), 11, 11)

    assert thin_parts(logo, 0.4) == []
    assert isinstance(keycap_parts(1, logo)[1], Manifold)
