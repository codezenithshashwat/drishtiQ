# Model card: RetinaScreen

Plain-language summary of what the models do, how they were checked and where they fail. The numbers live in [results/KEY_NUMBERS.md](../results/KEY_NUMBERS.md) and [results/SCORECARD.md](../results/SCORECARD.md); both are generated from `results/registry.csv` and are not typed by hand.

## What it is

| Part | What it does | Current model (see `configs/app/app.json`) |
|---|---|---|
| Quality gate | Rejects or flags images that are not fundus photographs, or are too dark, bright or blurred | Image heuristics; the corner-darkness threshold was fitted on training images (ADR-023) |
| Grader | Suggests the ICDR stage (0–4) | ConvNeXt-Tiny fine-tuned on IDRiD + APTOS + MMRDR (regression head, 384 px), adopted by a pre-registered rule (ADR-013/015). Later parts (thresholds, specialists, ensemble, TTA) are added only if their rule passes |
| Lesion segmenter | Marks microaneurysms, haemorrhages, hard and soft exudates | v0.1 (SegFormer-B0 + MA U-Net) or A3 (U-Net/ResNet18 trained with DDR), chosen per lesion by ADR-016 |
| Landmarks | Optic disc and fovea | Image heuristics; uncertain positions are shown dashed |
| Macular-edema rule | Flags hard exudates within one disc diameter of the fovea | Rule with one fitted area threshold (dev-train only) |
| Calibration and deferral | Probability of referable DR; defers to a human when unsure | Platt + isotonic on the grader's inner hold-out (ADR-019) |

## Intended use

- **Users:** screening programmes, as decision support for trained graders and doctors.
- **Input:** one colour fundus photograph per eye, from adults with diabetes.
- **Output:** a suggested stage, lesion map, macular-edema risk and a worklist order. A clinician reviews every case.

## Not intended for

- Diagnosis without clinician review.
- Children, other retinal diseases (glaucoma, AMD, vein occlusion), or OCT-confirmed macular edema.
- Images from cameras or populations very different from the training data, until externally validated.
- Commercial use of the trained weights (one training dataset, DDR, is CC BY-NC-SA).

## Training data

See [DATA_CARD.md](DATA_CARD.md). Grading uses IDRiD dev-train, the APTOS 2019 training split and the MMRDR colour fundus subset. Segmentation uses the IDRiD segmentation set and DDR lesion masks. No validation, locked test or external image was used for training, thresholds or selection.

## Evaluation

| Set | Role | Status |
|---|---|---|
| IDRiD-val (101) and APTOS-val (518) | Held-out validation for every decision (paired bootstrap, pre-registered rules) | Reported in KEY_NUMBERS |
| IDRiD clean test (102) | Locked internal test | Evaluated once, after release candidate `rc-1` |
| DeepDRiD (regular fundus) | Locked external test | Evaluated once, after `rc-1` |
| Messidor-2 | Locked external test | Evaluated once, after `rc-1` |

## Known failure modes

From the validation confusion matrices, the robustness tests (R1–R4) and the Grad-CAM audit (R3):

- **Mild DR is under-called:** stage-1 images are often called stage 0, because microaneurysms are a few pixels wide.
- **Stages 2 and 3 are confused** in both directions; the boundary depends on haemorrhage counts per quadrant and venous beading, which the grader sees only indirectly.
- **Stage 4 is under-called as stage 3** when new vessels are small or outside the image.
- **Image quality:** heavy blur, dark exposure and strong JPEG compression lower agreement (R1). The quality gate flags most such images, and non-fundus images are never given a confident stage (R2).
- **Landmarks:** the fovea heuristic can fail on dark or off-centre images. The macular-edema rule is then less reliable, and the macula ring is dashed.
- **Heatmaps:** Grad-CAM can focus on the optic disc or on light reflections (R3). It shows where the grader looked, not where the lesions are.
- **Population:** validated only on datasets from India so far.

## Licences

The code licence is still to be decided (see `queue/QUESTIONS_FOR_ME.md`). The trained weights inherit the most restrictive training-data licence: CC BY-NC-SA 4.0 (DDR), i.e. non-commercial.
