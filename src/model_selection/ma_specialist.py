"""Adaptive, matched MA-only diagnostic; not a four-lesion model or initial grid."""
import gc,time
import numpy as np
import pandas as pd
import torch
from torch import nn
import segmentation_models_pytorch as smp
from common import *
from segmentation import native,full_view,patch_view,evaluate

class MAHead(nn.Module):
    def __init__(self):
        super().__init__();self.net=smp.Unet(encoder_name='resnet18',encoder_weights='imagenet',classes=1,decoder_channels=(128,64,32,16,16))
    def forward(self,x):
        logits=self.net(x)
        # Dummy inactive channels reuse common native reconstruction; never optimized/evaluated.
        return torch.cat([logits,torch.full_like(logits,-20).expand(-1,3,-1,-1)],1)

def loss(logits,target,spatial,pos_weight):
    z=logits[:,0].float();y=target[:,0];bce=nn.functional.binary_cross_entropy_with_logits(z,y,reduction='none',pos_weight=torch.tensor(pos_weight,device=z.device));bce=(bce*spatial).sum()/spatial.sum().clamp_min(1)
    p=z.sigmoid();tp=(p*y*spatial).sum();fp=(p*(1-y)*spatial).sum();fn=((1-p)*y*spatial).sum()
    tversky=1-(tp+1)/(tp+.3*fp+.7*fn+1)
    return .5*bce+.5*tversky

def fit(seg,annotations,s,mode,epochs=12):
    size=512 if mode=='full' else 256;tag=f'ma_Unet_{mode}{size}_weighted_bce_tversky_e{epochs}_s{s}_fp32';folder=OUT/tag;folder.mkdir(exist_ok=True);done=folder/'result.json';checkpoint=CKPT/(tag+'.pt')
    if done.exists():return json.loads(done.read_text())
    seed(s);rng=np.random.default_rng(s);tr=seg[seg.role=='train'];va=seg[seg.role=='validation']
    for r in seg.itertuples():native(r,annotations)
    positive=sum(int(native(r,annotations)[1][0].sum()) for r in tr.itertuples());pixels=sum(int(native(r,annotations)[1][0].size) for r in tr.itertuples());weight=float(min(50,(pixels-positive)/positive))
    model=MAHead().to(DEVICE);model._disable_amp=True;opt=torch.optim.AdamW(model.parameters(),lr=.0003,weight_decay=.0001);scaler=torch.amp.GradScaler(DEVICE,enabled=False)
    config=dict(tag=tag,task='segmentation_MA_specialist',architecture='Unet',encoder='resnet18',pretraining='ImageNet-1k',targets=['MA'],mode=mode,resolution=size,seed=s,epochs=epochs,optimizer='AdamW',lr=.0003,weight_decay=.0001,objective='0.5 weighted BCE + 0.5 batch-global Tversky; FP alpha=.3, FN beta=.7, smoothing=1',positive_weight=weight,positive_weight_rule='min(50, training-native-negative/positive); no validation prevalence used',training_images=len(tr),validation_images=len(va),checkpoint='fixed final epoch',threshold=.5,BN='fixed running statistics',patch_sampling='50% MA-centered/jittered, 50% uniform; train only',nominal_pixels_per_image_epoch=2*512*512,parameters=sum(p.numel() for p in model.parameters()),trainable_parameters=sum(p.numel() for p in model.parameters()),amendment='adaptive failure analysis after initial four-lesion MA Dice was zero; not preregistered')
    config.update(precision='FP32',study_role='matched_primary_MA_followup',valid_for_comparison=True,numerical_checks='finite loss, logits and gradients before optimizer update; finite inference probabilities')
    dump(CFG/(tag+'.json'),config);full={}
    if mode=='full':
        for r in tr.itertuples():
            x,y,_,_=native(r,annotations);full[r.sample_key]=full_view(x,y,size)[:3]
    if DEVICE=='cuda':torch.cuda.reset_peak_memory_stats()
    history=[];start=time.perf_counter()
    for epoch in range(epochs):
        model.train()
        for module in model.modules():
            if isinstance(module,nn.BatchNorm2d):module.eval()
        repeats=2 if mode=='full' else 8;batch=1 if mode=='full' else 4;order=[r for r in tr.itertuples() for _ in range(repeats)];rng.shuffle(order);values=[]
        for offset in range(0,len(order),batch):
            xs=[];ys=[];spatial=[]
            for r in order[offset:offset+batch]:
                if mode=='full':
                    tx,ty,sp=full[r.sample_key]
                    if rng.random()<.5:tx=tx.flip(-1);ty=ty.flip(-1);sp=sp.flip(-1)
                else:
                    x,y,_,coords=native(r,annotations);only_ma=[coords[0]]+[np.empty((0,2),int)]*3;tx,ty,sp=patch_view(x,y,only_ma,size,rng)
                xs.append(tx);ys.append(ty);spatial.append(sp)
            opt.zero_grad()
            logits=model(torch.stack(xs))
            objective=loss(logits,torch.stack(ys),torch.stack(spatial),weight)
            if not torch.isfinite(objective) or not torch.isfinite(logits).all():raise FloatingPointError('Nonfinite MA training loss/logits; run invalid, not an empty-lesion prediction')
            scaler.scale(objective).backward();scaler.unscale_(opt);nn.utils.clip_grad_norm_(model.parameters(),5,error_if_nonfinite=True);scaler.step(opt);scaler.update();values.append(objective.item())
        history.append(dict(epoch=epoch,train_loss=float(np.mean(values))));print(tag,'epoch',epoch+1,'loss',float(np.mean(values)),flush=True)
    sync();seconds=time.perf_counter()-start;torch.save(model.state_dict(),checkpoint)
    perclass,eval_seconds=evaluate(model,va,annotations,mode,size,tag,components=True);ma=next(x for x in perclass if x['annotation_type']=='MA')
    # Other outputs in the adapter are inactive. Persist only the MA task evaluation.
    perimage=pd.read_csv(folder/'native_validation_metrics.csv');perimage[perimage.annotation_type=='MA'].to_csv(folder/'native_validation_metrics.csv',index=False)
    result=dict(config,training_seconds=seconds,evaluation_seconds=eval_seconds,peak_allocated_MiB=torch.cuda.max_memory_allocated()/2**20 if DEVICE=='cuda' else None,checkpoint_MiB=checkpoint.stat().st_size/2**20,MA_dice=ma['dice'],MA_iou=ma['iou'],MA_recall=ma['recall'],MA_precision=ma['precision'],component_recall=ma['component_recall'],component_precision=ma['component_precision'],per_class=[ma])
    pd.DataFrame(history).to_csv(folder/'history.csv',index=False);pd.DataFrame([ma]).to_csv(folder/'per_class.csv',index=False);dump(done,result)
    print('MA SPECIALIST RESULT',tag,ma,flush=True);del model,opt,full;gc.collect();torch.cuda.empty_cache();return result

def study(seg,annotations):
    dump(CFG/'adaptive_MA_amendment.json',{'timing':'after initial full-image and native-patch four-lesion failures; before these fits','motivation':'all initial MA predictions empty at fixed threshold; isolate MA supervision with matched input-strategy comparison','architecture':'existing U-Net/ResNet18, one MA head','modes':['full512','native_patch256'],'seeds':[17,29],'epochs':12,'objective':'weighted BCE + Tversky with prespecified fixed coefficients','new_test_access':False,'limits':'target, loss and schedule differ from initial four-lesion runs; compare input modes within this matched suite, not as a single-factor ablation of the original suite'})
    from run_study import protected_call
    records=[]
    for s in [17,29]:
        for mode in ['full','patch']:
            r=protected_call(fit,seg,annotations,s,mode)
            if r:records.append({k:v for k,v in r.items() if not isinstance(v,(dict,list))})
    pd.DataFrame(records).to_csv(OUT/'MA_specialist_runs.csv',index=False)
