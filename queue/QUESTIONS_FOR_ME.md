# Questions for you

Nothing here blocks work; each item has a default the prototype uses until you decide.

## Open

| # | Question | Default meanwhile |
|---|---|---|
| 1 | **Hindi strings:** `review/hindi_review.csv` is ready for your corrections (34 rows; the context column says where each string appears). After editing, restart the app with `start.bat`. | Current wording, with the "awaits review" note |
| 2 | **Quality gate trade-off:** the new non-fundus check flags about 2% of real APTOS/MMRDR training photos (cropped so the retina fills the frame) as "may not be an eye photo; a person should check". Acceptable? | Kept: it errs toward human review |
| 3 | **Calibration on IDRiD-val** got worse (ECE 0.040 → 0.083, 101 images), while APTOS-val improved (0.077 → 0.027). Show the calibrated P(referable) anyway? | Shown, with both numbers on the About page |
| 4 | **Running app instance:** I started the app on :8000 through `start.ps1` without a visible window. To stop it, run `start.bat -Restart` (it replaces it) or end the python process listening on port 8000. | Left running |
| 5 | **Messidor-2:** say "Messidor-2 placed" when the files are in `data/raw/Messidor2/`. | Not touched |

## Resolved (your decisions)

2026-10-30: lid set to "Do nothing" when plugged in (freeze detector kept) · code licence MIT (LICENSE added; weights not distributed; dataset licences in README) · Hindi and usability sessions: you will do them.

2026-10-29: keep keep_awake · Hindi via review CSV · server PDF works from start.bat (Edge kept, print fallback kept) · ICO 2017 cited · example cases are validation images · pseudo-label applies the swap rule · queue order fine.
