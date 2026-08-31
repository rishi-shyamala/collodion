# surface blur (bilateral)
group: effect | display-referred | typical position: late, resource intensive
synonyms: surface blur, bilateral denoise, edge aware blur, smooth skin, moire, cartoon effect, denoise, smoothing
purpose: Edge-aware bilateral blur with independent radius weighting for the red, green
  and blue channels; smooths surfaces and noise while preserving sharp edges,
  and can reduce colour moire when used in chromaticity blending mode.
use_when: you need edge-preserving smoothing of a texture or of colour moire, or a
  cartoon-like creative flattening; note the manual recommends astrophoto
  denoise or denoise (profiled) for general denoising, and warns the module is
  slow.
