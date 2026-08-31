# denoise (profiled) (denoiseprofile)
group: correction | scene-referred | typical position: early, before tone work
synonyms: noise, noisy, grain removal, high iso, chroma noise, luminance noise, speckles, denoise, clean up, smooth noise, iso 6400
purpose: Removes sensor noise using a per-camera, per-ISO noise profile measured
by the darktable community, so the algorithm knows the actual variance of the
signal at every brightness. Supports non-local means and wavelet algorithms and
is the recommended first-choice denoiser.
use_when: the file is high ISO and shows luminance speckle or coloured blotches;
you plan to lift shadows significantly (which amplifies noise); you see chroma
noise in dark, saturated areas; before any sharpening or backward diffusion.
do_not_combine: raw denoise, astrophoto denoise and surface blur are alternative
denoisers -- combining them all smears detail. Running denoise after sharpening
is the wrong order.
key_controls:
- profile: auto-detected from Exif (camera + ISO); darktable interpolates
  between profiled ISO values. If your camera is unprofiled the module falls
  back to a generic profile and the results are less reliable.
- mode: combinations of algorithm (non-local means | wavelets) and interface
  (auto | advanced). Wavelets auto is the default and the best general choice;
  non-local means preserves texture better on low-detail surfaces.
- strength: overall amount, with soft limits. Typical 0.5-1.5; 1.0 means "trust
  the profile exactly".
- adjust autoset parameters: single-slider shortcut in the auto modes that
  scales the whole preset up or down.
- central pixel weight (details) (non-local means, auto mode): higher preserves
  more of the original pixel and therefore more detail and more noise.
- patch size, search radius, scattering (non-local means, advanced): the
  classical NLM parameters; larger search radius is slower and smoother.
- color mode Y0U0V0 | RGB and the wavelet curves (wavelets mode): let you
  denoise chroma hard and luminance gently, which is the standard recipe.
- preserve shadows, bias correction (advanced mode): bias correction removes the
  colour cast that aggressive denoising can leave in deep shadows.
- whitebalance-adaptive transform: accounts for white balance changing the
  per-channel noise levels.
visual_effect: BEFORE: coloured blotches in the shadows, fizzing luminance
speckle across smooth skies, and mushy colour in dark saturated areas.
AFTER: clean, smooth tonal areas with fine detail preserved; skies render as
gradients instead of confetti. Overdone: waxy plastic skin, smeared foliage,
and a characteristic watercolour look.
pitfalls: over-denoising destroys texture irreversibly -- zoom to 100% and check
hair, fabric and foliage. The classic workflow is two instances: one on chroma
only (strong) and one on luminance (gentle), using the blend modes. Denoising
after sharpening amplifies the sharpening artefacts. If your camera has no
profile, results will be noticeably worse than a profiled body.
pairs_with: diffuse or sharpen (after), sharpen, astrophoto denoise, exposure,
tone equalizer (denoise before big shadow lifts).
