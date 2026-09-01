# rgb curve (rgbcurve)
group: tone | display-referred | typical position: after tone mapping
synonyms: curves, rgb curve, contrast curve, s curve, channel curve, color grading curve, cross process, split tone curve, red curve, blue curve
purpose: Applies transfer curves in RGB (ProPhoto) rather than Lab, either to
all three channels together or to each channel independently. Per-channel curves
are the classic way to build colour grades and cross-processed looks.
use_when: you want contrast applied the way most other editors do it; you need a
colour grade built from per-channel curves (lift the blue channel's shadows for
a cool shadow tint); you are recreating a look supplied as RGB curves.
do_not_combine: tone curve, rgb levels and base curve overlap heavily; pick one
primary curve tool. Independent-channel curves plus color balance rgb's 4 ways
tab is easy to overdo.
key_controls:
- mode (RGB, linked channels | RGB, independent channels): linked applies one
  curve to all three channels and only changes tonality; independent gives one
  curve per channel and changes colour.
- the curve itself: nodes are added by clicking and dragged to shape the
  transfer function. Raising the black end of the blue curve is the standard
  "faded film" cool-shadow move; lowering the blue highlight end warms highlights.
- preserve colors: the luminance-preservation method that stops RGB contrast
  from desaturating highlights and over-saturating shadows.
- interpolation method: cubic spline, centripetal, monotone hermite.
- compensate middle gray: changes only the histogram display behind the curve so
  scene-referred data is readable; it does not alter processing.
- the two pickers: the left picker marks sampled values on the graph, the right
  one creates nodes from a sampled area (ctrl+drag for a positive curve,
  shift+drag for a negative one).
visual_effect: BEFORE: neutral, correctly exposed but characterless colour.
AFTER (linked): stronger contrast with the RGB-space signature of slightly
desaturated highlights and richer shadows. AFTER (independent): a distinct
colour grade -- teal shadows and warm highlights, or a washed cross-processed
look with lifted, tinted blacks.
pitfalls: as the manual notes, adding contrast in RGB desaturates highlights and
boosts shadow saturation; that is sometimes the look you want and sometimes not.
Independent-channel curves quickly produce colour casts in neutrals -- check a
gray reference. Strong curves after filmic rgb fight the tone mapper.
pairs_with: tone curve, filmic rgb, color balance rgb, color look up table,
rgb levels.
