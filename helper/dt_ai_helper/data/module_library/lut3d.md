# LUT 3D (lut3d)
group: color | display-referred | typical position: after tone mapping
synonyms: lut, cube file, film emulation, look, color grading, teal orange, haldclut, creative lut, cinematic, preset look
purpose: Applies a 3D colour lookup table from an external file, mapping every
input RGB triplet to an output triplet. This is how third-party film emulations,
cinematic looks and vendor colour transforms are applied in darktable.
use_when: you have a .cube or HALD-CLUT film emulation you want to apply; a
client or house style is distributed as a LUT; you want a strong stylised colour
grade in one step; you need to match another application's colour rendering.
do_not_combine: stacking multiple LUTs, or a LUT plus a colour look up table
preset plus heavy colour zones, makes the colour result impossible to predict
and usually clips.
key_controls:
- file selection: the LUT file to load. Supported formats are .cube, .3dl,
  .png (HALD-CLUT) and .gmz (which requires G'MIC and is the only format whose
  data is stored in the database and XMP rather than referenced by path).
- application color space: the colour space the LUT was authored for --
  Rec. 709 (typical for .cube files) or sRGB (typical for the other formats).
  Choosing wrongly gives a plausible but incorrect grade.
- interpolation: tetrahedral, trilinear or pyramid. Tetrahedral is generally the
  most accurate; the differences show mainly in smooth gradients.
visual_effect: BEFORE: a neutral, correctly graded image. AFTER: the LUT's
signature look -- lifted teal shadows and warm skin, or the muted palette of a
specific film stock -- applied consistently across the whole tonal range.
pitfalls: LUTs expect display-referred input, so the module belongs after
filmic rgb; feeding it scene-referred linear data gives wildly wrong results.
Except for .gmz, the LUT file is referenced by path, so styles and XMP files that
use a LUT break on another machine if the file is missing. Strong LUTs clip
saturated colours and posterise gradients; reduce the effect with the module's
blending opacity. A LUT authored for log footage will look flat and wrong on
photographic input.
pairs_with: filmic rgb (before), color look up table, color balance rgb,
output color profile.
