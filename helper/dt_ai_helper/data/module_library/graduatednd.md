# graduated density (graduatednd)
group: tone | display-referred | typical position: mid pipeline
synonyms: nd grad, graduated filter, darken sky, sky too bright, gradient filter, half nd, sunset gradient, warm the sky, landscape sky
purpose: Simulates a graduated neutral density filter: a linear brightness ramp
across the frame, optionally tinted. It darkens (or lightens) one part of the
image along a straight gradient with a controllable angle and hardness.
use_when: the sky is a stop or two too bright for the land; you want to add a
warm or cool graduated tint to a sky; you need a simple linear brightness ramp
that a mask would be fiddly to draw.
do_not_combine: heavy use alongside tone equalizer on the same tonal region
double-darkens. For non-linear shapes use exposure with a drawn gradient mask
instead.
key_controls:
- density (EV): the strength of the filter. Typical 0.5-2 EV; low values are a
  subtle correction, high values are an obvious effect.
- hardness (%): the progressiveness of the transition. Low = a long, smooth
  ramp; high = an abrupt edge that will show against a broken horizon.
- rotation (deg): the angle of the gradient; negative values rotate clockwise.
  It can also be set by dragging the ends of the gradient line on the canvas.
- hue: the colour cast added along the gradient (only visible when saturation is
  above zero) -- warm oranges for sunsets, cool blues for overcast skies.
- saturation: the strength of that colour cast; defaults to 0, i.e. neutral.
visual_effect: BEFORE: a landscape where the sky is two stops brighter than the
foreground and reads as a bright, detail-free band. AFTER: sky and land sit at
comparable brightness, with the transition following the horizon line, and
optionally a warm tone in the upper part of the frame.
pitfalls: because the gradient is a straight line, anything protruding above the
horizon (mountains, trees, buildings) gets darkened too and looks obviously
filtered -- use tone equalizer or a drawn mask on broken horizons. High hardness
makes the gradient edge visible as a band. Applying it after tone mapping can
push already-compressed highlights into flat gray. Saturated hues at high density
tint the whole upper frame more than intended.
pairs_with: exposure, tone equalizer, filmic rgb, drawn masks, color balance rgb.
