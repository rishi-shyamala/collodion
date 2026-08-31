# base curve (basecurve)
group: tone | display-referred | typical position: early, display-referred workflow only
synonyms: camera look, jpeg look, default curve, display referred, legacy workflow, contrast, exposure fusion, hdr from single raw
purpose: Applies a manufacturer-style tone curve that makes a raw file look like
the camera's own JPEG. It is the tone mapper of darktable's legacy
display-referred workflow and is auto-applied only when that workflow is
selected in preferences.
use_when: you deliberately want the camera-JPEG rendering as a starting point;
you are editing an old darktable history stack that already uses it; you want the
exposure fusion feature to compress a high dynamic range scene from a single raw.
do_not_combine: filmic rgb, sigmoid, agx (choose exactly one display transform).
The scene-referred workflow explicitly replaces base curve with filmic/sigmoid.
key_controls:
- the curve and its preset list: camera-specific and generic manufacturer
  presets, chosen automatically from Exif when the display-referred workflow is
  active. Editing the curve directly changes global contrast and brightness.
- fusion: merges several internally-generated exposures of the same image, which
  is the module's built-in single-raw HDR compression.
- exposure shift (fusion, EV): the exposure difference between the merged
  copies; default 1 EV. Larger values compress more dynamic range.
- exposure bias (fusion): +1 generates overexposed copies (lifts shadows), -1
  generates underexposed copies (recovers highlights), 0 balances both.
- preserve colors: the luminance-preservation method that stops the curve from
  desaturating highlights.
- scale for graph: linear or logarithmic display of the curve axes.
visual_effect: BEFORE: flat linear raw data. AFTER: the punchy, contrasty,
slightly saturated rendering the camera would have produced in-camera, with a
hard highlight shoulder. With fusion enabled: a much flatter, HDR-like image
with open shadows and retained highlights, at the cost of some local contrast.
pitfalls: base curve clips highlights harder than filmic rgb and desaturates
them noticeably; it is the main reason legacy darktable edits show blown skies.
Because it is applied early and is display-referred, everything after it works on
non-linear data, which breaks the assumptions of modern modules like color
balance rgb and tone equalizer. Fusion is slow and can produce halos. Do not
enable it alongside filmic rgb -- the image will be double-tone-mapped.
pairs_with: exposure, tone curve, rgb curve, local contrast, velvia.
