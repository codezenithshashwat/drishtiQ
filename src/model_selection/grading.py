import gc,json,time,math
import numpy as np
import pandas as pd
import torch
from torch import nn
from common import *

def feature_matrix(g,name,size=224,prep='baseline'):
    cache=OUT/f'features_{name}_{size}_{prep}.npz'
    arr=grading_cache(g,size,prep)
    if cache.exists():return np.load(cache)['features']
    model=make_model(name,features=True).to(DEVICE).eval();start=time.perf_counter();features=[]
    with torch.no_grad():
        for i in range(0,len(g),16):
            with torch.autocast(DEVICE,enabled=DEVICE=='cuda'):f=model(batch_tensor(arr,list(range(i,min(i+16,len(g))))))
            features.append(f.float().cpu().numpy())
    sync();features=np.concatenate(features)
    np.savez(cache,features=features,sample_keys=np.asarray(g.sample_key.tolist(),dtype=np.str_),manifest_sha256=sha(OUT/'grading_folds.csv'))
    dump(OUT/f'feature_extraction_{name}_{size}_{prep}.json',{'seconds':time.perf_counter()-start,'images':len(g),'mode':'frozen ImageNet-1k feature extraction; no validation fit','batch':16,'preprocessing':prep,'size':size})
    del model;gc.collect();torch.cuda.empty_cache()
    return features

def save_predictions(path,g,index,prob):
    frame=g.iloc[index][['sample_key','image_id','DR_grade','fold','filepath']].copy();frame['predicted_grade']=prob.argmax(1);frame['confidence']=prob.max(1);frame['distance']=abs(frame.predicted_grade-frame.DR_grade)
    for i in range(5):frame['p'+str(i)]=prob[:,i]
    frame.to_csv(path,index=False)

def frozen_head(g,features,fold,s,tag):
    folder=OUT/tag;folder.mkdir(exist_ok=True)
    done=folder/'result.json'
    checkpoint=CKPT/(tag+'.pt')
    dump(CFG/(tag+'.json'),dict(task='grading',stage='frozen_feature_extractor',tag=tag,fold=fold,seed=s,manifest='outputs/metrics/model_selection/grading_folds.csv',manifest_sha256=sha(OUT/'grading_folds.csv'),feature_dimension=int(features.shape[1]),trainable_parameters=int(features.shape[1]*5+5),head='linear softmax over five grades',normalization='feature mean/std fitted on training fold only; std floor .1',optimizer='AdamW',lr=.01,weight_decay=.01,max_epochs=60,batch=64,patience=12,checkpoint='validation macro-F1 then QWK, earliest tie',augmentation='none; fixed cached ImageNet features'))
    if done.exists() and checkpoint.exists():return json.loads(done.read_text())
    seed(s);tr=np.flatnonzero(g.fold.values!=fold);va=np.flatnonzero(g.fold.values==fold)
    mean=features[tr].mean(0);std=features[tr].std(0).clip(.1)
    x=torch.tensor((features-mean)/std,device=DEVICE);y=torch.tensor(g.DR_grade.values,device=DEVICE)
    model=nn.Linear(features.shape[1],5).to(DEVICE);opt=torch.optim.AdamW(model.parameters(),lr=.01,weight_decay=.01)
    best=(-np.inf,-np.inf);history=[];start=time.perf_counter();beststate=None;patience=0
    for epoch in range(60):
        model.train();losses=[]
        for ix in np.array_split(np.random.permutation(tr),max(1,math.ceil(len(tr)/64))):
            opt.zero_grad();loss=nn.functional.cross_entropy(model(x[ix]),y[ix]);loss.backward();opt.step();losses.append(loss.item())
        model.eval()
        with torch.no_grad():prob=model(x[va]).softmax(1).cpu().numpy()
        score,_,_=metrics(g.iloc[va].DR_grade.values,prob);history.append(dict(epoch=epoch,train_loss=float(np.mean(losses)),**score))
        criterion=(score['macro_f1'],score['qwk'])
        if criterion>best:
            best=criterion;beststate={k:v.detach().cpu().clone() for k,v in model.state_dict().items()};bestprob=prob.copy();bestepoch=epoch;patience=0
        else:patience+=1
        if patience>=12:break
    model.load_state_dict(beststate)
    with torch.no_grad():trainprob=model(x[tr]).softmax(1).cpu().numpy()
    trainmetrics,_,_=metrics(g.iloc[tr].DR_grade.values,trainprob);score,cm,classes=metrics(g.iloc[va].DR_grade.values,bestprob)
    result=dict(tag=tag,task='grading',stage='frozen',fold=fold,seed=s,training_images=len(tr),validation_images=len(va),best_epoch=bestepoch,epochs_run=len(history),training_seconds=time.perf_counter()-start,train_macro_f1=trainmetrics['macro_f1'],overfit_gap=trainmetrics['macro_f1']-score['macro_f1'],**score,confusion_matrix=cm,per_class=classes)
    torch.save({'head':beststate,'feature_mean':torch.tensor(mean),'feature_std':torch.tensor(std)},checkpoint)
    save_predictions(folder/'validation_predictions.csv',g,va,bestprob);pd.DataFrame(history).to_csv(folder/'history.csv',index=False);dump(done,result)
    return result

def head_module(model,name):return model.fc if name=='resnet50' else model.head if name=='swin_t' else model.classifier[-1]

def fine(g,name,fold,s,size=224,prep='baseline',aug='none',objective='ce',epochs=6,micro_override=None):
    tag=f'fine_{name}_r{size}_{prep}_{aug}_{objective}_f{fold}_s{s}'
    folder=OUT/tag;folder.mkdir(exist_ok=True);done=folder/'result.json';checkpoint=CKPT/(tag+'.pt')
    if done.exists() and checkpoint.exists():return json.loads(done.read_text())
    seed(s);arr=grading_cache(g,size,prep);features=feature_matrix(g,name,size,prep)
    warmtag=f'frozen_{name}_r{size}_{prep}_f{fold}_s{s}'
    frozen_head(g,features,fold,s,warmtag);seed(s)
    model=make_model(name).to(DEVICE);warm=torch.load(CKPT/(warmtag+'.pt'),map_location='cpu',weights_only=True)
    with torch.no_grad():
        head=head_module(model,name);head.weight.copy_(warm['head']['weight']/warm['feature_std']);head.bias.copy_(warm['head']['bias']-(warm['head']['weight']*warm['feature_mean']/warm['feature_std']).sum(1))
    params=partial(model,name);headparams=list(head_module(model,name).parameters());headids={id(p) for p in headparams};backparams=[p for p in params if id(p) not in headids]
    opt=torch.optim.AdamW([{'params':backparams,'lr':1e-4},{'params':headparams,'lr':1e-3}],weight_decay=1e-4)
    scaler=torch.amp.GradScaler(DEVICE,enabled=DEVICE=='cuda')
    tr=np.flatnonzero(g.fold.values!=fold);va=np.flatnonzero(g.fold.values==fold);y=torch.tensor(g.DR_grade.values,device=DEVICE)
    weights=torch.tensor(len(tr)/(5*np.bincount(g.iloc[tr].DR_grade,minlength=5)),dtype=torch.float32,device=DEVICE)
    micro=micro_override or (4 if size<=384 else 2 if size<=512 else 1);effective=16;accum=effective//micro
    config=dict(task='grading',stage='partial_fine_tuning',architecture=name,fold=fold,seed=s,resolution=size,preprocessing=prep,augmentation=aug,objective=objective,max_epochs=epochs,microbatch=micro,effective_batch=effective,head_lr=.001,backbone_lr=.0001,optimizer='AdamW',weight_decay=.0001,checkpoint='maximum validation macro F1, then QWK, earliest exact tie',early_stopping='none within short prespecified screening budget',normalization='ImageNet mean/std',BN='eval/frozen running statistics',stochastic_depth_dropout='disabled; global eval with trainable gradients',warm_start=warmtag,parameters=sum(p.numel() for p in model.parameters()),trainable_parameters=sum(p.numel() for p in params),approx_reference_224_GFLOPs=model._imagenet_ops,pretraining='torchvision ImageNet-1k V1; recipes differ by architecture')
    dump(CFG/(tag+'.json'),config)
    if DEVICE=='cuda':torch.cuda.reset_peak_memory_stats()
    def predict(indices):
        outputs=[];model.eval()
        with torch.no_grad():
            for i in range(0,len(indices),micro):
                with torch.autocast(DEVICE,enabled=DEVICE=='cuda'):logits=model(batch_tensor(arr,indices[i:i+micro]))
                outputs.append(logits.float().softmax(1).cpu().numpy())
        return np.concatenate(outputs)
    # Include the frozen-head checkpoint in the allowed candidate trajectory.
    warmprob=predict(va);score,_,_=metrics(g.iloc[va].DR_grade.values,warmprob);best=(score['macro_f1'],score['qwk']);bestprob=warmprob;bestepoch=-1
    torch.save(model.state_dict(),checkpoint);history=[];start=time.perf_counter()
    for epoch in range(epochs):
        model.eval();order=np.random.permutation(tr);opt.zero_grad();losses=[];steps=math.ceil(len(order)/micro)
        for step,i in enumerate(range(0,len(order),micro)):
            ix=order[i:i+micro];x=batch_tensor(arr,ix,aug)
            with torch.autocast(DEVICE,enabled=DEVICE=='cuda'):logits=model(x)
            loss=grading_loss(logits,y[ix],objective,weights);scaler.scale(loss/accum).backward();losses.append(loss.item())
            if (step+1)%accum==0 or step+1==steps:
                scaler.unscale_(opt);nn.utils.clip_grad_norm_(params,5);scaler.step(opt);scaler.update();opt.zero_grad()
        prob=predict(va);score,_,_=metrics(g.iloc[va].DR_grade.values,prob);history.append(dict(epoch=epoch,train_loss=float(np.mean(losses)),**score))
        if (score['macro_f1'],score['qwk'])>best:
            best=(score['macro_f1'],score['qwk']);bestprob=prob;bestepoch=epoch;torch.save(model.state_dict(),checkpoint)
        print(f'{tag} epoch {epoch+1}/{epochs} F1={score["macro_f1"]:.3f} QWK={score["qwk"]:.3f}',flush=True)
    sync();duration=time.perf_counter()-start;model.load_state_dict(torch.load(checkpoint,map_location=DEVICE,weights_only=True));trainprob=predict(tr);trainmetrics,_,_=metrics(g.iloc[tr].DR_grade.values,trainprob)
    t=time.perf_counter();prob=predict(va);sync();inference=(time.perf_counter()-t)/len(va);score,cm,classes=metrics(g.iloc[va].DR_grade.values,prob)
    result=dict(tag=tag,**config,training_images=len(tr),validation_images=len(va),best_epoch=bestepoch,epochs_run=len(history),training_seconds=duration,inference_seconds_per_image=inference,peak_allocated_MiB=torch.cuda.max_memory_allocated()/2**20 if DEVICE=='cuda' else None,checkpoint_MiB=checkpoint.stat().st_size/2**20,train_macro_f1=trainmetrics['macro_f1'],overfit_gap=trainmetrics['macro_f1']-score['macro_f1'],confusion_matrix=cm,per_class=classes,**score)
    dump(done,result);save_predictions(folder/'validation_predictions.csv',g,va,prob);pd.DataFrame(history).to_csv(folder/'history.csv',index=False)
    del model,opt;gc.collect();torch.cuda.empty_cache();return result

def frozen_tournament(g):
    results=[]
    for name in MODELS:
        f=feature_matrix(g,name)
        for fold in range(3):
            for s in [17,29]:
                tag=f'frozen_{name}_r224_baseline_f{fold}_s{s}';r=frozen_head(g,f,fold,s,tag);r.update(architecture=name,resolution=224,preprocessing='baseline',augmentation='none',objective='ce');dump(OUT/tag/'result.json',r);results.append(r)
                print(tag,'F1',r['macro_f1'],flush=True)
    return results

def profile():
    rows=[]
    for name in MODELS:
        seed(17);model=make_model(name).to(DEVICE);params=partial(model,name);model.eval();x=torch.randn(16,3,224,224,device=DEVICE)
        if DEVICE=='cuda':torch.cuda.reset_peak_memory_stats()
        for _ in range(3):
            model.zero_grad()
            with torch.autocast(DEVICE,enabled=DEVICE=='cuda'):warm=model(x).float().square().mean()
            warm.backward()
        sync();start=time.perf_counter()
        for _ in range(5):
            model.zero_grad()
            with torch.autocast(DEVICE,enabled=DEVICE=='cuda'):loss=model(x).float().square().mean()
            loss.backward()
        sync();rows.append(dict(architecture=name,microbatch=16,resolution=224,seconds_per_forward_backward_batch=(time.perf_counter()-start)/5,parameters=sum(p.numel() for p in model.parameters()),trainable_parameters=sum(p.numel() for p in params),peak_MiB=torch.cuda.max_memory_allocated()/2**20 if DEVICE=='cuda' else None,reference_224_GFLOPs=model._imagenet_ops,estimated_6epoch_fold_seconds=((time.perf_counter()-start)/5)*math.ceil(270/16)*6))
        del model,x;gc.collect();torch.cuda.empty_cache()
    pd.DataFrame(rows).to_csv(OUT/'compute_pilot.csv',index=False);print(pd.DataFrame(rows).to_string(index=False),flush=True)
    return rows
