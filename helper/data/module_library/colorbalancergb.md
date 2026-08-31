# color balance rgb (colorbalancergb)
group: color | scene-referred | typical position: after tone mapping
synonyms: color grading, saturation, vibrance, punch, pop, contrast, lift gamma gain, shadows tint, highlights tint, teal and orange, brilliance, chroma, hue shift, cinematic look
purpose: A perceptually-tuned colour grading module that combines global
contrast, four-way lift/gamma/gain grading and three separate colourfulness
controls (chroma, saturation, brilliance) with built-in luminance masks. It is
the workhorse "make it look good" module of the scene-referred workflow and the
recommended replacement for the older color balance and vibrance modules.
use_when: the image needs more punch, pop or saturation; you want a colour cast
in the shadows and a different one in the highlights (split toning done right);
skin tones need de-saturating while the background stays colourful; you want to
add contrast after tone mapping without breaking hues.
do_not_combine: velvia and vibrance (superseded by global vibrance here),
split-toning (superseded by the 4 ways tab), color contrast, and the deprecated
color balance module.
key_controls:
- hue shift (master tab, deg): rotates all hues at constant luminance and chroma.
  Small values, +-5 deg, fix a global cast; large values are a creative effect.
- global vibrance (master tab, %): boosts chroma of low-chroma pixels first.
  Typical +5 to +20%; safer than saturation on skin.
- contrast (master tab, %): luminance contrast at constant hue and chroma around
  the contrast gray fulcrum. Typical +5 to +25%.
- global chroma (master tab, %): linear chroma gain. Typical +5 to +15%.
- global saturation (master tab, %): perceptual saturation grading; stronger and
  more likely to clip gamut than chroma.
- global brilliance (master tab, %): perceived luminance of colours without
  changing measured lightness. Keep within -20% to +20%.
- global offset / shadows lift / highlights gain / global power (4 ways tab):
  each has luminance, hue and chroma components. Lift tints and raises shadows,
  gain tints and scales highlights, offset shifts everything, power is a
  gamma-like mid-tone control.
- shadows fall-off / highlights fall-off / mask middle-gray fulcrum (masks tab):
  shape the internal luminance masks that separate shadows from highlights;
  the fulcrum sets where the masks reach 50% opacity.
- white fulcrum (EV) and contrast gray fulcrum (%) (masks tab, thresholds):
  normalisation points; contrast gray fulcrum defaults to about 18.45%.
- saturation formula (masks tab): JzAzBz (2021) or darktable UCS (2022).
visual_effect: BEFORE: technically correct but lifeless image, neutral shadows,
flat mid-tone colour. AFTER: separated colour between shadow and highlight
regions, more three-dimensional-looking colour, controlled punch without the
crunchy over-saturated look of a naive saturation slider.
pitfalls: pushing global saturation instead of vibrance blows out already
saturated reds and skin. Brilliance beyond +-20% produces an unnatural glow.
Using 4 ways lift/gain heavily before the tone mapper (it belongs after) gives
unpredictable results. Very large chroma boosts push colours outside the output
gamut -- check with the gamut clipping option in input color profile or the
over-exposed indicator.
pairs_with: filmic rgb or sigmoid (apply after), color calibration (fix white
balance first), color equalizer (hue-selective work), tone equalizer.
