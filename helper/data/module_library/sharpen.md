# sharpen (sharpen)
group: sharpness | display-referred | typical position: late, near output
synonyms: sharpen, sharpening, unsharp mask, usm, crisp, soft image, out of focus, detail, acutance, edges
purpose: Classic unsharp mask: subtracts a gaussian-blurred copy of the image
from itself to boost edge acutance. It is darktable's oldest sharpening module,
disabled by default in current versions because diffuse or sharpen and contrast
equalizer do the job with fewer artefacts.
use_when: you want a quick, cheap output sharpening pass for web or print; the
image is slightly soft and you do not need the sophistication of diffuse or
sharpen; you are reproducing a legacy edit that already used it.
do_not_combine: stacking sharpen with diffuse or sharpen's sharpening presets and
contrast equalizer's edge sharpening usually over-sharpens. Pick one primary
sharpener and use the others for different scales.
key_controls:
- radius: the sigma of the gaussian blur used to build the unsharp mask.
  Typical 0.5-2.0 px; small radii sharpen fine detail, large radii turn into a
  local-contrast/clarity effect.
- amount: strength of the edge boost. Typical 0.4-1.5; above about 2.0 halos
  become obvious.
- threshold: contrast differences below this value are excluded, which keeps the
  module from amplifying noise in smooth areas. Typical 0.002-0.02; raise it on
  high-ISO files.
visual_effect: BEFORE: slightly soft edges, especially after demosaic and
resizing. AFTER: crisper edge transitions and more apparent detail. Pushed too
far: bright halos on the light side of every dark/light boundary, crunchy noise
in the sky, and a gritty, digital look.
pitfalls: unsharp mask amplifies noise as enthusiastically as detail -- always
denoise first and use the threshold slider. Halos from a too-large radius cannot
be removed later. Sharpening before scaling for export means the export scaling
undoes some of it; sharpening is inherently output-size dependent. The manual
itself recommends the contrast equalizer or diffuse or sharpen modules instead.
pairs_with: denoise (profiled) (before), diffuse or sharpen (a better primary
sharpener), contrast equalizer, local contrast.
