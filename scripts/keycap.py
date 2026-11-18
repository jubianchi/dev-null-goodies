import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from manifold3d import CrossSection, JoinType, Manifold, Mesh, OpType

from bambu3mf import Model, read_project
from export_stl import _corners, colour_name, write_binary_stl

PITCH = 19.05
BASE_GAP = 0.85
HEIGHT = 8.0
TOP_INSET = 1.6
TOP_CHAMFER = 0.8
TOP_THICKNESS = 1.5
WALL = 1.2
CORNER = 1.5
STEM_DIAMETER = 5.5
STEM_RECESS = 0.5
CROSS_LENGTH = 4.0
CROSS_ARM = 1.17
CROSS_DEPTH = 4.5
STABILIZER_SPACING = 23.876
INLAY_DEPTH = 0.6
MIN_OUTLINE_WIDTH = 0.3
SEGMENTS = 64
THIN_TOLERANCE = 0.02
CLEARANCES = (0.0, 0.05, 0.1, 0.15, 0.2)
TAB_WIDTH = 10.0
TAB_LENGTH = 16.0
TAB_GAP = 3.0
NOTCH_WIDTH = 0.7
NOTCH_DEPTH = 2.0
REPOSITORY = Path(__file__).resolve().parent.parent
LAYOUTS: dict[str, tuple[float, str, tuple[float, float], float | None]] = {
    "1u": (1, "keychain-small", (11, 11), None),
    "2u": (2, "keychain-large", (30, 11), MIN_OUTLINE_WIDTH),
    "2u-mark": (2, "keychain-small", (11, 11), None),
}
VARIANTS = ("dark", "light")


@dataclass(frozen=True)
class LogoPart:
    name: str
    filament: int
    outline: CrossSection


@dataclass(frozen=True)
class Logo:
    background: int
    parts: tuple[LogoPart, ...]

    def bounds(self) -> tuple[float, float, float, float]:
        corners = np.array([part.outline.bounds() for part in self.parts])
        return corners[:, 0].min(), corners[:, 1].min(), corners[:, 2].max(), corners[:, 3].max()


def rounded_rectangle(width: float, depth: float, radius: float) -> CrossSection:
    return CrossSection.square([width - 2 * radius, depth - 2 * radius], center=True).offset(
        radius, circular_segments=SEGMENTS
    )


def _frustum(width: float, depth: float, inset: float, radius: float, height: float) -> Manifold:
    return rounded_rectangle(width, depth, radius).extrude(
        height, scale_top=((width - 2 * inset) / width, (depth - 2 * inset) / depth)
    )


def _section(width: float, depth: float, inset: float, radius: float, height: float, z: float) -> CrossSection:
    shrink = 2 * inset * z / height
    return rounded_rectangle(width, depth, radius).scale(((width - shrink) / width, (depth - shrink) / depth))


def _lifted(section: CrossSection, z: float) -> np.ndarray:
    points = np.concatenate(section.to_polygons())
    return np.column_stack([points, np.full(len(points), z)])


def _chamfered_frustum(width: float, depth: float, inset: float, radius: float, height: float) -> Manifold:
    shoulder = _section(width, depth, inset, radius, height, height - TOP_CHAMFER)
    top = shoulder.offset(-TOP_CHAMFER, JoinType.Round, circular_segments=SEGMENTS)
    return Manifold.hull_points(
        np.concatenate(
            [
                _lifted(rounded_rectangle(width, depth, radius), 0),
                _lifted(shoulder, height - TOP_CHAMFER),
                _lifted(top, height),
            ]
        )
    )


def top_face(units: float) -> CrossSection:
    """Return the flat top face of a keycap, inside its chamfer."""
    width, depth = PITCH * units - BASE_GAP, PITCH - BASE_GAP
    return _section(width, depth, TOP_INSET, CORNER, HEIGHT, HEIGHT - TOP_CHAMFER).offset(
        -TOP_CHAMFER, JoinType.Round, circular_segments=SEGMENTS
    )


def _stem(clearance: float) -> Manifold:
    length = HEIGHT - TOP_THICKNESS - STEM_RECESS
    cylinder = Manifold.cylinder(length, STEM_DIAMETER / 2, circular_segments=SEGMENTS)
    long_side, short_side = CROSS_LENGTH + 2 * clearance, CROSS_ARM + 2 * clearance
    cross = (
        CrossSection.square([long_side, short_side], center=True)
        + CrossSection.square([short_side, long_side], center=True)
    ).extrude(CROSS_DEPTH + 1).translate([0, 0, -1])
    return (cylinder - cross).translate([0, 0, STEM_RECESS])


def stem_offsets(units: float) -> tuple[float, ...]:
    if 1 <= units < 2:
        return (0.0,)
    if 2 <= units <= 2.75:
        return (-STABILIZER_SPACING / 2, 0.0, STABILIZER_SPACING / 2)
    raise ValueError(f"no stabilizer layout for {units} units, expected 1 to 2.75 units")


def keycap(units: float = 1, clearance: float = 0.05) -> Manifold:
    """Return a flat-top keycap upside down, top face on the plate (z = 0), opening upward."""
    offsets = stem_offsets(units)
    width, depth = PITCH * units - BASE_GAP, PITCH - BASE_GAP
    outer = _chamfered_frustum(width, depth, TOP_INSET, CORNER, HEIGHT)
    inner_height = HEIGHT - TOP_THICKNESS
    inner_inset = TOP_INSET * inner_height / HEIGHT
    inner = _frustum(width - 2 * WALL, depth - 2 * WALL, inner_inset, max(CORNER - WALL, 0.2), inner_height)
    stem = _stem(clearance)
    stems = Manifold.batch_boolean([stem.translate([x, 0, 0]) for x in offsets], OpType.Add)
    upright = (outer - inner.translate([0, 0, -0.01])) + stems
    return upright.mirror([0, 0, 1]).translate([0, 0, HEIGHT])


def _clearance_tab(clearance: float, notches: int) -> Manifold:
    stem_margin = STEM_DIAMETER / 2 + 2.25
    plate = rounded_rectangle(TAB_WIDTH, TAB_LENGTH, CORNER).translate([0, stem_margin - TAB_LENGTH / 2])
    edge = stem_margin - TAB_LENGTH
    slots = CrossSection.batch_boolean(
        [
            CrossSection.square([NOTCH_WIDTH, NOTCH_DEPTH + 1]).translate(
                [(2 * index - notches + 0.5) * NOTCH_WIDTH, edge - 1]
            )
            for index in range(notches)
        ],
        OpType.Add,
    )
    top = (plate - slots).extrude(TOP_THICKNESS).translate([0, 0, HEIGHT - TOP_THICKNESS])
    return (top + _stem(clearance)).mirror([0, 0, 1]).translate([0, 0, HEIGHT])


def clearance_coupon(clearances: tuple[float, ...] = CLEARANCES) -> list[tuple[float, Manifold]]:
    """Return one keycap top and stem per clearance, side by side, marked with as many notches as its rank."""
    return [
        (clearance, _clearance_tab(clearance, rank + 1).translate([rank * (TAB_WIDTH + TAB_GAP), 0, 0]))
        for rank, clearance in enumerate(clearances)
    ]


def _outline(vertices: np.ndarray, triangles: np.ndarray) -> CrossSection:
    mesh = Mesh(vert_properties=vertices.astype(np.float32), tri_verts=triangles.astype(np.uint32))
    mesh.merge()
    return Manifold(mesh).project()


def read_logo(model: Model) -> Logo:
    """Return the logo of a keychain model seen from above, centred on the origin, without its plate."""
    background = next(part.filament for part in model.parts if part.name == "plate")
    parts = [
        LogoPart(part.name, part.filament, _outline(part.vertices, part.triangles))
        for part in model.parts
        if part.name != "plate"
    ]
    low_x, low_y, high_x, high_y = Logo(background, tuple(parts)).bounds()
    centre = (-(low_x + high_x) / 2, -(low_y + high_y) / 2)
    return Logo(background, tuple(LogoPart(p.name, p.filament, p.outline.translate(centre)) for p in parts))


def fit_logo(logo: Logo, width: float, height: float) -> Logo:
    low_x, low_y, high_x, high_y = logo.bounds()
    factor = min(width / (high_x - low_x), height / (high_y - low_y))
    return Logo(
        logo.background,
        tuple(LogoPart(p.name, p.filament, p.outline.scale((factor, factor))) for p in logo.parts),
    )


def thin_parts(logo: Logo, line_width: float) -> list[str]:
    """Return the logo parts that lose area when every feature narrower than the line width is removed."""
    thin = []
    for part in logo.parts:
        opened = part.outline.offset(-line_width / 2, JoinType.Round, circular_segments=SEGMENTS).offset(
            line_width / 2, JoinType.Round, circular_segments=SEGMENTS
        )
        if part.outline.area() - opened.area() > THIN_TOLERANCE * part.outline.area():
            thin.append(part.name)
    return thin


def _signed_area(contour: np.ndarray) -> float:
    x, y = np.asarray(contour)[:, 0], np.asarray(contour)[:, 1]
    return float(np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y) / 2)


def thicken_outlines(logo: Logo, width: float) -> Logo:
    """Widen every stroke narrower than the width inward, keeping the outer silhouette of each part."""
    parts = []
    for part in logo.parts:
        filled = CrossSection([c for c in part.outline.to_polygons() if _signed_area(c) > 0])
        band = filled - filled.offset(-width, JoinType.Miter)
        parts.append(LogoPart(part.name, part.filament, part.outline + band))
    return Logo(logo.background, tuple(parts))


def keycap_parts(units: float, logo: Logo, clearance: float = 0.05) -> dict[int, Manifold]:
    """Split the keycap into one solid per filament, the logo inlaid in the top face on the plate."""
    outlines = CrossSection.batch_boolean([part.outline for part in logo.parts], OpType.Add)
    if not (outlines - top_face(units)).is_empty():
        raise ValueError("the logo does not fit on the top face of the keycap")

    covered = Manifold()
    regions: dict[int, list[Manifold]] = {}
    for part in reversed(logo.parts):
        # The printed keycap is turned over to be used, which mirrors the top face: print the logo mirrored.
        solid = part.outline.mirror([0, 1]).extrude(INLAY_DEPTH)
        regions.setdefault(part.filament, []).append(solid - covered)
        covered = covered + solid
    regions.setdefault(logo.background, []).append(keycap(units, clearance) - covered)
    return {filament: Manifold.batch_boolean(solids, OpType.Add) for filament, solids in sorted(regions.items())}


def export_keycaps(source: Path, output: Path, clearance: float) -> list[Path]:
    project = read_project(source)
    models = {model.name: model for model in project.models}
    needed = [f"{keychain}-{variant}" for _, keychain, _, _ in LAYOUTS.values() for variant in VARIANTS]
    if missing := [name for name in needed if name not in models]:
        raise ValueError(f"missing keychain logos in {source}: {', '.join(missing)}")

    shapes: dict[str, dict[int, Manifold]] = {}
    for size, (units, keychain, box, outline_width) in LAYOUTS.items():
        for variant in VARIANTS:
            logo = fit_logo(read_logo(models[f"{keychain}-{variant}"]), *box)
            if outline_width is not None:
                logo = thicken_outlines(logo, outline_width)
            shapes[f"keycap-{size}-{variant}"] = keycap_parts(units, logo, clearance)
    coupon = Manifold.batch_boolean([tab for _, tab in clearance_coupon()], OpType.Add)
    shapes["keycap-clearance-coupon"] = {1: coupon}

    output.mkdir(parents=True, exist_ok=True)
    for stale in output.glob("*.stl"):
        stale.unlink()
    written = []
    for name, solids in shapes.items():
        for filament, solid in solids.items():
            path = output / f"{name}-{filament}-{colour_name(project.filament_colours[filament - 1])}.stl"
            write_binary_stl(path, _corners(solid))
            written.append(path)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate the /dev/null keycaps, one STL per keycap and filament.")
    parser.add_argument(
        "source",
        type=Path,
        nargs="?",
        default=REPOSITORY / "keychains" / "keychains.3mf",
        help="Bambu Studio .3mf project holding the keychain logos (default: keychains/keychains.3mf)",
    )
    parser.add_argument(
        "--output", type=Path, default=REPOSITORY / "keycaps" / "stl", help="output folder (default: keycaps/stl)"
    )
    parser.add_argument(
        "--clearance", type=float, default=0.05, help="gap around the stem cross, per side, in mm (default: 0.05)"
    )
    args = parser.parse_args(argv)

    try:
        written = export_keycaps(args.source, args.output, args.clearance)
    except ValueError as error:
        parser.error(str(error))
    for path in written:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
