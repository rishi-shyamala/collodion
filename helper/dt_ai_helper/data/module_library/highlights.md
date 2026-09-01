# highlight reconstruction (highlights)
group: correction | raw | typical position: very early, raw stage
synonyms: blown highlights, clipped, sky is blown out, magenta clouds, pink highlights, recover highlights, clipping, overexposed sky, white sun, burned out
purpose: Reconstructs raw sensor data in areas where one or more channels have
clipped, so that clipped regions render as plausible colour instead of magenta
or flat white. It works on raw data before demosaic-stage colour is assigned, and
it is auto-applied to raw files by default.
use_when: highlights read magenta, pink or cyan (the classic clipped-channel
cast); the sky or a light source is blown out; you have raised exposure and the
brightest areas turned into flat white blobs; specular highlights show hard
banded edges.
do_not_combine: raw black/white point should be left at defaults unless you know
why you are changing it -- an incorrect white point makes this module misjudge
what is clipped. Filmic rgb's own highlight reconstruction is complementary, not
a replacement.
key_controls:
- method: inpaint opposed (default; averages adjacent unclipped pixels, fast and
  safe), segmentation based (treats each clipped blob separately; best for large
  clipped areas like skies), guided laplacians (Bayer sensors only; propagates
  detail from valid channels, best for medium clipped areas with structure),
  clip highlights (clamps everything to white -- a deliberate flat result), and
  reconstruct in LCh (legacy).
- clipping threshold: the raw value above which a pixel counts as clipped.
  Lower it if magenta fringes remain, raise it if the module is over-eager and
  is inventing detail where the data was fine. The clipping mask icon shows what
  is being treated as clipped, and is also exposed as a raster mask.
- noise level, iterations, inpaint a flat color, diameter of the reconstruction
  (guided laplacians): iterations refine the reconstruction at increasing cost;
  set the diameter to roughly twice the largest clipped area.
- combine, candidating, rebuild (small | large | flat | generic)
  (segmentation based): combine merges nearby segments, candidating trades
  segmentation analysis against plain inpaint opposed, rebuild picks the
  strategy for the size of the clipped regions.
visual_effect: BEFORE: a magenta or pink sun, cyan-edged clouds, hard flat
white patches with visible colour fringes at their borders. AFTER: clipped areas
take on neutral or scene-plausible colour and blend smoothly into the surrounding
unclipped pixels; large blown skies read as bright white/blue instead of pink.
pitfalls: no algorithm can invent detail that was never recorded -- if all three
channels are clipped, the best you get is smooth, plausible colour. Guided
laplacians with too few iterations leaves a soft plastic look; too many is slow.
Lowering the clipping threshold too far makes the module reconstruct valid data
and flattens real highlight detail. On X-Trans sensors guided laplacians is not
available -- use segmentation based or inpaint opposed.
pairs_with: exposure, filmic rgb (its reconstruct tab handles the display-side
rolloff), raw black/white point, color calibration.
