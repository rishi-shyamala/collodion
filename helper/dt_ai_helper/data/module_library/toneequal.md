# tone equalizer (toneequal)
group: tone | scene-referred | typical position: before filmic/sigmoid
synonyms: dodge and burn, dodging, burning, lift shadows, recover shadows, darken sky, zone system, selective brightness, open up shadows, local exposure, hdr look
purpose: Applies exposure corrections selectively by luminance zone using a
guided, edge-aware mask, so you can lift shadows or pull down highlights without
the halos of the old shadows and highlights module. Think of it as nine
independent exposure sliders, one per zone from -8 EV to 0 EV.
use_when: the subject is in shadow and the background is correctly exposed; the
sky is too bright relative to the land; you want dodge-and-burn by tonal range
rather than by drawn mask; the image needs an "HDR" look with more local range.
do_not_combine: shadows and highlights, global tonemap, fill light, zone system
(all superseded). Multiple instances of tone equalizer are fine and often useful.
key_controls:
- the nine zone sliders (simple tab, -8 EV to 0 EV): each raises or lowers the
  exposure of pixels whose mask luminance falls in that zone. Typical corrections
  +-1 EV; beyond +-2 EV artefacts become likely.
- curve / control points (advanced tab): drag the curve directly over the
  histogram of mask values -- usually faster than the sliders.
- curve smoothing (advanced tab): default around 0.6; higher gives more gradual
  transitions between zones, values well above 0.6 can make the fit unstable.
- mask exposure compensation (advanced tab, EV): shifts the mask histogram left
  or right so the image's tones line up with the sliders; the magic-wand button
  auto-centres it near -4 EV.
- mask contrast compensation (advanced tab): dilates or compresses the mask
  histogram to spread the image's tones across all nine zones.
- luminance estimator (masking tab): default "RGB euclidean norm".
- preserve details (masking tab): no | guided filter | averaged guided filter |
  eigf (default) | averaged eigf. eigf is exposure-independent and the safest.
- filter diffusion (masking tab): number of blur iterations, default 1.
- smoothing diameter (masking tab, % of image): default 5%; 1-10% for the guided
  filters. Larger = smoother, more halo-prone masks.
- edges refinement/feathering (masking tab): how tightly the mask follows edges.
- mask quantization (masking tab): posterises the mask; small values only.
- display exposure mask: the toggle you should use constantly -- tune the mask
  first, then the corrections.
visual_effect: BEFORE: a backlit subject reads as a silhouette against a
correctly exposed sky. AFTER: the subject's shadow zones are lifted by 1-2 EV
while the sky is untouched or pulled down, with edges that stay clean because
the mask is edge-aware.
pitfalls: the single biggest mistake is not tuning the mask -- if the mask
histogram is bunched at one end, the sliders do almost nothing or everything at
once. Large corrections plus a large smoothing diameter reintroduce halos.
Applying tone equalizer after filmic rgb defeats the point; it belongs earlier in
the pipe where the data is still scene-referred. Heavy shadow lifting amplifies
noise -- denoise first.
pairs_with: exposure, filmic rgb or sigmoid, color balance rgb, denoise
(profiled), diffuse or sharpen.
