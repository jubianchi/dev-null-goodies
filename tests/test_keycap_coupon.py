import pytest
from manifold3d import CrossSection, Manifold

from keycap import (
    CLEARANCES,
    CROSS_LENGTH,
    HEIGHT,
    STEM_RECESS,
    TAB_LENGTH,
    TOP_THICKNESS,
    clearance_coupon,
)

PROBE = 0.02


def solid_at(shape: Manifold, x: float, y: float, z: float) -> bool:
    probe = Manifold.cube([PROBE, PROBE, PROBE], center=True).translate([x, y, z])
    return (shape ^ probe).volume() > PROBE**3 / 2


def stem_centre(tab: Manifold) -> tuple[float, float]:
    box = tab.slice(HEIGHT - STEM_RECESS - 0.1).bounds()
    return (box[0] + box[2]) / 2, (box[1] + box[3]) / 2


def test_tries_clearances_from_tight_to_loose() -> None:
    assert CLEARANCES == (0.0, 0.05, 0.1, 0.15, 0.2)
    assert [clearance for clearance, _ in clearance_coupon()] == list(CLEARANCES)


def test_lays_out_separate_tabs_side_by_side() -> None:
    tabs = [tab for _, tab in clearance_coupon()]

    for tab in tabs:
        assert len(tab.decompose()) == 1
    for left, right in zip(tabs, tabs[1:]):
        assert left.bounding_box()[3] < right.bounding_box()[0]


def test_each_tab_is_a_keycap_top_with_its_stem() -> None:
    for _, tab in clearance_coupon():
        box = tab.bounding_box()
        x, y = stem_centre(tab)
        assert (box[2], box[5]) == pytest.approx((0, HEIGHT - STEM_RECESS))
        assert solid_at(tab, x + 3.5, y, TOP_THICKNESS - 0.1)
        assert not solid_at(tab, x + 3.5, y, TOP_THICKNESS + 0.1)


def test_each_stem_cuts_the_cross_with_its_clearance() -> None:
    z = HEIGHT - STEM_RECESS - 1
    for clearance, tab in clearance_coupon():
        x, y = stem_centre(tab)
        half = CROSS_LENGTH / 2 + clearance
        assert not solid_at(tab, x + half - 0.015, y, z)
        assert solid_at(tab, x + half + 0.015, y, z)


def test_marks_each_tab_with_as_many_notches_as_its_rank() -> None:
    for rank, (_, tab) in enumerate(clearance_coupon(), start=1):
        box = tab.bounding_box()
        edge = CrossSection.square([box[3] - box[0] + 2, 0.4]).translate([box[0] - 1, box[1] + 0.1])
        teeth = tab.slice(TOP_THICKNESS / 2) ^ edge

        assert len(teeth.decompose()) == rank + 1
        assert box[4] - box[1] == pytest.approx(TAB_LENGTH)
