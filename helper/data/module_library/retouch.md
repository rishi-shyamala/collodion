# retouch (retouch)
group: correction | any | typical position: after demosaic, before tone work
synonyms: spot removal, heal, clone, blemish, dust spot, sensor dust, remove object, skin retouching, frequency separation, wavelet, fix skin, remove power line
purpose: Removes or repairs local defects with clone, heal, fill and blur tools
applied through drawn shapes, optionally targeting individual wavelet detail
scales so you can retouch texture and tone separately (frequency separation).
use_when: there are sensor dust spots in the sky; a blemish or stray hair needs
removing; you want to smooth skin texture without losing pores; a distracting
object must be painted out; you need to even out tonal blotches at a coarse
wavelet scale only.
do_not_combine: the deprecated spot removal module. Liquify solves a different
problem (moving pixels rather than replacing them).
key_controls:
- shapes: circle, ellipse, path and brush; the header shows how many shapes are
  placed. Draw the shape over the defect and darktable positions the source.
- algorithms (clone | heal | fill | blur): clone copies the source area
  verbatim; heal copies and then matches the surrounding tone and colour --
  the right default for skin and skies; fill paints a flat colour; blur softens.
- scales (wavelet decompose): the number of detail layers the image is split
  into. Typical 4-6.
- current / merge from / display wavelet scale / preview single scale: select
  which detail scale your shapes act on, optionally merging several consecutive
  scales, and inspect a scale in isolation.
- cut and paste: move shapes between wavelet scales.
- temporarily switch off shapes and display masks: verification toggles; the
  mask overlay paints target shapes yellow.
- fill mode (erase | color), fill color, brightness: the fill tool's settings.
- blur type (gaussian | bilateral) and blur radius: the blur tool's settings.
- mask opacity (0.0-1.0): per-shape strength, so a heal can be applied at 60%.
visual_effect: BEFORE: dust spots across a clear sky, a blemish on a cheek, a
power line across the horizon. AFTER: the defects are gone with no visible seam,
because heal matches the surrounding gradient. Used with wavelet scales: skin
keeps its pore texture while blotchy colour underneath is evened out.
pitfalls: cloning across a gradient (a sky) leaves a visible patch -- use heal.
Placing a source area that itself contains a defect propagates it. Retouch data
is stored per image and does not survive being copied to a differently framed
photo. Many shapes make the pipeline noticeably slower. The retouch module is
positioned early in the pipe, so retouching after heavy tone work still looks
correct but is judged against the un-tone-mapped preview when the module is
focused.
pairs_with: denoise (profiled), diffuse or sharpen, liquify, drawn masks,
censorize.
