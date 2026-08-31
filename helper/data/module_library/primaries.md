# rgb primaries (primaries)
group: color | scene-referred | typical position: before or after tone mapping
synonyms: primaries, hue rotation, purity, saturation control, gamut, tint, color science, look, saturated lights, blue led, film primaries
purpose: Rotates and attenuates the working space's red, green and blue
primaries and applies a tint to neutrals. Used before the tone mapper it changes
how saturated colours survive compression (the "film look" of hue rotation in
highlights); used after it acts as a global colour-science adjustment.
use_when: intensely saturated lights render as flat slabs of colour through the
tone mapper; you want the characteristic hue paths of a particular film or camera
science; a global tint needs applying to neutrals; you want to reduce overall
purity for a muted, filmic palette.
do_not_combine: filmic rgb, sigmoid and agx have their own primaries controls --
using both means two stacked primary manipulations. Pick one place to do it.
key_controls:
- red hue: shifts the red primary toward yellow (positive) or magenta (negative).
  Small values, a few degrees, meaningfully change skin rendering.
- red purity: the saturation of the red primary. Lowering it desaturates reds
  before tone mapping so they compress gracefully instead of clipping.
- green hue: shifts green toward cyan (positive) or yellow (negative) -- the main
  control over how foliage renders.
- green purity: the saturation of the green primary.
- blue hue: shifts blue toward magenta (positive) or cyan (negative), which
  changes sky and shadow rendering.
- blue purity: the saturation of the blue primary.
- tint hue: applies a colour cast to gray areas. Used after tone mapping it is a
  creative tint; used before, it behaves like a white balance adjustment.
- tint purity: the strength of that tint.
visual_effect: BEFORE: a sunset where the sun's disc clips to a flat orange
patch with no internal structure. AFTER (purity reduced before tone mapping):
the disc desaturates toward white at its centre and reveals falloff, exactly the
way film behaves. Used after tone mapping the effect is subtler: a shift in the
overall colour identity of the image, like changing camera brands.
pitfalls: primaries manipulation is powerful and easy to overdo -- small values
are the rule. Large purity reductions produce a washed-out, pastel image.
Rotating hues changes the meaning of every downstream hue-selective adjustment,
so do it before color equalizer work rather than after. Because it changes the
working primaries, edits copied to other images may not translate.
pairs_with: sigmoid, agx, filmic rgb, color balance rgb, color equalizer.
