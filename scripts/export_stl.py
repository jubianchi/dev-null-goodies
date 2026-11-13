import argparse
from pathlib import Path

import numpy as np
from manifold3d import Manifold, Mesh, OpType
from numpy.typing import NDArray

from bambu3mf import Model, Part, read_project

STL_HEADER = b"dev-null-goodies".ljust(80, b" ")
STL_RECORD = np.dtype([("normal", "<f4", (3,)), ("vertices", "<f4", (3, 3)), ("attributes", "<u2")])
COLOUR_NAMES: dict[str, tuple[int, int, int]] = {
    "black": (0, 0, 0),
    "white": (255, 255, 255),
    "gray": (128, 128, 128),
    "red": (200, 30, 40),
    "orange": (240, 130, 30),
    "yellow": (240, 210, 40),
    "green": (40, 160, 70),
    "blue": (30, 90, 210),
    "purple": (130, 60, 170),
    "pink": (240, 130, 180),
    "brown": (120, 75, 40),
}


def colour_name(hex_colour: str) -> str:
    rgb = np.array([int(hex_colour.lstrip("#")[i : i + 2], 16) for i in (0, 2, 4)])
    return min(COLOUR_NAMES, key=lambda name: float(np.sum((rgb - np.array(COLOUR_NAMES[name])) ** 2)))


def write_binary_stl(path: Path, corners: NDArray[np.float64]) -> None:
    normals = np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0])
    lengths = np.linalg.norm(normals, axis=1, keepdims=True)
    normals = np.divide(normals, lengths, out=np.zeros_like(normals), where=lengths > 0)

    records = np.zeros(len(corners), dtype=STL_RECORD)
    records["normal"] = normals
    records["vertices"] = corners
    path.write_bytes(STL_HEADER + np.uint32(len(records)).tobytes() + records.tobytes())


def _bed_offset(model: Model) -> NDArray[np.float64]:
    vertices = np.concatenate([part.vertices for part in model.parts])
    low, high = vertices.min(axis=0), vertices.max(axis=0)
    return np.array([(low[0] + high[0]) / 2, (low[1] + high[1]) / 2, low[2]])


def _solid(part: Part, offset: NDArray[np.float64]) -> Manifold:
    mesh = Mesh(
        vert_properties=(part.vertices - offset).astype(np.float32),
        tri_verts=part.triangles.astype(np.uint32),
    )
    mesh.merge()
    return Manifold.batch_boolean(Manifold(mesh).decompose(), OpType.Add)


def filament_solids(model: Model) -> dict[int, Manifold]:
    offset = _bed_offset(model)
    covered = Manifold()
    regions: dict[int, list[Manifold]] = {}
    for part in reversed(model.parts):
        solid = _solid(part, offset)
        regions.setdefault(part.filament, []).append(solid - covered)
        covered = covered + solid
    return {filament: Manifold.batch_boolean(solids, OpType.Add) for filament, solids in sorted(regions.items())}


def _corners(solid: Manifold) -> NDArray[np.float64]:
    mesh = solid.to_mesh()
    vertices = np.asarray(mesh.vert_properties, dtype=np.float64)[:, :3]
    return vertices[np.asarray(mesh.tri_verts, dtype=np.int64)]


def export_stl(source: Path, output: Path) -> list[Path]:
    project = read_project(source)
    output.mkdir(parents=True, exist_ok=True)
    for stale in output.glob("*.stl"):
        stale.unlink()
    written: list[Path] = []
    for model in project.models:
        for filament, solid in filament_solids(model).items():
            if solid.is_empty():
                continue
            colour = colour_name(project.filament_colours[filament - 1])
            path = output / f"{model.name}-{filament}-{colour}.stl"
            write_binary_stl(path, _corners(solid))
            written.append(path)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export one STL per object and filament from a Bambu Studio 3MF.")
    parser.add_argument("source", type=Path, help="Bambu Studio .3mf project")
    parser.add_argument("--output", type=Path, help="output folder (default: stl/ next to the 3MF)")
    args = parser.parse_args(argv)

    for path in export_stl(args.source, args.output or args.source.parent / "stl"):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
