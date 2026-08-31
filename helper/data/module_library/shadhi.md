# shadows and highlights (shadhi)
group: tone | display-referred | typical position: after tone mapping
synonyms: lift shadows, recover shadows, darken highlights, open shadows, fill light, hdr, backlit, shadow detail, blown highlights, dodge burn
purpose: Lightens shadows and darkens highlights using a blurred version of the
image as the selection mask. It is the legacy display-referred answer to "the
subject is too dark and the sky is too bright"; the manual now recommends the
tone equalizer instead because this module halos and shifts hues when pushed.
use_when: you are working on a legacy display-referred edit; you want a quick
one-slider shadow lift on a JPEG; you are reproducing an existing history stack.
do_not_combine: tone equalizer (the modern replacement), global tonemap, fill
light, zone system. Using shadows and highlights on top of filmic rgb
double-compresses the tone range.
key_controls:
- shadows (default 0): positive lightens shadows, negative darkens them.
  Typical +20 to +50; beyond that halos and washed-out shadows appear.
- highlights (default 0): negative darkens highlights (the usual direction),
  positive lightens them. Typical -20 to -50.
- white point adjustment (default 0): corrects tonal values that exceed
  luminance 100 after the corrections, recovering highlight detail that would
  otherwise clip.
- soften with (gaussian (default) | bilateral filter): the blur used to build
  the mask; the bilateral filter is edge-aware and halos considerably less.
- radius: the mask blur radius. Higher gives softer transitions but introduces
  halos; lower makes the effect look local and gritty.
- compress (%, default 50): how far the effect extends into the mid-tones.
  Higher values confine the effect to the extremes.
- shadows color adjustment (%, default 100): how much saturation is boosted in
  the lightened shadows; high values make lifted shadows look garish.
- highlights color adjustment (%): the same for the highlight end.
visual_effect: BEFORE: a backlit portrait where the face is dark and the sky
behind is bright. AFTER: the face is lifted and the sky pulled down, at the cost
of a visible bright halo along the subject's outline if the radius is large.
pitfalls: this module's halos are its defining weakness -- switch to the
bilateral filter and keep the radius modest, or use tone equalizer instead.
Lifting shadows hard amplifies noise and, with shadows color adjustment at 100%,
produces oversaturated coloured shadows. Because it is display-referred it works
on already tone-mapped data and easily flattens the image into an HDR look.
pairs_with: tone equalizer (preferred), exposure, filmic rgb, denoise (profiled),
local contrast.
