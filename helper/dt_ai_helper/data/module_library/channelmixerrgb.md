# color calibration (channelmixerrgb)
group: color | scene-referred | typical position: after input color profile
synonyms: white balance, wb, chromatic adaptation, cat, illuminant, color cast, mixed lighting, channel mixer, black and white conversion, monochrome mix, color checker, calibration
purpose: Performs chromatic adaptation (the modern white balance) plus a full
3x3 channel mixer in the working RGB space. In the scene-referred workflow this
is where white balance actually happens, with the legacy white balance module
left at "camera reference". It also does colour-accurate black and white
conversion and colour-checker based camera calibration.
use_when: the image has a colour cast that white balance alone cannot fix;
lighting is mixed (tungsten indoors plus daylight through a window); you want a
filtered black and white conversion; you have shot a colour checker and want a
per-camera correction; you need to boost or damp one channel's contribution to
another.
do_not_combine: doing a second full white balance in the temperature module.
Also redundant with the deprecated channel mixer module.
key_controls:
- adaptation: linear Bradford (1985), CAT16 (2016) (default), non-linear
  Bradford, XYZ, or none. CAT16 handles saturated illuminants best.
- illuminant (CAT tab): same as pipeline (D50), CIE standard illuminant, custom,
  or as shot in camera. "As shot in camera" reads the camera's estimate.
- temperature (CAT tab, K): illuminant colour temperature along the Planckian
  locus, shown when the illuminant type supports it. Typical 2700 K tungsten,
  5000-6500 K daylight, 7500 K shade.
- hue and chroma (CAT tab): the custom illuminant expressed in LCh -- the way to
  correct illuminants that are off the blackbody locus (fluorescent, LED, mixed).
- gamut compression and clip negative RGB from gamut (CAT tab): tame
  out-of-gamut colours produced by an extreme adaptation.
- input R / input G / input B (R, G and B tabs): the channel mixer matrix rows,
  typically -1 to +1 with a "normalize channels" checkbox to preserve brightness.
- input R/G/B on the brightness and colorfulness tabs: perceptual variants that
  change luminance or saturation per channel instead of raw mixing.
- input R/G/B on the gray tab: the weights of the black and white conversion --
  this is the correct place to emulate a red or orange filter on B&W film.
- area color mapping (area mode: measure | correction; lightness, hue, chroma):
  sample a patch, state what it should be, and let the module solve for it.
- color checker calibration: chart selection, optimize for (none, neutral
  colors, saturated colors, skin and soil and foliage and sky colors, average
  delta E, maximum delta E) and a color space check button.
visual_effect: BEFORE: a neutral-looking but subtly wrong image where skin is
slightly green under fluorescent light, or a flat, muddy default black and white
conversion. AFTER: neutral, believable colour under difficult illuminants, or a
black and white rendering with real tonal separation between sky and clouds.
pitfalls: the module warns when white balance is also being applied in
temperature -- heed it. Extreme channel mixing pushes colours out of gamut and
produces posterised or fluorescent-looking areas. Colour checker calibration
requires an actual, evenly lit chart in the frame; using it on a guessed patch
makes things worse. Setting the illuminant from a coloured object bakes in the
complementary cast.
pairs_with: white balance (leave at camera reference), input color profile,
color balance rgb, color equalizer, monochrome.
