import argparse
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from bambu3mf import Model, read_project

STL_HEADER = b"dev-null-goodies".ljust(80, b" ")
STL_RECORD = np.dtype([("normal", "<f4", (3,)), ("vertices", "<f4", (3, 3)), ("attributes", "<u2")])


def write_binary_stl(path: Path, corners: NDArray[np.float64]) -> None:
    normals = np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0])
    lengths = np.linalg.norm(normals, axis=1, keepdims=True)
    normals = np.divide(normals, lengths, out=np.zeros_like(normals), where=lengths > 0)

    records = np.zeros(len(corners), dtype=STL_RECORD)
    records["normal"] = normals
    records["vertices"] = corners
    path.write_bytes(STL_HEADER + np.uint32(len(records)).tobytes() + records.tobytes())


def _centred_on_bed(model: Model) -> NDArray[np.float64]:
    corners = np.concatenate([part.vertices[part.triangles] for part in model.parts])
    low, high = corners.reshape(-1, 3).min(axis=0), corners.reshape(-1, 3).max(axis=0)
    return corners - np.array([(low[0] + high[0]) / 2, (low[1] + high[1]) / 2, low[2]])


def export_stl(source: Path, output: Path) -> list[Path]:
    output.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for model in read_project(source).models:
        path = output / f"{model.name}.stl"
        write_binary_stl(path, _centred_on_bed(model))
        written.append(path)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export one STL per object from a Bambu Studio 3MF.")
    parser.add_argument("source", type=Path, help="Bambu Studio .3mf project")
    parser.add_argument("--output", type=Path, help="output folder (default: stl/ next to the 3MF)")
    args = parser.parse_args(argv)

    for path in export_stl(args.source, args.output or args.source.parent / "stl"):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
