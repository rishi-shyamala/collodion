# grain (grain)
group: effect | display-referred | typical position: late, creative stage
synonyms: film grain, grain, texture, analog look, noise, filmic texture, iso grain, gritty, black and white grain
purpose: Adds simulated silver-halide film grain, with a grain size scaled to
emulate a chosen ISO number. Unlike sensor noise it is a deliberate, structured
texture used to give digital files an analog character or to disguise banding.
use_when: a black and white conversion looks too clean and digital; you want an
analog film character; smooth gradients are banding and a little grain breaks
them up; you are matching a set of images shot on film.
do_not_combine: adding grain and then denoising afterwards removes it again --
grain must come after all denoising. Censorize's noise level control and diffuse
or sharpen's noise options overlap slightly.
key_controls:
- coarseness: the grain size, scaled as an ISO number (typical 400-3200). Larger
  values give bigger, more visible grain clumps; the effect is resolution
  dependent, so judge it at the output size.
- strength: the intensity of the grain. Typical 10-40%; above about 60% it reads
  as an effect rather than a texture.
- mid-tone bias: shifts the grain toward the mid-tones. Higher values reduce
  visible grain in shadows and highlights, which is how real film behaves and
  usually looks more convincing.
visual_effect: BEFORE: a perfectly smooth digital image, especially obvious in
skies and in black and white conversions. AFTER: a fine, even texture across the
mid-tones that reads as film stock, with clean highlights and shadows if
mid-tone bias is raised. Overdone: an obvious dotted overlay that hides real
detail.
pitfalls: grain is added at full image resolution, so a setting judged at
fit-to-screen zoom will be far too strong (or invisible) in the export -- always
check at 100% and at the intended output size. Adding grain before sharpening
means the sharpener amplifies the grain. Grain plus heavy JPEG compression
produces ugly artefacts because grain is expensive to encode.
pairs_with: monochrome, color calibration (gray tab), split-toning, vignetting,
sharpen.
