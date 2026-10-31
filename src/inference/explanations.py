"""Grounded, template-based explanations generated only from the findings record (no language model).

Each sentence has two renderings of the same facts:
  simple    plain English, short sentences; medical terms only as "plain (clinical)" from the glossary
  clinical  ICDR wording with exact values
plus
  values    {name: {"path": JSON path in findings, "value": raw value}}; every number in either text is one of these
            or a declared constant
  refs      lesion keys / quadrants / landmarks the sentence is about (the UI highlights them on click)
ICDR criteria (Wilkinson et al., Ophthalmology 2003): mild = microaneurysms only; moderate = more than MA but less
than severe; severe = any of >20 intraretinal haemorrhages in each of 4 quadrants, definite venous beading in >=2
quadrants, prominent IRMA in >=1 quadrant (4-2-1 rule); PDR = neovascularisation and/or vitreous/preretinal
haemorrhage.
"""
from .glossary import STAGE_KEYS, TERMS, clinical, count_noun, inline, plain

GRADES = [clinical(k) for k in STAGE_KEYS]
# Numbers allowed in text that are not measured values: stage numbers and the 0-4 scale, guideline criteria (4-2-1
# rule, "more than 20", "4 quadrants", "1 disc diameter") and published flag thresholds. Tests enforce that every
# other number in a sentence is one of that sentence's measured values.
CONSTANTS = {"0", "0.25", "0.50", "0.67", "1", "2", "3", "4", "20", "25", "200"}


def get(f, path):
    cur = f
    for part in path.split("."):
        cur = cur[int(part)] if isinstance(cur, list) else cur[part]
    return cur


def fmt(v):
    if isinstance(v, float):
        return f"{v:.2f}"
    return str(v)


def region(n):
    return "region" if n == 1 else "regions"


def stage(g):
    return f"Stage {g} of 4: {plain(STAGE_KEYS[g])}"


class Builder:
    def __init__(self, findings):
        self.f, self.out = findings, []

    def add(self, sid, section, simple, clinical_text, paths=None, refs=None, extra=None):
        values = {name: dict(path=path, value=get(self.f, path)) for name, path in (paths or {}).items()}
        ctx = {k: fmt(v["value"]) for k, v in values.items()} | (extra or {})
        self.out.append(dict(id=sid, section=section, simple=simple.format(**ctx), clinical=clinical_text.format(**ctx),
                             text=clinical_text.format(**ctx), values=values, refs=refs or {}))


def explain(f):
    b = Builder(f)
    gr = f["grading"]
    g = gr["grade"]
    les = f["lesions"]
    ma, he, ex = (les[k]["count"] for k in ("MA", "HE", "EX"))
    hq = f["haemorrhage_quadrants"]
    P = {k: plain(k).lower() for k in ("MA", "HE", "EX", "SE")}

    # Summary
    if gr.get("score") is not None:
        between = gr["between"]
        b.add("grade", "summary",
              "{stage}. Between Stage {lo} and {hi}, closer to {near}.",
              "Grade: {label}. Continuous grade score {s} on a 0-4 scale; nearest grade boundary at {t}.",
              {"s": "grading.score", "t": f"grading.thresholds.{between['nearest_boundary']}", "lo": "grading.between.lower",
               "hi": "grading.between.upper", "near": "grading.between.closer_to"},
              extra={"label": GRADES[g], "stage": stage(g)})
    else:
        b.add("grade", "summary", "{stage}.", "Most likely grade: {label} (model score {p}).",
              {"p": f"grading.probabilities.{g}"}, extra={"label": GRADES[g], "stage": stage(g)})

    # Evidence
    for key in ("MA", "HE", "EX", "SE"):
        n = les[key]["count"]
        if n:
            b.add(f"lesion-{key}", "evidence", "We found {n} " + count_noun(key, n) + ".", clinical(key) + ": {n} segmented " + region(n) + ".",
                  {"n": f"lesions.{key}.count"}, refs={"lesions": [key]})
        else:
            b.add(f"lesion-{key}", "evidence", "No " + P[key] + " found.", clinical(key) + ": none segmented.", refs={"lesions": [key]})
    if he:
        b.add("he-quadrants", "evidence", "Bleeding spots appear in {k} of 4 areas of the retina.",
              "Haemorrhages in {k} of 4 quadrants (" + ", ".join(hq["quadrants"]) + "); at most {m} "
              + region(hq["max_per_quadrant"]) + " in one quadrant.",
              {"k": "haemorrhage_quadrants.count", "m": "haemorrhage_quadrants.max_per_quadrant"},
              refs={"lesions": ["HE"], "quadrants": hq["quadrants"]})

    # Why not one stage lower
    if g == 1:
        b.add("why-not-lower", "reasoning", "Not Stage 0, because we found {n} " + count_noun("MA", ma) + ".",
              "Why not No apparent DR: {n} microaneurysm " + region(ma) + "; microaneurysms alone define mild NPDR.",
              {"n": "lesions.MA.count"}, refs={"lesions": ["MA"]})
    elif g == 2:
        found = [f"{{{v}}} " + count_noun(k, c) for k, v, c in (("HE", "he", he), ("EX", "ex", ex)) if c]
        b.add("why-not-lower", "reasoning", "Not Stage 1. We found " + (" and ".join(found) or "lesions") + ", not only bulges.",
              "Why not Mild NPDR: lesions beyond microaneurysms (haemorrhage regions: {he}; hard-exudate regions: {ex}).",
              {"he": "lesions.HE.count", "ex": "lesions.EX.count"}, refs={"lesions": ["HE", "EX"]})
    elif g == 3:
        b.add("why-not-lower", "reasoning", "Not Stage 2. The overall pattern looks severe. Bleeding spots are in {k} of 4 areas.",
              "Why not Moderate NPDR: overall picture judged severe; haemorrhages in {k} of 4 quadrants. Venous beading and IRMA "
              "are not measured; confirm the 4-2-1 criteria.", {"k": "haemorrhage_quadrants.count"},
              refs={"lesions": ["HE"], "quadrants": hq["quadrants"]})
    elif g == 4:
        b.add("why-not-lower", "reasoning", "Not Stage 3. The AI sees signs of new vessel growth. A doctor must confirm.",
              "Why not Severe NPDR: features of proliferative disease; neovascularisation is not localised by this system.")

    # Why not one stage higher
    if g == 0:
        if ma:
            b.add("why-not-higher", "reasoning", "Not Stage 1. We saw {n} possible " + count_noun("MA", ma) + ", but the AI was not convinced.",
                  "Why not Mild NPDR: {n} possible microaneurysm " + region(ma) + ", not judged convincing by the grader. Review them.",
                  {"n": "lesions.MA.count"}, refs={"lesions": ["MA"]})
        else:
            b.add("why-not-higher", "reasoning", "Not Stage 1, because we found no tiny vessel bulges.",
                  "Why not Mild NPDR: no microaneurysms segmented.", refs={"lesions": ["MA"]})
    elif g == 1:
        if he or ex:
            seen = [f"{{{v}}} " + count_noun(k, c) for k, v, c in (("HE", "he", he), ("EX", "ex", ex)) if c]
            b.add("why-not-higher", "reasoning", "Not Stage 2. We saw " + " and ".join(seen) + ", judged too few.",
                  "Why not Moderate NPDR: haemorrhage regions {he} and exudate regions {ex} judged insufficient; review them.",
                  {"he": "lesions.HE.count", "ex": "lesions.EX.count"}, refs={"lesions": ["HE", "EX"]})
        else:
            b.add("why-not-higher", "reasoning", "Not Stage 2, because we found no bleeding spots or yellow deposits.",
                  "Why not Moderate NPDR: no haemorrhages or hard exudates segmented.", refs={"lesions": ["HE", "EX"]})
    elif g == 2:
        b.add("why-not-higher", "reasoning", "Not Stage 3. That needs many bleeding spots in all 4 areas. Here: {k} of 4 areas.",
              "Why not Severe NPDR: the 4-2-1 haemorrhage criterion needs more than 20 haemorrhages in each of 4 quadrants; here "
              "{k} of 4 quadrants, at most {m} in one. Venous beading and IRMA are not assessed.",
              {"k": "haemorrhage_quadrants.count", "m": "haemorrhage_quadrants.max_per_quadrant"},
              refs={"lesions": ["HE"], "quadrants": hq["quadrants"]})
    elif g == 3:
        b.add("why-not-higher", "reasoning", "Stage 4 is not ruled out. This tool cannot see new vessel growth.",
              "Why not Proliferative DR: PDR is defined by neovascularisation or vitreous/preretinal haemorrhage, which these models "
              "do not detect. PDR cannot be ruled out by the AI alone.")
    if g < 3:
        b.add("pdr-limit", "limits", "This tool cannot see " + plain("nv").lower() + ". A doctor must rule out Stage 4.",
              "Neovascularisation is not detected by these models; proliferative DR cannot be ruled out by the AI alone.")

    # Macula
    dme = f["macular_edema_risk"]
    risk = plain("dme")
    if dme["level"] == "high":
        b.add("dme", "macula", risk + ": high. A yellow deposit is {d} optic-nerve widths from the centre.",
              "Macular-edema risk: high. Nearest hard exudate {d} disc diameters from the fovea ({n} within 1 disc diameter).",
              {"d": "macular_edema_risk.nearest_exudate_dd", "n": "macular_edema_risk.exudates_within_1dd"},
              refs={"lesions": ["EX"], "landmarks": ["fovea"]})
    elif dme["level"] == "possible":
        b.add("dme", "macula", risk + ": possible. The nearest yellow deposit is {d} optic-nerve widths away.",
              "Macular-edema risk: possible. Hard exudates present; nearest {d} disc diameters from the fovea.",
              {"d": "macular_edema_risk.nearest_exudate_dd"}, refs={"lesions": ["EX"], "landmarks": ["fovea"]})
    else:
        b.add("dme", "macula", risk + ": low. No yellow deposits found.",
              "Macular-edema risk: low. No hard exudates segmented.", refs={"landmarks": ["fovea"]})
    if dme["landmarks_uncertain"]:
        b.add("landmarks", "limits", "We could not find the centre of vision reliably. Distances may be off.",
              "Fovea position uncertain (low macular contrast); exudate distances may be inaccurate.", refs={"landmarks": ["fovea"]})
    b.add("dme-note", "limits", "Only an " + inline("oct") + " can confirm swelling.",
          "Photographic risk sign only; macular edema is confirmed by OCT or clinical examination.")

    # Flags
    for k, flag in enumerate(f["flags"]):
        paths = {name: f"flags.{k}.trigger.{name}" for name in flag["trigger"]}
        b.add(f"flag-{flag['id']}", "flags", flag["simple"], flag["template"], paths, refs=flag.get("refs"))
    return b.out


def clinical_only_terms():
    """Clinical labels that must not appear in Simple text unless their plain label is also there."""
    return {key: (t["clinical"].lower(), t["plain"].lower()) for key, t in TERMS.items() if t["clinical"].lower() != t["plain"].lower()}

