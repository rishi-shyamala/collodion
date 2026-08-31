# blurs (blurs)
group: effect | scene-referred | typical position: late, creative stage, usually masked
synonyms: bokeh, lens blur, motion blur, gaussian blur, background blur, fake shallow depth of field, camera shake, dreamy, out of focus, blur background
purpose: Generates physically-plausible blurs -- a lens diaphragm bokeh, a
camera-motion path, or a plain gaussian -- and applies them to the image. Used
with a drawn mask it fakes shallow depth of field; used with blend modes the
gaussian mode becomes a glow or denoise source.
use_when: you want convincing background bokeh with visible aperture-blade
shapes; you want to simulate motion blur or camera shake as a creative effect;
you need a gaussian blur layer for blending; specular highlights should render as
polygonal bokeh discs.
do_not_combine: lowpass, surface blur and censorize also blur; use one blur
source per effect. Blurs is the one that produces realistic optical bokeh.
key_controls:
- blur type (lens blur | motion blur | gaussian blur): lens blur simulates a
  diaphragm, motion blur simulates a movement path, gaussian is a plain blur
  that the manual describes as not really an optical blur.
- blur radius: the size of the blur for every type. Typical 4-30 px; large radii
  are slow.
- diaphragm blades (lens blur): the number of aperture blades, which determines
  the shape of out-of-focus highlights. 5-9 blades give the polygonal bokeh of
  real lenses; high values approach a circle.
- concavity (lens blur): how curved the blade edges are -- the difference between
  the classic star-shaped and rounded bokeh.
- linearity (lens blur): how the intensity is distributed across the bokeh disc,
  from a bright ring (busy, "nervous" bokeh) to an even disc (smooth bokeh).
- rotation (lens blur): the angular orientation of the blade polygon.
- direction (motion blur): the angle of the simulated movement.
- curvature (motion blur): bends the motion path into an arc rather than a
  straight line.
- offset (motion blur): shifts the path relative to the pixel, which controls
  whether the blur trails behind or straddles the subject.
visual_effect: BEFORE: a background that is only slightly out of focus and full
of distracting detail. AFTER (lens blur, masked to the background): smooth,
optically convincing bokeh with polygonal highlight discs, so the subject
separates the way a fast lens would render it. AFTER (motion blur): a directional
smear that reads as movement.
pitfalls: faking depth of field with a uniform blur and a drawn mask never
matches a real lens, because real blur increases with distance -- feather the
mask and vary the radius across multiple instances. Blurring after sharpening
wastes the sharpening. Large radii are computationally expensive. Bokeh
generated from already-clipped highlights renders as flat discs with no
brightness falloff.
pairs_with: drawn masks, diffuse or sharpen, lowpass, censorize, vignetting.
