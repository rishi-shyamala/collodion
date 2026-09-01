# vignetting (vignette)
group: effect | display-referred | typical position: late, creative stage
synonyms: vignette, darken corners, darken edges, focus attention, lomo, spotlight, burn edges, frame the subject, brighten center
purpose: Adds a creative brightness and saturation falloff toward the edges of
the frame (or brightens them). This is a deliberate stylistic vignette; use the
lens correction module to remove an unwanted optical one.
use_when: the eye wanders to bright corners; you want to draw attention to a
central subject; you are emulating a lomo, holga or old-lens look; a bright edge
element distracts from the subject.
do_not_combine: it is not a substitute for lens correction's vignetting
compensation, and stacking a strong creative vignette on top of an uncorrected
optical one doubles the effect.
key_controls:
- brightness: the strength and sign of the effect. Negative darkens the edges
  (typical -0.2 to -0.6 for a subtle vignette), positive brightens them.
- fall-off start (%): the radius of the untouched central area. Typical 40-70%.
- fall-off radius (%): how progressive the transition is; lower values give a
  steeper, more visible edge.
- saturation: colour strength inside the affected area; negative desaturates the
  edges as they darken, which usually looks more natural.
- horizontal center / vertical center: shift the vignette away from the middle
  to sit over an off-centre subject.
- shape: 1.0 is a circle/ellipse, smaller values approach a rectangle, larger
  values give a cross-like falloff.
- automatic ratio: matches the vignette's aspect ratio to the image, producing an
  ellipse rather than a circle.
- width/height ratio: manual control of the vignette's proportions.
- dithering (off | 8-bit output | 16-bit output): prevents banding in the smooth
  falloff, which is very visible in 8-bit JPEG skies.
visual_effect: BEFORE: an evenly lit frame where a bright corner competes with
the subject. AFTER: a soft darkening from about two thirds of the way out to the
corners, so the subject is the brightest thing in the frame. Overdone: an
obvious dark ring, banding in skies and a "photo taken through a tube" look.
pitfalls: strong vignettes band badly in smooth gradients unless dithering is
enabled. A circular vignette on a wide crop looks wrong; enable automatic ratio.
Applying it before the crop means the vignette centre no longer matches the
final composition -- vignetting runs late in the pipe for exactly this reason.
Combining a negative brightness with a positive saturation gives muddy corners.
pairs_with: crop, framing, grain, split-toning, color balance rgb.
