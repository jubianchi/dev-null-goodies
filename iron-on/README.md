# /dev/null iron-on transfer

> Everything you write to /dev/null disappears. This one sticks.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="images/iron-on-light.png">
  <img alt="/dev/null iron-on transfer" src="images/iron-on-dark.png">
</picture>

[Print it on MakerWorld](TODO(MakerWorld URL))

The /dev/null logo and wordmark printed in two 0.08 mm layers, then ironed onto a t-shirt.

## Variants

| Dark (for light fabrics) | Light (for dark fabrics) |
| --- | --- |
| ![iron-on-dark](images/iron-on-dark.png) | ![iron-on-light](images/iron-on-light.png) |

## Files

| File | Description |
| --- | --- |
| `iron-on.3mf` | Bambu Studio project: one plate per transfer, colors already assigned |
| `stl/*.stl` | One STL per transfer and filament, for other slicers, generated from `iron-on.3mf` |
| `images/*.png` | One render per transfer, generated from `iron-on.3mf` |
| `MAKERWORLD.md` | Description posted on MakerWorld |

## Print settings

| Setting | Value |
| --- | --- |
| Profile | 0.08mm High Quality @BBL H2S |
| Layer height | 0.08 mm, 2 layers (0.16 mm thick) |
| Build plate | Textured PEI |
| Supports | None |
| Colors | 2 PLA per transfer: black `#131313` and red `#C42430` (dark), white `#ECECEB` and red `#C42430` (light) |
| Size | 227 × 178 mm |
| Print time | ~43 min, as estimated by Bambu Studio |
| Filament | ~2.5 g |

## Ironing it on

The logo is made of separate pieces (slashes and letters). Keep them together from the build plate to the t-shirt:

1. While the print is still on the build plate, cover its clean (top) side with transfer tape or painter's tape, then
   peel everything off the plate at once.
2. Place the t-shirt flat and position the logo, clean side facing up (the tape stays on top).
3. Hold it in place with a few strips of heat-resistant tape (e.g. Kapton) on the edges, then peel off the transfer or
   painter's tape, which is not meant to go under the iron.
4. Cover with baking/parchment paper.
5. Press with a hot iron (no steam) for 15–20 seconds. Move evenly for larger designs.
6. Let it cool slightly, then remove the paper and the heat-resistant tape.

> [!NOTE]
> The tape method still has to be validated with a test print.

TODO(washing advice)
