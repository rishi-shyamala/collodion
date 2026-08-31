# raw denoise (rawdenoise)
group: correction | raw | typical position: raw stage, before demosaic
synonyms: raw denoise, wavelet denoise, noise, high iso, pre demosaic denoise, chroma noise, luminance noise, clean raw
purpose: Applies wavelet-based noise reduction directly to the raw mosaic data before
  demosaic, with separate control per colour channel.
use_when: noise is bad enough that it is corrupting demosaic itself and producing maze
  or zipper artefacts; you want a light pre-demosaic pass in front of denoise
  (profiled). It has no camera noise profile, so it is less precise than denoise
  (profiled).
