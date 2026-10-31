"""Single glossary for every user-facing medical term: plain label, one-line plain explanation, clinical label.
Used by explanations, flags, reports and (via GET /api/glossary) the UI. Components must not hard-code medical terms.
"""
TERMS = {
    # Lesions
    "MA": dict(plain="Tiny vessel bulges", one="tiny vessel bulge", explain="Small swellings in the walls of tiny blood vessels; the earliest sign.",
               clinical="Microaneurysms"),
    "HE": dict(plain="Bleeding spots", one="bleeding spot", explain="Small bleeds from damaged blood vessels in the retina.", clinical="Haemorrhages"),
    "EX": dict(plain="Yellow deposits", one="yellow deposit", explain="Fat and protein that leaked from damaged vessels.", clinical="Hard exudates"),
    "SE": dict(plain="Cotton-wool spots", one="cotton-wool spot", explain="Pale fluffy patches where the nerve layer lacks blood supply.",
               clinical="Soft exudates"),
    # Stages (ICDR)
    "stage0": dict(plain="No diabetic damage seen by the AI", explain="The AI did not see changes from diabetes in this photo. It is not a full eye examination.", clinical="No apparent DR"),
    "stage1": dict(plain="Early signs", explain="Only tiny vessel bulges are present.", clinical="Mild NPDR"),
    "stage2": dict(plain="Moderate damage", explain="More than tiny bulges, but not severe.", clinical="Moderate NPDR"),
    "stage3": dict(plain="Severe damage", explain="Widespread damage with a high risk of new vessel growth.", clinical="Severe NPDR"),
    "stage4": dict(plain="Advanced disease", explain="Fragile new blood vessels are growing; sight is at risk.", clinical="Proliferative DR"),
    # Anatomy and concepts
    "retina": dict(plain="Retina", explain="The light-sensing layer at the back of the eye.", clinical="Retina"),
    "optic_disc": dict(plain="Optic nerve head", explain="Where the nerve leaves the eye; a bright round spot.", clinical="Optic disc"),
    "macula": dict(plain="Centre of vision area", explain="The part of the retina used for reading and faces.", clinical="Macula"),
    "fovea": dict(plain="Very centre of vision", explain="The middle of the macula, used for the sharpest vision.", clinical="Fovea"),
    "quadrant": dict(plain="area", explain="The retina is split into 4 areas around the centre of vision.", clinical="quadrant"),
    "disc_width": dict(plain="optic-nerve widths", explain="Distances are measured in widths of the optic nerve head.", clinical="disc diameters"),
    "dme": dict(plain="Swelling risk at the centre of vision", explain="Leaked fluid can swell the centre of vision and blur it.",
                clinical="Macular-edema risk"),
    "nv": dict(plain="New vessel growth", explain="Fragile new vessels that can bleed; the mark of advanced disease.",
               clinical="Neovascularisation"),
    "vb_irma": dict(plain="Vessel shape changes", explain="Beaded veins or abnormal small vessels seen in severe disease.",
                    clinical="Venous beading / IRMA"),
    "oct": dict(plain="Eye scan (OCT)", explain="A painless scan that shows retinal thickness.", clinical="OCT"),
    "referable": dict(plain="Needs an eye specialist", explain="Stage 2 or worse: should be seen by an eye specialist.", clinical="Referable DR"),
    # Model and metrics
    "low_confidence": dict(plain="Low confidence", explain="The AI is unsure; a doctor should look at this image.", clinical="Low model confidence"),
    "gradcam": dict(plain="Where the AI looked", explain="Areas that most influenced the AI's stage. Not a lesion map.", clinical="Grad-CAM attribution"),
    "qwk": dict(plain="Agreement with eye specialists", explain="How closely the AI's stages match specialist grades (1 = perfect).",
                clinical="Quadratic weighted kappa"),
    "sensitivity": dict(plain="Cases caught", explain="Share of real cases the AI flags.", clinical="Sensitivity"),
    "specificity": dict(plain="Non-referable correctly not flagged", explain="Share of images without referable disease that the AI does not flag.", clinical="Specificity"),
}

STAGE_KEYS = [f"stage{i}" for i in range(5)]


def plain(key):
    return TERMS[key]["plain"]


def count_noun(key, n):
    """Plain noun agreeing with the count, lower case: 1 -> 'bleeding spot', otherwise 'bleeding spots'."""
    t = TERMS[key]
    return t["one"] if n == 1 and "one" in t else t["plain"].lower()


def inline(key):
    """Plain label for use mid-sentence (first letter lower-cased, acronyms kept)."""
    p = TERMS[key]["plain"]
    return p[0].lower() + p[1:]


def clinical(key):
    return TERMS[key]["clinical"]


def both(key):
    """'Plain (clinical)' for places that must show the medical term next to the plain one."""
    t = TERMS[key]
    return t["plain"] if t["plain"].lower() == t["clinical"].lower() else f"{t['plain']} ({t['clinical']})"
