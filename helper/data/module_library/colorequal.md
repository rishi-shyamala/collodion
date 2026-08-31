# color equalizer (colorequal)
group: color | scene-referred | typical position: after tone mapping
synonyms: hsl, hue saturation brightness, selective color, make sky bluer, foliage green, skin tone, targeted saturation, color range, shift hue, desaturate reds, color grading by hue
purpose: Adjusts hue, saturation and brightness as a function of the pixel's
hue, using a guided filter to keep transitions clean. It is the modern
replacement for color zones and the tool of choice for any "change this colour"
request in a scene-referred edit.
use_when: the sky should be deeper blue; foliage is yellow-green and should be
green; skin needs desaturating relative to a colourful background; a single
garment colour clashes; you want per-hue brightness control (darken blues,
lighten yellows).
do_not_combine: color zones does the same job less safely -- prefer this. Heavy
per-hue saturation here plus large chroma boosts in color balance rgb compound.
key_controls:
- hue / saturation / brightness tabs: three curves, each mapping input hue to a
  change in that attribute.
- color nodes: fixed, equally spaced points on the hue axis. Click and drag up
  or down, use the scroll wheel, or ctrl+scroll for fine adjustment. Middle-click
  a curve section to reveal the equivalent sliders.
- node placement: shifts all nodes along the hue axis together, so you can align
  a node exactly with the hue you care about.
- white level: the upper bound used for brightness corrections.
- hue curve (default 1.0): interpolation between nodes; above 1.0 gives gradual
  blending between adjacent hues, below 1.0 gives sharper, more selective
  transitions.
- use guided filter (on by default): the artefact and noise suppression that
  distinguishes this module from color zones.
- hue analysis radius (default 1.5 px): how many neighbouring pixels contribute
  to the hue estimate.
- saturation threshold: the minimum saturation a pixel needs before it is
  adjusted, which protects near-neutral pixels.
- contrast: the steepness of the saturation weighting curve.
- effect radius: the smoothing radius of the guided filter.
- visualize weighting (saturation) and visualize changed output: diagnostic
  overlays -- blue/red for how strongly a pixel is affected, and red/blue for
  whether its value went up or down.
visual_effect: BEFORE: a pale cyan-leaning sky and yellowish foliage. AFTER: a
saturated blue sky and clean green foliage, with skin and neutrals untouched and
no hard seams where the adjusted hue band ends.
pitfalls: pushing brightness per hue creates unnatural luminance relationships
(a dark blue sky next to normally-lit clouds). Turning the guided filter off
brings back color zones' banding. Large hue rotations on skin are immediately
obvious. Very low hue curve values make the transitions between adjusted and
untouched hues visible in gradients.
pairs_with: color balance rgb, color calibration, color zones (legacy),
filmic rgb, color harmonizer.
