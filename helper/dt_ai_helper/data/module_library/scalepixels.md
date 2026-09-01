# scale pixels (scalepixels)
group: geometry | raw | typical position: raw stage, before demosaic
synonyms: scale pixels, non square pixels, aspect correction, anamorphic sensor, pixel aspect ratio, stretched raw
purpose: Rescales images from sensors with non-square photosites so that the output has
  the correct geometry. Auto-applied for the affected cameras.
use_when: the camera records non-square pixels and the image would otherwise be
  stretched; this is a technical auto-applied correction that rarely needs
  manual attention.
