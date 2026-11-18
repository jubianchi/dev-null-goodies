from pathlib import Path

import numpy as np
import pytest

from conftest import FixtureObject, FixturePart, write_3mf
from keycap import INLAY_DEPTH, main
from test_export_stl import read_binary_stl, volume

PLATE = "20 0 0 0 10 0 0 0 2 0 0 0"
LEFT = "4 0 0 0 6 0 0 0 1 2 2 2"
RIGHT = "8 0 0 0 2 0 0 0 1 10 4 2"


def keychains(path: Path, models: tuple[str, ...] = ("small", "large")) -> Path:
    objects = []
    for size in models:
        for variant, background, first in (("dark", 1, 3), ("light", 3, 1)):
            objects.append(
                FixtureObject(
                    f"keychain-{size}-{variant}",
                    [
                        FixturePart("plate", extruder=background, transform=PLATE),
                        FixturePart("first-slash", extruder=first, transform=LEFT),
                        FixturePart("second-slash", extruder=2, transform=RIGHT),
                    ],
                )
            )
    return write_3mf(path, objects, ["#131313", "#C42430", "#ECECEB"])


@pytest.fixture(scope="module")
def exported(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("keycaps")
    out = root / "stl"
    assert main([str(keychains(root / "keychains.3mf")), "--output", str(out)]) == 0
    return out


def test_writes_one_stl_per_keycap_variant_and_filament(exported: Path) -> None:
    keycaps = [
        f"keycap-{size}-{variant}-{filament}.stl"
        for size in ("1u", "2u", "2u-mark")
        for variant in ("dark", "light")
        for filament in ("1-black", "2-red", "3-white")
    ]

    assert sorted(path.name for path in exported.iterdir()) == sorted([*keycaps, "keycap-clearance-coupon-1-black.stl"])


def test_puts_the_one_unit_mark_on_a_two_unit_keycap_for_a_04_mm_nozzle(exported: Path) -> None:
    _, two_units = read_binary_stl(exported / "keycap-2u-dark-1-black.stl")
    _, mark_body = read_binary_stl(exported / "keycap-2u-mark-dark-1-black.stl")
    _, one_unit_slash = read_binary_stl(exported / "keycap-1u-dark-2-red.stl")
    _, mark_slash = read_binary_stl(exported / "keycap-2u-mark-dark-2-red.stl")

    assert np.ptp(mark_body.reshape(-1, 3), axis=0) == pytest.approx(np.ptp(two_units.reshape(-1, 3), axis=0))
    assert np.ptp(mark_slash.reshape(-1, 3), axis=0) == pytest.approx(np.ptp(one_unit_slash.reshape(-1, 3), axis=0))


def test_keeps_the_filaments_of_the_keychain_logo(exported: Path) -> None:
    _, dark_body = read_binary_stl(exported / "keycap-1u-dark-1-black.stl")
    _, light_body = read_binary_stl(exported / "keycap-1u-light-3-white.stl")

    assert volume(exported / "keycap-1u-dark-1-black.stl") == pytest.approx(
        volume(exported / "keycap-1u-light-3-white.stl"), rel=1e-4
    )
    assert dark_body.reshape(-1, 3)[:, 2].max() == pytest.approx(light_body.reshape(-1, 3)[:, 2].max())


def test_inlays_the_logo_parts_at_the_same_origin_as_the_body(exported: Path) -> None:
    _, body = read_binary_stl(exported / "keycap-2u-dark-1-black.stl")
    _, slash = read_binary_stl(exported / "keycap-2u-dark-2-red.stl")
    body, slash = body.reshape(-1, 3), slash.reshape(-1, 3)

    assert slash[:, 2].min() == pytest.approx(0)
    assert slash[:, 2].max() == pytest.approx(INLAY_DEPTH)
    assert (slash[:, :2].min(axis=0) > body[:, :2].min(axis=0)).all()
    assert (slash[:, :2].max(axis=0) < body[:, :2].max(axis=0)).all()


def test_applies_the_clearance_to_the_stems(tmp_path: Path) -> None:
    source = keychains(tmp_path / "keychains.3mf")
    volumes = []
    for clearance in ("0", "0.2"):
        out = tmp_path / clearance
        main([str(source), "--output", str(out), "--clearance", clearance])
        volumes.append(volume(out / "keycap-1u-dark-1-black.stl"))

    assert volumes[0] > volumes[1]


def test_replaces_previously_generated_stl_files(tmp_path: Path) -> None:
    out = tmp_path / "stl"
    out.mkdir()
    (out / "keycap.stl").write_bytes(b"stale")

    main([str(keychains(tmp_path / "keychains.3mf")), "--output", str(out)])

    assert not (out / "keycap.stl").exists()


def test_rejects_a_project_without_the_keychain_logos(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        main([str(keychains(tmp_path / "keychains.3mf", models=("small",))), "--output", str(tmp_path / "stl")])

    assert "keychain-large-dark" in capsys.readouterr().err
