from pathlib import Path
import os,sys,json,hashlib,random,time,platform
import numpy as np
import pandas as pd
from PIL import Image,ImageOps,ImageEnhance
import torch
from torch import nn
from torchvision import models
from sklearn.metrics import accuracy_score,balanced_accuracy_score,f1_score,confusion_matrix,cohen_kappa_score,roc_auc_score,log_loss

ROOT=Path(__file__).resolve().parents[2]
os.environ.setdefault('HF_HOME',str(ROOT/'models/pretrained/huggingface'))
OUT=ROOT/'outputs/metrics/model_selection';FIG=ROOT/'outputs/figures/model_selection';CFG=ROOT/'configs/experiments';CKPT=ROOT/'models/checkpoints/model_selection'
CACHE=ROOT/'data/processed/model_selection'
for p in [OUT,FIG,CFG,CKPT,CACHE]:p.mkdir(parents=True,exist_ok=True)
torch.hub.set_dir(str(ROOT/'models/pretrained'))
torch.set_num_threads(4)
DEVICE='cuda' if torch.cuda.is_available() else 'cpu'
MEAN=np.array([.485,.456,.406],dtype=np.float32)[:,None,None];STD=np.array([.229,.224,.225],dtype=np.float32)[:,None,None]
MODELS=['resnet50','efficientnet_b0','convnext_tiny','swin_t']

def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def seed(s):random.seed(s);np.random.seed(s);torch.manual_seed(s);torch.cuda.manual_seed_all(s);torch.backends.cudnn.benchmark=False;torch.backends.cudnn.deterministic=True
def sync():
    if DEVICE=='cuda':torch.cuda.synchronize()
def dump(p,d):Path(p).write_text(json.dumps(d,indent=2,allow_nan=True,default=str),encoding='utf-8')
def raw_stat():return {p.relative_to(ROOT/'data/raw').as_posix():[p.stat().st_size,p.stat().st_mtime_ns] for p in sorted((ROOT/'data/raw').rglob('*')) if p.is_file()}
def guard(allowed):
    raw=(ROOT/'data/raw').resolve();allowed={str((ROOT/p).resolve()).lower() for p in allowed}
    forbidden_manifest=str((ROOT/'data/interim/manifests/idrid_grading_test_clean.csv').resolve()).lower()
    def hook(event,args):
        if event!='open' or not isinstance(args[0],(str,bytes,os.PathLike)):return
        p=Path(os.fsdecode(args[0])).resolve();s=str(p).lower()
        if s==forbidden_manifest:raise PermissionError('Locked clean test manifest may not be opened by selection code')
        if p.is_relative_to(raw):
            mode=args[1] or '';flags=args[2]
            if any(x in mode for x in 'wax+') or flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC):raise PermissionError('Raw data is immutable')
            if s not in allowed:raise PermissionError('Raw read outside registered model-selection development manifest: '+str(p))
    sys.addaudithook(hook)

def prepare():
    from sklearn.model_selection import StratifiedKFold,StratifiedShuffleSplit
    base_inputs=[ROOT/'data/interim/manifests/idrid_grading_train_clean.csv',ROOT/'data/interim/manifests/idrid_grading_excluded.csv',ROOT/'outputs/metrics/idrid_segmentation_annotation_policy.csv',ROOT/'outputs/metrics/idrid_cross_task_mapping_review.csv',ROOT/'outputs/metrics/idrid_integrity_resolution_raw_after.json']
    fingerprints={p.relative_to(ROOT).as_posix():sha(p) for p in base_inputs};lock=OUT/'development_inputs_lock.json'
    if lock.exists():assert json.loads(lock.read_text())==fingerprints,'Development inputs changed: old checkpoints/caches cannot be resumed under new data'
    else:dump(lock,fingerprints)
    trusted=json.loads((ROOT/'outputs/metrics/idrid_integrity_resolution_raw_after.json').read_text())
    current=raw_stat()
    assert {k:v[:2] for k,v in trusted.items()}==current,'Raw path/size/mtime differs from integrity-resolution evidence'
    train_path=ROOT/'data/interim/manifests/idrid_grading_train_clean.csv';g=pd.read_csv(train_path)
    assert len(g)==404 and g.content_hash.nunique()==404 and g.original_split.eq('train').all()
    folds=np.full(len(g),-1);k=StratifiedKFold(n_splits=3,shuffle=True,random_state=20261028)
    for fold,(_,valid) in enumerate(k.split(g,g.DR_grade)):folds[valid]=fold
    g['fold']=folds;g.to_csv(OUT/'grading_folds.csv',index=False)
    a=pd.read_csv(ROOT/'outputs/metrics/idrid_segmentation_annotation_policy.csv');review=pd.read_csv(ROOT/'outputs/metrics/idrid_cross_task_mapping_review.csv');excluded=pd.read_csv(ROOT/'data/interim/manifests/idrid_grading_excluded.csv')
    quarantined=set(excluded.loc[excluded.duplicate_status=='conflicting_labels','content_hash'])
    meta=pd.read_csv(ROOT/'outputs/metrics/idrid_image_metadata.csv');path_hash=dict(zip(meta.path.str.replace('\\','/',regex=False),meta.decoded_sha256))
    seg=a[a.original_split.eq('train')].drop_duplicates('sample_key')[['sample_key','image_id','original_split','image_filepath','image_content_hash']].copy()
    disposition=[]
    for r in seg.itertuples():
        candidate=review[(review.segmentation_split=='train')&(review.segmentation_id==r.image_id)].iloc[0]
        candidate_hash=path_hash.get(str(candidate.grading_path).replace('\\','/'))
        reason='potential_clean_grading_test_correspondence' if candidate.grading_split=='test' else 'potential_quarantined_conflicting_content' if candidate_hash in quarantined or r.image_content_hash in quarantined else ''
        disposition.append(reason)
    seg['selection_exclusion_reason']=disposition
    seg.to_csv(OUT/'segmentation_selection_scope.csv',index=False);seg=seg[seg.selection_exclusion_reason.eq('')].copy().reset_index(drop=True)
    coverage=a[a.annotation_type.eq('SE')].set_index('sample_key').annotation_available
    # Stratify SE availability; all selected images have MA annotations. 80/20 image split, no patch overlap.
    splitter=StratifiedShuffleSplit(n_splits=1,test_size=.2,random_state=20261028)
    tr,va=next(splitter.split(seg,seg.sample_key.map(coverage)));seg['role']='train';seg.loc[va,'role']='validation'
    seg.to_csv(OUT/'segmentation_development_split.csv',index=False)
    allowed=g.filepath.tolist()+seg.image_filepath.tolist()+a[a.sample_key.isin(seg.sample_key)&a.annotation_available].mask_filepath.dropna().tolist()
    scope={'grading_train_manifest_sha256':sha(train_path),'grading_count':len(g),'folds':3,'fold_seed':20261028,'optimization_seeds':[17,29],
           'grading_test_manifest_opened':False,'grading_test_pixels_opened':False,'grading_test_evaluations':0,'official_segmentation_test_opened':False,'segmentation_development_images':len(seg),'segmentation_roles':seg.role.value_counts().to_dict(),
           'cross_task_candidate_test_images_conservatively_excluded':len(disposition)-len(seg),'patient_independence':'UNKNOWN','allowed_raw_paths':sorted(set(str(p).replace('\\','/') for p in allowed))}
    dump(OUT/'selection_scope.json',scope)
    return g,seg,a,allowed

def hardware():
    import torchvision,sklearn,timm,segmentation_models_pytorch as smp,psutil
    d={'python':sys.version,'platform':platform.platform(),'cpu_threads':os.cpu_count(),'RAM_GiB':psutil.virtual_memory().total/2**30,'torch':torch.__version__,'torchvision':torchvision.__version__,'sklearn':sklearn.__version__,'timm':timm.__version__,'smp':smp.__version__,'device':DEVICE}
    if DEVICE=='cuda':d.update(gpu=torch.cuda.get_device_name(0),vram_GiB=torch.cuda.get_device_properties(0).total_memory/2**30,cuda=torch.version.cuda,free_GiB=torch.cuda.mem_get_info()[0]/2**30)
    dump(OUT/'hardware.json',d);return d

def make_model(name,features=False):
    weights={'resnet50':models.ResNet50_Weights.IMAGENET1K_V1,'efficientnet_b0':models.EfficientNet_B0_Weights.IMAGENET1K_V1,'convnext_tiny':models.ConvNeXt_Tiny_Weights.IMAGENET1K_V1,'swin_t':models.Swin_T_Weights.IMAGENET1K_V1}[name]
    model=getattr(models,name)(weights=weights)
    if name=='resnet50':dim=model.fc.in_features;model.fc=nn.Identity() if features else nn.Linear(dim,5)
    elif name=='swin_t':dim=model.head.in_features;model.head=nn.Identity() if features else nn.Linear(dim,5)
    else:dim=model.classifier[-1].in_features;model.classifier[-1]=nn.Identity() if features else nn.Linear(dim,5)
    model._feature_dim=dim;model._imagenet_ops=weights.meta.get('_ops');return model
def partial(model,name):
    for p in model.parameters():p.requires_grad=False
    if name=='resnet50':blocks=[model.layer4,model.fc]
    elif name=='efficientnet_b0':blocks=[model.features[-2:],model.classifier]
    elif name=='convnext_tiny':blocks=[model.features[-2:],model.classifier]
    else:blocks=[model.features[-1],model.norm,model.head]
    for block in blocks:
        for p in block.parameters():p.requires_grad=True
    return [p for p in model.parameters() if p.requires_grad]

def letterbox(im,size,preprocessing='baseline',mask=False):
    if preprocessing=='crop' and not mask:
        small=np.asarray(im.resize((512,340)));ys,xs=np.where(small.max(2)>15)
        if len(xs):im=im.crop((int(xs.min()*im.width/512),int(ys.min()*im.height/340),min(im.width,int((xs.max()+1)*im.width/512)),min(im.height,int((ys.max()+1)*im.height/340))))
    w,h=im.size;scale=size/max(w,h);nw,nh=round(w*scale),round(h*scale)
    im=im.resize((nw,nh),Image.Resampling.NEAREST if mask else Image.Resampling.BILINEAR)
    return ImageOps.expand(im,((size-nw)//2,(size-nh)//2,size-nw-(size-nw)//2,size-nh-(size-nh)//2),fill=0)

def grading_cache(g,size,prep='baseline'):
    fingerprint=hashlib.sha256((''.join(g.file_sha256)+f'{size}:{prep}:letterbox_v1').encode()).hexdigest()[:16]
    p=CACHE/f'grading_{fingerprint}.npy'
    if p.exists():return np.load(p,mmap_mode='r')
    temporary=p.with_suffix('.incomplete.npy')
    data=np.lib.format.open_memmap(temporary,mode='w+',dtype=np.uint8,shape=(len(g),size,size,3))
    for i,r in enumerate(g.itertuples()):
        with Image.open(ROOT/r.filepath) as im:data[i]=np.asarray(letterbox(im.convert('RGB'),size,prep))
        with (OUT/'raw_image_access.jsonl').open('a') as log:log.write(json.dumps({'task':'grading','sample_key':r.sample_key,'filepath':r.filepath})+'\n')
    data.flush();del data;temporary.replace(p);return np.load(p,mmap_mode='r')

def batch_tensor(arr,indices,augment='none'):
    x=torch.from_numpy(np.array(arr[indices],copy=True)).permute(0,3,1,2).float()/255
    if augment!='none':
        for i in range(len(x)):
            if random.random()<.5:x[i]=x[i].flip(-1)
            if augment=='moderate':
                if random.random()<.5:x[i]=x[i].flip(-2)
                # Limited rotations preserve the padded whole-retina view; no random crop.
                angle=random.uniform(-10,10)
                from torchvision.transforms.functional import rotate
                x[i]=rotate(x[i],angle)
                x[i]=(x[i]*random.uniform(.9,1.1)).clamp(0,1)
    return ((x-torch.as_tensor(MEAN))/(torch.as_tensor(STD))).to(DEVICE)

def grading_loss(logits,y,kind,weights=None):
    logits=logits.float();ce=nn.functional.cross_entropy(logits,y,weight=weights if kind=='weighted_ce' else None,reduction='none')
    if kind=='focal':ce=ce*(1-logits.softmax(1).gather(1,y[:,None]).squeeze(1))**2
    if kind=='ordinal':
        target=nn.functional.one_hot(y,5).float().cumsum(1);pred=logits.softmax(1).cumsum(1)
        ce=ce+((pred[:,:4]-target[:,:4])**2).mean(1)
    return ce.mean()

def metrics(y,prob):
    y=np.asarray(y);prob=np.asarray(prob,dtype=np.float64)
    if not np.isfinite(prob).all() or (prob<0).any() or not np.allclose(prob.sum(1),1,atol=1e-5):raise ValueError('Invalid probabilities; cannot score a nonfinite or unnormalized run')
    prob=prob/prob.sum(1,keepdims=True)
    pred=prob.argmax(1);cm=confusion_matrix(y,pred,labels=range(5));tp=np.diag(cm);support=cm.sum(1);fp=cm.sum(0)-tp;fn=support-tp;tn=cm.sum()-tp-fp-fn
    conf=prob.max(1);correct=pred==y;ece=0
    for lo in np.arange(0,1,.1):
        ix=(conf>=lo)&(conf<lo+.1 if lo<.9 else conf<=1)
        if ix.any():ece+=ix.mean()*abs(correct[ix].mean()-conf[ix].mean())
    result={'accuracy':float(accuracy_score(y,pred)),'balanced_accuracy':float(balanced_accuracy_score(y,pred)),'macro_f1':float(f1_score(y,pred,average='macro',labels=range(5),zero_division=0)),'weighted_f1':float(f1_score(y,pred,average='weighted',zero_division=0)),'qwk':float(cohen_kappa_score(y,pred,weights='quadratic',labels=list(range(5)))),'mae_grade':float(np.abs(pred-y).mean()),'distance_ge2_rate':float((np.abs(pred-y)>=2).mean()),'high_grade_to_0_or_1_rate':float(((y>=3)&(pred<=1)).sum()/max(1,(y>=3).sum())),'grade0_to_3_or_4_count':int(((y==0)&(pred>=3)).sum()),'nll':float(-np.log(np.maximum(prob[np.arange(len(y)),y],1e-12)).mean()),'brier':float(((prob-np.eye(5)[y])**2).sum(1).mean()),'ece_10_bins':float(ece),'minority_grade1_recall':float(tp[1]/max(1,support[1]))}
    try:result['roc_auc_ovr_macro']=float(roc_auc_score(y,prob,multi_class='ovr',average='macro',labels=range(5)))
    except ValueError:result['roc_auc_ovr_macro']=None
    perclass=[{'grade':i,'precision':float(tp[i]/max(1,tp[i]+fp[i])),'recall':float(tp[i]/max(1,support[i])),'specificity':float(tn[i]/max(1,tn[i]+fp[i])),'support':int(support[i])} for i in range(5)]
    return result,cm.tolist(),perclass
