# output color profile (colorout)
group: color | technical | typical position: last colour step, at export
synonyms: output profile, srgb, adobe rgb, export color space, icc, rendering intent, colors look different, embed profile, print profile
purpose: Converts the working colour space to the profile the exported file or
the display should use, and embeds that profile in formats that support it. It
is the last colour management step in the pipeline.
use_when: preparing files for the web (sRGB), for print (Adobe RGB or a printer
profile), or for further editing in another application; exported images look
different from the darkroom view; a lab requires a specific colour space.
do_not_combine: this is a technical module -- creative colour work belongs
upstream. Applying a LUT or colour look up table after it is not possible in the
normal pipe order.
key_controls:
- output profile: the destination colour space. Predefined options include sRGB,
  Adobe RGB (compatible), XYZ and linear RGB; custom ICC profiles placed in
  darktable's colour "out" directory also appear. The profile is embedded in
  formats that support it.
- output intent: the rendering intent used for the conversion (perceptual,
  relative colorimetric, saturation, absolute colorimetric). It is only shown
  when LittleCMS2 is selected for profile application in preferences; with
  darktable's internal rendering the control is hidden.
visual_effect: BEFORE: an image whose numbers are in a wide working space.
AFTER: the same appearance, expressed in the destination space. The visible
consequence of getting it wrong is dramatic: an Adobe RGB file shown in a
non-colour-managed browser looks flat and desaturated, and an sRGB file sent to
a wide-gamut print workflow loses saturation it could have kept.
pitfalls: the manual's advice is to stick to sRGB unless you have a specific
reason otherwise, because many applications ignore embedded profiles. Choosing a
wide output space for web publishing is the most common cause of "my exports look
washed out". Rendering intent only matters for out-of-gamut colours and only when
LittleCMS2 is in use. This module does not soft-proof -- use the soft proof
feature in the darkroom for that.
pairs_with: input color profile, soft proofing, LUT 3D, filmic rgb,
color balance rgb.
