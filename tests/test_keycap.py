import pytest
from manifold3d import Manifold

from keycap import (
    BASE_GAP,
    CROSS_ARM,
    CROSS_LENGTH,
    HEIGHT,
    PITCH,
    STABILIZER_SPACING,
    STEM_DIAMETER,
    STEM_RECESS,
    TOP_INSET,
    TOP_THICKNESS,
    WALL,
    keycap,
)

PROBE = 0.02


def solid_at(shape: Manifold, x: float, y: float, z: float) -> bool:
    probe = Manifold.cube([PROBE, PROBE, PROBE], center=True).translate([x, y, z])
    return (shape ^ probe).volume() > PROBE**3 / 2


@pytest.fixture(scope="module")
def one_unit() -> Manifold:
    return keycap(units=1)


def test_fills_one_key_pitch_minus_the_gap_between_keys(one_unit: Manifold) -> None:
    low, high = one_unit.bounding_box()[:3], one_unit.bounding_box()[3:]

    assert high[0] - low[0] == pytest.approx(PITCH - BASE_GAP, abs=0.01)
    assert high[1] - low[1] == pytest.approx(PITCH - BASE_GAP, abs=0.01)
    assert (low[2], high[2]) == pytest.approx((0, HEIGHT), abs=0.01)


def test_is_a_single_watertight_solid(one_unit: Manifold) -> None:
    assert len(one_unit.decompose()) == 1
    assert one_unit.genus() == 0
    assert one_unit.volume() > 0


def test_lies_upside_down_with_a_flat_top_on_the_plate(one_unit: Manifold) -> None:
    top = PITCH - BASE_GAP - 2 * TOP_INSET
    face = one_unit.slice(PROBE)

    assert face.area() == pytest.approx(top**2, rel=0.03)
    assert face.num_contour() == 1


def test_top_is_thick_enough_to_hold_an_inlaid_logo(one_unit: Manifold) -> None:
    assert solid_at(one_unit, 5, 5, TOP_THICKNESS - 0.1)
    assert not solid_at(one_unit, 5, 5, TOP_THICKNESS + 0.1)


def test_opens_on_the_side_away_from_the_plate(one_unit: Manifold) -> None:
    base = PITCH - BASE_GAP
    opening = one_unit.slice(HEIGHT - PROBE)

    assert opening.area() == pytest.approx(base**2 - (base - 2 * WALL) ** 2, rel=0.03)
    assert not solid_at(one_unit, 0, 0, HEIGHT - PROBE)


def test_has_thin_walls_all_around(one_unit: Manifold) -> None:
    edge = (PITCH - BASE_GAP) / 2

    for x, y in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
        assert solid_at(one_unit, x * (edge - WALL / 2), y * (edge - WALL / 2), HEIGHT - 0.1)
        assert not solid_at(one_unit, x * (edge - WALL - 0.3), y * (edge - WALL - 0.3), HEIGHT - 0.1)


def test_has_a_cylindrical_stem_recessed_from_the_opening(one_unit: Manifold) -> None:
    ring = (STEM_DIAMETER / 2 + CROSS_LENGTH / 2) / 2
    depth = HEIGHT - STEM_RECESS

    assert solid_at(one_unit, ring * 0.7, ring * 0.7, depth - 0.1)
    assert not solid_at(one_unit, ring * 0.7, ring * 0.7, depth + 0.1)
    assert not solid_at(one_unit, STEM_DIAMETER / 2 + 0.2, 0, depth - 0.1)


@pytest.mark.parametrize("clearance", [0.0, 0.05, 0.15])
def test_cuts_a_cherry_mx_cross_with_the_given_clearance(clearance: float) -> None:
    shape = keycap(units=1, clearance=clearance)
    z = HEIGHT - STEM_RECESS - 1
    half_length = CROSS_LENGTH / 2 + clearance
    half_arm = CROSS_ARM / 2 + clearance

    assert not solid_at(shape, 0, 0, z)
    for x, y in [(1, 0), (0, 1)]:
        assert not solid_at(shape, x * (half_length - 0.03), y * (half_length - 0.03), z)
        assert solid_at(shape, x * (half_length + 0.05), y * (half_length + 0.05), z)
        assert not solid_at(shape, x * 1.5 + y * (half_arm - 0.03), y * 1.5 + x * (half_arm - 0.03), z)
        assert solid_at(shape, x * 1.5 + y * (half_arm + 0.05), y * 1.5 + x * (half_arm + 0.05), z)


def test_cross_is_deep_enough_for_the_switch_stem(one_unit: Manifold) -> None:
    opening = HEIGHT - STEM_RECESS

    assert not solid_at(one_unit, 0, 0, opening - 4.0)


@pytest.fixture(scope="module")
def two_units() -> Manifold:
    return keycap(units=2)


def test_two_units_span_two_key_pitches_minus_the_gap(two_units: Manifold) -> None:
    box = two_units.bounding_box()

    assert box[3] - box[0] == pytest.approx(2 * PITCH - BASE_GAP, abs=0.01)
    assert box[4] - box[1] == pytest.approx(PITCH - BASE_GAP, abs=0.01)
    assert len(two_units.decompose()) == 1


def test_two_units_have_a_cherry_stabilizer_stem_on_each_side(two_units: Manifold) -> None:
    z = HEIGHT - STEM_RECESS - 1
    ring = (STEM_DIAMETER / 2 + CROSS_LENGTH / 2) / 2 * 0.7

    for x in (-STABILIZER_SPACING / 2, 0, STABILIZER_SPACING / 2):
        assert not solid_at(two_units, x, 0, z)
        assert not solid_at(two_units, x + CROSS_LENGTH / 2 - 0.03, 0, z)
        assert solid_at(two_units, x + ring, ring, z)
        assert not solid_at(two_units, x + ring, ring, HEIGHT - STEM_RECESS + 0.1)


def test_stabilizer_stems_cut_the_same_cross_as_the_main_stem() -> None:
    shape = keycap(units=2, clearance=0.15)
    x, z = STABILIZER_SPACING / 2, HEIGHT - STEM_RECESS - 1

    assert not solid_at(shape, x + CROSS_LENGTH / 2 + 0.12, 0, z)
    assert solid_at(shape, x + CROSS_LENGTH / 2 + 0.2, 0, z)


@pytest.mark.parametrize(("units", "stems"), [(1, 1), (1.5, 1), (2, 3), (2.75, 3)])
def test_has_stabilizer_stems_from_two_units(units: float, stems: int) -> None:
    section = keycap(units=units).slice(HEIGHT - STEM_RECESS - 1)

    assert section.num_contour() == 2 + 2 * stems


@pytest.mark.parametrize("units", [0.5, 3, 6.25])
def test_rejects_sizes_without_a_known_stabilizer_layout(units: float) -> None:
    with pytest.raises(ValueError, match="units"):
        keycap(units=units)
