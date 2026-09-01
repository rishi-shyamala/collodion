# external raster mask (rasterfile)
group: mask | any | typical position: wherever a mask is needed
synonyms: external mask, raster mask, import mask, png mask, luminosity mask, mask from file, selection from another app, alpha mask
purpose: Loads a grayscale image file from disk and exposes it as a raster mask that
  other modules can use, allowing masks to be authored in an external editor.
use_when: the selection you need is too complex for darktable's drawn and parametric
  masks; you already have a mask (a sky selection, an AI-generated matte) as a
  file and want to reuse it across several modules or images.
