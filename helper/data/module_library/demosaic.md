# demosaic (demosaic)
group: correction | raw | typical position: raw stage, always on for raw files
synonyms: demosaic, bayer, x-trans, raw interpolation, maze, rcd, moire, zipper artifacts, false color, mosaic, capture sharpen
purpose: Interpolates the single-colour-per-photosite raw mosaic into full RGB
pixels. It is mandatory for raw files and always enabled; the choice of
algorithm determines how fine detail, edges and repeating patterns are rendered.
use_when: you see zipper artefacts or maze patterns on fine detail; there is
colour moire on fabric or architecture; you are optimising a high-detail landscape
for maximum resolution; a high-ISO file shows demosaic noise amplification.
do_not_combine: not applicable -- exactly one demosaic runs per raw image.
key_controls:
- method: PPG (fast, mild), AMaZE (highest detail on Bayer, slower), RCD
  (default on modern versions; a good detail/artefact balance), LMMSE (best for
  noisy high-ISO files), VNG4 (smooth, good in flat noisy areas), Markesteijn
  1-pass and 3-pass (X-Trans sensors), passthrough (monochrome), photosite color
  and monochrome (diagnostic/monochrome sensors), and the dual variants
  (RCD + VNG4, AMaZE + VNG4, Markesteijn 3-pass + VNG4).
- dual threshold (dual demosaic methods): the contrast level that decides where
  the detail-oriented algorithm is used and where the smooth one is used;
  "display blending mask" shows the split. Typical 0.02-0.30.
- edge threshold (PPG only): suppresses interpolation artefacts at edges.
- LMMSE refine (LMMSE only): additional refinement passes.
- color smoothing: extra median passes that remove residual false colour at the
  cost of a little colour detail.
- match greens: corrects for the two green photosites in a Bayer cell having
  slightly different responses, which otherwise shows as a fine grid pattern.
- capture sharpen, iterations, radius, contrast sensitivity, corner boost,
  sharp center: an optional deconvolution of the sensor/AA-filter blur applied at
  the raw stage; a small number of iterations recovers real detail cheaply.
visual_effect: BEFORE: raw mosaic data. AFTER: full-colour pixels. Between
methods the differences are visible only at 100%: AMaZE resolves the finest
detail but can produce maze artefacts in noise; VNG4 is smooth but softer;
dual demosaic gives detailed edges with smooth flat areas.
pitfalls: choosing a detail-hungry algorithm on a noisy file amplifies the noise
into maze patterns -- use LMMSE or a dual method instead. Capture sharpen with
too many iterations produces ringing that is baked in before every other module
sees the data. Demosaic differences are invisible at fit-to-screen zoom, so judge
at 100%. Colour smoothing passes soften genuine fine colour detail.
pairs_with: raw black/white point, highlight reconstruction, denoise (profiled),
raw chromatic aberrations, diffuse or sharpen.
