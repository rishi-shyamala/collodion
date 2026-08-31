# raw black/white point (rawprepare)
group: correction | raw | typical position: first raw step
synonyms: black level, white level, raw clipping, magenta highlights, black point, sensor calibration, crop borders, gain map, flat field
purpose: Applies the sensor's black and white levels to the raw data and crops
the masked border pixels, before demosaic. It is auto-applied to every raw file
using values from darktable's camera database, and it defines what "clipped"
means for every module downstream.
use_when: shadows show a colour cast or refuse to reach neutral black; highlights
clip early or show magenta because the white point is wrong for your body; you
are working with an unsupported or unusual camera; you need the DNG GainMap
lens-shading compensation applied.
do_not_combine: do not use this as an exposure or black-level creative control
-- that is the exposure module's black level correction slider. Changing these
values invalidates the assumptions of highlight reconstruction.
key_controls:
- black level 0-3: the four black levels corresponding to the R, G1, G2 and B
  positions of the Bayer pattern. Raising them darkens and can crush shadows;
  lowering them lifts a floor and may leave a colour cast. Differences between
  the four values show up as a fine chequer pattern in deep shadows.
- white point: the raw value treated as fully saturated. Too low and highlights
  clip prematurely with a colour shift; too high and genuinely clipped pixels
  are treated as valid, which makes highlight reconstruction do nothing.
- flat field correction: uses the GainMap data embedded in some DNG files to
  compensate for lens shading, evening out corner falloff at the raw stage.
visual_effect: BEFORE (wrong white point): highlights that turn magenta or cyan
before they reach white, and a highlight reconstruction module that has nothing
to work with. AFTER: neutral clipping, correct black, and a raw signal that the
rest of the pipeline can interpret. The correct settings look like nothing at
all -- that is the point.
pitfalls: these values come from the camera database and are almost always right;
changing them by guesswork is a good way to break colour subtly across the whole
image. Any change here shifts what highlight reconstruction considers clipped.
The module is invisible in the default darkroom layout because it lives in the
technical group. Border cropping differences explain why raw dimensions vary
slightly between converters.
pairs_with: demosaic, highlight reconstruction, white balance, denoise
(profiled), input color profile.
