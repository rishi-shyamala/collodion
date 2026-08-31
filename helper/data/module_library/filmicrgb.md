# filmic rgb (filmicrgb)
group: tone | scene-referred | typical position: late tone mapping, after exposure
synonyms: tone mapping, dynamic range, hdr look, highlight rolloff, recover highlights, contrast curve, film curve, scene to display, blown sky, flat raw
purpose: Compresses scene dynamic range to display dynamic range with an
explicitly parameterised film-like transfer curve, splitting the job into
"how much scene range is there" (scene tab) and "what look do I want" (look tab).
It is the main tone-mapping module of the scene-referred workflow and the
default in darktable's scene-referred (filmic) workflow preset.
use_when: the image looks flat, dark or washed out after setting exposure; the
sky or highlights need a smooth rolloff instead of a hard clip; the scene has
high dynamic range (backlit subject, window interior, sunset); you are replacing
base curve as part of moving to a scene-referred workflow.
do_not_combine: base curve, sigmoid, agx (choose exactly one display transform).
Also avoid stacking shadows and highlights or global tonemap on top of it.
key_controls:
- white relative exposure (scene tab, EV): how many stops above middle gray the
  scene white sits. Typical +2.5 to +5 EV; raise -> more highlight compression
  and more recovered highlight detail, at the cost of grayer highlights.
- black relative exposure (scene tab, EV): stops below middle gray for scene
  black. Typical -6 to -10 EV; lower (more negative) -> the deepest shadows lift
  and open up; raise -> deeper, denser blacks.
- dynamic range scaling / auto-tune levels (scene tab): the combined picker that
  sets both relative exposures from a sampled area or the whole image; a good
  starting point before manual tuning.
- contrast (look tab): slope of the curve through middle gray. Typical 1.0-1.8;
  higher = punchier mid-tones, flatter shoulders and toe. Raising white relative
  exposure normally requires raising contrast to keep the image from flattening.
- shadows/highlights balance (look tab, %): shifts the linear portion up or down
  the tone range; negative moves contrast into the shadows.
- latitude / linear region (look tab, %): the share of the dynamic range that is
  rendered with the straight contrast slope. Wide latitude with high contrast is
  the classic halo/posterisation recipe.
- highlights saturation mix (look tab): how much saturation survives at the
  extremes of the tone scale.
- target black luminance / target white luminance (display tab, %): the output
  black and white levels; white defaults to 100%.
- enable highlight reconstruction, threshold, transition (reconstruct tab):
  rebuilds clipped highlight areas; the structure<->texture, bloom<->reconstruct
  and gray<->colourful details sliders bias what the reconstruction invents.
- color science (options tab): v3 through v7; v7 is the current default and has
  the best behaviour with saturated highlights.
visual_effect: BEFORE: flat, low-contrast linear scene data, washed-out
highlights that clip abruptly to white, and dull mid-tones. AFTER: smooth
highlight rolloff with retained detail in the brightest areas, deeper blacks,
and mid-tone contrast that reads as a photograph rather than a linear scan.
pitfalls: over-raising white relative exposure grays out the highlights and
makes the whole image look milky. Latitude too wide combined with high contrast
causes halos around high-contrast edges and gradient reversals. Using filmic to
brighten the image instead of exposure is the single most common mistake --
filmic maps the range, exposure sets the level. Turning on highlight
reconstruction inside filmic without first setting the highlight reconstruction
module method sensibly produces magenta or plastic-looking skies.
pairs_with: exposure (set middle gray first), highlight reconstruction, color
balance rgb (contrast and saturation after tone mapping), tone equalizer
(range-selective dodging before filmic), color calibration.
