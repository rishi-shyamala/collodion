# unbreak input profile (profile_gamma)
group: color | technical | typical position: right after input color profile
synonyms: unbreak input profile, gamma, log, linearize, wrong input curve, tone curve fix, film scan gamma, linear input
purpose: Linearises an input image whose encoding curve darktable's input profile got
  wrong, using either a gamma/linear pair or a logarithmic model, so that the
  scene-referred modules downstream see linear data.
use_when: a non-raw file (a scan, a log-encoded frame, an unusual TIFF) renders with
  obviously wrong contrast that the input colour profile cannot fix; you are
  preparing log footage stills for the scene-referred workflow.
