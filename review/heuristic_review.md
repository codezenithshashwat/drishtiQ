# Heuristic usability review (Nielsen's 10 heuristics)

Reviewer: the developer (an expert walk-through, not a user test). Date: 2026-10-30. Screens: Worklist, New screening (single and camp), Case View (incl. physician view and review), Report, About the model, Disagreements. Severity: high = blocks or misleads a clinical decision; medium = slows or confuses a frequent task; low = cosmetic or rare. The machine-readable summary is `review/heuristic_review.json`.

| # | Screen | Heuristic | Finding | Severity | Status |
|---|---|---|---|---|---|
| 1 | Upload / Review | 1 Visibility of system status | The backend could be an older version than the page; saving failed with "Method Not Allowed" | high | **Fixed**: version check with a red "Backend is outdated" banner; JSON 404s; e2e test |
| 2 | Case View | 9 Error recovery | After saving a review the page went blank (missing field) | high | **Fixed**: complete case record from every endpoint; error boundary |
| 3 | Worklist | 7 Efficiency | 500 cases took 5.6 s to render | medium | **Fixed**: 50 per page, lazy thumbnails (0.8 s) |
| 4 | All | 2 Match with the real world | "Not recorded eye" in titles and lists | medium | **Fixed**: "Eye not recorded" |
| 5 | Case View | 7 Efficiency | No direct way to the next case after a review | medium | **Fixed**: "Next case" button (next case waiting, worklist order) |
| 6 | New screening | 3 User control | A camp batch defaulted every eye to "Right" | medium | **Fixed**: defaults to "Not recorded", chosen per batch |
| 7 | New screening | 5 Error prevention | One bad file could stop a camp upload | medium | **Fixed**: per-file errors and retry of failed files only |
| 8 | Case View | 10 Help | Grad-CAM and lesion maps were easy to confuse | medium | **Fixed**: physician view side by side, with a one-line difference |
| 9 | Report | 1 Visibility | Server-side PDF could silently fail | medium | **Fixed**: falls back to the print dialog with a visible note |
| 10 | About | 10 Help | Numbers lacked plain meaning | medium | **Fixed**: plain sentences with exact values and CIs on hover |
| 11 | All (a11y) | 4 Consistency / accessibility | 8 axe-core violations (1 critical, 3 serious) | high | **Fixed**: 0 violations on all six screens (`results/a11y.json`) |
| 12 | Case View | 8 Minimalist design | At 1280 px the layer chips wrap to four rows | low | Open: acceptable; the chips stay readable |
| 13 | Worklist | 4 Consistency | Stage labels are clinical (ICDR) even when the Case View is in Simple mode | low | Open: the worklist is a clinician tool |
| 14 | Worklist | 2 Real world | Validation case IDs repeat the dataset name ("IDRiD-IDRiD_047") | low | Open: the seed naming is kept so the source stays traceable |
| 15 | All | 3 User control | Cases cannot be deleted from the app | low | Open by design: reviews are kept as an audit trail; a store reset is documented |
| 16 | Disagreements | 6 Recognition | Disagreements are not counted on the nav item | low | Open |

**Open high/medium issues: 0.**
