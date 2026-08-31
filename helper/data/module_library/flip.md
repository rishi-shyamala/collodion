# orientation (flip)
group: geometry | any | typical position: first geometric step
synonyms: rotate 90, portrait, landscape, sideways, upside down, mirror, flip horizontal, flip vertical, wrong orientation, exif rotation
purpose: Applies whole-image 90-degree rotations and mirroring. It is
auto-applied from the Exif orientation tag so that images shot in portrait
appear upright, and it is the right place to fix a camera that recorded the wrong
orientation or to mirror a scanned negative.
use_when: the image appears sideways or upside down; a scan or a mirror-lens shot
is flipped; you want a mirrored version for layout reasons; the camera's
orientation sensor got it wrong.
do_not_combine: use rotate and perspective for arbitrary angles -- orientation
only does exact 90-degree steps and mirroring, losslessly.
key_controls:
- rotate counter-clockwise: 90 degrees anticlockwise.
- rotate clockwise: 90 degrees clockwise.
- flip horizontally: mirrors left-right.
- flip vertically: mirrors top-bottom.
- show guides: displays the composition guide overlay while the module is active.
visual_effect: BEFORE: a portrait-format frame displayed on its side. AFTER: the
frame is upright. No pixel values change and no resampling occurs -- this is a
lossless transform.
pitfalls: because it sits at the very start of the geometric chain, changing
orientation after cropping re-interprets the crop; darktable keeps the crop
rectangle but it may no longer frame what you intended. Flipping an image with a
watermark or framing applied mirrors the composition but not the watermark's
sense. Exif-driven orientation is already applied for you, so an image that looks
correct needs no action here.
pairs_with: crop, rotate and perspective, framing, watermark.
