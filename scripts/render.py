import argparse
import os
import shutil
import subprocess
from pathlib import Path

SCENE_SCRIPT = Path(__file__).resolve().parent / "blender_render.py"
MACOS_BLENDER = Path("/Applications/Blender.app/Contents/MacOS/Blender")


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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render one PNG per object of a Bambu Studio 3MF with Blender.")
    parser.add_argument("source", type=Path, help="Bambu Studio .3mf project")
    parser.add_argument("--output", type=Path, help="output folder (default: images/ next to the 3MF)")
    parser.add_argument("--samples", type=int, default=128, help="Cycles samples per pixel (default: 128)")
    parser.add_argument("--resolution", type=_resolution, default=(1600, 900), help="WIDTHxHEIGHT (default: 1600x900)")
    args = parser.parse_args(argv)

    blender = find_blender()
    if blender is None:
        parser.error("Blender not found: install it or set the BLENDER environment variable")

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
    ]
    return subprocess.run(command, check=False, stdout=subprocess.DEVNULL).returncode


if __name__ == "__main__":
    raise SystemExit(main())
