# lens correction (lens)
group: correction | geometry | typical position: early geometric stage
synonyms: distortion, barrel distortion, pincushion, vignetting, dark corners, chromatic aberration, purple fringing, tca, lensfun, lens profile, wide angle bulge
purpose: Corrects the optical defects of the taking lens -- geometric
distortion, transverse chromatic aberration and vignetting -- using either the
lensfun database or the correction metadata embedded in the raw file by the
camera manufacturer.
use_when: straight lines bow outward (barrel) or inward (pincushion), typically
on wide-angle and zoom lenses; corners are noticeably darker than the centre;
high-contrast edges show coloured fringes toward the frame corners; you are
stitching or need geometrically faithful output.
do_not_combine: correcting distortion here and again via rotate and perspective's
lens model, or vignetting here and again with a manual vignetting module, gives
double corrections. Chromatic aberrations (cacorrectrgb) is complementary and
handles what lensfun's TCA model cannot.
key_controls:
- correction method (lensfun | embedded metadata): embedded metadata uses the
  maker's own model and is usually more accurate when present.
- camera and lens (lensfun): the profile selection; darktable guesses from Exif
  but you often have to pick the exact lens by hand.
- focal length, aperture, focal distance (lensfun photometric parameters): the
  shooting conditions the correction is computed for; focal distance mainly
  matters for distortion at close range.
- target geometry and scale (lensfun): rectilinear, fisheye, panoramic and
  similar projections, plus how much the corrected image is scaled to fill frame.
- mode: which corrections are applied (distortion, TCA, vignetting) and in which
  direction (correct or distort).
- TCA override, TCA red, TCA blue (lensfun): manual transverse chromatic
  aberration scaling when the profile's values are wrong.
- use latest algorithm, distortion, vignetting, TCA red, TCA blue, image scale
  (embedded metadata): fine-tuning multipliers on top of the maker's correction.
- strength, radius, steepness (manual vignette correction): a hand-tuned
  vignette compensation available with either method.
visual_effect: BEFORE: a wide-angle architectural shot where the horizon bows,
corners fall off a stop and a half darker, and window frames show cyan/magenta
edges. AFTER: straight lines are straight, illumination is even across the
frame, and the coloured fringes are gone.
pitfalls: choosing the wrong lens profile applies a plausible-looking but wrong
correction; check straight lines at the frame edge. Distortion correction
resamples the image and slightly softens it, so it belongs before sharpening.
Full vignetting correction on a heavily vignetted fast lens lifts corner noise
dramatically. If lensfun has no profile for your lens, prefer the embedded
metadata method or correct manually with rotate and perspective plus vignetting.
pairs_with: rotate and perspective, chromatic aberrations, raw chromatic
aberrations, crop, denoise (profiled).
