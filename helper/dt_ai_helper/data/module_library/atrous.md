# contrast equalizer (atrous)
group: sharpness | display-referred | typical position: after tone mapping
synonyms: clarity, local contrast, sharpen, denoise, bloom, wavelet, frequency, detail scales, skin smoothing, texture, micro contrast
purpose: Decomposes the image into wavelet detail scales and lets you boost or
suppress contrast, saturation and noise independently at each scale, with an
edge-aware transform. One module covers sharpening, clarity, local contrast,
denoising and bloom depending on which end of the curve you move.
use_when: you want sharpening at one detail scale and smoothing at another (the
classic skin-retouching recipe); you need clarity without halos; you want to
denoise fine scales while boosting coarse structure; you want a bloom effect.
do_not_combine: stacking contrast equalizer, local contrast, contrast & texture
and diffuse or sharpen's local contrast preset multiplies the same effect.
key_controls:
- luma tab: the white spline controls local contrast per wavelet scale. Nodes to
  the left are the finest details (sharpening), nodes to the right are coarse
  structures (local contrast/clarity). Raising a node boosts that scale,
  lowering it suppresses it.
- chroma tab: the same per-scale control applied to colour contrast, i.e.
  saturation at each detail scale. Lowering the fine scales removes chroma noise.
- edges tab: the edge-awareness spline; it controls how strongly the a trous
  wavelet transform respects edges at each scale, which is what keeps halos and
  gradient reversals away.
- the denoising splines at the bottom of the luma and chroma graphs: pulling
  these down applies wavelet denoising at the corresponding scale.
- mix: overall effect strength; negative values invert the drawn graph, which is
  a quick way to try the opposite of what you drew.
- the influence circle: scroll the mouse wheel over the graph to change the
  radius of influence of the node you are dragging.
- background striping in the graph shows which detail levels are actually
  visible at the current zoom -- judge at 100%.
- presets: a set of ready-made curves (clarity, bloom, denoise, sharpen) that are
  the fastest way to understand the module.
visual_effect: BEFORE: a portrait with blotchy skin texture and soft eyes.
AFTER: eyes and eyelashes crisp (fine scales boosted) while skin blotches at
coarser scales are smoothed, without the plastic look of a blur. On landscapes:
clarity and depth without the dark halo along the horizon that naive local
contrast produces.
pitfalls: it works in CIE LCh and is display-referred, so very strong settings
shift hues. Boosting the finest scale is indistinguishable from sharpening noise;
denoise first. The graph is unintuitive until you use the presets as starting
points. Effects judged at fit-to-screen zoom are misleading because the visible
detail scales change with zoom level.
pairs_with: denoise (profiled), diffuse or sharpen, local contrast,
contrast & texture, retouch.
