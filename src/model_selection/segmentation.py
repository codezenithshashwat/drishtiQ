import gc,time,json,math
import numpy as np
import pandas as pd
from PIL import Image
from scipy import ndimage as ndi
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import maximum_bipartite_matching
import torch
from torch import nn
import segmentation_models_pytorch as smp
from common import *

TYPES=['MA','HE','EX','SE']
NATIVE={}

def native(row,annotation):
    if row.sample_key in NATIVE:return NATIVE[row.sample_key]
    base=CACHE/('seg_'+row.image_id)
    xp=base.with_suffix('.image.npy');yp=base.with_suffix('.mask.npy')
    ann=annotation[annotation.sample_key==row.sample_key].set_index('annotation_type');valid=np.array([bool(ann.loc[t].annotation_available) for t in TYPES],dtype=bool)
    if not xp.exists() or not yp.exists():
        with Image.open(ROOT/row.image_filepath) as im:x=np.asarray(im.convert('RGB')).copy()
        y=np.zeros((4,x.shape[0],x.shape[1]),dtype=np.uint8)
        for i,t in enumerate(TYPES):
            if not valid[i]:continue
            with Image.open(ROOT/ann.loc[t].mask_filepath) as im:
                a=np.asarray(im);a=a[:,:,:3] if im.mode=='RGBA' else a;b=a>0
                y[i]=b.any(2) if b.ndim==3 else b
        np.save(xp,x);np.save(yp,y)
        with (OUT/'raw_image_access.jsonl').open('a') as log:log.write(json.dumps({'task':'segmentation','sample_key':row.sample_key,'filepath':row.image_filepath})+'\n')
    x=np.load(xp,mmap_mode='r');y=np.load(yp,mmap_mode='r')
    # Positive coordinates support train-only lesion-balanced cropping; validation uses exhaustive tiles.
    coords=[np.argwhere(y[i]>0) if valid[i] else np.empty((0,2),int) for i in range(4)] if row.role=='train' else None
    NATIVE[row.sample_key]=(x,y,valid,coords);return NATIVE[row.sample_key]

def model_for(name):
    if name=='Segformer':return smp.Segformer(encoder_name='mit_b0',encoder_weights='imagenet',classes=4,decoder_segmentation_channels=128)
    kwargs=dict(encoder_name='resnet18',encoder_weights='imagenet',classes=4)
    if name in ['Unet','UnetPlusPlus']:kwargs['decoder_channels']=(128,64,32,16,16)
    else:kwargs['decoder_channels']=128
    return getattr(smp,name)(**kwargs)

def tensor(x):return torch.as_tensor((np.asarray(x,dtype=np.float32).transpose(2,0,1)/255-MEAN)/STD,device=DEVICE)
def full_view(x,y,size):
    h,w=x.shape[:2];ratio=size/max(h,w);nw,nh=round(w*ratio),round(h*ratio);left=(size-nw)//2;top=(size-nh)//2
    rgb=np.zeros((size,size,3),np.uint8);rgb[top:top+nh,left:left+nw]=np.asarray(Image.fromarray(np.asarray(x)).resize((nw,nh),Image.Resampling.BILINEAR))
    target=np.zeros((4,size,size),np.float32)
    for i in range(4):target[i,top:top+nh,left:left+nw]=np.asarray(Image.fromarray(np.asarray(y[i])).resize((nw,nh),Image.Resampling.NEAREST))
    spatial=np.zeros((size,size),np.float32);spatial[top:top+nh,left:left+nw]=1
    return tensor(rgb),torch.tensor(target,device=DEVICE),torch.tensor(spatial,device=DEVICE),(left,top,nw,nh)

def loss_for(logits,y,available,spatial,kind):
    logits=logits.float();gate=available[:,:,None,None]*spatial[:,None]
    bce=nn.functional.binary_cross_entropy_with_logits(logits,y,reduction='none')
    if kind=='focal':
        p=logits.sigmoid();pt=p*y+(1-p)*(1-y);bce=bce*(1-pt)**2
    pixel=(bce*gate).sum()/gate.sum().clamp_min(1)
    if kind=='bce':return pixel
    p=logits.sigmoid()*spatial[:,None];target=y*spatial[:,None]
    dice=1-(2*(p*target).sum((2,3))+1)/(p.sum((2,3))+target.sum((2,3))+1)
    overlap=(dice*available).sum()/available.sum().clamp_min(1)
    return pixel+overlap

def patch_view(x,y,coords,size,rng):
    h,w=x.shape[:2]
    choices=[i for i,c in enumerate(coords) if len(c)]
    if choices and rng.random()<.5:
        c=coords[int(rng.choice(choices))];cy,cx=c[rng.integers(len(c))]
        # Jitter lesion position within patch, not always at its center.
        sy=int(np.clip(cy-rng.integers(size//4,3*size//4),0,h-size));sx=int(np.clip(cx-rng.integers(size//4,3*size//4),0,w-size))
    else:sy=int(rng.integers(0,h-size+1));sx=int(rng.integers(0,w-size+1))
    a=np.array(x[sy:sy+size,sx:sx+size],copy=True);b=np.array(y[:,sy:sy+size,sx:sx+size],dtype=np.float32,copy=True)
    if rng.random()<.5:a=a[:,::-1].copy();b=b[:,:,::-1].copy()
    return tensor(a),torch.tensor(b,device=DEVICE),torch.ones((size,size),device=DEVICE)

def component_counts(truth,pred):
    gt,ng=ndi.label(truth,np.ones((3,3)));pr,npred=ndi.label(pred,np.ones((3,3)))
    if not ng or not npred:return 0,ng,npred
    both=(gt>0)&(pr>0)
    if not both.any():return 0,ng,npred
    pairs,overlap=np.unique(np.stack((gt[both]-1,pr[both]-1),1),axis=0,return_counts=True)
    ga=np.bincount(gt.ravel())[1:];pa=np.bincount(pr.ravel())[1:]
    good=overlap/(ga[pairs[:,0]]+pa[pairs[:,1]]-overlap)>=.1
    pairs=pairs[good]
    if not len(pairs):return 0,ng,npred
    graph=csr_matrix((np.ones(len(pairs)),(pairs[:,0],pairs[:,1])),shape=(ng,npred))
    matches=int((maximum_bipartite_matching(graph,perm_type='column')>=0).sum())
    return matches,ng,npred

def infer(model,x,y,mode,size):
    model.eval();h,w=x.shape[:2]
    with torch.no_grad():
        if mode=='full':
            tx,_,_,(left,top,nw,nh)=full_view(x,y,size)
            with torch.autocast(DEVICE,enabled=DEVICE=='cuda' and not getattr(model,'_disable_amp',False)):prob=model(tx[None]).float().sigmoid()[0].cpu().numpy()
            if not np.isfinite(prob).all():raise FloatingPointError('Nonfinite segmentation probabilities; cannot threshold as background')
            pred=np.empty((4,h,w),bool)
            for i in range(4):pred[i]=np.asarray(Image.fromarray(prob[i,top:top+nh,left:left+nw]).resize((w,h),Image.Resampling.BILINEAR))>=.5
            return pred
        pred=np.zeros((4,h,w),bool);positions=[(sy,sx) for sy in range(0,h,size) for sx in range(0,w,size)]
        for i in range(0,len(positions),4):
            coords=positions[i:i+4];batch=[]
            for sy,sx in coords:
                crop=np.zeros((size,size,3),np.uint8);part=np.asarray(x[sy:min(h,sy+size),sx:min(w,sx+size)]);crop[:part.shape[0],:part.shape[1]]=part;batch.append(tensor(crop))
            with torch.autocast(DEVICE,enabled=DEVICE=='cuda' and not getattr(model,'_disable_amp',False)):prob=model(torch.stack(batch)).float().sigmoid().cpu().numpy()
            if not np.isfinite(prob).all():raise FloatingPointError('Nonfinite patch probabilities; cannot threshold as background')
            m=prob>=.5
            for patch,(sy,sx) in zip(m,coords):pred[:,sy:min(h,sy+size),sx:min(w,sx+size)]=patch[:,:min(size,h-sy),:min(size,w-sx)]
        return pred

def evaluate(model,validation,annotation,mode,size,tag,components=True):
    rows=[];examples=[];start=time.perf_counter()
    for row in validation.itertuples():
        x,y,available,_=native(row,annotation);t=time.perf_counter();pred=infer(model,x,y,mode,size);sync();infer_s=time.perf_counter()-t
        for i,typ in enumerate(TYPES):
            if not available[i]:continue
            truth=np.asarray(y[i],dtype=bool);p=pred[i];tp=int((truth&p).sum());fp=int((~truth&p).sum());fn=int((truth&~p).sum())
            matched,ng,npred=component_counts(truth,p) if components else (None,None,None)
            rows.append(dict(sample_key=row.sample_key,annotation_type=typ,tp=tp,fp=fp,fn=fn,dice=2*tp/max(1,2*tp+fp+fn),iou=tp/max(1,tp+fp+fn),recall=tp/max(1,tp+fn),precision=tp/max(1,tp+fp),matched_components=matched,true_components=ng,predicted_components=npred,inference_seconds=infer_s))
        if components and len(examples)<2:
            examples.append((row.image_id,np.asarray(Image.fromarray(np.asarray(x)).resize((900,598))),np.asarray(Image.fromarray((y[0]*255).astype(np.uint8)).resize((900,598),Image.Resampling.NEAREST)),np.asarray(Image.fromarray((pred[0]*255).astype(np.uint8)).resize((900,598),Image.Resampling.NEAREST))))
    frame=pd.DataFrame(rows);frame.to_csv(OUT/tag/'native_validation_metrics.csv',index=False)
    by=[]
    for typ,z in frame.groupby('annotation_type'):
        tp=z.tp.sum();fp=z.fp.sum();fn=z.fn.sum();matched=z.matched_components.sum();ng=z.true_components.sum();npred=z.predicted_components.sum()
        by.append(dict(annotation_type=typ,images=len(z),dice=float(2*tp/max(1,2*tp+fp+fn)),iou=float(tp/max(1,tp+fp+fn)),recall=float(tp/max(1,tp+fn)),precision=float(tp/max(1,tp+fp)),mean_image_dice=float(z.dice.mean()),component_recall=float(matched/max(1,ng)) if components else None,component_precision=float(matched/max(1,npred)) if components else None))
    if components:
        import matplotlib.pyplot as plt
        fig,axes=plt.subplots(len(examples),3,figsize=(14,4*len(examples)),squeeze=False)
        for axs,(ident,rgb,truth,pred) in zip(axes,examples):
            for ax,mask,title in zip(axs,[None,truth,pred],[ident,'MA reference','MA predicted @0.5']):
                overlay=rgb.copy()
                if mask is not None:overlay[mask>0]=(overlay[mask>0]*.3+np.array([255,0,255])*.7).astype(np.uint8)
                ax.imshow(overlay);ax.set_title(title);ax.axis('off')
        plt.tight_layout();plt.savefig(FIG/(tag+'_gallery.png'),dpi=120);plt.close()
    return by,time.perf_counter()-start

def train(seg,annotation,name,s,mode='full',size=512,objective='bce_dice',epochs=6):
    tag=f'seg_{name}_{mode}{size}_{objective}_s{s}';folder=OUT/tag;folder.mkdir(exist_ok=True);done=folder/'result.json';checkpoint=CKPT/(tag+'.pt')
    if done.exists():return json.loads(done.read_text())
    seed(s);rng=np.random.default_rng(s);train_rows=seg[seg.role=='train'];validation=seg[seg.role=='validation']
    # Warm all native caches only from registered development identities.
    for row in seg.itertuples():native(row,annotation)
    model=model_for(name).to(DEVICE);opt=torch.optim.AdamW(model.parameters(),lr=.0003,weight_decay=.0001);scaler=torch.amp.GradScaler(DEVICE,enabled=DEVICE=='cuda')
    config=dict(tag=tag,task='segmentation',architecture=name,encoder='mit_b0' if name=='Segformer' else 'resnet18',pretraining='ImageNet-1k encoder',seed=s,mode=mode,resolution=size,objective=objective,epochs=epochs,optimizer='AdamW',lr=.0003,weight_decay=.0001,parameters=sum(p.numel() for p in model.parameters()),trainable_parameters=sum(p.numel() for p in model.parameters()),checkpoint='final fixed-budget epoch, no validation tuning of threshold',threshold=.5,component_matching='one-to-one eight-connected overlap IoU >=0.1',patch_sampling='50% lesion-centered with type-uniform choice, 50% uniform location; training only',training_images=len(train_rows),validation_images=len(validation),validation='all eligible held-out images reconstructed at native resolution, unavailable channels omitted',BN='running statistics frozen to allow batch1 across architectures',normalization='ImageNet RGB',training_pixel_budget_per_image_epoch=2*512*512)
    dump(CFG/(tag+'.json'),config);history=[];start=time.perf_counter()
    if DEVICE=='cuda':torch.cuda.reset_peak_memory_stats()
    full={}
    if mode=='full':
        for row in train_rows.itertuples():
            x,y,available,_=native(row,annotation);full[row.sample_key]=(*full_view(x,y,size)[:3],torch.tensor(available,dtype=torch.float32,device=DEVICE))
    for epoch in range(epochs):
        model.train()
        for module in model.modules():
            if isinstance(module,nn.BatchNorm2d):module.eval()
        losses=[];repeats=2 if mode=='full' or size==512 else 8;order=[r for r in train_rows.itertuples() for _ in range(repeats)];rng.shuffle(order)
        batch=1 if mode=='full' or size==512 else 4
        for offset in range(0,len(order),batch):
            xs=[];ys=[];spatial=[];valid=[]
            for row in order[offset:offset+batch]:
                if mode=='full':
                    tx,ty,sp,av=full[row.sample_key]
                    if rng.random()<.5:tx=tx.flip(-1);ty=ty.flip(-1);sp=sp.flip(-1)
                else:
                    x,y,available,coords=native(row,annotation);tx,ty,sp=patch_view(x,y,coords,size,rng);av=torch.tensor(available,dtype=torch.float32,device=DEVICE)
                xs.append(tx);ys.append(ty);spatial.append(sp);valid.append(av)
            opt.zero_grad()
            with torch.autocast(DEVICE,enabled=DEVICE=='cuda'):logits=model(torch.stack(xs))
            loss=loss_for(logits,torch.stack(ys),torch.stack(valid),torch.stack(spatial),objective);scaler.scale(loss).backward();scaler.unscale_(opt);nn.utils.clip_grad_norm_(model.parameters(),5);scaler.step(opt);scaler.update();losses.append(loss.item())
        history.append(dict(epoch=epoch,train_loss=float(np.mean(losses))));print(tag,'epoch',epoch+1,'loss',np.mean(losses),flush=True)
    sync();training_seconds=time.perf_counter()-start;torch.save(model.state_dict(),checkpoint)
    perclass,eval_seconds=evaluate(model,validation,annotation,mode,size,tag,components=True)
    result=dict(config,training_seconds=training_seconds,evaluation_seconds=eval_seconds,checkpoint_MiB=checkpoint.stat().st_size/2**20,peak_allocated_MiB=torch.cuda.max_memory_allocated()/2**20 if DEVICE=='cuda' else None,mean_dice=float(np.mean([x['dice'] for x in perclass])),MA_dice=next(x['dice'] for x in perclass if x['annotation_type']=='MA'),per_class=perclass)
    dump(done,result);pd.DataFrame(history).to_csv(folder/'history.csv',index=False);pd.DataFrame(perclass).to_csv(folder/'per_class.csv',index=False)
    print('SEGMENTATION RESULT',tag,'MA Dice',result['MA_dice'],'mean Dice',result['mean_dice'],flush=True)
    del model,opt,full;gc.collect();torch.cuda.empty_cache();return result

def study(seg,annotation):
    from run_study import protected_call
    profile_segmenters()
    results=[]
    for name in ['Unet','UnetPlusPlus','DeepLabV3Plus','Segformer']:
        for s in [17,29]:
            r=protected_call(train,seg,annotation,name,s)
            if r:results.append(r)
    # High-priority paired full-versus-native-patch experiment on the simplest common baseline.
    for s in [17,29]:
        for mode,size,objective in [('patch',256,'bce_dice'),('patch',512,'bce_dice'),('patch',256,'bce'),('full',512,'bce')]:
            r=protected_call(train,seg,annotation,'Unet',s,mode=mode,size=size,objective=objective)
            if r:results.append(r)
    pd.DataFrame([{k:v for k,v in r.items() if not isinstance(v,(list,dict))} for r in results]).to_csv(OUT/'segmentation_runs.csv',index=False)
    summary=pd.DataFrame([{k:v for k,v in r.items() if not isinstance(v,(list,dict))} for r in results])
    if len(summary):
        ranking=summary.groupby(['architecture','mode','resolution','objective']).agg(MA_dice=('MA_dice','mean'),mean_dice=('mean_dice','mean'),seconds=('training_seconds','mean')).sort_values(['MA_dice','mean_dice'],ascending=False)
        dump(OUT/'segmentation_selection.json',{'scope':'provisional, two seeds on one image-level validation split; no external or official test evaluation','ranking':{str(k):v for k,v in ranking.to_dict('index').items()},'selection_rule':'prioritize native-image MA Dice, then four-lesion mean Dice, inspect compute before final recommendation'})

def profile_segmenters():
    path=OUT/'segmentation_compute_pilot.csv'
    if path.exists():return
    rows=[]
    for name,size,batch in [('Unet',512,1),('UnetPlusPlus',512,1),('DeepLabV3Plus',512,1),('Segformer',512,1),('Unet',256,4)]:
        model=model_for(name).to(DEVICE).eval();x=torch.randn(batch,3,size,size,device=DEVICE)
        if DEVICE=='cuda':torch.cuda.reset_peak_memory_stats()
        for _ in range(2):
            model.zero_grad()
            with torch.autocast(DEVICE,enabled=DEVICE=='cuda'):loss=model(x).float().square().mean()
            loss.backward()
        sync();start=time.perf_counter()
        for _ in range(3):
            model.zero_grad()
            with torch.autocast(DEVICE,enabled=DEVICE=='cuda'):loss=model(x).float().square().mean()
            loss.backward()
        sync();seconds=(time.perf_counter()-start)/3
        rows.append(dict(architecture=name,input_size=size,batch=batch,parameters=sum(p.numel() for p in model.parameters()),forward_backward_seconds=seconds,estimated_480_update_seconds=480*seconds,peak_MiB=torch.cuda.max_memory_allocated()/2**20 if DEVICE=='cuda' else None,scope='synthetic warm-up/pilot only; no optimizer steps or held-out images'))
        del model,x,loss;gc.collect();torch.cuda.empty_cache()
    pd.DataFrame(rows).to_csv(path,index=False);print('Segmentation compute pilot',pd.DataFrame(rows).to_string(index=False),flush=True)
