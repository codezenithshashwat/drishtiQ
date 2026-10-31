# Usability test: 3 tasks, 2–3 participants

**Who:** 2–3 people who did not build the app. One should ideally be a clinician or optometrist; one may be a health worker or a student.
**Time:** about 15 minutes each.
**Setup:** run `start.bat`; the worklist holds the validation example cases. Have one fundus image file on the desktop (any IDRiD-val or APTOS-val image).

## Script (read aloud)

> "This is a prototype that helps with eye screening for diabetes. I'm testing the software, not you. Please think aloud: say what you look for and what you expect. I won't help unless you're stuck for two minutes."

| Task | Instruction to the participant | Done when |
|---|---|---|
| 1 | "A patient with ID **TEST-01** had a photo of the right eye taken; it's on the desktop. Add it, read what the AI found, then confirm or change the stage as you see fit." | A review is saved for TEST-01 (agree, or disagree with a stage) |
| 2 | "You have time for one case before lunch. Find the case that most needs a person's attention and open it." | They open the top case of the worklist (a deferred or most-likely-referable case) |
| 3 | "Print the patient summary for that case in **Hindi** (saving it as a PDF is fine)." | A Hindi patient summary is printed or saved |

After each task ask: "On a scale from 1 (very hard) to 5 (very easy), how easy was that?"
At the end ask: "What was the most confusing thing?" and "Would you trust the result? Why?"

## Results (fill in)

| Participant | Role | Task 1 time | Task 1 done? | Task 1 ease (1–5) | Task 2 time | Task 2 done? | Task 2 ease | Task 3 time | Task 3 done? | Task 3 ease |
|---|---|---|---|---|---|---|---|---|---|---|
| P1 | | | | | | | | | | |
| P2 | | | | | | | | | | |
| P3 | | | | | | | | | | |

## Problems observed (fill in)

| # | Participant | Task | What happened (quote if possible) | Severity (high / medium / low) | Suggested fix |
|---|---|---|---|---|---|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |

**Severity:** high = could not finish or misread a clinical result; medium = finished but slowly or with an error; low = comment or small hesitation.

When this is filled in, I fix every high and medium problem and re-run the heuristic review.
