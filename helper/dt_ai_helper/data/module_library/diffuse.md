# diffuse or sharpen (diffuse)
group: sharpness | scene-referred | typical position: mid-to-late, after tone work
synonyms: clarity, sharpen, deblur, lens blur recovery, dehaze, denoise, bloom, orton, texture, soft focus, glow, structure, local contrast, inpaint highlights
purpose: A generalised PDE-based diffusion engine. Run forward it blurs
(denoise, bloom, surface smoothing, Orton glow); run backward it reverses
diffusion and therefore deblurs (lens deblur, demosaic sharpening, local
contrast, dehaze). Almost every "clarity", "texture" or "deblur" request in
darktable is best answered with one of this module's presets.
use_when: the image needs clarity or micro-contrast; the lens is soft and you
want real deconvolution rather than unsharp halos; you want a dreamy glow or
Orton effect; you need edge-aware smoothing of skin or sky; you want to inpaint
clipped highlights.
do_not_combine: multiple aggressive instances of this module compound quickly;
also avoid stacking it with heavy sharpen and contrast equalizer sharpening.
key_controls:
- iterations (properties): how many times the PDE is applied. Typical 1-8;
  more iterations = stronger and slower, and the main quality/cost dial.
- central radius and radius span (properties): which detail scale is affected.
  Central radius 0 with a large span covers all scales; a non-zero central
  radius targets a specific feature size (grain, hair, foliage).
- 1st order speed (gradient), 2nd order speed (laplacian), 3rd order speed
  (gradient of laplacian), 4th order speed (laplacian of laplacian) (speed
  section): negative values sharpen, positive values diffuse. Typical +-10 to
  +-50%. Fourth order affects the finest structures, first order the coarsest.
- 1st/2nd/3rd/4th order anisotropy (direction section): how strongly diffusion
  follows edge direction (isotropic at 0, strongly directional at high values).
- sharpness, edge sensitivity, edge threshold (edge management): control how the
  effect is held back at edges to avoid halos and ringing.
- luminance masking threshold (diffusion spatiality): restricts the effect to
  pixels above a luminance, used by the highlight-inpainting presets.
- presets: sharpen demosaicing, lens deblur (soft/medium/hard), dehaze, local
  contrast, bloom, orton, inpaint highlights, denoise, surface blur, simulate
  line drawing, simulate watercolor, plus "fast" variants for machines without
  OpenCL.
visual_effect: BEFORE: a slightly soft, hazy image with mushy fine detail.
AFTER (lens deblur preset): genuinely resolved fine detail without the bright
halos of unsharp mask. AFTER (bloom/orton preset): highlights bleed softly into
their surroundings for a dreamy, film-like glow.
pitfalls: this is the most expensive module in darktable -- without OpenCL,
high iteration counts make the darkroom crawl; use the fast presets. Backward
diffusion amplifies noise and demosaic artefacts, so denoise first. Too many
iterations produce a scratchy, etched look and ringing at high-contrast edges.
Starting from scratch instead of from a preset is a reliable way to waste an
evening.
pairs_with: denoise (profiled) (before), contrast & texture, local contrast,
filmic rgb, censorize (for the blur-based creative effects).
