# contrast & texture (contrastntexture)
group: sharpness | scene-referred | typical position: after tone mapping
synonyms: clarity, texture, local contrast, micro contrast, structure, punch, detail, depth, crisp, definition
purpose: Boosts or suppresses local contrast at a chosen detail scale using an
exposure-independent guided filter (eigf), so the strength of the effect is the
same in shadows and highlights. It is the modern, well-behaved answer to
"clarity" and "texture" in a scene-referred edit.
use_when: the image needs clarity or definition without halos; you want texture
in rock, fabric or foliage to read more strongly; you want to reduce texture
(negative values) to smooth skin; local contrast and contrast equalizer are
producing halos or uneven strength across the tonal range.
do_not_combine: stacking this with local contrast, contrast equalizer's coarse
scales and diffuse or sharpen's local contrast preset triples the same effect.
Multiple instances of this module at different detail levels is the intended way
to layer the effect.
key_controls:
- local contrast (%, 0% neutral): the strength. Positive boosts texture,
  negative reduces it. Typical +10 to +40%; negative -10 to -30% for skin.
  A mask visualisation icon shows what is being affected.
- detail level (filter settings tab): the spatial scale targeted. Higher values
  target finer details (texture, grain, pores), lower values target coarse
  structure (clarity, depth).
- adjust edge protection (filter settings tab): how sensitive the guided filter
  is to high-contrast edges. Lower values give stronger local contrast with more
  halo risk; higher values give smoother, safer transitions.
- filter iterations (filter settings tab): the number of guided filter passes.
  More iterations diffuse the edges of the effect and reduce artefacts, at a
  performance cost.
- noise bias (filter settings tab): holds the effect back in the shadows so that
  shadow noise is not amplified. Higher values suppress more noise but also
  suppress genuine fine shadow detail.
visual_effect: BEFORE: a correctly toned but slightly soft image where rock
texture, fabric weave and foliage all read as mush. AFTER: those surfaces gain
definition and the image reads as three-dimensional, with no bright halo along
the horizon and with the effect equally strong in the dark foreground and the
bright sky -- the property that distinguishes eigf from ordinary guided filters.
pitfalls: judging the effect at fit-to-screen zoom is misleading because the
detail level is measured in pixels; check at 100%. High local contrast with low
edge protection still halos, just less than the older modules. Boosting fine
detail levels amplifies noise; raise noise bias or denoise first. Negative values
for skin smoothing quickly look plastic.
pairs_with: diffuse or sharpen, local contrast, contrast equalizer, denoise
(profiled), filmic rgb.
