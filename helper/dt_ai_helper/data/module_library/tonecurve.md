# tone curve (tonecurve)
group: tone | display-referred | typical position: after tone mapping
synonyms: curves, curve, s curve, contrast curve, lift shadows, crush blacks, levels, tonal adjustment, film curve, fade, matte look
purpose: Applies a user-drawn transfer curve to lightness (and optionally the a
and b colour channels) in Lab space. It is the classic display-referred contrast
tool; in the scene-referred workflow filmic rgb, sigmoid and color balance rgb
handle the same job with better colour behaviour.
use_when: you want precise manual control over a specific part of the tone
range; you need a faded/matte look by lifting the black end of the curve; you
are reproducing a look defined as a curve; a small S-curve is all the contrast
the image needs.
do_not_combine: rgb curve, rgb levels and base curve do overlapping work -- use
one contrast curve, not three. Heavy curve work on top of filmic rgb undoes
filmic's careful rolloff.
key_controls:
- L-channel curve: the lightness transfer function. A shallow S (pull the
  quarter-tone down, push the three-quarter-tone up) adds contrast; lifting the
  bottom-left node gives a matte, faded look; steepening the middle increases
  mid-tone contrast at the cost of shadow and highlight separation.
- a-channel and b-channel curves: available in "Lab, separated channels" mode;
  a is the green-magenta axis, b is the blue-yellow axis. Steepening them
  increases saturation, tilting them adds a colour cast.
- color space (Lab, linked channels | Lab, separated channels | XYZ, linked
  channels | RGB, linked channels): how the curve is applied. RGB linked behaves
  most like other editors; Lab separated gives per-axis colour control.
- preserve colors: the method used to keep hue stable when contrast changes;
  without it, contrast in RGB desaturates highlights.
- interpolation method: cubic spline, centripetal spline, monotone hermite --
  monotone avoids the overshoot that cubic splines produce between sparse nodes.
- scale for graph: linear or logarithmic axis display, which makes shadow nodes
  easier to place.
- middle gray is always at 50% of the graph, remapped to 18% when the curve is
  applied in RGB or XYZ.
visual_effect: BEFORE: a flat image with the histogram bunched in the middle.
AFTER: a classic photographic S-curve rendering -- deeper blacks, brighter
highlights, more mid-tone snap. Lifting the toe instead produces the faded,
low-contrast "film emulation" look.
pitfalls: steep curves in Lab cause hue shifts and can posterise in smooth
gradients; the preserve colors option mitigates but does not eliminate this.
Placing many nodes close together produces wobbles with cubic interpolation --
switch to monotone. Applying strong curves after filmic rgb double-compresses
the highlights and flattens them.
pairs_with: rgb curve, filmic rgb, color balance rgb, rgb levels, tone equalizer.
