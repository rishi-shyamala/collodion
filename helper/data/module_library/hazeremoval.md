# haze removal (hazeremoval)
group: correction | display-referred | typical position: after tone mapping
synonyms: dehaze, haze, fog, mist, atmospheric haze, low contrast distance, murky, clear the air, add fog, smog
purpose: Estimates and removes atmospheric haze using a dark-channel-prior
depth estimate, restoring contrast and saturation in distant parts of the scene
without flattening the foreground. Negative strength adds haze instead.
use_when: distant hills or city skylines look washed out and low-contrast;
shooting through humid or smoggy air; aerial or long-lens landscape shots;
you deliberately want to add atmospheric depth (negative strength).
do_not_combine: it is not a general contrast tool -- for a non-hazy image, local
contrast, contrast & texture or diffuse or sharpen's dehaze preset give better
results. Stacking haze removal with a big local-contrast boost over-crunches.
key_controls:
- strength (default 1.0): how much of the detected haze is removed. At 1.0 the
  module removes 100% of the haze it detects up to the specified distance.
  Typical 0.2-0.8; negative values add haze.
- distance (default 1.0, range 0-1): how far into the scene the correction
  reaches. Low values affect only the foreground; 1.0 processes the whole depth
  range. It has no effect when strength is negative.
visual_effect: BEFORE: distant mountains fade into a pale gray-blue murk with
almost no contrast or colour. AFTER: the distant layers regain contrast and
colour separation and the image reads as deeper. Overdone: black, crunchy
shadows in the distance, cyan or magenta casts in the sky, and a hard,
oversaturated look.
pitfalls: the manual recommends keeping both sliders below unity -- at 1.0/1.0
the module frequently produces artefacts and unnatural colour. Haze removal
darkens the image overall, so it usually needs a small exposure or tone
adjustment afterwards. It amplifies noise in the recovered distant areas. On
images with genuine fog as the subject, removing it destroys the photograph.
pairs_with: local contrast, contrast & texture, diffuse or sharpen (dehaze
preset), color balance rgb, exposure.
