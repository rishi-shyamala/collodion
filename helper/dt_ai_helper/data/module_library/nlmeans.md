# astrophoto denoise (nlmeans)
group: correction | display-referred | typical position: late, after tone work
synonyms: denoise, noise, astro, non local means, nlmeans, star field, chroma noise, luminance noise, high iso, smooth noise, night sky
purpose: Non-local means denoising tuned for images with fine point-like detail
against smooth backgrounds -- astrophotography above all. Each pixel is averaged
with surrounding pixels weighted by how similar their neighbourhoods are, which
preserves stars and fine texture better than a plain spatial filter. Previously
known simply as "denoise (non-local means)".
use_when: denoising a night-sky or astro image where stars must survive; the
profiled denoiser is smearing fine point detail; you need an extra chroma-only
denoising pass late in the pipeline; the camera has no noise profile.
do_not_combine: running this and denoise (profiled) at full strength on the same
image smears texture. Use profiled denoise as the primary and this as a targeted
second pass, or vice versa.
key_controls:
- patch size: the radius of the neighbourhood used to judge similarity. Typical
  1-3; larger patches are more selective and much slower.
- strength: the overall denoising amount. Typical 0.3-1.0.
- luma (%): how much of the effect applies to luminance. Keep this low (10-40%)
  to preserve detail; luminance noise is also the component that reads as
  "texture" rather than "damage".
- chroma (%): how much applies to colour. This can be pushed hard (80-100%) --
  chroma noise carries almost no useful information and removing it is nearly
  always an improvement.
visual_effect: BEFORE: a star field speckled with coloured noise, where it is
hard to tell faint stars from noise. AFTER: a clean dark background with the
stars intact and their colour preserved. On ordinary photographs: smooth skies
and shadows with fine texture largely retained.
pitfalls: this module operates in non-linear Lab and slows the pipeline
significantly -- the manual recommends enabling it late in the workflow. High
luma values smear faint stars out of existence, which is the exact failure the
module is meant to avoid. It is not profiled, so it does not know the real noise
level and its settings do not transfer between ISO values.
pairs_with: denoise (profiled), raw denoise, exposure, contrast equalizer,
surface blur.
