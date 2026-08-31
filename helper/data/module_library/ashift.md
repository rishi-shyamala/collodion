# rotate and perspective (ashift)
group: geometry | any | typical position: early geometric stage
synonyms: straighten, level horizon, tilted, crooked, keystone, converging verticals, perspective correction, architecture, leaning buildings, rotate, shear, upright
purpose: Rotates the image to level the horizon and applies a projective
transform to correct converging verticals and horizontals (keystoning). Since
darktable 3.8 it no longer crops -- that is the crop module's job -- so it can be
re-tuned at any time without losing your framing.
use_when: the horizon is not level; a building leans backwards because the
camera was tilted up; you need to correct both vertical and horizontal
convergence in an interior shot; an anamorphic or stretched image needs an
aspect adjustment.
do_not_combine: the deprecated crop and rotate (clipping) module. Running two
instances of ashift for rotation and perspective separately is unnecessary.
key_controls:
- rotation (deg): soft limit of 10 deg, expandable to 180 deg. Use the
  straightening line (ctrl+drag on the image) to set it from a reference edge.
- lens shift (vertical): corrects converging verticals -- the main control for
  architecture shot from below.
- lens shift (horizontal): corrects converging horizontals.
- shear: diagonal warping, needed when correcting vertical and horizontal
  convergence at the same time.
- automatic cropping (off | largest area | original format): trims the black
  wedges the transform introduces.
- lens model (generic | specific): generic assumes a 28mm-equivalent lens;
  specific exposes focal length and crop factor for an exact transform.
- focal length and crop factor (lens model = specific): the real camera values;
  getting these right matters for strong corrections.
- aspect adjust: free aspect ratio scaling, for anamorphic lenses or to
  counteract the stretching that a strong perspective correction introduces.
- show guides: overlay to check that lines are truly vertical.
- the automatic fitting buttons: fit vertical lines only, horizontal only, or
  both; ctrl+click fits rotation without lens shift, shift+click fits lens shift
  without rotation. darktable detects structural lines in the image first.
visual_effect: BEFORE: a cathedral that narrows toward the top, with a horizon
tilted two degrees to the left. AFTER: vertical lines are parallel to the frame
edges and the horizon is level, at the cost of some resolution at the edges and
a slightly stretched top of the frame.
pitfalls: strong keystone correction stretches the far end of the image and
enlarges pixels there -- correct only as far as looks natural; fully corrected
verticals sometimes look top-heavy and photographers deliberately stop short.
The automatic fit needs detectable straight lines; on organic subjects it fails
and produces nonsense. Perspective correction resamples the image, so do it
before sharpening. Remember to re-check the crop afterwards.
pairs_with: crop, lens correction, orientation, framing.
