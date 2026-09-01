# sigmoid (sigmoid)
group: tone | scene-referred | typical position: late tone mapping, after exposure
synonyms: tone mapping, display transform, simple filmic alternative, s-curve, contrast, rolloff, per channel, rgb ratio, hue preservation
purpose: Maps scene-referred linear RGB to display range using a smooth
sigmoidal curve with only a handful of controls. It is the simpler, more
predictable alternative to filmic rgb: fewer knobs, no explicit dynamic range
declaration, and very stable behaviour on saturated highlights.
use_when: you want a quick, robust display transform without tuning filmic's
scene tab; the image has moderate dynamic range; filmic is producing halos or
you find its parameterisation fiddly; you want per-channel film-like hue shifts
in saturated highlights (sunsets, neon, stage lighting).
do_not_combine: filmic rgb, base curve, agx (pick one display transform).
key_controls:
- contrast: how aggressively the curve compresses while holding middle gray
  fixed. Typical 1.2-2.0; higher -> darker shadows and less exposure needed to
  reach display white; lower -> a larger displayable dynamic range and a flatter
  look.
- skew: biases compression toward shadows (negative) or highlights (positive)
  without moving middle gray. Typical -1 to +1; negative opens the shadows.
- color processing (per channel | rgb ratio): per channel applies the curve to
  R, G and B separately, giving film-like hue rotation in bright saturated
  areas; rgb ratio preserves the spectral hue and keeps chromaticity intact.
- preserve hue (%) (per channel only): 0% = full per-channel hue skew,
  100% = behaves like rgb ratio. Typical 40-100%.
- target black / target white: the display convergence bounds; normally left
  alone.
- base primaries, red/green/blue attenuation, red/green/blue rotation,
  recover purity (primaries section): pre-tone-mapping primary manipulation that
  tames extremely saturated colours before compression, then restores purity.
visual_effect: BEFORE: linear scene data with hard-clipping highlights and no
mid-tone contrast. AFTER: a gentle S-shaped rendering with clean highlight
convergence, saturated lights that turn toward yellow/white the way film does
(per channel mode) or that keep their hue exactly (rgb ratio mode).
pitfalls: high contrast values crush shadows quickly because sigmoid has no
separate black-relative-exposure control -- use skew or exposure's black level
instead of pushing contrast. Per-channel mode on strongly coloured light sources
can shift hues more than expected; raise preserve hue. Like filmic, sigmoid is
not a brightness control: set exposure first.
pairs_with: exposure, color balance rgb, tone equalizer, rgb primaries,
highlight reconstruction.
