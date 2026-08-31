# rgb levels (rgblevels)
group: tone | display-referred | typical position: after tone mapping
synonyms: levels, black point, white point, gamma, midtone, histogram stretch, auto levels, contrast, clipping, set black and white
purpose: Sets black point, mid-gray and white point directly on the histogram in
RGB space, either for all channels together or per channel. It is the simplest
way to stretch a flat histogram to fill the range or to neutralise a cast by
setting per-channel black and white points.
use_when: the histogram does not reach either end and the image looks flat; a
scan or a JPEG has a lifted black point; you want a quick auto-levels
normalisation; a colour cast can be removed by aligning the per-channel end
points.
do_not_combine: tone curve, rgb curve and base curve all do overlapping work.
In a scene-referred edit prefer exposure plus filmic rgb over levels.
key_controls:
- mode (RGB, linked channels (default) | RGB, independent channels): linked gives
  one set of black/gray/white handles for tonality only; independent gives a set
  per channel and changes colour balance.
- black point handle: everything at or below this input value becomes black.
  Moving it right deepens blacks and increases contrast; move it just to the
  left of where the histogram data begins.
- mid-gray / gamma handle: repositions the mid-tone without moving the end
  points. Left brightens, right darkens.
- white point handle: everything at or above becomes white. Moving it left
  brightens the highlights and increases contrast.
- auto: sets the end points automatically from the histogram.
- the three pickers: sample a pixel that should be black, gray or white and the
  corresponding handle is set from it. The gray picker is the fast way to remove
  a cast.
- preserve colors: the luminance-preservation method that keeps hues stable as
  the levels change.
visual_effect: BEFORE: a hazy scan whose histogram occupies only the middle
third of the range. AFTER: full black-to-white range, restored contrast and
saturation. With independent channels: a neutral image where a green or magenta
cast has been removed by aligning the channel end points.
pitfalls: moving the black or white point past the ends of the histogram clips
real data irreversibly. Independent-channel levels on an image without a true
neutral reference introduce a cast rather than removing one. Auto levels on an
image with a legitimately dark or bright subject makes it worse. In a
scene-referred pipeline, levels applied before the tone mapper breaks the linear
assumption.
pairs_with: exposure, tone curve, rgb curve, color calibration, filmic rgb.
