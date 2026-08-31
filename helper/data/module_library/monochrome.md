# monochrome (monochrome)
group: color | display-referred | typical position: after tone mapping
synonyms: black and white, b&w, monochrome, grayscale, desaturate, film filter, red filter, orange filter, convert to black and white, mono
purpose: Converts the image to monochrome by applying a virtual colour filter
over the hue circle, emulating the coloured glass filters used with black and
white film. The filter's position selects which hues are lightened and its size
controls how selective it is.
use_when: you want a quick black and white conversion with filter-style control;
a sky needs darkening relative to clouds (a red or orange filter position); you
want the classic film-filter workflow rather than channel mixing.
do_not_combine: color calibration's gray tab does a more colour-accurate
conversion and is the recommended modern approach; running both means converting
twice.
key_controls:
- filter position: drag the filter marker across the hue palette to choose which
  colour the virtual filter passes. Placing it on orange/red lightens skin and
  darkens blue sky (the classic landscape choice); placing it on blue does the
  opposite.
- filter size: the scroll wheel changes the size of the filter spot. A small
  filter is highly selective and produces dramatic tonal separation; a large one
  approaches a plain desaturation.
- picker: samples an area of the image and sets the filter position and size
  automatically so that area is rendered as a chosen tone.
- highlights: controls how much highlight detail is retained through the
  conversion.
visual_effect: BEFORE: a colour landscape where a blue sky and white clouds have
similar luminance and merge into each other. AFTER: with the filter on orange,
the sky renders dark and the clouds stand out dramatically, foliage darkens and
skin lightens -- the classic red-filter black and white landscape.
pitfalls: the manual warns about black pixel artefacts, particularly with highly
saturated blue light sources; the gamut clipping option in input color profile
mitigates this. A very small filter size can push some hues to pure black.
Because it is display-referred, converting before tone mapping gives less
predictable tonal separation than doing it after. For colour-managed, accurate
conversions the color calibration gray tab is better.
pairs_with: color calibration (gray tab), split-toning, grain, contrast
equalizer, tone curve.
