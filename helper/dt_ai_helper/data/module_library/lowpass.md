# lowpass (lowpass)
group: effect | display-referred | typical position: late, creative stage
synonyms: blur, soften, glow, dreamy, mask source, luminance mask, gaussian blur, bilateral blur, contrast overlay, orton
purpose: Blurs the image in Lab space with either a gaussian or an edge-aware
bilateral filter, then optionally re-applies contrast, brightness and saturation
to the blurred result. In practice it is used far more often as the source layer
for a blend mode (overlay, softlight) than as a visible blur.
use_when: you want a dreamy soft-focus or Orton effect via blending; you need a
smooth luminance layer to blend for contrast or glow; you are reproducing a
legacy edit.
do_not_combine: blurs, surface blur, soften and diffuse or sharpen's diffusion
presets all overlap with this; the manual recommends the contrast equalizer or
tone equalizer instead for contrast work.
key_controls:
- radius: the blur strength. Typical 5-50 px depending on image size and intent.
- soften with (gaussian blur | bilateral filter): gaussian blurs all Lab
  channels; the bilateral filter blurs only L and preserves edges.
- contrast: applied to the blurred result. Absolute values above 1 increase
  contrast, below 1 reduce it, 0 is a neutral flat plane, and negative values
  invert the tonality (a negative image).
- brightness: negative darkens, positive lightens the blurred layer.
- saturation: values above 1 boost, below 1 reduce, 0 fully desaturates and
  negative values invert the a/b channels into complementary colours.
visual_effect: BEFORE: a normal sharp image. AFTER (used directly): a soft,
hazy version of the image. AFTER (blended in overlay at 30-50% opacity): a
glowing, luminous Orton-style rendering where highlights bloom into their
surroundings while edges remain readable.
pitfalls: working in Lab, aggressive settings produce hue shifts and the
documentation no longer recommends the module for general contrast work. Large
radii on big files are slow. Negative contrast or saturation values are a
special-effect trick, not a correction. Blend mode and opacity matter more than
the module's own sliders for most real uses.
pairs_with: blend modes (overlay, soft light, screen), blurs, censorize,
diffuse or sharpen, contrast equalizer.
