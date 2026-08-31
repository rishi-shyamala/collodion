# white balance (temperature)
group: color | raw | typical position: very early, before color calibration
synonyms: wb, white balance, color temperature, kelvin, tint, too warm, too orange, too blue, too cool, color cast, yellow cast, blue cast, neutral gray, as shot
purpose: Applies per-channel multipliers to raw sensor data so that a neutral
object in the scene renders neutral. In the modern scene-referred workflow this
module is normally left at "camera reference" (D65) and the actual white balance
is done downstream in color calibration; in legacy workflows it does the whole
job itself.
use_when: the image is too warm/orange or too cool/blue; an artificial light
source has produced a colour cast; you shot under mixed lighting and need a
neutral starting point; you want to warm up a sunset deliberately.
do_not_combine: doing a full white balance here AND in color calibration
double-corrects the image. Pick one: either temperature does it (legacy) or
temperature is set to camera reference and color calibration does it (modern).
key_controls:
- setting (preset dropdown): as shot, from image area, user modified, camera
  reference, as shot to reference (the default when color calibration is
  handling white balance), plus camera-specific presets.
- temperature (K) (scene illuminant temp tab): the colour temperature of the
  assumed scene illuminant. Typical daylight 5000-6500 K, shade 7000-8000 K,
  tungsten 2700-3200 K. Raising the value makes the image warmer/more orange
  (it assumes a cooler illuminant), lowering it makes the image cooler/bluer.
- tint (scene illuminant temp tab): the green<->magenta axis; below 1 pushes
  magenta, above 1 pushes green. Typical 0.9-1.1; fluorescent light often needs
  a magenta correction.
- red / green / blue (channel coefficients tab, 0-8): the raw multipliers
  themselves, hidden by default. Editing these directly is for special cases
  (astrophotography, unusual sensors) or for matching another program's values.
- finetune (camera presets): camera-specific offsets when the manufacturer
  provides them.
visual_effect: BEFORE: snow that reads as blue, an indoor scene drowning in
orange tungsten light, or skin that looks jaundiced. AFTER: neutral whites and
grays, skin tones that read as skin, and colour relationships that respond
predictably to later grading.
pitfalls: white-balancing off a coloured object rather than a neutral one bakes
in the complementary cast. With color calibration enabled, changing temperature
here shifts the illuminant color calibration assumes and the two fight -- leave
it at "as shot to reference". Extreme temperature values clip a channel to the
0-8 coefficient limit and produce unrecoverable colour. Auto white balance from
image area needs an actual neutral patch in the frame.
pairs_with: color calibration (the modern place to do this), input color
profile, exposure, color balance rgb.
