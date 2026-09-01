# color look up table (colorchecker)
group: color | display-referred | typical position: after tone mapping
synonyms: clut, color lookup, film emulation, style, look, color grading, patch based, darktable-chart, match colors, calibrate colors
purpose: Applies a colour transform defined by a set of source/target colour
patches in Lab space. It is the module darktable's own styles and
darktable-chart output use to encode film-simulation looks and camera-matching
corrections.
use_when: you want to apply a downloaded film-emulation style; you have used
darktable-chart to match a raw to a reference JPEG or a colour target; you need a
precise "make this specific colour become that specific colour" adjustment that
hue-based tools cannot express.
do_not_combine: stacking several colour look up table instances plus LUT 3D plus
heavy colour zones makes colour behaviour impossible to reason about.
key_controls:
- the colour patch grid: the source colours, drawn as a board. The default is a
  24-patch colour checker; boards with 24 or more patches are laid out in a 7x7
  grid. A white outline marks the selected patch and an outline marks any patch
  that has been modified.
- patch selection combo box: pick a patch by number instead of clicking.
- L, a, b, C sliders: the target values for the selected patch -- lightness, the
  green-red axis, the blue-yellow axis, and saturation. Small moves go a long way.
- picker: select a source colour from the image.
- double-click resets a patch to its default, right-click deletes it, and
  shift+click on empty board space adds a new patch; shift+click on a patch with
  the picker active replaces its source colour with the sampled one.
visual_effect: BEFORE: accurate but characterless colour. AFTER: a specific
colour identity -- warmer skin with cooler shadows, or the muted greens and
strong blues of a particular film stock -- applied smoothly across the whole
image because the transform interpolates between patches.
pitfalls: moving a patch a long way from its source colour distorts the
interpolation for neighbouring colours and produces blotches; make many small
patch edits rather than a few large ones. The module works in display-referred
Lab, so it should sit after the tone mapper. Presets built for one workflow
(display-referred) look wrong when applied to a scene-referred edit.
pairs_with: color balance rgb, LUT 3D, color calibration, filmic rgb,
color equalizer.
