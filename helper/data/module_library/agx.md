# agx (agx)
group: tone | scene-referred | typical position: late tone mapping, after exposure
synonyms: tone mapping, display transform, agx, filmic alternative, sigmoid alternative, highlight rolloff, contrast, pivot, look, hdr, saturated lights
purpose: A scene-to-display tone mapping module based on the AgX transform,
combining a parametric sigmoid-like curve with explicit primary manipulation so
that very saturated light sources desaturate gracefully toward white instead of
clipping to a flat colour. It is the third option alongside filmic rgb and
sigmoid.
use_when: the scene contains intensely saturated bright areas (stage lights,
neon, sunsets, fire) that filmic or sigmoid render as flat blobs of colour; you
want a modern film-like rolloff with a single pivot-based contrast control; you
want a look preset (slope/lift/brightness/saturation) built into the tone mapper.
do_not_combine: filmic rgb, sigmoid, base curve (choose exactly one display
transform).
key_controls:
- white relative exposure and black relative exposure (settings tab, input
  exposure range, EV): the scene range being mapped, with pickers; the same
  concept as filmic's scene tab.
- dynamic range scaling and auto tune levels (settings tab): set both ends from
  a sampled area; "read exposure" pulls the value from the exposure module.
- pivot relative exposure (basic curve parameters): where middle gray sits,
  defaulting to mid-gray; the curve rotates around this point.
- pivot target output: what that pivot maps to on the display.
- contrast (basic curve parameters): the slope through the pivot. Typical
  1.5-3.0; higher = punchier.
- shoulder power and toe power: how quickly the curve flattens at the highlight
  and shadow ends. Higher shoulder power = a harder highlight rolloff.
- shoulder start, target white, toe start, target black, curve y gamma and
  "keep the pivot on the diagonal" (advanced curve parameters): explicit control
  over where the straight section ends and what the extremes converge to.
- slope, lift, brightness, saturation, preserve hue (look section): a built-in
  grade applied in the tone-mapping space. Slope defaults to 1.0, lift to 0,
  brightness to 1.0, saturation to 1.0, preserve hue is 0-100%.
- base primaries, red/green/blue attenuation and rotation (primaries tab, before
  tone mapping): reduce purity and rotate hues before compression so saturated
  lights survive the curve.
- master purity boost, red/green/blue purity boost, reverse rotation, reverse
  all and "set from above" (primaries tab, after tone mapping): restore purity
  after compression.
- show curve: the visualisation, with EV on the x axis and linear output % on y.
visual_effect: BEFORE: a concert shot where the red stage lights render as a
featureless slab of pure red. AFTER: those lights desaturate toward white at
their brightest points, revealing shape and falloff, while the rest of the image
keeps a normal filmic contrast. The overall rendering is slightly softer in the
extremes than filmic rgb at the same contrast.
pitfalls: the primaries controls interact strongly with the curve; changing them
after tuning the curve usually means re-tuning the contrast. Like every display
transform, agx is not a brightness control -- set exposure first. Attenuation
values that are too high produce washed-out, pastel colour throughout. Presets
and styles built for filmic rgb do not translate.
pairs_with: exposure, rgb primaries, color balance rgb, tone equalizer,
highlight reconstruction.
