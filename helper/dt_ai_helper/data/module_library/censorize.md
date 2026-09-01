# censorize (censorize)
group: effect | scene-referred | typical position: late, with a mask
synonyms: pixelate, blur face, anonymize, censor, hide face, mosaic, privacy, number plate, redact, obscure
purpose: Anonymises part of an image with a configurable chain of gaussian blur,
pixellation, a second blur and added noise. It is designed to be used with a
drawn mask over the region that must be hidden, and its blur stages also make it
usable for creative bloom and glow effects.
use_when: a face, a licence plate or a document must be obscured before
publication; you want a pixellated mosaic effect over part of the frame; you
want a controlled blur-plus-noise creative effect.
do_not_combine: nothing conflicts, but it is not a substitute for cropping the
sensitive area out when real anonymity is required.
key_controls:
- input blur radius: the first gaussian blur pass, applied before pixellation.
  Blurring first is what prevents the original detail from being recoverable
  from the block averages.
- pixellation radius: the size of the mosaic blocks. Typical 8-40 px depending on
  output size; larger blocks hide more.
- output blur radius: a second gaussian pass that softens the block edges so the
  censored area does not look like a pasted-in grid.
- noise level: the standard deviation of added luminance gaussian noise, which
  further destroys residual structure and helps the region blend with a grainy
  image.
- the module is intended to be used with a drawn mask (circle, ellipse, path or
  brush) restricting it to the region of interest; at defaults with a mask it
  gives a sensible result immediately.
visual_effect: BEFORE: a recognisable face or a readable number plate. AFTER: a
soft mosaic block with no recoverable detail, edges that blend into the
surrounding image, and grain that matches the rest of the frame.
pitfalls: the manual states plainly that the methods here are not forensically
safe -- for genuine protection, paint the area with a solid colour or crop it
out. Pixellation without the input blur can leave enough structure for
reconstruction. Applying censorize without a mask blurs the entire image. It
works in linear RGB and sits late in the pipe; the block size is in output
pixels, so check the effect at export resolution.
pairs_with: drawn masks, retouch, blurs, liquify, lowpass.
