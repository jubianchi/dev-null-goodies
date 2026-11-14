import argparse
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

SCENE_SCRIPT = Path(__file__).resolve().parent / "blender_render.py"
MACOS_BLENDER = Path("/Applications/Blender.app/Contents/MacOS/Blender")
MACOS_BAMBU_STUDIO = Path("/Applications/BambuStudio.app/Contents/MacOS/BambuStudio")
LIGHTINGS = ("front", "far", "far-rough", "back-right", "side-low")


def find_blender() -> str | None:
    if candidate := os.environ.get("BLENDER"):
        return candidate
    if candidate := shutil.which("blender"):
        return candidate
    return str(MACOS_BLENDER) if MACOS_BLENDER.is_file() else None


def _resolution(value: str) -> tuple[int, int]:
    width, _, height = value.partition("x")
    try:
        return int(width), int(height)
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected WIDTHxHEIGHT, got {value!r}") from None


def find_bambu_studio() -> str | None:
    if candidate := os.environ.get("BAMBU_STUDIO"):
        return candidate
    if candidate := shutil.which("bambu-studio"):
        return candidate
    return str(MACOS_BAMBU_STUDIO) if MACOS_BAMBU_STUDIO.is_file() else None


def slice_plates(bambu_studio: str, source: Path, output: Path) -> int:
    command = [bambu_studio, "--slice", "0", "--outputdir", str(output.resolve()), str(source.resolve())]
    return subprocess.run(
        command, check=False, cwd=output, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    ).returncode


def _render(blender: str, args: argparse.Namespace, gcode: Path | None) -> int:
    width, height = args.resolution
    command = [
        blender,
        "--background",
        "--factory-startup",
        "--python-exit-code",
        "1",
        "--python",
        str(SCENE_SCRIPT),
        "--",
        str(args.source.resolve()),
        str((args.output or args.source.parent / "images").resolve()),
        str(args.samples),
        str(width),
        str(height),
        str(gcode.resolve()) if gcode else "",
        args.view,
        str(args.exposure),
        args.lighting,
    ]
    return subprocess.run(command, check=False, stdout=subprocess.DEVNULL).returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render one PNG per object of a Bambu Studio 3MF with Blender.")
    parser.add_argument("source", type=Path, help="Bambu Studio .3mf project")
    parser.add_argument("--output", type=Path, help="output folder (default: images/ next to the 3MF)")
    parser.add_argument("--samples", type=int, default=128, help="Cycles samples per pixel (default: 128)")
    parser.add_argument("--resolution", type=_resolution, default=(1600, 900), help="WIDTHxHEIGHT (default: 1600x900)")
    parser.add_argument(
        "--view", choices=("three-quarter", "top"), default="three-quarter", help="camera view (default: three-quarter)"
    )
    parser.add_argument(
        "--exposure", type=float, default=0.0, help="exposure in stops, negative to darken (default: 0)"
    )
    parser.add_argument("--lighting", choices=LIGHTINGS, default="front", help="lighting preset (default: front)")
    toolpaths = parser.add_mutually_exclusive_group()
    toolpaths.add_argument(
        "--toolpaths", action="store_true", help="slice with Bambu Studio and render one PNG per plate from the G-code"
    )
    toolpaths.add_argument("--gcode", type=Path, help="render one PNG per plate from already sliced plate_N.gcode files")
    args = parser.parse_args(argv)

    blender = find_blender()
    if blender is None:
        parser.error("Blender not found: install it or set the BLENDER environment variable")

    if not args.toolpaths:
        return _render(blender, args, args.gcode)

    bambu_studio = find_bambu_studio()
    if bambu_studio is None:
        parser.error("Bambu Studio not found: install it or set the BAMBU_STUDIO environment variable")
    with tempfile.TemporaryDirectory() as directory:
        status = slice_plates(bambu_studio, args.source, Path(directory))
        return status or _render(blender, args, Path(directory))


if __name__ == "__main__":
    raise SystemExit(main())
