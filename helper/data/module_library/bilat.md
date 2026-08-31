# local contrast (bilat)
group: tone | display-referred | typical position: after tone mapping
synonyms: clarity, punch, local contrast, micro contrast, structure, depth, texture, flat image, hdr look, dehaze, tone mapping local
purpose: Boosts contrast at intermediate spatial scales without changing global
tonality, using either a bilateral grid or a local laplacian filter. This is the
module people reach for when they say "clarity" or "the image needs depth".
use_when: the image is globally correct but looks flat and two-dimensional;
landscape detail needs to read more strongly; you want a mild HDR-like local
tone-mapping effect; haze reduces apparent contrast in the mid-tones.
do_not_combine: stacking local contrast with contrast & texture, contrast
equalizer's coarse scales and diffuse or sharpen's local contrast preset triples
the same effect and produces halos.
key_controls:
- mode (local laplacian (default) | bilateral grid): local laplacian resists
  halos and gradient reversals and is the recommended choice.
- detail (local laplacian, %): the S-curve applied to local detail; typical
  100-160%, higher = more local contrast.
- highlights (local laplacian, %): compresses or expands contrast in the bright
  end; low values pull highlights down.
- shadows (local laplacian, %): higher = more shadow contrast, lower behaves
  like a fill light. Note it can only manipulate locally -- it cannot brighten
  areas that are genuinely black.
- mid-tone range (local laplacian): widens the S-curve so more tones count as
  mid-tones; reduce it for HDR-style compression. Extreme values cause banding.
- coarseness (bilateral grid): the size of the details being affected.
- contrast (bilateral grid): how strongly brightness levels are separated.
- detail (bilateral grid, %): the local contrast strength; typical 120-180%.
visual_effect: BEFORE: a technically correct but flat landscape where rock
texture and cloud structure blend together. AFTER: rocks, clouds and foliage
gain three-dimensional separation while the overall brightness and global
contrast stay where you put them. Overdone: dark halos around the horizon,
grubby-looking skies and a gritty HDR-postcard look.
pitfalls: the module works on the L channel in Lab, which is display-referred
thinking -- on scene-referred edits, diffuse or sharpen's local contrast preset
or the newer contrast & texture module are better behaved. Bilateral grid mode
halos more readily than local laplacian. Extreme mid-tone range values band in
smooth skies. Local contrast amplifies noise in flat shadow areas.
pairs_with: contrast & texture, diffuse or sharpen, contrast equalizer,
filmic rgb, haze removal.
