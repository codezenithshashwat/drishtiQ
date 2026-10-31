import json,re,hashlib,subprocess
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image
from common import *

def table(df):
    df=df.copy()
    for c in df.select_dtypes('number').columns:df[c]=df[c].round(5)
    return '| '+' | '.join(map(str,df.columns))+' |\n| '+' | '.join(['---']*len(df.columns))+' |\n'+'\n'.join('| '+' | '.join(str(v).replace('|','/') for v in row)+' |' for row in df.itertuples(index=False,name=None))

def load_runs():
    rows=[];details={}
    for path in OUT.glob('*/result.json'):
        r=json.loads(path.read_text());details[r['tag']]=r
        if r.get('task')=='grading':
            if r.get('stage')=='frozen' and 'architecture' not in r:
                m=re.match(r'frozen_(.+)_r(\d+)_(.+)_f(\d+)_s(\d+)',r['tag'])
                if m:r.update(architecture=m[1],resolution=int(m[2]),preprocessing=m[3],augmentation='none',objective='ce')
            if r.get('stage')=='frozen' and not (CFG/(r['tag']+'.json')).exists():
                dim={'resnet50':2048,'efficientnet_b0':1280,'convnext_tiny':768,'swin_t':768}[r['architecture']]
                dump(CFG/(r['tag']+'.json'),dict(task='grading',stage='frozen_feature_extractor',tag=r['tag'],fold=r['fold'],seed=r['seed'],architecture=r['architecture'],resolution=r['resolution'],preprocessing=r['preprocessing'],manifest='outputs/metrics/model_selection/grading_folds.csv',manifest_sha256=sha(OUT/'grading_folds.csv'),feature_dimension=dim,trainable_parameters=dim*5+5,head='linear five-class softmax',normalization='feature mean/std fitted on training fold only; std floor .1',optimizer='AdamW',lr=.01,weight_decay=.01,max_epochs=60,batch=64,patience=12,checkpoint='validation macro-F1 then QWK, earliest exact tie',augmentation='none',configuration_record='backfilled from fixed executed trainer constants; no retraining'))
            if r.get('stage')=='frozen':
                cfg=json.loads((CFG/(r['tag']+'.json')).read_text());cfg.setdefault('architecture',r['architecture']);cfg.setdefault('resolution',r['resolution']);cfg.setdefault('preprocessing',r['preprocessing']);dump(CFG/(r['tag']+'.json'),cfg)
            rows.append({k:v for k,v in r.items() if not isinstance(v,(dict,list))})
    frame=pd.DataFrame(rows);frame.to_csv(OUT/'grading_runs.csv',index=False);return frame,details

def grading_plots(rows,details,chosen,g):
    group=rows[(rows.stage==chosen.stage)&(rows.architecture==chosen.architecture)&(rows.resolution==chosen.resolution)&(rows.preprocessing==chosen.preprocessing)&(rows.augmentation==chosen.augmentation)&(rows.objective==chosen.objective)]
    oof=[]
    for s in [17,29]:
        parts=[pd.read_csv(OUT/r.tag/'validation_predictions.csv') for r in group[group.seed==s].itertuples()]
        if len(parts)!=3:continue
        z=pd.concat(parts,ignore_index=True);assert len(z)==404 and z.sample_key.nunique()==404
        z['seed']=s;oof.append(z)
    if not oof:return
    allpred=pd.concat(oof,ignore_index=True);allpred.to_csv(OUT/'selected_grading_OOF_predictions.csv',index=False)
    scalar=[]
    for s,z in allpred.groupby('seed'):
        result,cm,classes=metrics(z.DR_grade.values,z[['p'+str(i) for i in range(5)]].values)
        scalar.append(dict(seed=int(s),images=len(z),**result))
        pd.DataFrame(classes).to_csv(OUT/f'selected_grading_per_class_seed{s}.csv',index=False)
        plt.figure(figsize=(6,5));plt.imshow(cm,cmap='Blues');plt.xticks(range(5));plt.yticks(range(5));plt.xlabel('Predicted DR');plt.ylabel('True DR');plt.title(f'Development OOF, seed {s}; not test')
        for i in range(5):
            for j in range(5):plt.text(j,i,str(cm[i][j]),ha='center',va='center',color='white' if cm[i][j]>max(map(max,cm))*.5 else 'black')
        plt.tight_layout();plt.savefig(FIG/f'grading_confusion_seed{s}.png',dpi=140);plt.close()
    pd.DataFrame(scalar).to_csv(OUT/'selected_grading_OOF_metrics.csv',index=False)
    z=allpred[allpred.seed==17].copy();z['correct']=z.predicted_grade.eq(z.DR_grade)
    representative=group[(group.seed==17)&(group.fold==0)].iloc[0]
    hist=pd.read_csv(OUT/representative.tag/'history.csv');fig,axes=plt.subplots(1,2,figsize=(12,4))
    axes[0].plot(hist.epoch,hist.train_loss,label='Training loss');axes[0].plot(hist.epoch,hist.nll,label='Validation NLL');axes[0].legend();axes[0].set_xlabel('Epoch');axes[0].set_title('Selected package: training versus validation')
    axes[1].plot(hist.epoch,hist.macro_f1,label='Validation macro-F1');axes[1].plot(hist.epoch,hist.qwk,label='Validation QWK');axes[1].axvline(representative.best_epoch,color='gray',linestyle='--',label='Selected checkpoint');axes[1].legend();axes[1].set_xlabel('Epoch');plt.tight_layout();plt.savefig(FIG/'selected_grading_learning_curves.png',dpi=140);plt.close()
    # Bootstrap at image level within a seed; neither patient independence nor selection correction implied.
    rng=np.random.default_rng(20261028);boot=[]
    for _ in range(500):
        ix=rng.integers(0,len(z),len(z));b=z.iloc[ix];r,_,_=metrics(b.DR_grade.values,b[['p'+str(i) for i in range(5)]].values);boot.append({k:r[k] for k in ['macro_f1','qwk','balanced_accuracy','mae_grade']})
    ci=pd.DataFrame(boot).quantile([.025,.975]).T.reset_index();ci.columns=['metric','image_bootstrap_low','image_bootstrap_high'];ci.to_csv(OUT/'selected_grading_descriptive_intervals.csv',index=False)
    plt.figure(figsize=(6,5));cal=[]
    for lo in np.arange(0,1,.1):
        b=z[(z.confidence>=lo)&(z.confidence<(lo+.1) if lo<.9 else z.confidence<=1)]
        if len(b):cal.append((b.confidence.mean(),b.correct.mean(),len(b)))
    plt.plot([0,1],[0,1],'--',color='gray');plt.plot([v[0] for v in cal],[v[1] for v in cal],'o-');plt.xlabel('Mean confidence');plt.ylabel('Observed accuracy');plt.title('Uncalibrated OOF probabilities, seed 17');plt.tight_layout();plt.savefig(FIG/'grading_reliability.png',dpi=140);plt.close()
    metadata=pd.read_csv(ROOT/'outputs/metrics/idrid_image_metadata.csv');metadata['filepath']=metadata.path.str.replace('\\','/',regex=False)
    z=z.merge(metadata[['filepath','brightness','contrast','black_fraction','laplacian_variance']],on='filepath',validate='one_to_one')
    assoc=[]
    for col in ['brightness','contrast','black_fraction','laplacian_variance']:
        bins=pd.qcut(z[col],4,duplicates='drop')
        for interval,sub in z.groupby(bins,observed=True):assoc.append(dict(characteristic=col,quartile=str(interval),n=len(sub),error_rate=float((~sub.correct).mean()),mean_distance=float(sub.distance.mean())))
    pd.DataFrame(assoc).to_csv(OUT/'grading_error_quality_associations.csv',index=False)
    subsets={'high_confidence_wrong':z[~z.correct].sort_values('confidence',ascending=False).head(6),'low_confidence':z.sort_values('confidence').head(6),'high_grade_undergraded':z[(z.DR_grade>=3)&(z.predicted_grade<=1)].head(6),'minority_grade1_errors':z[(z.DR_grade==1)&~z.correct].head(6)}
    for name,subset in subsets.items():
        if not len(subset):continue
        fig,axes=plt.subplots(2,3,figsize=(13,7))
        for ax in axes.flat:ax.axis('off')
        for ax,r in zip(axes.flat,subset.itertuples()):
            with Image.open(ROOT/r.filepath) as im:ax.imshow(im.resize((640,425)))
            ax.set_title(f'{r.image_id} true={r.DR_grade} pred={r.predicted_grade}\nconfidence={r.confidence:.2f}, OOF fold={r.fold}')
        plt.tight_layout();plt.savefig(FIG/(name+'.png'),dpi=130);plt.close()
    # All four serious architecture packages: same fold and seed gallery, without test reads.
    common=rows[(rows.stage=='partial_fine_tuning')&(rows.resolution==224)&(rows.fold==0)&(rows.seed==17)&(rows.preprocessing=='baseline')&(rows.augmentation=='none')&(rows.objective=='ce')]
    for r in common.itertuples():
        pred=pd.read_csv(OUT/r.tag/'validation_predictions.csv');sub=pred[pred.predicted_grade!=pred.DR_grade].sort_values('confidence',ascending=False).head(4)
        fig,axes=plt.subplots(1,4,figsize=(14,4))
        for ax in axes:ax.axis('off')
        for ax,x in zip(axes,sub.itertuples()):
            with Image.open(ROOT/x.filepath) as im:ax.imshow(im.resize((600,399)))
            ax.set_title(f'{r.architecture}: {x.image_id}\ntrue {x.DR_grade}, pred {x.predicted_grade}, p={x.confidence:.2f}')
        plt.tight_layout();plt.savefig(FIG/(r.architecture+'_screen_errors.png'),dpi=120);plt.close()

def generate(g,seg,annotations):
    rows,details=load_runs();keys=['stage','architecture','resolution','preprocessing','augmentation','objective']
    summary=rows.groupby(keys,dropna=False).agg(runs=('tag','size'),folds=('fold','nunique'),seeds=('seed','nunique'),macro_f1_mean=('macro_f1','mean'),macro_f1_std=('macro_f1','std'),qwk_mean=('qwk','mean'),qwk_std=('qwk','std'),balanced_accuracy=('balanced_accuracy','mean'),minority_grade1_recall=('minority_grade1_recall','mean'),undergrading_3_4_to_0_1=('high_grade_to_0_or_1_rate','mean'),nll=('nll','mean'),brier=('brier','mean'),ece=('ece_10_bins','mean'),overfit_gap=('overfit_gap','mean'),training_seconds=('training_seconds','mean')).reset_index()
    summary.to_csv(OUT/'grading_scorecard.csv',index=False)
    complete=summary[(summary.runs==6)&(summary.folds==3)&(summary.seeds==2)].copy()
    # All complete frozen and fine-tuned packages are eligible; partial screening groups cannot win.
    params={'resnet50':23518277,'efficientnet_b0':4013953,'convnext_tiny':27823973,'swin_t':27523199};ops={'resnet50':4.089,'efficientnet_b0':.386,'convnext_tiny':4.456,'swin_t':4.491}
    complete['parameters']=complete.architecture.map(params);complete['approx_reference_GFLOPs']=complete.architecture.map(ops)*(complete.resolution/224)**2
    head_dims={'resnet50':2048,'efficientnet_b0':1280,'convnext_tiny':768,'swin_t':768};partial_counts={'resnet50':14974981,'efficientnet_b0':1135797,'convnext_tiny':15475973,'swin_t':14189237}
    complete['trainable_parameters']=complete.apply(lambda r:head_dims[r.architecture]*5+5 if r.stage=='frozen' else partial_counts[r.architecture],axis=1)
    complete=complete.sort_values(['macro_f1_mean','qwk_mean'],ascending=False);best=complete.iloc[0]
    eligible=complete[(complete.macro_f1_mean>=best.macro_f1_mean-.02)&(complete.qwk_mean>=best.qwk_mean-.02)]
    chosen=eligible.sort_values(['approx_reference_GFLOPs','parameters','trainable_parameters','resolution']).iloc[0]
    dump(CFG/'final_engineering_tiebreak_note.json',{'timing':'after development CV; not a preregistered confirmatory hypothesis','performance_band':'unchanged .02 absolute macro-F1 and .02 QWK from best complete package','inference_cost_rule':'prefer lower reference compute and total parameters within that band','same_backbone_tiebreak':'prefer fewer trainable parameters; a tiny partial-tuning gain within the band does not justify updating millions of extra weights','scope':'engineering recommendation, not statistical equivalence or clinical noninferiority; test remains locked'})
    dump(OUT/'final_development_recommendation.json',chosen.to_dict());grading_plots(rows,details,chosen,g)
    common=rows[(rows.stage=='partial_fine_tuning')&(rows.resolution==224)&(rows.fold==0)&(rows.preprocessing=='baseline')&(rows.augmentation=='none')&(rows.objective=='ce')]
    screen=common.groupby('architecture').agg(runs=('tag','size'),macro_f1=('macro_f1','mean'),qwk=('qwk','mean'),grade1_recall=('minority_grade1_recall','mean'),undergrading=('high_grade_to_0_or_1_rate','mean'),parameters=('parameters','first'),trainable_parameters=('trainable_parameters','first'),peak_MiB=('peak_allocated_MiB','max'),inference_s_per_cached_image=('inference_seconds_per_image','mean'),checkpoint_MiB=('checkpoint_MiB','mean')).reset_index()
    screen.to_csv(OUT/'grading_common_screen.csv',index=False)
    screen['explanation_tooling_compatibility']=screen.architecture.map(lambda x:'gradient maps / attention analysis; fidelity untested' if x=='swin_t' else 'Grad-CAM compatible; fidelity untested')
    screen['external_validation_evidence']='none locally; independent evaluation required'
    screen['resolution_evidence']=screen.architecture.map(lambda x:'224/384/512/768 screen; targeted confirmation' if x=='convnext_tiny' else '224 only in this bounded study')
    screen.to_csv(OUT/'grading_common_screen.csv',index=False)
    ablations=rows[(rows.stage=='partial_fine_tuning')&(rows.architecture==json.loads((OUT/'grading_backbone_selection.json').read_text())['model'])&(rows.fold==0)]
    ablations=ablations.groupby(['resolution','preprocessing','augmentation','objective']).agg(runs=('tag','size'),macro_f1=('macro_f1','mean'),qwk=('qwk','mean'),grade1_recall=('minority_grade1_recall','mean'),undergrading=('high_grade_to_0_or_1_rate','mean'),nll=('nll','mean'),training_seconds=('training_seconds','mean')).reset_index()
    ablations.to_csv(OUT/'grading_ablation_comparison.csv',index=False)
    frozen=summary[(summary.stage=='frozen')&(summary.resolution==224)&(summary.preprocessing=='baseline')]
    for metric in ['macro_f1_mean','qwk_mean']:
        plt.figure(figsize=(9,4));plt.bar(frozen.architecture,frozen[metric],yerr=frozen[metric.replace('_mean','_std')]);plt.ylabel(metric);plt.title('Frozen ImageNet features: 3 folds × 2 seeds');plt.tight_layout();plt.savefig(FIG/(metric+'_frozen.png'),dpi=140);plt.close()
    perclass=[]
    for tag,r in details.items():
        if r.get('task')=='grading':
            for c in r['per_class']:perclass.append(dict(tag=tag,**c))
    pd.DataFrame(perclass).to_csv(OUT/'grading_per_class_all_runs.csv',index=False)
    segmentation=[]
    for p in OUT.glob('seg_*/result.json'):
        r=json.loads(p.read_text());segmentation.append({k:v for k,v in r.items() if not isinstance(v,(list,dict))})
    sr=pd.DataFrame(segmentation);sr.to_csv(OUT/'segmentation_runs.csv',index=False)
    ss=sr.groupby(['architecture','mode','resolution','objective']).agg(runs=('seed','size'),MA_dice=('MA_dice','mean'),MA_dice_std=('MA_dice','std'),mean_dice=('mean_dice','mean'),mean_dice_std=('mean_dice','std'),training_seconds=('training_seconds','mean'),native_validation_seconds=('evaluation_seconds','mean'),peak_MiB=('peak_allocated_MiB','max'),parameters=('parameters','first'),checkpoint_MiB=('checkpoint_MiB','mean')).reset_index()
    ss.to_csv(OUT/'segmentation_scorecard.csv',index=False);sb=ss[ss.runs>=2].sort_values(['MA_dice','mean_dice'],ascending=False).iloc[0]
    ma_warning=('No initial four-lesion package demonstrated nonzero MA Dice at the fixed threshold. There is no demonstrated MA-capable winner in that suite; its four-lesion mean leader is only a larger-lesion baseline. Zero Dice may reflect optimization, calibration/threshold, sparse supervision and resolution together; it cannot isolate resizing as the cause.' if ss.MA_dice.max()==0 else 'A nonzero MA result is an exploratory signal. Inspect both seeds, native precision/recall and false positives; a small MA-first mean advantage does not establish a reliable clinical segmenter or dominance on other lesions.')
    ma_runs=[json.loads(p.read_text()) for p in OUT.glob('ma_*/result.json')]
    ma_summary=pd.DataFrame()
    ma_note='No MA-only follow-up completed.'
    if ma_runs:
        ma_frame=pd.DataFrame([{k:v for k,v in r.items() if not isinstance(v,(dict,list))} for r in ma_runs]);ma_frame.to_csv(OUT/'MA_specialist_runs.csv',index=False)
        primary_ma=ma_frame[ma_frame.precision.eq('FP32')&ma_frame.valid_for_comparison.eq(True)]
        ma_summary=primary_ma.groupby(['mode','resolution','epochs']).agg(runs=('seed','size'),MA_dice=('MA_dice','mean'),MA_dice_std=('MA_dice','std'),recall=('MA_recall','mean'),precision=('MA_precision','mean'),component_recall=('component_recall','mean'),component_precision=('component_precision','mean'),training_seconds=('training_seconds','mean')).reset_index();ma_summary.to_csv(OUT/'MA_specialist_scorecard.csv',index=False)
        ma_best=ma_summary[ma_summary.runs>=2].sort_values('MA_dice',ascending=False).iloc[0]
        ma_note=f"Adaptive MA-only follow-up leader: U-Net/ResNet18, {ma_best['mode']}{int(ma_best.resolution)}, 12 epochs, 0.5 weighted BCE + 0.5 Tversky (FP=.3, FN=.7; training-only positive weight capped at 50). Mean native MA Dice={ma_best.MA_dice:.5f}, recall={ma_best.recall:.5f}, precision={ma_best.precision:.5f}. This suite changes target/loss/schedule from the original four-lesion suite; input modes are compared within the matched follow-up, not as a pure resolution ablation across suites. It is a diagnostic experiment, not validated MA capability."
        fig,axes=plt.subplots(1,2,figsize=(12,4));x=np.arange(len(ma_summary))
        axes[0].bar(x,ma_summary.MA_dice,yerr=ma_summary.MA_dice_std);axes[0].set_xticks(x,ma_summary['mode']);axes[0].set_ylabel('Native MA Dice');axes[0].set_title('Matched FP32 MA-only suite, two seeds')
        axes[1].bar(x-.15,ma_summary.recall,width=.3,label='Pixel recall');axes[1].bar(x+.15,ma_summary.precision,width=.3,label='Pixel precision');axes[1].set_xticks(x,ma_summary['mode']);axes[1].legend();axes[1].set_title('Recall/precision trade-off; threshold 0.5');plt.tight_layout();plt.savefig(FIG/'MA_full_vs_native_patch_FP32.png',dpi=140);plt.close()
    segclass=[]
    for p in OUT.glob('seg_*/per_class.csv'):
        f=pd.read_csv(p);f['tag']=p.parent.name;segclass.append(f)
    if segclass:pd.concat(segclass).to_csv(OUT/'segmentation_per_class_all_runs.csv',index=False)
    plt.figure(figsize=(11,5));plt.bar([f'{r.architecture}\n{r.mode}{r.resolution}\n{r.objective}' for r in ss.itertuples()],ss.MA_dice,yerr=ss.MA_dice_std);plt.ylabel('MA native-image Dice');plt.xticks(rotation=40,ha='right');plt.tight_layout();plt.savefig(FIG/'segmentation_MA_comparison.png',dpi=140);plt.close()
    actual=sum(float(r.get('training_seconds',0)) for r in details.values() if r.get('task')=='grading')+float(sr.training_seconds.sum())+sum(float(r.get('training_seconds',0)) for r in ma_runs)
    warm=rows[(rows.stage=='partial_fine_tuning')].best_epoch.eq(-1).sum();nf=int(rows.stage.eq('partial_fine_tuning').sum())
    scope=json.loads((OUT/'selection_scope.json').read_text());hardware=json.loads((OUT/'hardware.json').read_text());failed=(OUT/'failed_runs.jsonl').read_text() if (OUT/'failed_runs.jsonl').exists() else 'None recorded.'
    intro=f'''# DR model-selection scorecard

This is a **bounded development study**, not clinical validation or a final clean-test result. Only the clean 404-image development manifest was used for grading; the 102-image clean test manifest and its pixels were blocked by the runner. Official segmentation test images were also blocked. No joint grading/segmentation model was trained. Patient independence remains unknown.

Hardware: {hardware['gpu']}, {hardware['vram_GiB']:.2f} GiB VRAM; {hardware['torch']}. Each fit records a configuration and checkpoint. Frozen features: three stratified folds × two seeds; each validation fold contains only six grade-1 images. All four grading architectures received the same common screen. Only two finalists received complete partial-tuning CV. Resolution and one-factor screens use fold0/two seeds before matched confirmation. Fold/seed spread is descriptive; six scores are correlated, not six independent clinical studies.

## Common grading screen: equal fold, seeds, resolution and objective

{table(screen)}

## Complete grading packages: three folds × two seeds only

{table(complete)}

## Isolated resolution, preprocessing, augmentation and objective screens

{table(ablations)}

These rows share fold0 and the two optimization seeds. Compare each transformation against the same-resolution baseline. A one-fold screen is exploratory. Matched baseline and selected-recipe confirmation on the other folds is kept separate; changes are never declared additive merely because each individually looks favorable. The 512 CE confirmation is a documented adaptive extension prompted by disagreement between macro-F1, QWK and MA preservation, not a retrospective claim of preregistration.

Selected-package pooled OOF metrics (each seed covers the same 404 development images once):

{table(pd.read_csv(OUT/'selected_grading_OOF_metrics.csv'))}

## All grading packages, including exploratory partial screens

{table(summary)}

The recommendation ranks mean macro-F1, then QWK. Within the declared 0.02 absolute macro-F1 and 0.02 QWK band around the best complete package, prefer lower reference compute and total parameters. For the same backbone/input, the final engineering tie-break prefers fewer trainable parameters. That tie-break was articulated after observing development CV and is transparently recorded in final_engineering_tiebreak_note.json; it is not retrospectively called preregistered. These are engineering tolerances, not significance tests, statistical equivalence, clinical noninferiority or a clinical utility score. No aggregate weighted score is used. Macro-F1, QWK, minority recall, severe undergrading bins, calibration and compute remain separate columns. All fitted head/partial-stage results and raw validation predictions are retained.

**Warm-start checkpoint finding:** {warm} of {nf} partial-tuning runs selected their pre-fine-tuning frozen-head checkpoint (best_epoch=-1). Fine-tuning was attempted, but was not automatically assumed beneficial. Overfit gap compares training versus validation macro-F1 at the selected checkpoint. Short six-epoch partial schedules, head-only warm-up, model-specific pretrained recipes and selected-checkpoint optimism limit architectural conclusions. A model eliminated in this screen is not proven inferior under all training budgets.

## Segmentation: native-image evaluation, no patch-level split

{table(ss)}

**MA capability limitation:** {ma_warning}

## Adaptive MA-only follow-up, analyzed separately

{table(ma_summary) if len(ma_summary) else 'Not completed.'}

{ma_note}

This four-fit extension (two input modes × two seeds) was motivated by empty MA predictions from the initial suite. Its source rationale is [Salehi et al., Tversky loss](https://arxiv.org/abs/1706.05721); MRI evidence does not establish retinal loss coefficients or clinical costs. The amendment is recorded before fitting. It uses one MA head, the same 40/10 image split, a longer common fixed budget, the same two seeds and held-out native images. Patch-positive sampling is MA-specific. BCE weights use training-native prevalence only, with an explicit engineering cap; coefficients are not tuned on the official test. MA-only Dice is never averaged as if it were a four-lesion score. PR/threshold analysis and independent validation remain needed before concluding capability.

**Numerical failure and recovery:** an exploratory FP16 MA patch run (seed29) developed NaN loss. Its thresholded empty-mask score is invalid and excluded, not treated as genuine zero capability. All four matched MA fits were rerun in FP32 with finite-loss/logit/gradient checks. Only that matched FP32 suite is ranked above. Original probe artifacts and the failure log are retained. Initial four-lesion checkpoints were also re-evaluated with finite-checked FP32 inference, preserving original AMP metrics and unchanged weights separately. This is a documented numerical correction, not test-driven tuning.

Segmentation used {scope['segmentation_roles']} within {scope['segmentation_development_images']} eligible organizer training images; four potential grading-test correspondences were conservatively excluded before its split. All validation patches from one original image remain held out together. Pixel metrics are computed against native masks after reconstruction, with unavailable channels omitted. Threshold 0.5 was fixed. Component recall/precision use one-to-one eight-connected components matched at IoU≥0.1; these are geometric annotation regions, not adjudicated lesion diagnoses. Per-class results, including precision/recall/IoU and component detection, are saved separately.

U-Net/U-Net++/DeepLabV3+ share an ImageNet residual encoder; SegFormer uses MiT-B0. This compares packages, not decoders in isolation. All encoders are fine-tuned in segmentation; BatchNorm running statistics are frozen to accommodate full-image batch1 consistently. Decoder widths are bounded for the laptop. Full512 receives two views/image/epoch; patch256 receives eight and patch512 two. This matches nominal input-pixel and optimizer-update budgets, but full-image letterbox padding is excluded from supervised pixels, so supervised native-area coverage differs. Training patch sampling is half lesion-centered/type-uniform, half uniform; validation uses all tiles with no lesion selection. Both modes receive horizontal flips. Nonoverlapping tiling is computationally bounded but may introduce seams; overlapping/hybrid inference was not silently substituted.

BCE and BCE+Dice are the bounded initial loss comparison. Tversky is used only in the explicitly adaptive MA-only follow-up; focal segmentation loss is not an unrun winner. OD is excluded from lesion outputs so disc overlap cannot inflate lesion metrics. Empty patch regions from an available full mask are legitimate background; absent full-mask supervision is never background. Native RGBA alpha is excluded by the decoder. All runs use the same image-level validation split and two seeds; there is no segmentation K-fold claim. Every available MA mask is nonempty: background pixels within those images do not supply a verified cohort of MA-negative photographs. Image-level specificity on lesion-free screening photographs is unestablished. HE/SE metrics are conditional on annotation availability; unannotated image/type pairs cannot establish negatives.

## Calibration, errors and explanation compatibility

Accuracy, balanced accuracy, macro/weighted F1, QWK, per-class precision/recall/specificity, confusion matrices, OvR macro AUC, NLL, multiclass Brier and 10-bin ECE are recorded. Probabilities are raw; no calibration fit is evaluated on its own fit data. Error bins grade3/4→0/1 and grade0→3/4 are descriptive, not adopted referral thresholds. Galleries include common-screen errors for every grading family, high-confidence mistakes, low-confidence cases and minority-grade mistakes. Brightness/contrast/black fraction/blur-proxy quartiles are descriptive associations, not causal explanations or gradability labels. Lesion-size correlation is not supportable for all 404 images: only three exact cross-task correspondences exist; candidates were not assigned lesion labels for this analysis.

CNN gradients and hierarchical attention support explanation tooling, but no explanation-fidelity or clinician-benefit evaluation was performed. No model can be awarded external-validation performance from an architecture alone. Approximate cross-task identities and patient identities remain unresolved, even though protected test paths were not accessed.

## Compute, failure log and limitations

Sum of recorded grading/head/segmentation fitting durations: {actual:.1f} seconds (excludes weight downloads, raw decoding/caching, some initialization and analysis). Runtime is measured on this machine and is not portable. Peak allocated MiB measures PyTorch tensors, not total display/system VRAM. Cached-image grading latency includes normalization/batching and probability output; native segmentation validation time also includes reconstruction/component analysis, and is not pure GPU latency. Approximate torchvision 224 reference GFLOPs are not a measured retinal-task FLOP trace; resolution-square scaling is a CNN approximation and not exact Swin cost.

Recorded failed runs:

```
{failed}
```

No low sample-size confidence interval can remove patient dependence or repeated model-selection bias. Image-bootstrap intervals are descriptive for the selected development pipeline, not selection-corrected patient-level inference. All confidence/error results need independent verification. The official test remains unscored.
'''
    (ROOT/'docs/research/DR_MODEL_SELECTION_SCORECARD.md').write_text(intro,encoding='utf-8')
    chosen_text=f"{chosen.architecture}, {int(chosen.resolution)}-width aspect-preserved padded input, {chosen.stage}, preprocessing={chosen.preprocessing}, augmentation={chosen.augmentation}, objective={chosen.objective}"
    recipe=(chosen.preprocessing,chosen.augmentation,chosen.objective)
    recommendation=f'''# DR architecture recommendation

## Decision and its scope

**Provisional development baseline:** {chosen_text}. Mean fold/seed macro-F1={chosen.macro_f1_mean:.4f}, QWK={chosen.qwk_mean:.4f}; grade-1 recall={chosen.minority_grade1_recall:.4f}. This recommendation is conditional on the recorded short-budget study. It does not establish a deployable final architecture. No clean-test or external score exists.

**Provisional segmentation experiment leader:** {sb.architecture}, {sb['mode']} at {int(sb.resolution)}, objective={sb.objective}; native validation MA Dice={sb.MA_dice:.4f}, mean lesion Dice={sb.mean_dice:.4f}. Inspect every lesion's precision/recall and seed spread in the scorecard before treating this as a usable segmentation baseline. Leadership on ten validation images is weak evidence, not clinical validity. **{ma_warning}**

**Separate MA investigation:** {ma_note}

Evidence codes below: **E**=our experiment; **P**=primary-source literature review; **C**=explicit compute/protocol constraint. Study result files and configs are under outputs/metrics/model_selection and configs/experiments.

1. **Grading backbone:** {chosen.architecture} [E]. Selected only among complete three-fold/two-seed packages using the declared macro-F1/QWK/compute band and a documented post-CV same-backbone preference for fewer trainable weights. The latter is an engineering judgment, not a preregistered efficacy claim. This is a local baseline recommendation, not a universal CNN-versus-transformer conclusion.
2. **Why:** measured ordered agreement, rare-class behavior, stability and resource cost are listed in the scorecard [E,C]. Published binary/four-class results were not treated as equivalent to our five-class endpoint [P].
3. **Alternatives tested:** pretrained ResNet50, EfficientNet-B0, ConvNeXt-Tiny, Swin-Tiny; frozen-feature CV for all, partial-tuning common screen for all, expanded CV for two finalists [E]. DenseNet/global ViT and larger EfficientNets were reviewed but not added to the grid [P,C].
4. **Why alternatives were not advanced:** the common-screen and complete-package tables show their measured trade-offs [E]. Screening eliminates a package under this budget, not the architecture in all settings. No untested variant is called experimentally rejected. Calibration and minority errors can prevent claiming a decisive winner even when one mean score is highest.
5. **Input:** {int(chosen.resolution)} active long-side pixels, aspect preserved with black padding [E,C]. The 224/384/512/768 ladder was screened on the selected backbone, not every architecture. The audit's MA sampling loss does not by itself prove that grading improves monotonically with resolution [P,E].
6. **Preprocessing:** {chosen.preprocessing}; bilinear image resize, aspect preservation and ImageNet RGB normalization [E,C]. Border cropping was an isolated ablation. CLAHE, aggressive illumination enhancement and stacked transformations were not validated and are not selected [E].
7. **Augmentation:** {chosen.augmentation} for the selected package [E]. None/minimal horizontal flip/moderate flips plus ±10° rotation and ±10% brightness were compared at the chosen screen size. No random lesion-destroying crop or elastic deformation was added. These are isolated screens, not proof of independent benefit for every transform.
8. **Grading loss:** {chosen.objective} [E]. CE, training-fold-only inverse-frequency weighted CE, gamma-2 focal and CE plus fixed cumulative squared-distance penalty were tested. No clinical grade weights or referral cutoff were invented.
9. **Categorical versus ordinal:** the selected objective above reflects measured development results [E]. The ordinal ablation uses CE + mean squared difference between predicted/target cumulative probabilities over four ordered thresholds (coefficient 1), retaining a five-class softmax [P,E]. Other ordinal heads were not tested; no ordinal superiority is presumed.
10. **Segmentation architecture:** {sb.architecture} is the observed leader for the stated split/budget [E]. U-Net/U-Net++/DeepLabV3+/SegFormer were all trained; package/encoder differences are disclosed. Increase complexity only if a matched multi-split study supports it [C].
11. **Full image versus patch:** observed leader is {sb['mode']}{int(sb.resolution)} [E]. U-Net full512, native patch256 and patch512 were directly compared on the same native validation images, with matched nominal input-pixel/update budgets. Native patches preserve sampling but lose context and introduce tiling seams; a hybrid remains an untested hypothesis [P,E].
12. **Segmentation loss:** {sb.objective} for the initial four-lesion leader [E]. BCE versus BCE+Dice was bounded and availability-gated; no missing mask was an all-zero negative. Weighted BCE + Tversky was tested separately in the documented MA-only extension; it is not an automatic replacement for the four-lesion objective [P,E,C].
13. **Remaining failures:** rare-grade recognition, high-confidence mistakes, overfitting, selected-checkpoint instability, sparse-lesion recall, patch seams and unknown patient/domain dependence. Consult error galleries and native per-image segmentation metrics [E]. Short-budget failure is not evidence that longer or differently regularized training cannot help.
14. **Lesion-aware fusion:** not yet justified by a controlled benefit experiment [E]. Pixel evidence might address observed errors, but only three exact cross-task links are currently automatic. The candidate mappings cannot support confident attribution of grading failures to lesion-size omissions.
15. **Multi-task learning:** not selected or trained [E,C]. Resolve correspondence, protect all task holdouts and first show complementary baseline errors. Recent literature already contains lesion/grading combinations; combining them alone is not novelty [P].
16. **External validation:** independent institutions, cameras/protocols/populations, compatible adjudicated grades and patient/visit grouping with overlap checks are required. A locked external evaluation must not be used repeatedly to choose the architecture. Calibration, abstention, image-quality handling and any referral rule require their own evidence [P,C].
17. **Unsupported claims:** clinical validity, patient independence, prospective workflow benefit, autonomous diagnosis, calibrated confidence, representative rural deployment, explainability faithfulness, novelty, or external generalization. The 102-image clean test is still unused [E,C].

The four-lesion baseline and MA-only follow-up are separate tasks. A larger-lesion mean winner must not be advertised as solving MA segmentation. The MA-only 256-versus-full comparison does not establish that 256 is the best MA patch size; binary 512, overlap/stitching variants and hybrids were not silently assumed equivalent. No DME, clinical-gradability or referral model was trained. Background-pixel precision does not establish specificity on MA-negative photographs.

## What should happen before final training

Keep the frozen manifest and content exclusions. Reproduce the shortlisted configuration, confirm adequate convergence with a prespecified larger training budget and preferably additional image-level splits/patient IDs, and establish a separate calibration policy. For final fitting, derive the schedule from development evidence or reserve training-only validation; never select a final checkpoint on the 102 test samples. Only after locking the entire pipeline should a separately authorized, once-only clean internal test evaluation be run. No final 404-image fit or test evaluation was performed in this study.

## Reproduce

Use requirements-model-selection.txt and the captured CUDA runtime/hardware metadata. From project root run `python src/model_selection/literature.py`, then `python src/model_selection/run_study.py --stage pilot`, `--stage grading`, `--stage ablations`, `--stage segmentation`, and `--stage report`. Completed runs resume from saved results/checkpoints. Do not delete scope/fold metadata while retaining caches. Each fit has its JSON config, history, predictions and checkpoint. GPU/library changes may prevent bit-for-bit reproducibility; fixed folds/seeds and original artifacts permit protocol replication. No independent exact numerical rerun of all training was claimed.
'''
    (ROOT/'docs/research/DR_ARCHITECTURE_RECOMMENDATION.md').write_text(recommendation,encoding='utf-8')
    # Record complete reproducibility dependencies and code/config/manifest hashes, never read test manifest.
    paths=list((ROOT/'src/model_selection').glob('*.py'))+list(CFG.glob('*.json'))+[ROOT/'data/interim/manifests/idrid_grading_train_clean.csv',OUT/'grading_folds.csv',OUT/'segmentation_development_split.csv']
    paths.extend([ROOT/'requirements-model-selection.txt',OUT/'environment_freeze.txt',OUT/'literature_evidence.csv'])
    registry=[]
    for tag,r in details.items():
        probe=r.get('study_role')=='exploratory_mixed_precision_probe';valid=r.get('valid_for_comparison',True)
        registry.append(dict(tag=tag,task=r['task'],config_filepath=(CFG/(tag+'.json')).relative_to(ROOT).as_posix(),checkpoint_filepath=(CKPT/(tag+'.pt')).relative_to(ROOT).as_posix(),valid_for_primary_comparison=not probe and valid,exclusion_reason=r.get('failure_reason','unranked exploratory AMP probe' if probe else ''),deployment_ready=False))
        if not valid:dump(CKPT/(tag+'.pt.invalid.json'),{'status':'INVALID_EXCLUDED','reason':r.get('failure_reason'),'not_permitted_for_model_selection_or_deployment':True})
    pd.DataFrame(registry).to_csv(OUT/'experiment_registry.csv',index=False)
    dump(OUT/'study_provenance.json',{'files_sha256':{p.relative_to(ROOT).as_posix():sha(p) for p in paths},'raw_test_reads':0,'test_evaluations':0,'training_runs':len(rows)+len(sr)+len(ma_runs),'raw_stat_method':'path,size,mtime_ns before/after each guarded stage','selected_grading_package':chosen.to_dict(),'selected_segmentation_package':sb.to_dict(),'MA_specialist_summary':ma_summary.to_dict('records'),'patient_independence':'UNKNOWN','external_validation':'NOT PERFORMED','full_model_numerical_reproduction':'NOT PERFORMED'})
    print('MODEL SELECTION DEVELOPMENT STUDY COMPLETE',flush=True);print(chosen_text,flush=True);print('Segmentation leader:',sb.to_dict(),flush=True)
    print('Test evaluations: 0; raw data protected; recommendation remains provisional.',flush=True)
