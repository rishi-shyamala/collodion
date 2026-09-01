# hot pixels (hotpixels)
group: correction | raw | typical position: raw stage
synonyms: hot pixels, stuck pixels, dead pixels, white dots, colored dots, long exposure noise, sensor defect, speckles
purpose: Detects and removes isolated bright or dead pixels in the raw data by
  comparing each photosite with its same-colour neighbours.
use_when: long exposures or a hot sensor show isolated bright coloured dots that survive
  denoising; a known stuck pixel appears in every frame from the camera.
