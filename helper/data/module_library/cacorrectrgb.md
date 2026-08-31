# chromatic aberrations (cacorrectrgb)
group: correction | scene-referred | typical position: after demosaic
synonyms: chromatic aberration, purple fringing, color fringing, green fringe, ca, fringe removal, lateral ca, longitudinal ca, defringe, edge color
purpose: Removes colour fringing by re-aligning the chromaticity of the R and B
channels to a guide channel. Unlike raw chromatic aberrations it works after
demosaic and can handle both lateral and longitudinal (purple/green out-of-focus)
aberrations, including fringing that lens profiles do not model.
use_when: high-contrast edges show purple or green fringes, especially toward the
frame corners or in out-of-focus areas of fast lenses; lens correction's TCA
model did not remove all the fringing; backlit branches against a bright sky show
coloured outlines.
do_not_combine: it complements rather than replaces lens correction's TCA and
raw chromatic aberrations; apply those first and use this for what remains.
The deprecated defringe module is superseded by it.
key_controls:
- guide: the colour channel used as the geometric reference the other two are
  matched to. Green is the usual choice because it is the sharpest and least
  noisy channel; switch it if the fringing is predominantly green.
- radius: the effect radius, described by the manual as the module's most
  important slider. Increase it until the aberrations disappear; too large and
  genuine colour detail near edges is dragged toward the guide channel.
- strength: a safeguard that preserves genuinely colourful areas that have no
  aberration. Raise it for stronger correction, lower it to protect real colour.
- correction mode: restricts the effect to only brighten or only darken pixels,
  which combined with R, G and B blend modes and multiple instances lets you
  target one fringe colour at a time.
- very large chromatic aberrations: switches the algorithm to an iterative mode
  for severe cases, at a performance cost.
visual_effect: BEFORE: bright purple outlines along backlit branches and window
frames, green halos on out-of-focus highlights. AFTER: those edges render
neutral, with the underlying luminance detail unchanged. Overdone: genuinely
purple or green objects lose their colour and drift toward gray near their edges.
pitfalls: over-large radii desaturate real coloured detail -- check any small
saturated object in the frame, not just the fringed edges. The module cannot fix
fringing that has already been clipped to white. Running it before demosaic
artefacts are dealt with can lock in false colour. It is comparatively expensive
on large files.
pairs_with: lens correction, raw chromatic aberrations, demosaic, diffuse or
sharpen, color balance rgb.
