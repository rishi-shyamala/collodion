# input color profile (colorin)
group: color | technical | typical position: early, right after demosaic
synonyms: input profile, icc, camera profile, working profile, color space, rec2020, gamut clipping, wrong colors, embedded profile, prophoto
purpose: Interprets the camera's or file's RGB numbers as real colours by
applying an input profile, and sets the working colour space that every
subsequent module operates in. It is auto-applied to every image and is the
foundation of darktable's colour management.
use_when: colours are systematically wrong for a specific camera and a better
matrix or ICC profile exists; you need a wider or narrower working space; highly
saturated colours are producing artefacts and need gamut clipping; a JPEG or DNG
has an embedded profile that should be honoured.
do_not_combine: this is a technical module; it should not be used as a creative
colour tool. Use color calibration or color balance rgb for that.
key_controls:
- input profile: the colour transform applied to the camera data. darktable
  supplies standard and, for some bodies, enhanced matrices; custom ICC profiles
  dropped into the colour "in" directory appear here. The "embedded icc profile"
  option restores the file's own profile for JPEGs and DNGs.
- working profile (default "linear Rec. 2020 RGB"): the colour space all
  downstream modules compute in. Rec. 2020 is wide enough to hold almost any
  camera gamut; narrower spaces clip saturated colours earlier but can be more
  forgiving with legacy modules.
- gamut clipping (default off; options linear Rec. 2020 RGB, Adobe RGB
  (compatible), sRGB, linear Rec. 709 RGB): clips out-of-gamut colours to the
  chosen space to prevent artefacts. Rec. 2020 and Adobe RGB clip least;
  sRGB and Rec. 709 clip most aggressively.
visual_effect: BEFORE (wrong profile): systematically shifted colour -- skin too
magenta, foliage too yellow -- that no amount of white balancing fixes.
AFTER: neutral, camera-accurate colour that responds predictably to grading.
Enabling gamut clipping visibly tames fluorescent-looking saturated flowers and
blue LEDs at the cost of some saturation.
pitfalls: changing the working profile changes the numeric meaning of every
downstream module's settings, so an existing edit will shift. Very wide working
spaces can produce out-of-gamut intermediate values that later modules mishandle
-- that is exactly what gamut clipping is for. Using a custom ICC profile built
for a different illuminant than the shot introduces a cast. This module is not
where white balance belongs.
pairs_with: color calibration, output color profile, white balance,
color balance rgb, monochrome.
