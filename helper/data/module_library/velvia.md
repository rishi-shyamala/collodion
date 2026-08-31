# velvia (velvia)
group: color | display-referred | typical position: late, creative stage
synonyms: saturation, vivid, punchy colors, slide film, fuji velvia, boost color, more saturated, vibrance, colorful
purpose: Increases saturation with a weighting that favours dark, bright and
already low-saturation pixels, emulating the look of Fujichrome Velvia slide
film. It deliberately spares already-saturated mid-tone colours to avoid the
blocky look of a flat saturation boost.
use_when: the image needs an overall colour boost with a slide-film character;
landscape colours are dull; you want a quick vivid look without shaping curves.
do_not_combine: color balance rgb's global vibrance and chroma do the same job
with far more control and better gamut behaviour -- prefer it on modern edits.
Stacking velvia, vibrance and colour balance saturation over-saturates fast.
key_controls:
- strength (%): the overall intensity of the resaturation. Typical 10-40%;
  the default (around 25%) is already a visible effect.
- mid-tones bias: reduces the effect on mid-tones, which is what protects skin
  tones from turning orange. Decreasing this value strengthens the overall
  effect across the whole tonal range.
visual_effect: BEFORE: flat, slightly washed foliage and a pale sky. AFTER:
deeper greens, a more saturated blue sky and stronger reds, with the boost
concentrated in shadows, highlights and previously-muted colours. Overdone:
neon foliage, orange skin and clipped red channels in flowers.
pitfalls: it is a display-referred module and can push colours out of gamut,
which shows as flat patches of pure colour in reds and blues. Skin tones suffer
first -- lower the strength or raise mid-tones bias. On a scene-referred edit,
color balance rgb is the better tool and velvia is mostly of historical interest.
pairs_with: color balance rgb, color zones, color equalizer, filmic rgb.
