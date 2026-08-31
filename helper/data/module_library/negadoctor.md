# negadoctor (negadoctor)
group: color | scene-referred | typical position: after input color profile, before tone mapping
synonyms: film negative, scan, invert negative, c41, color negative, film scanning, orange mask, darkroom print, paper grade, negative to positive
purpose: Converts a scanned or digitally-photographed colour or black and white
negative into a positive, modelling the physical darkroom printing process:
film base density, the enlarger exposure, the paper grade and the paper's black
and gloss.
use_when: you have digitised film negatives with a camera or scanner; the
orange film base mask needs removing; a simple invert plus curves is producing
unmanageable colour casts.
do_not_combine: the deprecated invert module (negadoctor supersedes it), and any
white balance done to "fix" the orange mask before this module -- the mask is
handled here, from the film base colour.
key_controls:
- film stock (color film | black and white film): selects the model; colour film
  exposes RGB triplets where B&W exposes single values.
- color of the film base (film properties tab): pick an unexposed area of the
  film base with the picker. Getting this right is the single most important
  step.
- D min (film properties): the minimum density of the film, per channel for
  colour film. Derived from the film base colour.
- D max (film properties): the dynamic range of the scan, with a picker; sets
  how much density separates black from white on the negative.
- scan exposure bias (film properties): compensates for how the scan itself was
  exposed.
- shadows color cast R/G/B (corrections tab): removes residual casts in the
  print's shadows.
- highlights white balance R/G/B (corrections tab): neutralises the highlight end.
- paper black (density correction) (print properties tab): where the print's
  black point sits.
- paper grade (gamma) (print properties, default 4): the contrast of the virtual
  paper, exactly as darkroom paper grades work -- higher is more contrasty.
- paper gloss (specular highlights) (print properties): how bright the specular
  highlights are allowed to get.
- print exposure adjustment (print properties): the enlarger exposure time, i.e.
  overall brightness of the print.
visual_effect: BEFORE: an orange-cast negative image. AFTER: a positive with
neutral whites, believable skin tones and film-like contrast, without the
crushed, cast-ridden result that a naive channel inversion gives.
pitfalls: the manual is emphatic that the controls must be set in the order they
appear in the GUI -- film properties, then corrections, then print properties.
Sampling the film base from an exposed area rather than the clear base ruins
everything downstream. Applying white balance or exposure corrections before
negadoctor changes the density model's inputs. The module expects linear input,
so it belongs before the tone mapper.
pairs_with: input color profile, exposure, filmic rgb, color balance rgb,
color calibration.
