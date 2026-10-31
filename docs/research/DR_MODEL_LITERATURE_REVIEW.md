# DR model literature review

Search/review date: 2026-10-28. Focused primary-source review, not a systematic review or meta-analysis. Queries covered 2024–2026 DR CNN/transformer comparisons, MA/local-global segmentation, ordinal losses and external validation. Author arXiv texts are labeled preprints; PubMed indexing is not independent validation. Some PMC/full-text requests returned CAPTCHA or inaccessible PDF responses; inaccessible details remain explicitly unextracted. Numeric literature results below are **reported**, never our results. The initial 20-source review preceded initial fitting. Tversky was added after observing baseline MA failures and before the explicitly adaptive MA follow-up; it was not an initial preregistered choice.

The strongest reasons for our design are task compatibility and our audited data: 404 content-clean development images, only 18 grade-1 training labels, unknown patient grouping, and 35.459% MA component loss at width 224. Binary referable-DR, four-class DR, five-class DR and pixel segmentation results are not interchangeable. High accuracy on selected/imbalanced data is not architecture evidence by itself.

For each study, critically audit sample independence, whether augmentation followed splitting, label compatibility, patient grouping, external cohorts, pretraining overlap and model/threshold selection. “Not extracted” below is a review limitation, not proof that authors failed to report a detail. Our local duplicate findings prohibit assuming published official IDRiD splits are leakage-free. Separate training on IDRiD and DDR is not automatically cross-domain validation. Test-led selection on an alleged external cohort would also weaken its independence.

## Evidence ledger

Every requested extraction field is recorded in `outputs/metrics/model_selection/literature_evidence.csv`. The concise records below avoid presenting missing methods as known.

### Goh et al., Comparative Analysis of Vision Transformers and Conventional CNNs in Detecting Referable DR, Ophthalmology Science, doi:10.1016/j.xops.2024.100552

[Peer-reviewed; abstract and accessible primary excerpts](https://pmc.ncbi.nlm.nih.gov/articles/PMC11334703/)

**Year:** 2024

**Dataset:** 41,614 Kaggle photographs; two external test sets

**Task:** Binary referable DR

**Architecture:** Five CNNs and four ViTs, including ResNet50 and Swin-T

**Input resolution:** Not extracted from the reviewed source; do not infer

**Preprocessing:** Not extracted from the reviewed source; do not infer

**Training strategy:** Not extracted from the reviewed source; do not infer

**Loss:** Not extracted from the reviewed source; do not infer

**Metrics:** Sensitivity at fixed specificity

**Reported results:** Swin sensitivity 94.4% at 80% specificity internally; CNN range 76.3–83.8%

**External validation:** Reported two external sets; detailed independence audit not verified

**Strengths:** Contemporary head-to-head with external evaluation

**Limitations:** Binary endpoint, much larger data; patient split/augmentation timing not verified here

**Relevance:** Motivates testing both families, not declaring Swin our five-grade winner

### Ding et al., HRDecoder: High-Resolution Decoder Network for Fundus Image Lesion Segmentation

[arXiv preprint; full methods/table reviewed](https://arxiv.org/html/2411.03976v1)

**Year:** 2024

**Dataset:** IDRiD 54/27; DDR 383/149/225

**Task:** Four-lesion segmentation

**Architecture:** HRNetv2 plus high-resolution decoder; ConvNeXt variant

**Input resolution:** IDRiD 2880×1920; train crops 1920²

**Preprocessing:** Resize and crop; sliding-window inference

**Training strategy:** SGD 0.01; batch 4; 20k/40k iterations; three repeats

**Loss:** Not extracted from the reviewed source; do not infer

**Metrics:** AUPR, F, IoU

**Reported results:** IDRiD mean AUPR 71.29%, F 67.41%, IoU 51.94%; MA F 49.35%

**External validation:** Separate dataset experiments are not necessarily cross-domain transfer

**Strengths:** Explicit global/detail and compute analysis

**Limitations:** Large compute; official split caveats differ from our protocol

**Relevance:** Supports native-detail experiment; not a performance target

### Dutta and Jeong, Multi-Resolution Feature Stem for DR lesion segmentation

[arXiv preprint, not verified peer-reviewed; full methods reviewed](https://arxiv.org/html/2607.08679v1)

**Year:** 2026

**Dataset:** DDR; 383 training photographs

**Task:** Four-lesion segmentation

**Architecture:** U-Net, U-Net++, DeepLabV3+, FPN; proposed multiresolution U-Net++

**Input resolution:** 512² versus 1024²

**Preprocessing:** Aspect-preserved resize and center crop; bilinear image/nearest mask

**Training strategy:** M4 Max and A100; geometric/photometric augmentation

**Loss:** 0.6 focal + 0.4 Dice

**Metrics:** mAP, mIoU, lesion AP/IoU

**Reported results:** Proposed test mAP .3985; mIoU .2853; HE below its best baseline

**External validation:** No locked independent-source transfer established

**Strengths:** Lesion-specific trade-offs instead of assuming higher is always better

**Limitations:** Resolution/crop, protocol and preliminary weight tuning confound comparisons

**Relevance:** Measure MA and each other lesion separately; avoid universal claims

### Fang, Ma, Qian, Multi-task transformer framework and radiomic signatures, Photodiagnosis Photodyn Ther, doi:10.1016/j.pdpdt.2026.105455

[Peer-reviewed PubMed abstract; full methods not independently inspected](https://pubmed.ncbi.nlm.nih.gov/41895558/)

**Year:** 2026

**Dataset:** 987 lesion images; 6,852 four-class grading images, two clinical centers

**Task:** Segmentation, detection and four-class grading

**Architecture:** UNet++, CE-Net, Swin-UNet, SegFormer; ViT versus radiomics classifiers

**Input resolution:** Not extracted from the reviewed source; do not infer

**Preprocessing:** CLAHE, artifact filtering, retinal masking

**Training strategy:** Harmonized settings; internal CV and external multicenter testing

**Loss:** Not extracted from the reviewed source; do not infer

**Metrics:** Dice, mAP, accuracy, AUC

**Reported results:** Reported external radiomics accuracy .883/AUC .947 versus ViT .838/.902; lesion Dice .871–.963

**External validation:** Reported multicenter; exact protocol needs full-text audit

**Strengths:** Already combines lesion analysis and grading evidence

**Limitations:** Four-class outcome; unknown patient grouping/pretraining details in abstract

**Relevance:** Combining grading and segmentation is not novelty; no basis for automatic fusion

### Jiang et al., GlanceSeg, IEEE JBHI, doi:10.1109/JBHI.2024.3377592

[Peer-reviewed PubMed; DOI 2024, issue December 2025](https://pubmed.ncbi.nlm.nih.gov/38483801/)

**Year:** 2025

**Dataset:** IDRiD and Retinal-Lesions with gaze-related annotations

**Task:** MA segmentation and annotation assistance

**Architecture:** Gaze-prompted SAM plus domain filtering

**Input resolution:** Not extracted from the reviewed source; do not infer

**Preprocessing:** Gaze ROI and saliency prompts

**Training strategy:** Human-in-loop; optional annotation fine-tuning

**Loss:** Not extracted from the reviewed source; do not infer

**Metrics:** Quantitative metrics not extracted

**Reported results:** No numeric claim extracted from abstract

**External validation:** Two dataset evaluations; independent autonomous deployment not established

**Strengths:** Targets minute lesions and annotation efficiency

**Limitations:** Requires gaze/prompt information absent from our masks-only protocol

**Relevance:** Do not compare prompted/human-assisted results to our automatic baseline

### He et al., Deep Residual Learning for Image Recognition (CVPR 2016)

[Foundational author source; abstract-level extraction](https://arxiv.org/abs/1512.03385)

**Year:** 2016

**Dataset:** ImageNet; CIFAR; COCO

**Task:** Image recognition

**Architecture:** ResNet

**Input resolution:** Not extracted from the reviewed source; do not infer

**Preprocessing:** Not extracted from the reviewed source; do not infer

**Training strategy:** Paper-specific; local implementation/weights documented separately

**Loss:** Not extracted from the reviewed source; do not infer

**Metrics:** Paper benchmark metrics; no local DR result

**Reported results:** No architecture-specific number transposed to our task

**External validation:** Not evidence of retinal external validation

**Strengths:** Established architecture mechanism

**Limitations:** Domain and training recipes differ; full hyperparameter extraction incomplete

**Relevance:** Residual paths provide a standard transfer baseline

### Huang et al., Densely Connected Convolutional Networks (CVPR 2017)

[Foundational author source; abstract-level extraction](https://arxiv.org/abs/1608.06993)

**Year:** 2017

**Dataset:** CIFAR, SVHN, ImageNet

**Task:** Image recognition

**Architecture:** DenseNet

**Input resolution:** Not extracted from the reviewed source; do not infer

**Preprocessing:** Not extracted from the reviewed source; do not infer

**Training strategy:** Paper-specific; local implementation/weights documented separately

**Loss:** Not extracted from the reviewed source; do not infer

**Metrics:** Paper benchmark metrics; no local DR result

**Reported results:** No architecture-specific number transposed to our task

**External validation:** Not evidence of retinal external validation

**Strengths:** Established architecture mechanism

**Limitations:** Domain and training recipes differ; full hyperparameter extraction incomplete

**Relevance:** Feature reuse; retain as literature alternative, no extra tournament slot

### Tan and Le, EfficientNet (ICML 2019)

[Foundational author source; abstract-level extraction](https://arxiv.org/abs/1905.11946)

**Year:** 2019

**Dataset:** ImageNet

**Task:** Image recognition

**Architecture:** EfficientNet

**Input resolution:** Not extracted from the reviewed source; do not infer

**Preprocessing:** Not extracted from the reviewed source; do not infer

**Training strategy:** Paper-specific; local implementation/weights documented separately

**Loss:** Not extracted from the reviewed source; do not infer

**Metrics:** Paper benchmark metrics; no local DR result

**Reported results:** No architecture-specific number transposed to our task

**External validation:** Not evidence of retinal external validation

**Strengths:** Established architecture mechanism

**Limitations:** Domain and training recipes differ; full hyperparameter extraction incomplete

**Relevance:** Compound scaling; B0 is the compact comparator, B7 results do not describe B0

### Liu et al., A ConvNet for the 2020s (CVPR 2022)

[Foundational author source; abstract-level extraction](https://arxiv.org/abs/2201.03545)

**Year:** 2022

**Dataset:** ImageNet, COCO, ADE20K

**Task:** Classification/dense prediction

**Architecture:** ConvNeXt

**Input resolution:** Not extracted from the reviewed source; do not infer

**Preprocessing:** Not extracted from the reviewed source; do not infer

**Training strategy:** Paper-specific; local implementation/weights documented separately

**Loss:** Not extracted from the reviewed source; do not infer

**Metrics:** Paper benchmark metrics; no local DR result

**Reported results:** No architecture-specific number transposed to our task

**External validation:** Not evidence of retinal external validation

**Strengths:** Established architecture mechanism

**Limitations:** Domain and training recipes differ; full hyperparameter extraction incomplete

**Relevance:** Modern CNN controls against attributing all gains to attention

### Liu et al., Swin Transformer (ICCV 2021)

[Foundational author source; abstract-level extraction](https://arxiv.org/abs/2103.14030)

**Year:** 2021

**Dataset:** ImageNet, COCO, ADE20K

**Task:** Classification/dense prediction

**Architecture:** Swin

**Input resolution:** Not extracted from the reviewed source; do not infer

**Preprocessing:** Not extracted from the reviewed source; do not infer

**Training strategy:** Paper-specific; local implementation/weights documented separately

**Loss:** Not extracted from the reviewed source; do not infer

**Metrics:** Paper benchmark metrics; no local DR result

**Reported results:** No architecture-specific number transposed to our task

**External validation:** Not evidence of retinal external validation

**Strengths:** Established architecture mechanism

**Limitations:** Domain and training recipes differ; full hyperparameter extraction incomplete

**Relevance:** Hierarchical local attention; resolution scalable compared with global ViT

### Dosovitskiy et al., An Image is Worth 16x16 Words (ICLR 2021)

[Foundational author source; abstract-level extraction](https://arxiv.org/abs/2010.11929)

**Year:** 2021

**Dataset:** Large-scale pretraining; ImageNet, CIFAR, VTAB

**Task:** Image recognition

**Architecture:** ViT

**Input resolution:** Not extracted from the reviewed source; do not infer

**Preprocessing:** Not extracted from the reviewed source; do not infer

**Training strategy:** Paper-specific; local implementation/weights documented separately

**Loss:** Not extracted from the reviewed source; do not infer

**Metrics:** Paper benchmark metrics; no local DR result

**Reported results:** No architecture-specific number transposed to our task

**External validation:** Not evidence of retinal external validation

**Strengths:** Established architecture mechanism

**Limitations:** Domain and training recipes differ; full hyperparameter extraction incomplete

**Relevance:** Data/pretraining dependence cautions against scratch training on 404 images

### Ronneberger et al., U-Net (MICCAI 2015)

[Foundational author source; abstract-level extraction](https://arxiv.org/abs/1505.04597)

**Year:** 2015

**Dataset:** Microscopy segmentation

**Task:** Biomedical segmentation

**Architecture:** U-Net

**Input resolution:** Not extracted from the reviewed source; do not infer

**Preprocessing:** Not extracted from the reviewed source; do not infer

**Training strategy:** Paper-specific; local implementation/weights documented separately

**Loss:** Not extracted from the reviewed source; do not infer

**Metrics:** Paper benchmark metrics; no local DR result

**Reported results:** No architecture-specific number transposed to our task

**External validation:** Not evidence of retinal external validation

**Strengths:** Established architecture mechanism

**Limitations:** Domain and training recipes differ; full hyperparameter extraction incomplete

**Relevance:** Skip connections preserve localization; baseline decoder

### Zhou et al., UNet++ (DLMIA/ML-CDS 2018)

[Foundational author source; abstract-level extraction](https://arxiv.org/abs/1807.10165)

**Year:** 2018

**Dataset:** CT, microscopy, colonoscopy

**Task:** Medical segmentation

**Architecture:** U-Net++

**Input resolution:** Not extracted from the reviewed source; do not infer

**Preprocessing:** Not extracted from the reviewed source; do not infer

**Training strategy:** Paper-specific; local implementation/weights documented separately

**Loss:** Not extracted from the reviewed source; do not infer

**Metrics:** Paper benchmark metrics; no local DR result

**Reported results:** No architecture-specific number transposed to our task

**External validation:** Not evidence of retinal external validation

**Strengths:** Established architecture mechanism

**Limitations:** Domain and training recipes differ; full hyperparameter extraction incomplete

**Relevance:** Nested skip paths are a controlled increase in decoder complexity

### Chen et al., Encoder-Decoder with Atrous Separable Convolution (ECCV 2018)

[Foundational author source; abstract-level extraction](https://arxiv.org/abs/1802.02611)

**Year:** 2018

**Dataset:** PASCAL VOC, Cityscapes

**Task:** Semantic segmentation

**Architecture:** DeepLabV3+

**Input resolution:** Not extracted from the reviewed source; do not infer

**Preprocessing:** Not extracted from the reviewed source; do not infer

**Training strategy:** Paper-specific; local implementation/weights documented separately

**Loss:** Not extracted from the reviewed source; do not infer

**Metrics:** Paper benchmark metrics; no local DR result

**Reported results:** No architecture-specific number transposed to our task

**External validation:** Not evidence of retinal external validation

**Strengths:** Established architecture mechanism

**Limitations:** Domain and training recipes differ; full hyperparameter extraction incomplete

**Relevance:** Atrous context with decoder; small-lesion output stride must be considered

### Lin et al., Feature Pyramid Networks (CVPR 2017)

[Foundational author source; abstract-level extraction](https://arxiv.org/abs/1612.03144)

**Year:** 2017

**Dataset:** COCO

**Task:** Object detection

**Architecture:** FPN

**Input resolution:** Not extracted from the reviewed source; do not infer

**Preprocessing:** Not extracted from the reviewed source; do not infer

**Training strategy:** Paper-specific; local implementation/weights documented separately

**Loss:** Not extracted from the reviewed source; do not infer

**Metrics:** Paper benchmark metrics; no local DR result

**Reported results:** No architecture-specific number transposed to our task

**External validation:** Not evidence of retinal external validation

**Strengths:** Established architecture mechanism

**Limitations:** Domain and training recipes differ; full hyperparameter extraction incomplete

**Relevance:** Lateral multiscale features; not originally a retinal segmentation system

### Xie et al., SegFormer (NeurIPS 2021)

[Foundational author source; abstract-level extraction](https://arxiv.org/abs/2105.15203)

**Year:** 2021

**Dataset:** ADE20K, Cityscapes

**Task:** Semantic segmentation

**Architecture:** MiT encoder and MLP decoder

**Input resolution:** Not extracted from the reviewed source; do not infer

**Preprocessing:** Not extracted from the reviewed source; do not infer

**Training strategy:** Paper-specific; local implementation/weights documented separately

**Loss:** Not extracted from the reviewed source; do not infer

**Metrics:** Paper benchmark metrics; no local DR result

**Reported results:** No architecture-specific number transposed to our task

**External validation:** Not evidence of retinal external validation

**Strengths:** Established architecture mechanism

**Limitations:** Domain and training recipes differ; full hyperparameter extraction incomplete

**Relevance:** Lightweight B0 attention comparator; no absolute positional encoding

### Cao et al., Swin-Unet (2021 preprint; ECCV workshops 2022)

[Foundational author source; abstract-level extraction](https://arxiv.org/abs/2105.05537)

**Year:** 2022

**Dataset:** Medical segmentation benchmarks

**Task:** Medical segmentation

**Architecture:** Swin-Unet

**Input resolution:** Not extracted from the reviewed source; do not infer

**Preprocessing:** Not extracted from the reviewed source; do not infer

**Training strategy:** Paper-specific; local implementation/weights documented separately

**Loss:** Not extracted from the reviewed source; do not infer

**Metrics:** Paper benchmark metrics; no local DR result

**Reported results:** No architecture-specific number transposed to our task

**External validation:** Not evidence of retinal external validation

**Strengths:** Established architecture mechanism

**Limitations:** Domain and training recipes differ; full hyperparameter extraction incomplete

**Relevance:** Pure transformer alternative; not an additional local grid dimension

### Hou, Yu, Samaras, Squared Earth Mover’s Distance loss for ordered classes

[Author preprint / NIPS 2017 workshop version](https://arxiv.org/abs/1611.05916)

**Year:** 2016

**Dataset:** Age and image aesthetics

**Task:** Ordinal classification

**Architecture:** CNN with cumulative-distribution loss

**Input resolution:** Not extracted from the reviewed source; do not infer

**Preprocessing:** Not extracted from the reviewed source; do not infer

**Training strategy:** Supervised ordered targets

**Loss:** Squared differences of cumulative class distributions

**Metrics:** Ordered prediction performance

**Reported results:** No numerical result imported

**External validation:** Not retinal external validation

**Strengths:** Simple objective keeps a standard five-probability interface

**Limitations:** Equal grade spacing is an analysis convention, not calibrated clinical harm

**Relevance:** Test CE plus fixed-strength cumulative penalty, not a novel ordinal network

### Lin et al., Focal Loss for Dense Object Detection (ICCV 2017)

[Peer-reviewed foundational source](https://arxiv.org/abs/1708.02002)

**Year:** 2017

**Dataset:** COCO

**Task:** Dense detection

**Architecture:** RetinaNet

**Input resolution:** Not extracted from the reviewed source; do not infer

**Preprocessing:** Not extracted from the reviewed source; do not infer

**Training strategy:** Downweight easy examples

**Loss:** Focal loss

**Metrics:** Detection AP

**Reported results:** No DR performance inferred

**External validation:** Not retinal external validation

**Strengths:** Direct foreground/background imbalance rationale

**Limitations:** Detection success does not guarantee five-class grading benefit

**Relevance:** Compare fixed gamma=2 against CE/weighted CE on training-only folds

### Guo et al., On Calibration of Modern Neural Networks (ICML 2017)

[Peer-reviewed PMLR](https://proceedings.mlr.press/v70/guo17a.html)

**Year:** 2017

**Dataset:** Image and document classification

**Task:** Probability calibration

**Architecture:** Post-hoc temperature scaling

**Input resolution:** Not extracted from the reviewed source; do not infer

**Preprocessing:** Not extracted from the reviewed source; do not infer

**Training strategy:** Fit scalar temperature on held-out calibration data

**Loss:** Negative log likelihood

**Metrics:** Reliability/calibration measures

**Reported results:** Temperature scaling often effective; no DR number imported

**External validation:** No retinal validation

**Strengths:** Separates confidence from correctness

**Limitations:** Fitting temperature and reporting calibration on the same predictions is optimistic

**Relevance:** Report raw Brier/NLL/ECE; any later fitted calibration needs independent/cross-fitted evaluation

### Salehi, Erdogmus, Gholipour, Tversky loss function for image segmentation

[Author source; adaptive MA follow-up reference](https://arxiv.org/abs/1706.05721)

**Year:** 2017

**Dataset:** Multiple-sclerosis MRI lesions

**Task:** Imbalanced lesion segmentation

**Architecture:** 3D fully convolutional networks

**Input resolution:** Not extracted from the reviewed source; do not infer

**Preprocessing:** Not extracted from the reviewed source; do not infer

**Training strategy:** Supervised lesion segmentation

**Loss:** Asymmetric Tversky index

**Metrics:** Dice, F2, precision-recall area

**Reported results:** Improved trade-off reported; no numeric retinal result imported

**External validation:** Not retinal external validation

**Strengths:** Explicit FP/FN trade-off for sparse positives

**Limitations:** MRI result does not validate MA loss coefficients or clinical costs

**Relevance:** Justifies a bounded MA-only hypothesis; coefficients are engineering choices

## Translation into prespecified local experiments

- ResNet50 establishes difficulty; EfficientNet-B0 tests compactness; ConvNeXt-Tiny distinguishes a modern convolutional recipe from Swin-Tiny attention. DenseNet121, EfficientNet-B2 and global ViT are literature alternatives, not extra grid slots.
- Frozen ImageNet features test what transfers without representation adaptation; controlled last-stage fine-tuning tests whether adaptation helps with 404 labels. Different published pretrained recipes remain a confound even when all use ImageNet-1k.
- Use common aspect-preserving resize plus padding, ImageNet channel normalization, AdamW family and checkpoint rule. Do not copy aggressive medical image enhancements without ablation. Cropping may remove border artifacts but also changes field of view.
- Three stratified folds give six grade-1 validation cases per fold; fixed seeds separate optimization variability from split variability. These remain image-level, not patient-level folds. Model-selection CV is optimistically selected and is not final generalization evidence.
- Grading loss candidates are CE, training-fold-only inverse-frequency weighted CE, fixed gamma-2 focal loss and CE plus a fixed cumulative squared-distance penalty. No validation labels enter class weights or sample generation.
- Segmentation starts with U-Net/U-Net++/DeepLabV3+ sharing a pretrained residual encoder; SegFormer-B0 changes encoder family and is therefore a model-package comparison, not a decoder-only causal experiment. Mask availability gates loss and metrics.
- A native 256/512 patch retains source pixel sampling but loses global context. Full-image and patch predictions must be evaluated on the same original validation images, not separately selected lesion patches. Split image identities before extracting patches. Record tiling cost and component matching.
- Grad-CAM/attention compatibility is not proof of explanation faithfulness. No joint lesion/grading system or novelty claim is justified without observed complementary baseline errors and resolved correspondence. External validation, gradability and clinical utility remain unestablished.
