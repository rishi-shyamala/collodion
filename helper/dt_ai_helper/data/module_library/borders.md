# framing (borders)
group: effect | output | typical position: very late, after crop
synonyms: border, frame, matte, white border, black border, passepartout, print border, add margin, instagram border, keyline
purpose: Adds a coloured border around the image, optionally with a thin frame
line inset from the border edge, and can change the output aspect ratio in the
process. Previously called "framing"/"borders"; it is a presentation module, not
a correction.
use_when: you are preparing an image for print or social media and want a mat or
keyline; a square output frame is needed around a rectangular image; you want a
white border to separate the photo from a dark web page.
do_not_combine: enlarge canvas does a related job (adding canvas without the
frame-line styling); using both means two nested borders unless that is the
intent.
key_controls:
- border size (%): the border width as a percentage of the underlying image.
  Typical 2-10%; large values turn the image into a small inset.
- aspect: the final output ratio, with a right-click custom entry (for example
  "6:5" or "1:1"). This is how you square-crop for social media without cropping
  the photo.
- orientation (auto | portrait | landscape): which way a rectangular aspect ratio
  is applied.
- horizontal position / vertical position: where the image sits within the
  border; a custom "x/y" ratio can be typed. Offsetting vertically produces the
  classic gallery mat with a deeper bottom margin.
- frame line size (%): the thickness of the keyline, relative to the narrowest
  part of the border.
- frame line offset (%): where the keyline sits between the image (0%) and the
  outer border edge (100%).
- border color and frame line color: colour selectors with common colours, an
  RGB entry dialog and a picker so the border can be sampled from the image.
- show guides: guide overlay while the module is active.
visual_effect: BEFORE: an image that bleeds to the edge of the frame. AFTER: the
photograph sits inside a clean coloured margin, optionally separated from it by a
thin keyline, at whatever aspect ratio the destination requires.
pitfalls: the border is part of the exported pixels, so it scales with export
size -- a 2% border on a 6000px export is 120px, on a 1000px web export only
20px. Sampling the border colour from the image often looks better than pure
white or black. Because framing runs late, it is applied on top of watermark
placement decisions; check both together. Large borders reduce the effective
resolution of the photograph in a fixed-size export.
pairs_with: crop, enlarge canvas, watermark, vignetting.
