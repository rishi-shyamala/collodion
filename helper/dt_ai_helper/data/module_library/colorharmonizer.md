# color harmonizer (colorharmonizer)
group: color | scene-referred | typical position: after tone mapping
synonyms: color harmony, complementary colors, color theory, palette, teal and orange, triad, analogous, unify colors, vectorscope, color grading
purpose: Nudges the hues in an image toward the nodes of a chosen colour-harmony
rule (complementary, triad, analogous and so on), so that a scene with scattered
colours resolves into a coherent palette. It works with the vectorscope overlay,
which visualises the harmony nodes against the image's actual hue distribution.
use_when: the image contains several clashing hues and you want a unified,
designed-looking palette; you want a teal-and-orange or other complementary
grade driven by colour theory rather than by hand; you want to nudge colours
toward a house palette across a series.
do_not_combine: it overlaps with per-hue work in color equalizer; doing large
moves in both makes the result hard to predict. Do harmonisation first, then
fine-tune specific hues.
key_controls:
- harmony rule: monochromatic, analogous, complementary, triad, tetrad, square,
  split complementary, dyad, or custom. Complementary and split complementary are
  the workhorses for portrait/background separation.
- anchor hue: the primary hue from which the other node positions are derived,
  with an eyedropper so it can be sampled from the subject.
- infer from image: analyses the preview's chroma-weighted hue histogram and
  picks the rule and anchor that best fit what is already there -- the fastest
  starting point.
- nodes (custom mode, 2-4): how many harmony targets are active.
- node hue sliders (custom mode): position each node individually, each with its
  own eyedropper.
- pull strength: how hard hues are dragged toward the nearest node. Typical
  10-40%; high values flatten the image into a few hues.
- pull width: how wide the attraction zone around each node is, i.e. how many
  hues are considered "near" a node.
- neutral color protection: shields low-chroma pixels so skin, gray and near-
  neutral areas are not dragged into the palette.
- smoothing: reduces spatial transitions at the boundaries between zones.
- node saturation sliders: per-node saturation multipliers, so one harmony
  target can be boosted and another damped.
- vectorscope two-way sync and import from vectorscope: link the module to the
  scope overlay so nodes can be positioned visually against the hue histogram.
visual_effect: BEFORE: a street scene with a dozen unrelated hues competing for
attention. AFTER: those hues converge on two or three related families, so the
image reads as deliberately graded -- warm skin against a cool background, or a
triadic palette that feels designed rather than accidental.
pitfalls: high pull strength destroys genuine colour variety and makes the image
look posterised. Without neutral colour protection, skin drifts toward the nearest
harmony node and stops looking like skin. Choosing a rule that fights the image's
actual content produces obvious colour errors -- use "infer from image" first.
Harmonising before white balance is settled bakes in a cast.
pairs_with: color equalizer, color balance rgb, color calibration, vectorscope,
filmic rgb.
