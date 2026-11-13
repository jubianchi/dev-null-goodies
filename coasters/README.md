# /dev/null coaster

> Pipe your coffee to /dev/null. It won't leak.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="images/coaster-light.png">
  <img alt="/dev/null coaster" src="images/coaster-dark.png">
</picture>

[Print it on MakerWorld](TODO(MakerWorld URL))

The coaster is printed without top surface: the Hilbert curve infill stays visible and gives it its texture. The renders
are made from the sliced toolpaths, so they show what comes out of the printer.

## Variants

| Dark | Light |
| --- | --- |
| ![coaster-dark](images/coaster-dark.png) | ![coaster-light](images/coaster-light.png) |

## Files

| File | Description |
| --- | --- |
| `coasters.3mf` | Bambu Studio project: one plate per coaster, colors and per-part settings already assigned |
| `stl/*.stl` | One STL per coaster and filament, for other slicers, generated from `coasters.3mf` |
| `images/*.png` | One render per coaster, generated from the sliced `coasters.3mf` |
| `MAKERWORLD.md` | Description posted on MakerWorld |

## Print settings

| Setting | Value |
| --- | --- |
| Profile | 0.20mm Standard @BBL H2S |
| Layer height | 0.2 mm |
| Top shell layers | 0 (coaster body only) |
| Infill | 10 % Hilbert curve (coaster body only) |
| Supports | None |
| Colors | 3 PLA (Basic black `#000000`, Matte red `#BB3D43`, Matte white `#FFFFFF`): AMS, or filament swaps |
| Size | Ø 120 mm, 5 mm thick |
| Print time | ~2 h, as estimated by Bambu Studio |
| Filament | ~55 g |

The top shell and infill settings only apply to the coaster body (`*-1-black.stl` for the dark coaster,
`*-3-white.stl` for the light one), the logo keeps a regular top surface. STL files cannot carry these per-part
settings: set them on the body part in your slicer, or use the 3MF.
