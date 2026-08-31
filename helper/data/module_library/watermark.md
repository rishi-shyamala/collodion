# watermark (watermark)
group: effect | output | typical position: very late, output stage
synonyms: watermark, logo, signature, copyright, branding, text overlay, credit, svg overlay, add my name
purpose: Overlays an SVG or PNG marker -- typically a logo, signature or
copyright line -- on the image, with support for variable substitution so text
can be drawn from image metadata.
use_when: you are publishing images and want a signature or logo; a client
proof needs a visible copyright; you want to burn the title or date into an
exported file.
do_not_combine: nothing conflicts, but multiple instances are the correct way to
add both a logo and a text credit rather than trying to do both in one.
key_controls:
- marker: the watermark file to apply, chosen from darktable's watermarks
  directory; the reload button rescans that directory after you add a file.
- text: up to 511 characters, substituted into SVG markers that reference
  $(WATERMARK_TEXT).
- font and color: typeface and colour for the text, with a preview.
- opacity (%): how strongly the marker is composited. Typical 30-70% for a
  discreet credit, 100% for a solid logo.
- rotation (deg): angle of the marker.
- scale (%) and scale on (image | larger border | smaller border | height |
  advanced options): how the marker size is derived, so a watermark stays
  proportionate across different export sizes and aspect ratios.
- scale marker to and scale marker reference (advanced options): finer control
  over which dimension drives the scaling.
- alignment: a nine-position grid (corners, edges, centre).
- x offset / y offset: nudges from the chosen alignment, expressed
  resolution-independently so exports at different sizes match.
- variables: $(WATERMARK_TEXT), $(WATERMARK_COLOR), $(WATERMARK_FONT_FAMILY),
  $(WATERMARK_FONT_STYLE) (normal, oblique, italic) and $(WATERMARK_FONT_WEIGHT)
  are substituted into SVG markers, alongside darktable's general variables for
  metadata such as title, creator and capture date.
visual_effect: BEFORE: a clean image. AFTER: a logo or credit line sits in the
chosen corner at a consistent relative size, semi-transparent enough not to
dominate the photograph.
pitfalls: PNG markers do not scale as cleanly as SVG -- prefer SVG for logos.
A watermark placed before the crop or framing modules would be mispositioned;
watermark deliberately runs late, so re-check it after changing the crop.
Opacity at 100% over a busy area makes the image look cheap; sample a corner with
low detail. Watermarks are burned into the export and cannot be removed later.
pairs_with: framing, crop, enlarge canvas, orientation.
