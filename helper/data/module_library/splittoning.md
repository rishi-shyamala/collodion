# split-toning (splittoning)
group: effect | display-referred | typical position: late, creative stage
synonyms: split toning, sepia, tone shadows, tint highlights, duotone, warm highlights cool shadows, cyanotype, selenium, black and white toning, color grade
purpose: Adds one colour to the shadows and a different colour to the
highlights, with controls for where the two regions meet and how much of the
mid-tones is left alone. It is the classic darkroom toning effect and is at its
most useful on monochrome images.
use_when: a black and white conversion needs a sepia, selenium or cyanotype
tone; you want warm highlights and cool shadows on a colour image; you are
emulating a printed-paper look.
do_not_combine: color balance rgb's 4 ways tab (shadows lift / highlights gain)
does this with better control and gamut behaviour on colour images -- prefer it
there and keep split-toning for monochrome work.
key_controls:
- shadows color: a hue and saturation selector for the shadow tone. Typical
  choices are a cool blue (selenium) or a warm brown (sepia) at low saturation,
  10-30%.
- highlights color: the same for the highlight tone; warm yellows and creams
  read as classic paper tones.
- balance (%, default 50): the split point between the shadow and highlight
  regions. At 50% each gets an equal share of the lightness range; lower values
  give the highlight tone more of the image.
- compress (%): how much of the mid-tone lightness range is left untouched.
  Higher values push the two tones toward the extremes and give a subtler,
  more convincing result.
visual_effect: BEFORE: a neutral black and white print. AFTER: shadows carry a
faint blue-green cast and highlights a warm cream tint, so the image reads as a
toned silver print rather than a digital grayscale. On colour images the effect
is a cinematic warm/cool separation.
pitfalls: the manual notes it gives limited benefit on colour images -- the
existing colours fight the added tones and the result often looks muddy.
Saturation above about 40% turns the effect into an obvious duotone. With
compress at 0 the tones bleed all the way into the mid-tones and neutrals
disappear. It is display-referred and sits late; applying it before tone mapping
gives unpredictable results.
pairs_with: monochrome, color calibration (gray tab), grain, vignetting,
color balance rgb.
