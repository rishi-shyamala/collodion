# color zones (colorzones)
group: color | display-referred | typical position: after tone mapping
synonyms: hsl, hue saturation luminance, selective color, change color, make the sky bluer, green foliage, skin tone adjust, desaturate a color, color range, targeted saturation
purpose: Adjusts lightness, chroma and hue of pixels selected by hue, lightness
or chroma, using editable splines in CIE LCh space. It is darktable's classic
HSL-style selective colour tool; on current versions the newer color equalizer
module does the same job with better guided filtering.
use_when: you want to deepen just the blues of a sky; foliage is too yellow and
should be greener; a red garment is over-saturated relative to everything else;
skin needs desaturating without touching the background.
do_not_combine: color equalizer covers the same ground more safely -- prefer it
on 5.x. Heavy colour zones plus heavy color balance rgb chroma work fights.
key_controls:
- lightness / chroma / hue tabs: three independent splines; each tab adjusts that
  attribute for the selected pixels.
- select by (hue | lightness | chroma): what the horizontal axis of the spline
  means. "By hue" is the familiar HSL-style behaviour.
- the spline itself: drag nodes up or down; the scroll wheel changes the radius
  of influence, which controls how wide a band of hues is affected.
- mix: overall strength of the effect; also allows going past or backing off the
  drawn curve.
- process mode (smooth | strong): smooth (default) is gentler and less prone to
  banding.
- interpolation method: how the spline is interpolated between nodes.
- edit by area: enables the legacy area-based spline editing mode.
- mask display: paints the affected pixels yellow -- use it to check your
  selection width before judging the effect.
- the two pickers: the left picker shows where a sampled pixel sits on the axis;
  the right picker samples a rectangular area and auto-creates a curve (ctrl for
  a positive curve, shift for a negative one).
visual_effect: BEFORE: a sky that is pale and slightly cyan while everything
else is fine. AFTER: the same sky reads deeper and bluer, with foliage and skin
untouched. Overdone: hard-edged colour transitions where the adjusted hue band
meets the untouched one, and posterised gradients in skies.
pitfalls: narrow influence radii create visible seams in smooth gradients -- the
manual explicitly says to use this module with care and to combine it with
parametric or drawn masks. Large hue shifts on skin look immediately artificial.
Because it works in LCh after tone mapping, extreme chroma boosts can exceed the
output gamut and clip.
pairs_with: color equalizer (the modern replacement), color balance rgb,
color calibration, drawn and parametric masks.
