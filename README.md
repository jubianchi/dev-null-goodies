# /dev/null goodies

> Things you can print. Unlike everything else you send to /dev/null, they come back.

Unofficial, fan-made printable goodies based on the logo of [/dev/null](https://dev-null.sh), the open-source social
network where developers commit messages to the log ([source code](https://github.com/dev-null-sh/dev-null.sh)).

## Goodies

| Preview | Goodie | Description | Print it |
| --- | --- | --- | --- |
| <picture><source media="(prefers-color-scheme: dark)" srcset="keychains/images/keychain-large-light.png"><img alt="/dev/null keychains" src="keychains/images/keychain-large-dark.png"></picture> | [Keychains](keychains/) | The /dev/null logo, on your keys. | [Print it on MakerWorld](https://makerworld.com/en/models/3611268-dev-null-keychains) |
| <picture><source media="(prefers-color-scheme: dark)" srcset="coasters/images/coaster-light.png"><img alt="/dev/null coasters" src="coasters/images/coaster-dark.png"></picture> | [Coasters](coasters/) | The /dev/null logo, under your mug. | [Print it on MakerWorld](TODO(MakerWorld URL)) |
| <picture><source media="(prefers-color-scheme: dark)" srcset="iron-on/images/iron-on-light.png"><img alt="/dev/null iron-on transfer" src="iron-on/images/iron-on-dark.png"></picture> | [Iron-on transfer](iron-on/) | The /dev/null logo, on your t-shirt. | [Print it on MakerWorld](TODO(MakerWorld URL)) |

More goodies may land here later. Follow the [/dev/null collection](https://makerworld.com/en/collections/40672455-dev-null)
on MakerWorld to get them all.

## Printing

- Each goodie ships a `.3mf` file with ready-to-print Bambu Studio plates and colors.
- Each goodie also has a `stl/` folder for other slicers, with one STL per object and filament, named
  `<object>-<filament>-<color>.stl`. Import the STLs of an object together as parts of a single object and assign each
  one its filament: they share the same origin, so they line up, and they never overlap.

## Tooling

The STL files and the renders are generated from the `.3mf` projects. The tooling requires
[uv](https://docs.astral.sh/uv/), and the renders require [Blender](https://www.blender.org/) (found on the `PATH`, in
`/Applications` on macOS, or through the `BLENDER` environment variable).

```console
$ uv run scripts/export_stl.py keychains/keychains.3mf   # writes keychains/stl/<object>-<filament>-<color>.stl
$ uv run scripts/render.py keychains/keychains.3mf       # writes keychains/images/<object>.png
$ uv run pytest
```

`render.py` accepts `--resolution WIDTHxHEIGHT` (default `1600x900`), `--samples N` (default `128`) and
`--view three-quarter|top` (default `three-quarter`). Flat goodies read better from the top:

```console
$ uv run scripts/render.py <goodie>/<goodie>.3mf --view top
```

Some goodies only show their look once sliced (e.g. coasters printed without top surface, so the infill pattern is
visible). For those, `--toolpaths` slices the project with [Bambu Studio](https://bambulab.com/en/download/studio)
(found on the `PATH`, in `/Applications` on macOS, or through the `BAMBU_STUDIO` environment variable) and renders the
G-code toolpaths, one image per plate:

```console
$ uv run scripts/render.py coasters/coasters.3mf --toolpaths
```

`--gcode DIR` renders already sliced `plate_N.gcode` files instead.

## Changelog

The changelog is the [git history](../../commits/main): there are no releases, the `main` branch is always the latest
version.

## Contributing

Remixes, new variants and photos of your prints are welcome: open an issue or a pull request.

Printed one? Commit it to the log on [/dev/null](https://dev-null.sh) and tag @jubianchi.

## License

This repository holds three kinds of content, under different terms:

| Content | License |
| --- | --- |
| Models: `.3mf` projects, STL files, renders and descriptions | [CC BY-NC-SA 4.0](LICENSE) |
| Code: `scripts/`, `tests/` and the Python project files | [MIT](LICENSE-MIT) |
| The /dev/null name and logo | Not licensed by this repository, see below |

The /dev/null name and logo belong to the /dev/null project, and all rights to them are reserved by their owners: neither
license above covers them. This is an unofficial fan project, not affiliated with or endorsed by /dev/null. The logo is
used in line with the [/dev/null brand guidelines](https://dev-null.sh/brand) and the
[/dev/null terms](https://dev-null.sh/terms).
