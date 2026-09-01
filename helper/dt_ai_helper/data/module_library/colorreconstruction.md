# color reconstruction (colorreconstruction)
group: correction | display-referred | typical position: after tone mapping
synonyms: blown highlights, white highlights, recover color, clipped color, gray highlights, sky color, highlight color
purpose: Replaces the colour of clipped or near-white highlight pixels with colour
  propagated from neighbouring unclipped pixels, based on a luminance threshold.
use_when: highlights have been recovered in luminance but render as flat gray or white
  and need plausible colour back; the raw highlight reconstruction module has
  already done what it can.
