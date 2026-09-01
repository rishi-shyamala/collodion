# exposure (exposure)
group: tone | scene-referred | typical position: very early, first tonal step
synonyms: brightness, brighter, darker, ev, stops, underexposed, overexposed, too dark, too bright, lift, black point, exposure compensation, iso brightening
purpose: Multiplies the linear scene RGB signal by a constant gain expressed in
EV, and optionally shifts the black point. This is the module that sets middle
gray for the whole scene-referred pipeline; every later tone module (filmic rgb,
sigmoid, agx, tone equalizer, color balance rgb) assumes exposure has already
placed the subject's mid-tones near 18% gray.
use_when: the image is globally too dark or too bright; the raw looks flat and
dim straight out of camera (normal for scene-referred defaults); you need to
"expose to the right" in post; the subject's face or main mid-tone sits far from
the middle of the histogram; before touching any tone-mapping module.
do_not_combine: nothing is forbidden, but do not use exposure to fix only
highlights or only shadows -- it is a global multiplier. Use tone equalizer or
color balance rgb for range-selective work. Avoid stacking many exposure
instances where one would do.
key_controls:
- mode (manual | automatic): manual is the normal choice. automatic (raw only)
  derives the correction from a histogram percentile.
- exposure (EV): the gain, in stops. Soft range roughly -3 to +4 EV in practice;
  the slider allows up to about +-18 EV. Typical raw starting point is +0.5 to
  +1.5 EV on top of the default +0.7 EV auto-applied preset. Raise -> everything
  brightens proportionally, colours stay physically consistent.
- black level correction: subtracts a small constant before the gain. Typical
  values -0.005 to +0.005 (default around -0.000122). Lower (more negative) ->
  deeper blacks and slightly more contrast; raising it lifts the floor and can
  unclip negative RGB values that cause colour artefacts in deep shadows.
- compensate camera exposure: toggle; removes the exposure bias recorded in Exif
  so bracketed frames land at the same level.
- percentile / target level (EV) (automatic mode only): percentile picks the
  histogram location analysed (50% = median), target level says where that
  location should end up relative to camera white.
- area exposure mapping / colour picker: sample a patch and let darktable solve
  for the exposure that maps it to a chosen target lightness -- the fastest way
  to normalise a series of frames.
visual_effect: BEFORE: dark, flat, muddy raw with the histogram bunched to the
left; the subject reads as underexposed even though highlights are intact.
AFTER: the histogram is spread across the range, mid-tones sit where the eye
expects them, and later modules have room to work. Excessive positive exposure
pushes highlights past the clipping point and they can no longer be recovered
downstream; negative exposure crushes shadow detail into noise.
pitfalls: setting exposure after filmic/sigmoid instead of before it makes the
tone mapping fight you -- always set exposure first. Pushing exposure to fix a
dark subject in a high dynamic range scene blows the sky; use exposure for the
mid-tones and let filmic rgb roll off the highlights. Very large positive values
amplify sensor noise; denoise (profiled) works better applied with the true ISO
profile regardless of the exposure boost. Black level correction is a blunt
tool -- large negative values clip shadow colour information irreversibly.
pairs_with: filmic rgb or sigmoid (set exposure first, then the tone mapper),
tone equalizer, color balance rgb, denoise (profiled), highlight reconstruction.
