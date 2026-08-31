# crop (crop)
group: geometry | any | typical position: early geometric stage
synonyms: crop, cropping, trim, aspect ratio, framing, composition, straighten, 16:9, square, golden ratio, rule of thirds, cut off edges
purpose: Defines the visible rectangle of the image and its aspect ratio. Since
darktable 3.8 cropping is a separate module from rotation and perspective, so
crop only crops -- it never resamples or rotates the pixels.
use_when: the composition needs tightening; you want a specific output aspect
ratio (16:9, square, 4:5 for social, golden cut); there are distracting elements
at the frame edges; you are removing black borders left by perspective
correction.
do_not_combine: the deprecated crop and rotate (clipping) module does the same
job plus rotation; do not enable both. Use rotate and perspective for straighten
and keystone work.
key_controls:
- aspect: freehand, original image, square, golden cut (1.62:1) and a list of
  standard ratios; a custom ratio can be typed as "x:y" or as a decimal, and
  custom entries are stored in darktablerc. A portrait/landscape toggle swaps
  the orientation of any rectangular ratio.
- left / right / top / bottom (margins section, %): the crop borders expressed
  as a percentage of each edge, updated live when you drag the crop handles.
  Editing them numerically is the way to make several images crop identically.
- guides: shows composition overlays (thirds, golden sections, diagonals,
  harmonious triangles) while the module is focused; the properties icon opens
  the guide settings.
visual_effect: BEFORE: a loose frame with dead space and distracting edge
elements. AFTER: a tighter composition at the intended aspect ratio, with the
subject placed against a guide line. Cropping does not change any pixel values.
pitfalls: cropping heavily reduces resolution -- check the pixel dimensions shown
while dragging. Crop sits after the geometric modules, so black wedges from
rotation or perspective correction must be cropped away here (or handled by
rotate and perspective's automatic cropping). Applying a crop before you have
finished perspective correction usually means redoing it. Watermark and framing
operate on the cropped image, so change the crop before fine-tuning them.
pairs_with: rotate and perspective, orientation, framing, enlarge canvas,
watermark.
