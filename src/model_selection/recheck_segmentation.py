"""Re-evaluate saved initial-suite weights with finite FP32 probabilities, no retraining."""
import gc,time
from common import *
from segmentation import model_for,evaluate

def recheck(seg,annotations):
    records=[]
    for path in sorted(OUT.glob('seg_*/result.json')):
        r=json.loads(path.read_text());tag=r['tag'];original=path.parent/'result_AMP_original.json'
        if r.get('evaluation_precision')=='FP32_finite_checked':continue
        history=pd.read_csv(path.parent/'history.csv')
        if not np.isfinite(history.train_loss).all():raise FloatingPointError('Initial-suite nonfinite training: '+tag)
        if not original.exists():
            original.write_text(path.read_text())
            for name in ['native_validation_metrics.csv','per_class.csv']:
                p=path.parent/name;p.with_name(p.stem+'_AMP_original.csv').write_bytes(p.read_bytes())
        checkpoint=CKPT/(tag+'.pt');before=sha(checkpoint);model=model_for(r['architecture']).to(DEVICE);model.load_state_dict(torch.load(checkpoint,map_location=DEVICE,weights_only=True));model._disable_amp=True
        if not all(torch.isfinite(p).all().item() for p in model.parameters()):raise FloatingPointError('Nonfinite checkpoint parameters: '+tag)
        if DEVICE=='cuda':torch.cuda.reset_peak_memory_stats()
        perclass,seconds=evaluate(model,seg[seg.role=='validation'],annotations,r['mode'],int(r['resolution']),tag,components=True)
        old={k:r[k] for k in ['MA_dice','mean_dice','evaluation_seconds']};r.update(original_AMP_summary=old,evaluation_precision='FP32_finite_checked',FP32_eval_peak_MiB=torch.cuda.max_memory_allocated()/2**20 if DEVICE=='cuda' else None,evaluation_seconds=seconds,MA_dice=next(x['dice'] for x in perclass if x['annotation_type']=='MA'),mean_dice=float(np.mean([x['dice'] for x in perclass])),per_class=perclass)
        dump(path,r);pd.DataFrame(perclass).to_csv(path.parent/'per_class.csv',index=False)
        records.append(dict(tag=tag,original_MA_dice=old['MA_dice'],FP32_MA_dice=r['MA_dice'],original_mean_dice=old['mean_dice'],FP32_mean_dice=r['mean_dice'],checkpoint_unchanged=before==sha(checkpoint),all_probabilities_finite=True,reference='same native validation images and fixed .5 threshold; weights unmodified'))
        print('FP32 RECHECK',tag,'MA',r['MA_dice'],'mean',r['mean_dice'],flush=True);del model;gc.collect();torch.cuda.empty_cache()
    if records:pd.DataFrame(records).to_csv(OUT/'segmentation_FP32_inference_recheck.csv',index=False)
