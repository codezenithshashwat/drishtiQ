"""Staged, resumable development-only study. No test-evaluation entry point exists."""
import argparse,traceback
from common import *
from grading import profile,frozen_tournament,fine

def protected_call(fn,*args,**kwargs):
    try:return fn(*args,**kwargs)
    except Exception as e:
        entry={'operation':fn.__name__,'args':list(args[1:]) if args and isinstance(args[0],pd.DataFrame) else list(args),'kwargs':kwargs,'error':repr(e),'traceback':traceback.format_exc()}
        with (OUT/'failed_runs.jsonl').open('a') as log:log.write(json.dumps(entry,default=str)+'\n')
        gc=None
        if DEVICE=='cuda':torch.cuda.empty_cache()
        print('FAILED',entry['operation'],entry['error'],flush=True);return None

def results():
    rows=[]
    for p in OUT.glob('*/result.json'):
        r=json.loads(p.read_text())
        if r.get('task')=='grading':rows.append({k:v for k,v in r.items() if not isinstance(v,(dict,list))})
    frame=pd.DataFrame(rows)
    if len(frame):frame.to_csv(OUT/'grading_runs.csv',index=False)
    return frame

def choose(frame):
    means=frame.groupby('architecture').agg(macro_f1=('macro_f1','mean'),qwk=('qwk','mean'),parameters=('parameters','first')).sort_values(['macro_f1','qwk'],ascending=False)
    best=means.iloc[0];eligible=means[(means.macro_f1>=best.macro_f1-.02)&(means.qwk>=best.qwk-.02)]
    return eligible.sort_values('parameters').index[0],means

def main():
    import gc
    parser=argparse.ArgumentParser();parser.add_argument('--stage',choices=['pilot','grading','ablations','confirmation','segmentation','ma_specialist','recheck_segmentation','report'],required=True);args=parser.parse_args()
    assert (OUT/'literature_review_completed.json').exists(),'Complete primary-source review before training'
    before=raw_stat();g,seg,annotations,allowed=prepare();guard(allowed);hardware()
    plan={'protocol_version':'IDRID_MODEL_SELECTION_V1','test_access':'No test manifest open, no test-image open, no test inference; audited metadata only','grading_manifest':'data/interim/manifests/idrid_grading_train_clean.csv','n_folds':3,'fold_seed':20261028,'seeds':[17,29],'initial_models':MODELS,'screen_size':224,'fine_tune_epochs':6,'frozen_head_max_epochs':60,'frozen_patience':12,'frozen_optimizer':'AdamW lr=.01 wd=.01','fine_optimizer':'AdamW backbone .0001/head .001 wd=.0001','fine_tuning':'last stage only; BN statistics frozen; no train augmentation in baseline','checkpoint':'macro-F1 then QWK; ties retain earliest checkpoint','finalists':2,'selection_rule':'mean validation macro F1; within .02 F1 and .02 QWK prefer smaller parameter count; no test selection','resolution_ladder':[224,384,512,768],'ablation_scope':'selected baseline, two seeds on fold0, one factor at a time; confirm final recipe on folds1/2','segmentation_candidates':['Unet','UnetPlusPlus','DeepLabV3Plus','Segformer'],'segmentation_holdout':'split within eligible official train images before patches; official test unused','compute_rule':'profile before candidate fitting; AMP and bounded six-epoch screens; OOMs reported, no arbitrary Cartesian grid','inference':'no clinical referral threshold; grade3/4-to0/1 is descriptive error bin only'}
    if not (CFG/'model_selection_preregistered.json').exists():dump(CFG/'model_selection_preregistered.json',plan)
    if args.stage=='pilot':
        profile()
    elif args.stage=='grading':
        frozen_tournament(g)
        for name in MODELS:
            for s in [17,29]:protected_call(fine,g,name,0,s)
        frame=results();screen=frame[(frame.stage=='partial_fine_tuning')&(frame.resolution==224)&(frame.fold==0)]
        ranking=screen.groupby('architecture').agg(macro_f1=('macro_f1','mean'),qwk=('qwk','mean')).sort_values(['macro_f1','qwk'],ascending=False)
        finalists=ranking.head(2).index.tolist();dump(OUT/'grading_finalists.json',{'models':finalists,'basis':'common fold0, two seeds, partial fine-tuning; exploratory screening','ranking':ranking.to_dict('index')})
        for name in finalists:
            for fold in [1,2]:
                for s in [17,29]:protected_call(fine,g,name,fold,s)
        frame=results();complete=frame[(frame.stage=='partial_fine_tuning')&(frame.resolution==224)&frame.architecture.isin(finalists)]
        winner,ranking=choose(complete);dump(OUT/'grading_backbone_selection.json',{'model':winner,'selection_evidence':'two seeds × three folds, initial partial-tuning budget','scope':'development-only provisional baseline, not clinical or external validation','ranking':ranking.to_dict('index')})
    elif args.stage=='ablations':
        selection=json.loads((OUT/'grading_backbone_selection.json').read_text());name=selection['model']
        for size in [384,512,768]:
            for s in [17,29]:protected_call(fine,g,name,0,s,size=size)
        frame=results();base=frame[(frame.architecture==name)&(frame.stage=='partial_fine_tuning')&(frame.fold==0)&(frame.preprocessing=='baseline')&(frame.augmentation=='none')&(frame.objective=='ce')]
        ranking=base.groupby('resolution').macro_f1.mean().sort_values(ascending=False);best=float(ranking.iloc[0]);size=int(min(ranking[ranking>=best-.02].index))
        # One factor at a time: do not combine independently favorable choices without a confirmation run.
        for prep,aug,loss in [('crop','none','ce'),('baseline','minimal','ce'),('baseline','moderate','ce'),('baseline','none','weighted_ce'),('baseline','none','focal'),('baseline','none','ordinal')]:
            for s in [17,29]:protected_call(fine,g,name,0,s,size=size,prep=prep,aug=aug,objective=loss)
        frame=results();ab=frame[(frame.architecture==name)&(frame.stage=='partial_fine_tuning')&(frame.fold==0)&(frame.resolution==size)]
        choices=ab.groupby(['preprocessing','augmentation','objective']).agg(macro_f1=('macro_f1','mean'),qwk=('qwk','mean')).sort_values(['macro_f1','qwk'],ascending=False)
        # Keep a tested single-factor recipe; no unjustified additive stack of operations.
        recipe=choices.index[0];baseline=choices.loc[('baseline','none','ce')]
        if choices.iloc[0].macro_f1<baseline.macro_f1+.02:recipe=('baseline','none','ce')
        for fold in [1,2]:
            for s in [17,29]:protected_call(fine,g,name,fold,s,size=size,prep=recipe[0],aug=recipe[1],objective=recipe[2])
        # Matched baseline on the same folds is required to attribute recipe effects.
        for fold in [1,2]:
            for s in [17,29]:protected_call(fine,g,name,fold,s,size=size,prep='baseline',aug='none',objective='ce')
        dump(OUT/'grading_recipe_selection.json',{'model':name,'resolution':size,'preprocessing':recipe[0],'augmentation':recipe[1],'objective':recipe[2],'scope':'selected single-factor recipe, confirmed on remaining development folds; not test validated','resolution_fold0_ranking':ranking.to_dict(),'ablation_fold0_ranking':{str(k):v for k,v in choices.to_dict('index').items()}});results()
    elif args.stage=='confirmation':
        name=json.loads((OUT/'grading_backbone_selection.json').read_text())['model']
        recipe=json.loads((OUT/'grading_recipe_selection.json').read_text())
        dump(CFG/'adaptive_confirmation_amendment.json',{'timing':'after initial resolution screen; before expanded confirmation scores','reason':'macro-F1 and QWK/MA-detail preservation disagree across resolutions; confirm the selected recipe against matched baseline and 512 CE rather than asserting resolution superiority from one fold','not_original_preregistration':True,'unchanged':'same folds, two seeds, six epochs, checkpoint criterion and test freeze','additional_packages':['chosen-resolution CE baseline on folds1/2','512 CE on folds1/2'],'new_test_access':False})
        for size in sorted({int(recipe['resolution']),512}):
            for fold in [1,2]:
                for s in [17,29]:protected_call(fine,g,name,fold,s,size=size,prep='baseline',aug='none',objective='ce')
        results()
    elif args.stage=='segmentation':
        from segmentation import study
        study(seg,annotations)
    elif args.stage=='ma_specialist':
        from ma_specialist import study
        study(seg,annotations)
    elif args.stage=='recheck_segmentation':
        from recheck_segmentation import recheck
        recheck(seg,annotations)
    elif args.stage=='report':
        from report import generate
        generate(g,seg,annotations)
    after=raw_stat();dump(OUT/f'immutability_{args.stage}.json',{'unchanged':before==after,'raw_files':len(before),'method':'all raw path/size/mtime_ns; raw writes and test/unregistered raw reads prohibited by process audit hook','test_manifest_opened':False,'test_image_inference_count':0})
    assert before==after,'Raw metadata changed during study'

if __name__=='__main__':main()
